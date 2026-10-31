import json
import re
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from backend.config import NOC_ROOT, resolve_readiness_profile


TITLE_PATTERN = re.compile(r"^# Investigation:\s*(.+?)\s*$", re.MULTILINE)
METADATA_PATTERN = re.compile(r"^-\s+([^:]+):\s*(.*)$")
URL_PATTERN = re.compile(r"https://[^\s<>\"']+")
MAX_FINDING_LENGTH = 500
_DEFAULT_NOC_ROOT = NOC_ROOT
LIFECYCLE_STATUS_LABELS = {
    "ready_for_review": "Ready for Review",
    "escalated_to_incident": "Escalated to Incident",
    "cured": "Cured",
}
RESOLVED_REVIEW_STATES = frozenset({
    "cured",
    "done",
    "resolved",
    "complete",
    "completed",
    "closed",
    "fixed",
    "recovered",
    "cleared",
    "remediated",
    "fully cured",
    "fully resolved",
    "self-recovered",
    "done (cured)",
})
ACTIVE_REVIEW_STATES = frozenset({
    "active",
    "open",
    "ongoing",
    "in progress",
    "investigating",
    "monitoring",
    "escalated",
    "unresolved",
    "follow-up required",
    "follow up required",
})
SAFE_SHIFT_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SAFE_INVESTIGATION_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")


class InvestigationAttachmentError(ValueError):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def get_noc_root() -> Path:
    if NOC_ROOT != _DEFAULT_NOC_ROOT:
        return NOC_ROOT
    return resolve_readiness_profile().noc_root


def _investigation_file(shift_date: str, investigation_name: str) -> Path | None:
    if (
        not isinstance(shift_date, str)
        or not SAFE_SHIFT_DATE_PATTERN.fullmatch(shift_date)
        or not isinstance(investigation_name, str)
        or not SAFE_INVESTIGATION_NAME_PATTERN.fullmatch(investigation_name)
        or ".." in investigation_name
    ):
        return None
    try:
        date.fromisoformat(shift_date)
        root = get_noc_root().resolve()
        shift_directory = root / shift_date
        investigations_directory = shift_directory / "investigations"
        investigation_directory = investigations_directory / investigation_name
        for directory in (
            shift_directory,
            investigations_directory,
            investigation_directory,
        ):
            if directory.is_symlink():
                return None
        investigation_directory.resolve(strict=False).relative_to(root)
    except (OSError, ValueError):
        return None
    return investigation_directory / "investigation.md"


def _is_valid_shift_date(value: object) -> bool:
    if not isinstance(value, str) or not SAFE_SHIFT_DATE_PATTERN.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


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


def _write_reviewed_context(investigation_dir: Path, context: dict) -> None:
    context_file = _context_file(investigation_dir)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=investigation_dir,
            prefix=".reviewed-context.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(json.dumps(context, indent=2) + "\n")
        temporary_path.replace(context_file)
    except OSError:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise


def _classify_legacy_state(value: object) -> str:
    if not isinstance(value, str):
        return "ready_for_review"
    normalized = " ".join(value.casefold().split())
    if normalized in RESOLVED_REVIEW_STATES:
        return "cured"
    if normalized in ACTIVE_REVIEW_STATES:
        return "escalated_to_incident"
    return "ready_for_review"


