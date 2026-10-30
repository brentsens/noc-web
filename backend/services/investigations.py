import json
import re
from datetime import datetime, timezone
from pathlib import Path

from backend.config import NOC_ROOT, resolve_readiness_profile


TITLE_PATTERN = re.compile(r"^# Investigation:\s*(.+?)\s*$", re.MULTILINE)
METADATA_PATTERN = re.compile(r"^-\s+([^:]+):\s*(.*)$")
URL_PATTERN = re.compile(r"https://[^\s<>\"']+")
MAX_FINDING_LENGTH = 500
_DEFAULT_NOC_ROOT = NOC_ROOT


def get_noc_root() -> Path:
    if NOC_ROOT != _DEFAULT_NOC_ROOT:
        return NOC_ROOT
    return resolve_readiness_profile().noc_root


def _read_metadata(investigation_file: Path) -> tuple[str, dict[str, str]]:
    content = investigation_file.read_text(encoding="utf-8")
    title_match = TITLE_PATTERN.search(content)
    if not title_match:
        raise ValueError("Investigation title not found")

    metadata: dict[str, str] = {}
    for line in content[title_match.start():].splitlines():
        match = METADATA_PATTERN.match(line)
        if match:
            metadata[match.group(1).strip()] = match.group(2).strip()
    return title_match.group(1).strip(), metadata


def _provenance(investigation_dir: Path, metadata: dict[str, str]) -> str | None:
    source = " ".join(metadata.values()).casefold()
    if (investigation_dir / "evidence" / "copilot-notebook-summary.md").is_file() or "copilot" in source:
        return "copilot-mcp"
    if (investigation_dir / "noc-inv.log").is_file() or "noc-inv" in source:
        return "noc-inv"
    return None


def _source_reference(investigation_dir: Path, metadata: dict[str, str]) -> str | None:
    reference_file = investigation_dir / "notebook-url.txt"
    candidates = []
    if reference_file.is_file():
        try:
            candidates.append(reference_file.read_text(encoding="utf-8"))
        except OSError:
            pass
    candidates.extend(value for key, value in metadata.items() if "notebook" in key.casefold())
    for candidate in candidates:
        match = URL_PATTERN.search(candidate)
        if match:
            return match.group(0)
    return None


def _context_file(investigation_dir: Path) -> Path:
    return investigation_dir / "reviewed-context.json"


def _read_generation_status(investigation_dir: Path) -> dict | None:
    status_file = investigation_dir / "generation-status.json"
    if not status_file.is_file():
        return None
    try:
        value = json.loads(status_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"generationStatus": "failed", "validationStatus": "needs_review"}
    if not isinstance(value, dict):
        return {"generationStatus": "failed", "validationStatus": "needs_review"}
    if value.get("validationStatus") not in {"ready_for_review", "needs_review"}:
        return {"generationStatus": "failed", "validationStatus": "needs_review"}
    return value


def _validation_issues(generation: dict) -> list[str]:
    issues = generation.get("validationIssues")
    if not isinstance(issues, list):
        return []
    return [issue[:80] for issue in issues if isinstance(issue, str)][:20]


