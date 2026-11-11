from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from backend.services.ai_provider import (
    ProviderInvalid,
    ProviderTimeout,
    ProviderUnavailable,
    resolve_provider_runtime,
)
from backend.services.handover_ai import (
    HANDOVER_SYSTEM_PROMPT,
    HandoverAIError,
    build_handover_envelope,
    extract_citations,
    validate_advisory_output,
)
from backend.services.handover_evidence import (
    HandoverEvidenceError,
    build_handover_evidence,
    evidence_summary,
)
from backend.services.handover_provenance import (
    PROVENANCE_FILENAME,
    build_handover_provenance,
    read_handover_provenance,
)
from backend.services.investigations import get_noc_root, get_reviewed_findings
from backend.services.tickets import get_operational_work_summary


SECTION_PATTERN = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
CLOSING_LINE = "Please tag me if any clarification is needed."
HANDOVER_SIGNATURE = (
    "Regards,\n\n"
    "Brentsen Smith\n"
    "NOC Engineer\n\n"
    "2025 W. Belt Line Rd. #114\n"
    "Carrollton, TX 75006\n\n"
    "[sesami.io](https://www.sesami.io/) | [LinkedIn](https://www.linkedin.com/company/sesami-cash-management-technologies-corporation)"
)


class HandoverGenerationError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _validate_shift_date(shift_date: str) -> str:
    try:
        date.fromisoformat(shift_date)
    except (TypeError, ValueError):
        raise HandoverGenerationError(
            400, "invalid-shift", "shift_date must use YYYY-MM-DD format."
        ) from None
    return shift_date


def _handover_paths(shift_date: str) -> tuple[Path, Path]:
    _validate_shift_date(shift_date)
    root = get_noc_root().resolve()
    shift_dir = root / shift_date
    handover_dir = shift_dir / "handover"
    handover_file = handover_dir / f"handover-{shift_date}.md"
    provenance_file = handover_dir / PROVENANCE_FILENAME
    try:
        shift_dir.resolve(strict=False).relative_to(root)
        handover_dir.resolve(strict=False).relative_to(root)
    except ValueError:
        raise HandoverGenerationError(
            503, "storage-unavailable", "Handover storage is unavailable."
        ) from None
    if shift_dir.is_symlink() or handover_dir.is_symlink():
        raise HandoverGenerationError(
            503, "storage-unavailable", "Handover storage is unavailable."
        )
    return handover_file, provenance_file


def _read_provenance(handover_file: Path) -> dict[str, Any] | None:
    value = read_handover_provenance(handover_file.parent / PROVENANCE_FILENAME)
    if value is None:
        return None
    return {
        "formatVersion": value.get("formatVersion"),
        "evidenceDigest": value.get("evidenceDigest"),
        "availability": value.get("availability"),
        "provider": value.get("provider") if isinstance(value.get("provider"), dict) else {},
        "advisoryStatus": value.get("advisoryStatus"),
        "advisorySection": value.get("advisorySection"),
        "references": value.get("references") if isinstance(value.get("references"), dict) else {},
        "unavailable": value.get("unavailable") if isinstance(value.get("unavailable"), list) else [],
        "generatedAt": value.get("generatedAt"),
    }


def get_handover(shift_date: str) -> dict:
    handover_file, _ = _handover_paths(shift_date)
    if not handover_file.is_file():
        return {
            "shiftDate": shift_date,
            "exists": False,
            "file": None,
            "intro": "",
            "sections": [],
            "closing": "",
            "content": "",
            "localWork": get_operational_work_summary(),
            "reviewedFindings": get_reviewed_findings(shift_date),
            "generationMode": "none",
            "advisoryStatus": None,
            "evidence": None,
        }

    content = handover_file.read_text(encoding="utf-8")
    sections = []
    intro_lines = []
    closing_lines = []
    current_section = None
    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        section_match = SECTION_PATTERN.match(line)
        if section_match:
            current_section = {"name": section_match.group(1).strip(), "content": []}
            sections.append(current_section)
            continue
        if current_section is None:
            if line.strip():
                intro_lines.append(line)
            continue
        current_section["content"].append(line)

    if sections:
        final_lines = sections[-1]["content"]
        closing_start = None
        for index, line in enumerate(final_lines):
            if line.strip().startswith(CLOSING_LINE):
                closing_start = index
                break
        if closing_start is not None:
            closing_lines = final_lines[closing_start:]
            sections[-1]["content"] = final_lines[:closing_start]

    normalized_sections = [
        {"name": section["name"], "content": "\n".join(section["content"]).strip()}
        for section in sections
    ]
    provenance = _read_provenance(handover_file)
    return {
        "shiftDate": shift_date,
        "exists": True,
        "file": handover_file.name,
        "intro": "\n".join(intro_lines).strip(),
        "sections": normalized_sections,
        "closing": "\n".join(closing_lines).strip(),
        "content": content.strip(),
        "localWork": get_operational_work_summary(),
        "reviewedFindings": get_reviewed_findings(shift_date),
        "generationMode": "ai-advisory" if provenance else "legacy",
        "advisoryStatus": provenance.get("advisoryStatus") if provenance else None,
        "evidence": provenance,
    }