def _default_reviewed_context() -> dict:
    return {
        "reviewState": "unreviewed",
        "lifecycleStatus": "ready_for_review",
        "finding": "",
        "state": "",
        "lastLifecycleChangedAt": None,
        "lastLifecycleChangedShiftDate": None,
    }


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
        if context_file.exists():
            return None, "unavailable"
        return _default_reviewed_context(), "unreviewed"
    try:
        context = json.loads(context_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "unavailable"
    if not isinstance(context, dict):
        return None, "unavailable"
    migrated = False
    review_state = context.get("reviewState")
    if review_state is None:
        review_state = "unreviewed"
        context["reviewState"] = review_state
        migrated = True
    elif review_state not in {"unreviewed", "reviewed", "rejected"}:
        review_state = "unavailable"

    lifecycle_status = context.get("lifecycleStatus")
    if lifecycle_status not in LIFECYCLE_STATUS_LABELS:
        if lifecycle_status is not None:
            context.setdefault("legacyLifecycleStatus", lifecycle_status)
        if "lifecycleStatus" in context:
            lifecycle_status = "ready_for_review"
        else:
            lifecycle_status = (
                _classify_legacy_state(context.get("state"))
                if review_state == "reviewed"
                and isinstance(context.get("finding"), str)
                and context["finding"].strip()
                else "ready_for_review"
            )
        context["lifecycleStatus"] = lifecycle_status
        migrated = True
    elif lifecycle_status != "ready_for_review":
        finding = context.get("finding")
        if review_state != "reviewed" or not isinstance(finding, str) or not finding.strip():
            context.setdefault("legacyLifecycleStatus", lifecycle_status)
            lifecycle_status = "ready_for_review"
            context["lifecycleStatus"] = lifecycle_status
            migrated = True

    for field in ("lastLifecycleChangedAt", "lastLifecycleChangedShiftDate"):
        if field not in context:
            context[field] = None
            migrated = True

    if migrated:
        _write_reviewed_context(investigation_dir, context)
    return context, review_state


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
        "lifecycleStatus": "ready_for_review",
        "lifecycleLabel": LIFECYCLE_STATUS_LABELS["ready_for_review"],
        "lifecycle": {
            "state": LIFECYCLE_STATUS_LABELS["ready_for_review"],
            "reviewState": "unavailable",
        },
        "lastLifecycleChangedAt": None,
        "lastLifecycleChangedShiftDate": None,
        "datadogIncidentReference": None,
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
    context, review_state = _read_reviewed_context(investigation_dir)
    availability = "available" if provenance else "unavailable"
    validation_status = generation.get("validationStatus") if generation else None
    lifecycle_status = context["lifecycleStatus"] if context else "ready_for_review"
    lifecycle_label = LIFECYCLE_STATUS_LABELS[lifecycle_status]
    reviewed = None
    if context is not None and review_state == "reviewed":
        finding = context.get("finding")
        state = context.get("state")
        if isinstance(finding, str) and isinstance(state, str):
            reviewed = {
                "finding": finding[:MAX_FINDING_LENGTH],
                "state": state[:MAX_FINDING_LENGTH],
                "reviewedAt": context.get("reviewedAt"),
                "reviewedBy": context.get("reviewedBy"),
            }
    try:
        advisory_content = investigation_file.read_text(encoding="utf-8")[:MAX_FINDING_LENGTH * 20]
    except (OSError, UnicodeError):
        advisory_content = None
    projection = {
        "name": investigation_dir.name,
        "title": display_title,
        "displayTitle": display_title,
        "lifecycleStatus": lifecycle_status,
        "lifecycleLabel": lifecycle_label,
        "lifecycle": {
            "state": lifecycle_label,
            "reviewState": review_state,
        },
        "lastLifecycleChangedAt": context.get("lastLifecycleChangedAt") if context else None,
        "lastLifecycleChangedShiftDate": (
            context.get("lastLifecycleChangedShiftDate") if context else None
        ),
        "datadogIncidentReference": (
            context.get("datadogIncidentReference") if context else None
        ),
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


def _cross_shift_projection(
    investigation_file: Path,
    selected_shift_date: str,
    *,
    include_advisory: bool = False,
) -> dict:
    source_shift_date = investigation_file.parents[2].name
    investigation_name = investigation_file.parent.name
    projection = _project(investigation_file)
    lifecycle_status = projection["lifecycleStatus"]
    changed_shift_date = projection["lastLifecycleChangedShiftDate"]
    if lifecycle_status == "cured":
        visibility = (
            "cured_this_shift"
            if changed_shift_date == selected_shift_date
            else "historical"
        )
    elif source_shift_date == selected_shift_date:
        visibility = "created_this_shift"
    else:
        visibility = "carried"
    projection.update({
        "selectedShiftDate": selected_shift_date,
        "creationShiftDate": source_shift_date,
        "sourceReference": {
            "creationShiftDate": source_shift_date,
            "investigationName": investigation_name,
        },
        "visibility": visibility,
    })
    if not include_advisory:
        projection.pop("advisory", None)
    return projection


def get_investigations(
    selected_shift_date: str,
    view: str = "active",
) -> list[dict]:
    if not _is_valid_shift_date(selected_shift_date):
        raise ValueError("Selected Shift must use YYYY-MM-DD format.")
    if view not in {"active", "history"}:
        raise ValueError("Investigation view must be active or history.")
    root = get_noc_root().resolve()
    if not root.is_dir():
        return []
    results = []
    for shift_directory in sorted(root.iterdir()):
        if (
            shift_directory.is_symlink()
            or not _is_valid_shift_date(shift_directory.name)
            or shift_directory.name > selected_shift_date
        ):
            continue
        investigations_directory = shift_directory / "investigations"
        if investigations_directory.is_symlink() or not investigations_directory.is_dir():
            continue
        for investigation_directory in sorted(investigations_directory.iterdir()):
            if (
                investigation_directory.is_symlink()
                or not SAFE_INVESTIGATION_NAME_PATTERN.fullmatch(investigation_directory.name)
                or ".." in investigation_directory.name
            ):
                continue
            investigation_file = investigation_directory / "investigation.md"
            if investigation_file.is_symlink() or not investigation_file.is_file():
                continue
            try:
                investigation_file.resolve(strict=True).relative_to(root)
                projection = _cross_shift_projection(
                    investigation_file,
                    selected_shift_date,
                )
            except (OSError, UnicodeError, ValueError):
                projection = _unavailable_projection(
                    investigation_file,
                    title="Investigation unavailable",
                    code="investigation-unavailable",
                    message="Investigation metadata is unavailable.",
                )
                projection.update({
                    "selectedShiftDate": selected_shift_date,
                    "creationShiftDate": shift_directory.name,
                    "sourceReference": {
                        "creationShiftDate": shift_directory.name,
                        "investigationName": investigation_directory.name,
                    },
                    "visibility": "historical",
                })
            if (
                view == "history"
                or projection["lifecycleStatus"] != "cured"
                or projection["visibility"] == "cured_this_shift"
            ):
                results.append(projection)
    return results


def get_investigation(
    shift_date: str,
    investigation_name: str,
    selected_shift_date: str | None = None,
) -> dict | None:
    investigation_file = _investigation_file(shift_date, investigation_name)
    if investigation_file is None or not investigation_file.is_file():
        return None
    selected = selected_shift_date or shift_date
    if not _is_valid_shift_date(selected) or selected < shift_date:
        return None
    try:
        return _cross_shift_projection(
            investigation_file,
            selected,
            include_advisory=True,
        )
    except (OSError, UnicodeError, ValueError):
        return _unavailable_projection(
            investigation_file,
            title="Investigation unavailable",
            code="investigation-unavailable",
            message="Investigation metadata is unavailable.",
        )


def transition_investigation(
    creation_shift_date: str,
    investigation_name: str,
    selected_shift_date: str,
    lifecycle_status: str,
    finding: str,
    reviewed_by: str | None = None,
) -> dict:
    investigation_file = _investigation_file(creation_shift_date, investigation_name)
    if investigation_file is None or not investigation_file.is_file():
        raise FileNotFoundError("Investigation not found")
    if (
        not isinstance(selected_shift_date, str)
        or not SAFE_SHIFT_DATE_PATTERN.fullmatch(selected_shift_date)
    ):
        raise ValueError("Selected Shift must use YYYY-MM-DD format.")
    try:
        date.fromisoformat(selected_shift_date)
    except ValueError:
        raise ValueError("Selected Shift must use YYYY-MM-DD format.") from None
    if selected_shift_date < creation_shift_date:
        raise ValueError(
            "Selected Shift cannot predate the investigation's creation shift."
        )
    if lifecycle_status not in {"escalated_to_incident", "cured"}:
        raise ValueError("Lifecycle status is invalid.")
    if not isinstance(finding, str) or "\n" in finding or "\r" in finding:
        raise ValueError("A concise, single-line reviewed finding is required.")
    clean_finding = " ".join(finding.split())
    if not clean_finding:
        raise ValueError("A concise, single-line reviewed finding is required.")
    if len(clean_finding) > MAX_FINDING_LENGTH:
        raise ValueError("Reviewed finding must be concise.")

    projected = _project(investigation_file)
    if projected.get("error"):
        raise ValueError("Investigation operator context is unavailable.")
    if projected.get("validationStatus") == "needs_review":
        raise ValueError("This generated investigation needs validation and cannot be reviewed.")
    if projected["evidence"]["provenance"] not in {"noc-inv", "copilot-mcp"}:
        raise ValueError("Investigations require noc-inv or Copilot MCP provenance.")
    current_status = projected["lifecycleStatus"]
    allowed_transitions = {
        "ready_for_review": {"escalated_to_incident", "cured"},
        "escalated_to_incident": {"cured"},
        "cured": set(),
    }
    if lifecycle_status not in allowed_transitions.get(current_status, set()):
        raise ValueError("This lifecycle transition is not allowed.")

    context, review_state = _read_reviewed_context(investigation_file.parent)
    if context is None or review_state == "unavailable":
        raise ValueError("Investigation operator context is unavailable.")
    changed_at = datetime.now(timezone.utc).isoformat()
    context.update({
        "reviewState": "reviewed",
        "lifecycleStatus": lifecycle_status,
        "finding": clean_finding,
        "reviewedAt": changed_at,
        "reviewedBy": "operator" if not reviewed_by else " ".join(reviewed_by.split())[:100],
        "lastLifecycleChangedAt": changed_at,
        "lastLifecycleChangedShiftDate": selected_shift_date,
    })
    _write_reviewed_context(investigation_file.parent, context)
    return _project(investigation_file)


def attach_datadog_incident(
    creation_shift_date: str,
    investigation_name: str,
    selected_shift_date: str,
    incident_id: str,
) -> dict:
    from backend.services import datadog_incidents

    investigation_file = _investigation_file(creation_shift_date, investigation_name)
    if investigation_file is None or not investigation_file.is_file():
        raise FileNotFoundError("Investigation not found")
    if not _is_valid_shift_date(selected_shift_date) or selected_shift_date < creation_shift_date:
        raise ValueError("Selected Shift must use YYYY-MM-DD format.")
    if not isinstance(incident_id, str) or not incident_id.strip():
        raise ValueError("Select a Datadog incident to attach.")

    snapshot = datadog_incidents.get_incident_snapshot(schedule_refresh=False)
    freshness = snapshot.get("freshness") if isinstance(snapshot, dict) else None
    if freshness != "current":
        raise InvestigationAttachmentError(
            f"Datadog incident snapshot is {freshness or 'unavailable'}; refresh it before attaching."
        )
    projected = _project(investigation_file)
    if projected.get("error"):
        raise ValueError("Investigation operator context is unavailable.")
    if projected["lifecycleStatus"] != "escalated_to_incident":
        raise ValueError("Datadog incidents can be attached only to escalated investigations.")

    incidents = snapshot.get("incidents")
    if not isinstance(incidents, list):
        raise InvestigationAttachmentError("Datadog incident snapshot is unavailable.")
    incident = next(
        (
            candidate for candidate in incidents
            if isinstance(candidate, dict) and candidate.get("id") == incident_id
        ),
        None,
    )
    if incident is None:
        raise InvestigationAttachmentError(
            "The selected Datadog incident is not in the current snapshot."
        )
    if incident.get("state") not in {"ACTIVE", "STABLE"}:
        raise InvestigationAttachmentError(
            "Only current ACTIVE or STABLE Datadog incidents can be attached."
        )
    title = incident.get("title")
    url = incident.get("url")
    if (
        not isinstance(title, str)
        or not title.strip()
        or len(title) > 200
        or not isinstance(url, str)
        or not url
        or len(url) > 2048
    ):
        raise InvestigationAttachmentError(
            "The selected Datadog incident does not include a usable title and URL."
        )

    context, review_state = _read_reviewed_context(investigation_file.parent)
    if context is None or review_state != "reviewed":
        raise ValueError("Escalated investigations require an operator-reviewed finding.")
    if context.get("datadogIncidentReference") is not None:
        raise InvestigationAttachmentError(
            "An incident is already attached to this investigation.",
            status_code=409,
        )
    attached_at = datetime.now(timezone.utc).isoformat()
    reference = {
        "incidentId": incident_id,
        "url": url,
        "title": title,
        "lastKnownState": incident["state"],
        "attachedAt": attached_at,
    }
    context["datadogIncidentReference"] = reference
    _write_reviewed_context(investigation_file.parent, context)
    projection = _project(investigation_file)
    projection["selectedShiftDate"] = selected_shift_date
    projection["datadogIncidentCacheFreshness"] = freshness
    return projection


def review_investigation(
    shift_date: str,
    investigation_name: str,
    finding: str,
    state: str,
    reviewed_by: str | None = None,
) -> dict:
    investigation_file = _investigation_file(shift_date, investigation_name)
    if investigation_file is None or not investigation_file.is_file():
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
    investigation_file = _investigation_file(shift_date, investigation_name)
    if investigation_file is None or not investigation_file.is_file():
        raise FileNotFoundError("Investigation not found")
    projected = _project(investigation_file)
    if projected.get("error"):
        raise ValueError("Investigation operator context is unavailable.")
    if projected["evidence"]["provenance"] not in {"noc-inv", "copilot-mcp"}:
        raise ValueError("Investigations require noc-inv or Copilot MCP provenance.")
    if projected["lifecycleStatus"] != "ready_for_review":
        raise ValueError("Only Ready for Review investigations can reject an advisory.")
    context, review_state = _read_reviewed_context(investigation_file.parent)
    if context is None or review_state != "unreviewed":
        raise ValueError("Only unreviewed advisories can be rejected.")
    context.update({
        "reviewState": "rejected",
        "reviewedAt": datetime.now(timezone.utc).isoformat(),
    })
    _write_reviewed_context(investigation_file.parent, context)
    return _project(investigation_file)


def get_reviewed_findings(shift_date: str) -> list[dict]:
    findings = []
    for investigation in get_investigations(shift_date):
        lifecycle_status = investigation.get("lifecycleStatus")
        reviewed = investigation.get("reviewedFinding")
        if (
            reviewed is None
            or lifecycle_status not in {"escalated_to_incident", "cured"}
            or investigation.get("validationStatus") == "needs_review"
        ):
            continue
        findings.append({
            "investigation": investigation["name"],
            **reviewed,
            "state": LIFECYCLE_STATUS_LABELS[lifecycle_status],
            "lifecycleStatus": lifecycle_status,
        })
    return findings
