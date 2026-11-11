from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable

from backend.services.dashboard import get_dashboard
from backend.services.datadog_incidents import get_incident_snapshot
from backend.services.end_shift import get_end_shift_preflight
from backend.services.investigations import (
    get_investigations,
    get_reviewed_findings,
)
from backend.services.jira_cache import get_jira_cache_health
from backend.services.jira_ticket_queue import get_jira_ticket_queue
from backend.services.shift_notes import get_shift_notes
from backend.services.status import get_status
from backend.services.tickets import (
    get_open_tickets,
    get_operational_work_summary,
)


MAX_PACKAGE_BYTES = 1024 * 1024
MAX_OPEN_TICKETS = 500
MAX_SHIFT_NOTE_ENTRIES = 2000
MAX_INVESTIGATIONS = 200
MAX_DATADOG_INCIDENTS = 100
MAX_TEXT_BYTES = 4096

_SENSITIVE_KEY_PATTERN = re.compile(
    r"^(authorization|api[_-]?key|apikey|access[_-]?token|token|secret|"
    r"password|credential|credentials)$",
    re.IGNORECASE,
)
_SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)(bearer\s+[a-z0-9._~+/=-]{8,}|"
    r"deepseek_api_key|noc_web_deepseek_api_key|"
    r"dd_access_token|noc_web_datadog_access_token|"
    r"authorization\s*:)"
)
_SAFE_TICKET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")


class HandoverEvidenceError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _digest(package: dict[str, Any]) -> str:
    body = {
        key: value
        for key, value in package.items()
        if key not in {"digest", "sizeBytes"}
    }
    return "sha256:" + hashlib.sha256(_canonical_bytes(body)).hexdigest()


def _bounded_text(value: Any, maximum: int = MAX_TEXT_BYTES) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if len(text.encode("utf-8")) > maximum:
        raise HandoverEvidenceError(
            "evidence-too-large",
            "Handover evidence exceeded its text bound.",
        )
    return text