def _ticket_line(ticket: dict[str, Any]) -> str:
    status = ticket.get("status") or "State not recorded"
    priority = ticket.get("priority")
    status_text = f"{status}, {priority}" if priority else status
    next_action = ticket.get("nextAction") or "Next action not recorded"
    summary = ticket.get("summary") or "Summary not recorded"
    parts = [f"- {ticket.get('jiraKey')} — {summary} ({status_text})"]
    assignee = ticket.get("assignee")
    if assignee:
        parts.append(f"Assignee: {assignee}")
    environment = ticket.get("environment")
    if environment:
        parts.append(f"Environment: {environment}")
    parts.append(f"Next action: {next_action}")
    return " — ".join(parts)


def _salesforce_content(package: dict[str, Any]) -> str:
    entries = []
    for note in package.get("shiftNotes", []):
        if not isinstance(note, dict):
            continue
        if "salesforce" not in str(note.get("section", "")).casefold():
            continue
        time_value = note.get("time")
        text = note.get("text")
        if isinstance(text, str) and text.strip():
            prefix = f"{time_value} " if isinstance(time_value, str) and time_value else ""
            entries.append(f"- {prefix}{text.strip()}")
    return "\n".join(entries) if entries else "No validated Salesforce ticket source is available."


def _availability_lines(package: dict[str, Any]) -> list[str]:
    availability = str(package.get("availability", "unavailable")).upper()
    lines = [f"- Evidence availability: {availability}."]
    if availability != "COMPLETE":
        lines.append(
            "- Some source data was stale, partial, or unavailable; "
            "all validated open tickets remain included to the best available data."
        )
    return lines


def _shift_time_label(now: datetime | None = None) -> str:
    hour = (now or datetime.now()).hour
    return "day" if 7 <= hour < 19 else "night"


def assemble_handover_content(package: dict[str, Any]) -> tuple[str, list[dict[str, str]], str]:
    tickets = package.get("tickets") if isinstance(package.get("tickets"), dict) else {}
    merged = tickets.get("merged") if isinstance(tickets.get("merged"), list) else []
    investigations = package.get("investigations") if isinstance(package.get("investigations"), list) else []
    reviewed = [
        investigation
        for investigation in investigations
        if isinstance(investigation, dict)
        and investigation.get("authoritative") is True
        and isinstance(investigation.get("reviewedFinding"), dict)
    ]
    incidents = package.get("datadogIncidents") if isinstance(package.get("datadogIncidents"), list) else []
    readiness = package.get("readiness") if isinstance(package.get("readiness"), dict) else {}
    readiness_ready = bool(readiness.get("summary", {}).get("ready"))
    summary_lines = [
        f"- Open tickets: {len(merged)}.",
        f"- Operator-reviewed investigation findings: {len(reviewed)}.",
        f"- Datadog incidents in available context: {len(incidents)}.",
        f"- Handover readiness: {'READY' if readiness_ready else 'BLOCKED'}.",
        *_availability_lines(package),
    ]
    sections = [
        {"name": "Summary", "content": "\n".join(summary_lines)},
        {"name": "Open Salesforce Tickets", "content": _salesforce_content(package)},
        {
            "name": "Open Jira Tickets",
            "content": "\n".join(_ticket_line(ticket) for ticket in merged)
            if merged
            else "No open tickets.",
        },
        {
            "name": "Investigation Updates",
            "content": "\n".join(
                f"- **{investigation.get('displayTitle') or investigation.get('name')}:** "
                f"{investigation['reviewedFinding'].get('finding', '')} "
                f"(State: {investigation['reviewedFinding'].get('state') or investigation.get('lifecycleStatus') or 'Review recorded'})"
                for investigation in reviewed
            )
            if reviewed
            else "No operator-reviewed findings are available for handover.",
        },
        {
            "name": "Next Shift Actions",
            "content": "\n".join(
                f"- {ticket.get('jiraKey')}: {ticket.get('nextAction')}"
                for ticket in merged
                if isinstance(ticket.get("nextAction"), str) and ticket["nextAction"].strip()
            )
            if any(
                isinstance(ticket.get("nextAction"), str) and ticket["nextAction"].strip()
                for ticket in merged
            )
            else "No deterministic next actions were identified from open-ticket next actions.",
        },
    ]
    closing = f"{CLOSING_LINE}\n\n{HANDOVER_SIGNATURE}"
    intro = (
        "Hi Team,\n\n"
        f"Please see the handover for the {_shift_time_label()} shift on "
        f"{package.get('shiftDate')}."
    )
    return intro, sections, closing