def _read_reviewed_context(investigation_dir: Path) -> tuple[dict | None, str]:
    context_file = _context_file(investigation_dir)
    if not context_file.is_file():
        return None, "unreviewed" if not context_file.exists() else "unavailable"
    try:
        context = json.loads(context_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "unavailable"
    if not isinstance(context, dict):
        return None, "unavailable"
    if context.get("reviewState") == "rejected":
        return None, "rejected"
    if context.get("reviewState") not in {None, "reviewed"}:
        return None, "unreviewed"
    finding, state = context.get("finding"), context.get("state")
    if not isinstance(finding, str) or not isinstance(state, str):
        return None, "unavailable"
    return {
        "finding": finding[:MAX_FINDING_LENGTH],
        "state": state[:MAX_FINDING_LENGTH],
        "reviewedAt": context.get("reviewedAt"),
        "reviewedBy": context.get("reviewedBy"),
    }, "reviewed"


def _unavailable_projection(
    investigation_file: Path,
    *,
    title: str,
    code: str,
    message: str,
) -> dict:
    generation = _read_generation_status(investigation_file.parent)
    display_title = (
        generation.get("displayTitle")
        if generation and isinstance(generation.get("displayTitle"), str)
        else title
    )
    projection = {
        "name": investigation_file.parent.name,
        "title": display_title,
        "displayTitle": display_title,
        "lifecycle": {
            "state": "unavailable",
            "reviewState": "unavailable",
        },
        "evidence": {
            "provenance": None,
            "availability": "unavailable",
            "access": "read-only",
            "reference": None,
        },
        "advisory": {
            "available": False,
            "label": "Investigation data is unavailable and cannot be reviewed.",
        },
        "reviewedFinding": None,
        "error": {"code": code, "message": message},
    }
    if generation:
        try:
            advisory_content = (
                investigation_file.read_text(encoding="utf-8")[:MAX_FINDING_LENGTH * 20]
                if investigation_file.is_file()
                else ""
            )
        except (OSError, UnicodeError):
            advisory_content = ""
        projection.update({
            "generationStatus": generation.get("generationStatus", "failed"),
            "validationStatus": generation.get("validationStatus", "needs_review"),
            "notebookUrl": generation.get("notebookUrl"),
            "validationIssues": _validation_issues(generation),
            "advisory": {
                **projection["advisory"],
                "content": advisory_content,
            },
        })
    return projection


def _project(investigation_file: Path) -> dict:
    investigation_dir = investigation_file.parent
    title, metadata = _read_metadata(investigation_file)
    provenance = _provenance(investigation_dir, metadata)
    generation = _read_generation_status(investigation_dir)
    display_title = (
        generation.get("displayTitle")
        if generation and isinstance(generation.get("displayTitle"), str)
        else title
    )
    reviewed, review_state = _read_reviewed_context(investigation_dir)
    availability = "available" if provenance else "unavailable"
    validation_status = generation.get("validationStatus") if generation else None
    if validation_status == "needs_review":
        reviewed = None
        if review_state == "reviewed":
            review_state = "unreviewed"
    try:
        advisory_content = investigation_file.read_text(encoding="utf-8")[:MAX_FINDING_LENGTH * 20]
    except (OSError, UnicodeError):
        advisory_content = None
    projection = {
        "name": investigation_dir.name,
        "title": display_title,
        "displayTitle": display_title,
        "lifecycle": {
            "state": metadata.get("Status", "status not recorded"),
            "reviewState": review_state,
        },
        "evidence": {
            "provenance": provenance,
            "availability": availability,
            "access": "read-only",
            "reference": _source_reference(investigation_dir, metadata),
        },
        "advisory": {
            "available": provenance is not None and review_state == "unreviewed",
            "label": "AI analysis is advisory and is not operational state until reviewed.",
            **({"content": advisory_content} if generation and advisory_content else {}),
        },
        "reviewedFinding": reviewed,
    }
    if generation:
        projection.update({
            "generationStatus": generation.get("generationStatus", "failed"),
            "validationStatus": validation_status,
            "notebookUrl": generation.get("notebookUrl"),
            "validationIssues": _validation_issues(generation),
        })
    if review_state == "unavailable":
        projection["error"] = {
            "code": "reviewed-context-unavailable",
            "message": "Operator-reviewed context is unavailable.",
        }
    return projection


def get_investigations(shift_date: str) -> list[dict]:
    root = get_noc_root() / shift_date / "investigations"
    if not root.is_dir():
        return []
    results = []
    for investigation_file in sorted(root.glob("*/investigation.md")):
        try:
            results.append(_project(investigation_file))
        except (OSError, UnicodeError, ValueError):
            results.append(_unavailable_projection(
                investigation_file,
                title="Investigation unavailable",
                code="investigation-unavailable",
                message="Investigation metadata is unavailable.",
            ))
    return results


def get_investigation(shift_date: str, investigation_name: str) -> dict | None:
    investigation_file = get_noc_root() / shift_date / "investigations" / investigation_name / "investigation.md"
    if not investigation_file.is_file() or Path(investigation_name).name != investigation_name:
        return None
    try:
        return _project(investigation_file)
    except (OSError, UnicodeError, ValueError):
        return _unavailable_projection(
            investigation_file,
            title="Investigation unavailable",
            code="investigation-unavailable",
            message="Investigation metadata is unavailable.",
        )


def review_investigation(
    shift_date: str,
    investigation_name: str,
    finding: str,
    state: str,
    reviewed_by: str | None = None,
) -> dict:
    investigation_file = get_noc_root() / shift_date / "investigations" / investigation_name / "investigation.md"
    if not investigation_file.is_file() or Path(investigation_name).name != investigation_name:
        raise FileNotFoundError("Investigation not found")
    projected = _project(investigation_file)
    if projected.get("validationStatus") == "needs_review":
        raise ValueError("This generated investigation needs validation and cannot be reviewed.")
    if (
        projected["evidence"]["provenance"] not in {"noc-inv", "copilot-mcp"}
        and projected.get("validationStatus") != "needs_review"
    ):
        raise ValueError("Investigations require noc-inv or Copilot MCP provenance.")
    clean_finding, clean_state = " ".join(finding.split()), " ".join(state.split())
    if not clean_finding or not clean_state:
        raise ValueError("A concise reviewed finding and state are required.")
    if len(clean_finding) > MAX_FINDING_LENGTH or len(clean_state) > MAX_FINDING_LENGTH:
        raise ValueError("Reviewed finding and state must be concise.")
    context = {
        "reviewState": "reviewed",
        "finding": clean_finding,
        "state": clean_state,
        "reviewedAt": datetime.now(timezone.utc).isoformat(),
        "reviewedBy": "operator" if not reviewed_by else " ".join(reviewed_by.split())[:100],
    }
    context_file = _context_file(investigation_file.parent)
    temporary_file = context_file.with_suffix(".json.tmp")
    temporary_file.write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")
    temporary_file.replace(context_file)
    return _project(investigation_file)


def reject_investigation(shift_date: str, investigation_name: str) -> dict:
    investigation_file = get_noc_root() / shift_date / "investigations" / investigation_name / "investigation.md"
    if not investigation_file.is_file() or Path(investigation_name).name != investigation_name:
        raise FileNotFoundError("Investigation not found")
    projected = _project(investigation_file)
    if projected["evidence"]["provenance"] not in {"noc-inv", "copilot-mcp"}:
        raise ValueError("Investigations require noc-inv or Copilot MCP provenance.")
    context = {
        "reviewState": "rejected",
        "reviewedAt": datetime.now(timezone.utc).isoformat(),
    }
    context_file = _context_file(investigation_file.parent)
    temporary_file = context_file.with_suffix(".json.tmp")
    temporary_file.write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")
    temporary_file.replace(context_file)
    return _project(investigation_file)


def get_reviewed_findings(shift_date: str) -> list[dict]:
    return [
        {
            "investigation": investigation["name"],
            **investigation["reviewedFinding"],
        }
        for investigation in get_investigations(shift_date)
        if investigation["reviewedFinding"] is not None
        and investigation.get("validationStatus") != "needs_review"
    ]