def _source_reference(
    identifier: str,
    *,
    kind: str,
    source: str,
    availability: str = "available",
    authoritative: bool = True,
    freshness: str | None = None,
    source_url: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    reference = {
        "id": identifier,
        "kind": kind,
        "source": source,
        "availability": availability,
        "authoritative": authoritative,
    }
    if freshness is not None:
        reference["freshness"] = freshness
    if source_url is not None:
        reference["sourceUrl"] = source_url
    if error is not None:
        reference["error"] = error
    return reference


def _scan_credentials(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if _SENSITIVE_KEY_PATTERN.fullmatch(str(key)):
                raise HandoverEvidenceError(
                    "evidence-credential-detected",
                    "The handover evidence contained credential-like content.",
                )
            _scan_credentials(item)
        return
    if isinstance(value, list):
        for item in value:
            _scan_credentials(item)
        return
    if isinstance(value, str) and _SENSITIVE_VALUE_PATTERN.search(value):
        raise HandoverEvidenceError(
            "evidence-credential-detected",
            "The handover evidence contained credential-like content.",
        )


def _ticket_record(
    *,
    identifier: str,
    ticket: dict[str, Any],
    source: str,
    freshness: str,
    tracked: bool,
    tracking_state: str,
) -> dict[str, Any]:
    if not _SAFE_TICKET_ID.fullmatch(identifier):
        raise HandoverEvidenceError(
            "evidence-invalid",
            "A ticket identifier was unsafe.",
        )
    return {
        "id": f"ticket:{identifier}",
        "jiraKey": identifier,
        "summary": _bounded_text(ticket.get("summary")),
        "status": _bounded_text(ticket.get("status")),
        "priority": _bounded_text(ticket.get("priority")),
        "assignee": _bounded_text(ticket.get("assignee"), 200),
        "environment": _bounded_text(ticket.get("environment"), 200),
        "nextAction": _bounded_text(ticket.get("nextAction")),
        "tracked": tracked,
        "trackingState": tracking_state,
        "source": source,
        "freshness": freshness,
        "needsReview": bool(ticket.get("needsReview", False)),
    }


def _ticket_union(
    *,
    local_tickets: list[dict[str, Any]],
    local_available: bool,
    remote_queue: dict[str, Any],
    remote_health: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    remote_tickets = remote_queue.get("tickets")
    if not isinstance(remote_tickets, list):
        remote_tickets = []
    remote_cache_available = bool(remote_queue.get("cacheAvailable"))
    remote_freshness = remote_health.get("freshness")
    if remote_freshness not in {"current", "stale", "partial", "unavailable"}:
        remote_freshness = "unavailable" if not remote_cache_available else "partial"
    remote_available = remote_cache_available and remote_freshness != "unavailable"
    local_freshness = "current" if local_available else "partial"

    local_by_id: dict[str, dict[str, Any]] = {}
    for ticket in local_tickets:
        if not isinstance(ticket, dict):
            continue
        identifier = ticket.get("id")
        if isinstance(identifier, str) and identifier:
            local_by_id[identifier] = ticket
    remote_by_id: dict[str, dict[str, Any]] = {}
    for ticket in remote_tickets:
        if not isinstance(ticket, dict):
            continue
        identifier = ticket.get("id")
        if isinstance(identifier, str) and identifier:
            remote_by_id[identifier] = ticket

    if not local_available and not remote_available:
        raise HandoverEvidenceError(
            "tickets-unavailable",
            "No validated source can establish the open-ticket set.",
        )

    merged = []
    for identifier in sorted(set(local_by_id) | set(remote_by_id)):
        local = local_by_id.get(identifier)
        remote = remote_by_id.get(identifier)
        source = "merged" if local is not None and remote is not None else (
            "local" if local is not None else "remote"
        )
        base = {**(remote or {}), **(local or {})}
        freshness = (
            local_freshness
            if remote is None
            else remote_freshness
            if local is None
            else (
                "stale"
                if remote_freshness == "stale"
                else "partial"
                if local_freshness != "current" or remote_freshness != "current"
                else "current"
            )
        )
        tracked = bool(base.get("tracked", local is not None))
        tracking_state = base.get("trackingState") or (
            "active" if local is not None else "jira-only"
        )
        merged.append(_ticket_record(
            identifier=identifier,
            ticket=base,
            source=source,
            freshness=freshness,
            tracked=tracked,
            tracking_state=tracking_state,
        ))
    if len(merged) > MAX_OPEN_TICKETS:
        raise HandoverEvidenceError(
            "tickets-over-bound",
            "The open-ticket set exceeds the validated handover bound.",
        )
    completeness = {
        "localOpen": [
            _ticket_record(
                identifier=identifier,
                ticket=ticket,
                source="local",
                freshness=local_freshness,
                tracked=bool(ticket.get("tracked", True)),
                tracking_state=ticket.get("trackingState") or "active",
            )
            for identifier, ticket in sorted(local_by_id.items())
        ],
        "remoteOpen": [
            _ticket_record(
                identifier=identifier,
                ticket=ticket,
                source="remote",
                freshness=remote_freshness,
                tracked=bool(ticket.get("tracked", False)),
                tracking_state=ticket.get("trackingState") or "jira-only",
            )
            for identifier, ticket in sorted(remote_by_id.items())
        ],
        "merged": merged,
        "sourcesAvailable": {
            "local": local_available,
            "remote": remote_available,
        },
        "freshness": {
            "local": local_freshness,
            "remote": remote_freshness,
        },
        "complete": bool(local_available or remote_available),
        "count": len(merged),
    }
    references = {
        ticket["id"]: _source_reference(
            ticket["id"],
            kind="ticket",
            source=ticket["source"],
            freshness=ticket["freshness"],
        )
        for ticket in merged
    }
    return completeness, references


def _shift_note_evidence(
    shift_date: str,
    notes: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    entries = []
    references = {}
    activity = notes.get("activity")
    if not isinstance(activity, list):
        activity = []
    if len(activity) > MAX_SHIFT_NOTE_ENTRIES:
        raise HandoverEvidenceError(
            "evidence-too-large",
            "The handover evidence exceeded the shift-note bound.",
        )
    for entry in activity:
        if not isinstance(entry, dict):
            continue
        section = _bounded_text(entry.get("section"), 200)
        time_value = entry.get("time")
        text = _bounded_text(entry.get("text"))
        if not text:
            continue
        digest_input = f"{shift_date}|{section}|{time_value or ''}|{text}"
        suffix = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()[:12]
        identifier = f"shift-note:{shift_date}:{suffix}"
        item = {
            "id": identifier,
            "section": section,
            "time": time_value if isinstance(time_value, str) else None,
            "text": text,
            "source": "shift-notes",
            "availability": "available" if notes.get("exists") else "unavailable",
        }
        entries.append(item)
        references[identifier] = _source_reference(
            identifier,
            kind="shift-note",
            source="shift-notes",
        )
    return entries, references


def _investigation_evidence(
    shift_date: str,
    investigations: list[dict[str, Any]],
    reviewed_findings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    reviewed_names = {
        finding.get("investigation")
        for finding in reviewed_findings
        if isinstance(finding, dict)
    }
    if len(investigations) > MAX_INVESTIGATIONS:
        raise HandoverEvidenceError(
            "evidence-too-large",
            "The handover evidence exceeded the investigation bound.",
        )
    items = []
    references = {}
    for investigation in investigations:
        if not isinstance(investigation, dict):
            continue
        name = investigation.get("name")
        if not isinstance(name, str) or not name:
            continue
        authoritative = name in reviewed_names
        reviewed = investigation.get("reviewedFinding")
        identifier = f"investigation:{name}"
        item = {
            "id": identifier,
            "name": name,
            "displayTitle": _bounded_text(investigation.get("displayTitle") or name, 200),
            "lifecycleStatus": investigation.get("lifecycleStatus"),
            "reviewState": "reviewed" if authoritative else "unreviewed",
            "authoritative": authoritative,
            "reviewedFinding": reviewed if authoritative and isinstance(reviewed, dict) else None,
            "availability": (
                investigation.get("evidence", {}).get("availability", "available")
                if isinstance(investigation.get("evidence"), dict)
                else "available"
            ),
            "sourceReference": investigation.get("sourceReference") if isinstance(
                investigation.get("sourceReference"), dict
            ) else {},
        }
        items.append(item)
        references[identifier] = _source_reference(
            identifier,
            kind="investigation",
            source="investigations",
            authoritative=authoritative,
        )
    return items, references


def _datadog_evidence(
    snapshot: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], str]:
    incidents = snapshot.get("incidents")
    if not isinstance(incidents, list):
        incidents = []
    freshness = snapshot.get("freshness")
    if freshness not in {"current", "stale", "partial", "unavailable"}:
        freshness = "unavailable"
    if len(incidents) > MAX_DATADOG_INCIDENTS:
        raise HandoverEvidenceError(
            "evidence-too-large",
            "The handover evidence exceeded the Datadog context bound.",
        )
    items = []
    references = {}
    for incident in incidents:
        if not isinstance(incident, dict):
            continue
        identifier_value = incident.get("id")
        if not isinstance(identifier_value, str) or not identifier_value:
            continue
        identifier = f"incident:{identifier_value}"
        item = {
            "id": identifier,
            "title": _bounded_text(incident.get("title"), 200),
            "state": _bounded_text(incident.get("state"), 64),
            "severity": _bounded_text(incident.get("severity"), 64),
            "sourceUrl": incident.get("url") if isinstance(incident.get("url"), str) else None,
            "freshness": freshness,
            "source": "datadog-snapshot",
        }
        items.append(item)
        references[identifier] = _source_reference(
            identifier,
            kind="incident",
            source="datadog-snapshot",
            freshness=freshness,
            source_url=item["sourceUrl"],
        )
    return items, references, freshness


def _summary_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 3:
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value if not isinstance(value, str) or len(value) <= 500 else value[:500]
    if isinstance(value, dict):
        return {
            str(key)[:80]: _summary_value(item, depth=depth + 1)
            for key, item in list(value.items())[:30]
        }
    if isinstance(value, list):
        return [_summary_value(item, depth=depth + 1) for item in value[:30]]
    return None


def _status_summary(kind: str, shift_date: str, value: Any) -> dict[str, Any]:
    identifier = f"{kind}:{shift_date}"
    if not isinstance(value, dict):
        return {
            "id": identifier,
            "available": False,
            "summary": {},
            "freshness": "unavailable",
        }
    summary = {}
    for key in (
        "openTickets",
        "investigations",
        "needsReview",
        "handover",
        "datadog",
    ):
        item = value.get(key)
        if not isinstance(item, dict):
            continue
        safe_item = {}
        for safe_key in (
            "count",
            "needsReview",
            "created",
            "exists",
            "available",
            "state",
            "readiness",
            "status",
        ):
            raw = item.get(safe_key)
            if isinstance(raw, (str, int, float, bool)) or raw is None:
                safe_item[safe_key] = raw
        summary[key] = safe_item
    return {
        "id": identifier,
        "available": True,
        "summary": summary,
        "freshness": "current",
    }


def _readiness_summary(shift_date: str, value: Any) -> dict[str, Any]:
    identifier = f"readiness:{shift_date}"
    if not isinstance(value, dict):
        return {
            "id": identifier,
            "available": False,
            "summary": {},
            "freshness": "unavailable",
            "blockers": [],
            "warnings": [],
        }
    return {
        "id": identifier,
        "available": True,
        "summary": {
            "ready": bool(value.get("ready")),
            "generation": _summary_value(value.get("generation")),
            "health": _summary_value(value.get("health")),
            "tickets": _summary_value(value.get("tickets")),
            "investigations": _summary_value(value.get("investigations")),
        },
        "freshness": "current",
        "blockers": [
            _bounded_text(item, 500)
            for item in value.get("blockers", [])[:20]
            if isinstance(item, str)
        ],
        "warnings": [
            _bounded_text(item, 500)
            for item in value.get("warnings", [])[:20]
            if isinstance(item, str)
        ],
    }


def build_handover_evidence(
    shift_date: str,
    *,
    shift_notes_loader: Callable[[str], dict[str, Any]] = get_shift_notes,
    local_tickets_loader: Callable[[], list[dict[str, Any]]] = get_open_tickets,
    local_summary_loader: Callable[[], dict[str, Any]] = get_operational_work_summary,
    remote_queue_loader: Callable[[], dict[str, Any]] = get_jira_ticket_queue,
    remote_health_loader: Callable[[], dict[str, Any]] = get_jira_cache_health,
    investigations_loader: Callable[[str], list[dict[str, Any]]] = get_investigations,
    reviewed_findings_loader: Callable[[str], list[dict[str, Any]]] = get_reviewed_findings,
    datadog_snapshot_loader: Callable[..., dict[str, Any]] = get_incident_snapshot,
    status_loader: Callable[[str], dict[str, Any]] = get_status,
    dashboard_loader: Callable[[str], dict[str, Any]] = get_dashboard,
    readiness_loader: Callable[[str], dict[str, Any]] = get_end_shift_preflight,
) -> dict[str, Any]:
    try:
        notes = shift_notes_loader(shift_date)
    except Exception:
        notes = {"exists": False, "activity": []}
    try:
        local_summary = local_summary_loader()
        local_available = bool(local_summary.get("available"))
    except Exception:
        local_summary = {"available": False}
        local_available = False
    try:
        local_tickets = local_tickets_loader()
    except Exception:
        local_tickets = []
    try:
        remote_queue = remote_queue_loader()
    except Exception:
        remote_queue = {"cacheAvailable": False, "tickets": []}
    try:
        remote_health = remote_health_loader()
    except Exception:
        remote_health = {"freshness": "unavailable"}

    tickets, ticket_references = _ticket_union(
        local_tickets=local_tickets if isinstance(local_tickets, list) else [],
        local_available=local_available,
        remote_queue=remote_queue if isinstance(remote_queue, dict) else {},
        remote_health=remote_health if isinstance(remote_health, dict) else {},
    )

    try:
        investigations = investigations_loader(shift_date)
    except Exception:
        investigations = []
    try:
        reviewed_findings = reviewed_findings_loader(shift_date)
    except Exception:
        reviewed_findings = []
    investigation_items, investigation_references = _investigation_evidence(
        shift_date,
        investigations if isinstance(investigations, list) else [],
        reviewed_findings if isinstance(reviewed_findings, list) else [],
    )

    try:
        snapshot = datadog_snapshot_loader(schedule_refresh=False)
    except Exception:
        snapshot = {"incidents": [], "freshness": "unavailable"}
    datadog_items, datadog_references, datadog_freshness = _datadog_evidence(
        snapshot if isinstance(snapshot, dict) else {}
    )

    try:
        status_value = status_loader(shift_date)
    except Exception:
        status_value = None
    try:
        dashboard_value = dashboard_loader(shift_date)
    except Exception:
        dashboard_value = None
    try:
        readiness_value = readiness_loader(shift_date)
    except Exception:
        readiness_value = None
    status_summary = _status_summary("status", shift_date, status_value)
    dashboard_summary = _status_summary("dashboard", shift_date, dashboard_value)
    readiness_summary = _readiness_summary(shift_date, readiness_value)

    shift_notes, shift_note_references = _shift_note_evidence(shift_date, notes if isinstance(notes, dict) else {})
    references: dict[str, dict[str, Any]] = {}
    references.update(shift_note_references)
    references.update(ticket_references)
    references.update(investigation_references)
    references.update(datadog_references)
    for summary in (status_summary, dashboard_summary, readiness_summary):
        identifier = summary["id"]
        references[identifier] = _source_reference(
            identifier,
            kind=identifier.split(":", 1)[0],
            source=identifier.split(":", 1)[0],
            availability="available" if summary["available"] else "unavailable",
            freshness=summary["freshness"],
        )
    if not notes.get("exists"):
        identifier = f"shift-note:{shift_date}:unavailable"
        references[identifier] = _source_reference(
            identifier,
            kind="shift-note",
            source="shift-notes",
            availability="unavailable",
            error="shift-notes-unavailable",
        )
    if datadog_freshness == "unavailable":
        identifier = f"datadog-context:{shift_date}"
        references[identifier] = _source_reference(
            identifier,
            kind="datadog-context",
            source="datadog-snapshot",
            availability="unavailable",
            error="datadog-context-unavailable",
        )

    unavailable = [
        reference
        for reference in references.values()
        if reference["availability"] != "available"
    ]
    source_partial = (
        not notes.get("exists")
        or any(
            value not in (True, "current")
            for value in (
                tickets["sourcesAvailable"]["local"],
                tickets["freshness"]["local"],
                tickets["freshness"]["remote"],
            )
        )
        or tickets["freshness"]["remote"] != "current"
        or datadog_freshness != "current"
        or not status_summary["available"]
        or not dashboard_summary["available"]
        or not readiness_summary["available"]
        or not readiness_summary["summary"].get("ready", False)
        or any(
            investigation.get("availability") != "available"
            for investigation in investigation_items
        )
    )
    package: dict[str, Any] = {
        "shiftDate": shift_date,
        "packageVersion": "1",
        "shiftNotes": shift_notes,
        "tickets": tickets,
        "investigations": investigation_items,
        "datadogIncidents": datadog_items,
        "status": status_summary,
        "dashboard": dashboard_summary,
        "readiness": readiness_summary,
        "references": references,
        "unavailable": unavailable,
        "availability": "partial" if source_partial else "complete",
    }
    _scan_credentials(package)
    size_bytes = len(_canonical_bytes(package))
    if size_bytes > MAX_PACKAGE_BYTES:
        raise HandoverEvidenceError(
            "evidence-too-large",
            "The handover evidence package exceeded its size bound.",
        )
    package["sizeBytes"] = size_bytes
    package["digest"] = _digest(package)
    if len(_canonical_bytes(package)) > MAX_PACKAGE_BYTES:
        raise HandoverEvidenceError(
            "evidence-too-large",
            "The handover evidence package exceeded its size bound.",
        )
    return package


def evidence_summary(package: dict[str, Any]) -> dict[str, Any]:
    tickets = package.get("tickets", {})
    return {
        "availability": package.get("availability"),
        "ticketCount": tickets.get("count", 0),
        "ticketFreshness": tickets.get("freshness", {}),
        "investigationCount": len(package.get("investigations", [])),
        "incidentCount": len(package.get("datadogIncidents", [])),
        "unavailable": [
            {
                "id": item.get("id"),
                "kind": item.get("kind"),
                "error": item.get("error"),
            }
            for item in package.get("unavailable", [])
            if isinstance(item, dict)
        ],
        "digest": package.get("digest"),
    }
