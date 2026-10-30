import json
import re
from datetime import datetime, timezone
from pathlib import Path

from backend.config import NOC_ROOT


TITLE_PATTERN = re.compile(r"^# Investigation:\s*(.+?)\s*$", re.MULTILINE)
METADATA_PATTERN = re.compile(r"^-\s+([^:]+):\s*(.*)$")
URL_PATTERN = re.compile(r"https://[^\s<>\"']+")
MAX_FINDING_LENGTH = 500


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


def _read_reviewed_context(investigation_dir: Path) -> dict | None:
    try:
        context = json.loads(_context_file(investigation_dir).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(context, dict):
        return None
    finding, state = context.get("finding"), context.get("state")
    if not isinstance(finding, str) or not isinstance(state, str):
        return None
    return {
        "finding": finding[:MAX_FINDING_LENGTH],
        "state": state[:MAX_FINDING_LENGTH],
        "reviewedAt": context.get("reviewedAt"),
        "reviewedBy": context.get("reviewedBy"),
    }


def _review_state(investigation_dir: Path, reviewed: dict | None) -> str:
    if reviewed:
        return "reviewed"
    try:
        context = json.loads(_context_file(investigation_dir).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "unreviewed"
    return "rejected" if context.get("reviewState") == "rejected" else "unreviewed"


def _project(investigation_file: Path) -> dict:
    investigation_dir = investigation_file.parent
    title, metadata = _read_metadata(investigation_file)
    provenance = _provenance(investigation_dir, metadata)
    reviewed = _read_reviewed_context(investigation_dir)
    availability = "available" if provenance else "unavailable"
    return {
        "name": investigation_dir.name,
        "title": title,
        "lifecycle": {
            "state": metadata.get("Status", "status not recorded"),
            "reviewState": _review_state(investigation_dir, reviewed),
        },
        "evidence": {
            "provenance": provenance,
            "availability": availability,
            "access": "read-only",
            "reference": _source_reference(investigation_dir, metadata),
        },
        "advisory": {
            "available": provenance is not None and reviewed is None,
            "label": "AI analysis is advisory and is not operational state until reviewed.",
        },
        "reviewedFinding": reviewed,
    }


def get_investigations(shift_date: str) -> list[dict]:
    root = NOC_ROOT / shift_date / "investigations"
    if not root.is_dir():
        return []
    results = []
    for investigation_file in sorted(root.glob("*/investigation.md")):
        try:
            results.append(_project(investigation_file))
        except (OSError, UnicodeError, ValueError):
            continue
    return results


def get_investigation(shift_date: str, investigation_name: str) -> dict | None:
    investigation_file = NOC_ROOT / shift_date / "investigations" / investigation_name / "investigation.md"
    if not investigation_file.is_file() or Path(investigation_name).name != investigation_name:
        return None
    try:
        return _project(investigation_file)
    except (OSError, UnicodeError, ValueError):
        return None


def review_investigation(
    shift_date: str,
    investigation_name: str,
    finding: str,
    state: str,
    reviewed_by: str | None = None,
) -> dict:
    investigation_file = NOC_ROOT / shift_date / "investigations" / investigation_name / "investigation.md"
    if not investigation_file.is_file() or Path(investigation_name).name != investigation_name:
        raise FileNotFoundError("Investigation not found")
    projected = _project(investigation_file)
    if projected["evidence"]["provenance"] not in {"noc-inv", "copilot-mcp"}:
        raise ValueError("Investigations require noc-inv or Copilot MCP provenance.")
    clean_finding, clean_state = " ".join(finding.split()), " ".join(state.split())
    if not clean_finding or not clean_state:
        raise ValueError("A concise reviewed finding and state are required.")
    if len(clean_finding) > MAX_FINDING_LENGTH or len(clean_state) > MAX_FINDING_LENGTH:
        raise ValueError("Reviewed finding and state must be concise.")
    context = {
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
    investigation_file = NOC_ROOT / shift_date / "investigations" / investigation_name / "investigation.md"
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
    ]