def render_handover_markdown(
    intro: str,
    sections: list[dict[str, str]],
    closing: str,
) -> str:
    parts = [intro, ""]
    for section in sections:
        parts.extend([f"## {section['name']}", section["content"], ""])
    parts.extend([closing, ""])
    return "\n".join(parts).rstrip() + "\n"


def _provider_metadata(runtime) -> dict[str, Any]:
    readiness = runtime.readiness if isinstance(runtime.readiness, dict) else {}
    return {
        "configuredProvider": runtime.identifier,
        "model": readiness.get("model"),
        "readiness": readiness.get("readiness"),
    }


def _require_provider(runtime) -> None:
    readiness = runtime.readiness if runtime is not None and isinstance(runtime.readiness, dict) else {}
    if (
        runtime is None
        or runtime.provider is None
        or readiness.get("readiness") == "notConfigured"
    ):
        raise HandoverGenerationError(
            503,
            "provider-not-configured",
            "No AI provider is configured for handover generation.",
        )
    if readiness.get("readiness") != "ready":
        raise HandoverGenerationError(
            503,
            "provider-not-ready",
            "The configured AI provider is not ready.",
        )


def _resolve_provider():
    return resolve_provider_runtime(system_prompt=HANDOVER_SYSTEM_PROMPT)


def _preview_package(
    shift_date: str,
    evidence_loader: Callable[[str], dict[str, Any]] | None,
) -> dict[str, Any]:
    loader = evidence_loader or build_handover_evidence
    try:
        return loader(shift_date)
    except HandoverEvidenceError as error:
        status = 504 if error.code == "evidence-timeout" else 422
        if error.code in {"evidence-unavailable", "tickets-unavailable"}:
            status = 503
        raise HandoverGenerationError(status, error.code, error.message) from None


def preview_handover(
    shift_date: str,
    *,
    evidence_loader: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    _validate_shift_date(shift_date)
    package = _preview_package(shift_date, evidence_loader)
    intro, sections, closing = assemble_handover_content(package)
    readiness = package.get("readiness") if isinstance(package.get("readiness"), dict) else {}
    return {
        "shiftDate": shift_date,
        "preview": True,
        "evidenceDigest": package.get("digest"),
        "intro": intro,
        "sections": sections,
        "closing": closing,
        "evidence": evidence_summary(package),
        "readiness": {
            "enabled": bool(readiness.get("summary", {}).get("ready")),
            "blockers": readiness.get("blockers", []),
            "warnings": readiness.get("warnings", []),
        },
        "generationMode": "deterministic-preview",
        "requiresConfirmation": True,
    }


def _publish_handover(
    shift_date: str,
    markdown: str,
    provenance: dict[str, Any],
    *,
    replace: bool,
) -> None:
    handover_file, provenance_file = _handover_paths(shift_date)
    handover_dir = handover_file.parent
    try:
        handover_dir.mkdir(parents=True, exist_ok=True)
        staging_context = tempfile.TemporaryDirectory(
            prefix=".handover-generation-",
            dir=handover_dir,
        )
    except OSError:
        raise HandoverGenerationError(
            503, "storage-unavailable", "Handover storage is unavailable."
        ) from None
    with staging_context as temporary_directory:
        staging = Path(temporary_directory)
        published = staging / "published"
        published.mkdir(mode=0o700)
        (published / handover_file.name).write_text(markdown, encoding="utf-8")
        provenance_content = json.dumps(provenance, indent=2) + "\n"
        if len(provenance_content.encode("utf-8")) > 1024 * 1024:
            raise HandoverGenerationError(
                422,
                "evidence-too-large",
                "The handover provenance exceeded its size bound.",
            )
        (published / PROVENANCE_FILENAME).write_text(
            provenance_content,
            encoding="utf-8",
        )
        if handover_file.exists() and not replace:
            raise FileExistsError(f"Handover already exists: {handover_file}")
        try:
            os.replace(published / handover_file.name, handover_file)
            os.replace(published / PROVENANCE_FILENAME, provenance_file)
        except OSError:
            raise HandoverGenerationError(
                500, "storage-failed", "The handover could not be stored."
            ) from None


def _generate_handover(
    shift_date: str,
    *,
    preview_digest: str | None,
    evidence_loader: Callable[[str], dict[str, Any]] | None,
    provider_runtime,
    replace: bool,
) -> dict[str, Any]:
    _validate_shift_date(shift_date)
    handover_file, _ = _handover_paths(shift_date)
    if handover_file.exists() and not replace:
        raise FileExistsError(f"Handover already exists: {handover_file}")
    package = _preview_package(shift_date, evidence_loader)
    if preview_digest is not None and preview_digest != package.get("digest"):
        raise HandoverGenerationError(
            409,
            "preview-stale",
            "Handover evidence changed; preview the handover again.",
        )
    readiness = package.get("readiness") if isinstance(package.get("readiness"), dict) else {}
    if not readiness.get("summary", {}).get("ready"):
        blockers = readiness.get("blockers") or []
        message = "Handover readiness is blocked."
        if blockers:
            message = "Handover readiness is blocked: " + "; ".join(str(item) for item in blockers[:5])
        raise HandoverGenerationError(409, "handover-readiness-blocked", message)
    runtime = provider_runtime or _resolve_provider()
    _require_provider(runtime)
    intro, sections, closing = assemble_handover_content(package)
    envelope = build_handover_envelope(package, shift_date=shift_date)
    try:
        raw_output = runtime.provider(envelope)
    except ProviderTimeout:
        raise HandoverGenerationError(504, "provider-timeout", "The AI provider timed out.") from None
    except ProviderInvalid:
        raise HandoverGenerationError(
            502, "provider-invalid-response", "The AI provider returned an invalid response."
        ) from None
    except ProviderUnavailable:
        raise HandoverGenerationError(
            503, "provider-unavailable", "The AI provider is unavailable."
        ) from None
    except (OSError, TimeoutError):
        raise HandoverGenerationError(
            503, "provider-unavailable", "The AI provider is unavailable."
        ) from None
    except Exception:
        raise HandoverGenerationError(
            502, "provider-invalid-response", "The AI provider returned an invalid response."
        ) from None
    try:
        advisory = validate_advisory_output(raw_output, package)
    except HandoverAIError as error:
        raise HandoverGenerationError(422, error.code, error.message) from None
    advisory_citations = sorted({
        citation
        for items in advisory.values()
        for item in items
        for citation in extract_citations(item)
    })
    markdown = render_handover_markdown(intro, sections, closing)
    provider = _provider_metadata(runtime)
    provenance = build_handover_provenance(
        package,
        provider_identifier=provider.get("configuredProvider"),
        model=provider.get("model"),
        advisory_citations=advisory_citations,
    )
    _publish_handover(shift_date, markdown, provenance, replace=replace)
    result = get_handover(shift_date)
    result["generationMode"] = "ai-advisory"
    result["advisoryStatus"] = "completed"
    result["evidenceDigest"] = package.get("digest")
    result["evidence"] = _read_provenance(handover_file)
    return result


def generate_handover(
    shift_date: str,
    *,
    preview_digest: str | None = None,
    evidence_loader: Callable[[str], dict[str, Any]] | None = None,
    provider_runtime=None,
) -> dict:
    return _generate_handover(
        shift_date,
        preview_digest=preview_digest,
        evidence_loader=evidence_loader,
        provider_runtime=provider_runtime,
        replace=False,
    )


def _archive_existing(handover_file: Path, provenance_file: Path) -> tuple[Path, Path | None]:
    archive_dir = handover_file.parent / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    archive_file = archive_dir / f"handover-{handover_file.parent.parent.name}-{timestamp}.md"
    shutil.copy2(handover_file, archive_file)
    if not archive_file.is_file() or archive_file.stat().st_size == 0:
        raise HandoverGenerationError(
            500, "archive-failed", "The previous handover could not be archived."
        )
    archive_provenance = None
    if provenance_file.is_file():
        archive_provenance = archive_dir / f"handover-provenance-{handover_file.parent.parent.name}-{timestamp}.json"
        shutil.copy2(provenance_file, archive_provenance)
        if not archive_provenance.is_file():
            raise HandoverGenerationError(
                500, "archive-failed", "The previous handover provenance could not be archived."
            )
    return archive_file, archive_provenance


def regenerate_handover(
    shift_date: str,
    *,
    preview_digest: str | None = None,
    evidence_loader: Callable[[str], dict[str, Any]] | None = None,
    provider_runtime=None,
) -> dict:
    handover_file, provenance_file = _handover_paths(shift_date)
    if not handover_file.is_file() or handover_file.stat().st_size == 0:
        raise FileNotFoundError(f"Existing handover not found: {handover_file}")
    archive_file, archive_provenance = _archive_existing(handover_file, provenance_file)
    try:
        result = _generate_handover(
            shift_date,
            preview_digest=preview_digest,
            evidence_loader=evidence_loader,
            provider_runtime=provider_runtime,
            replace=True,
        )
    except Exception:
        try:
            shutil.copy2(archive_file, handover_file)
            if archive_provenance is not None:
                shutil.copy2(archive_provenance, provenance_file)
        except OSError:
            raise HandoverGenerationError(
                500, "restore-failed", "The previous handover could not be restored."
            ) from None
        raise
    result["regenerated"] = True
    result["archivedFile"] = str(archive_file)
    return result
