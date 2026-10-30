"""Read-only, selected-shift evidence minimization for the assistant."""

from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit

from backend.services import jira_cache
from backend.services.dashboard import get_dashboard
from backend.services.handover import get_handover
from backend.services.investigations import get_investigations
from backend.services.jira_ticket_queue import get_jira_ticket_queue
from backend.services.shift_notes import get_shift_notes
from backend.services.status import get_status
from backend.services.tickets import get_operational_work_summary


VALID_AVAILABILITY = {"available", "unavailable", "stale", "malformed", "conflicting"}
JIRA_FRESHNESS = {"current", "stale", "unavailable", "malformed"}
MAX_CONTEXT_TEXT = 4000


def _availability(value: Any) -> str:
    if value is None:
        return "available"
    return value if value in VALID_AVAILABILITY else "malformed"


def _bounded(value: Any, limit: int = MAX_CONTEXT_TEXT) -> str:
    if not isinstance(value, str):
        return ""
    return value[:limit]


def _safe_reference(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _item(
    identifier: str,
    kind: str,
    provenance: str,
    availability: str,
    reference: str | None = None,
    summary: Any = None,
    *,
    freshness: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": identifier,
        "kind": kind,
        "provenance": provenance,
        "availability": availability,
        "reference": reference,
    }
    if summary is not None:
        result["summary"] = summary
    if freshness is not None:
        result["freshness"] = freshness
    return result


def _source(
    identifier: str,
    kind: str,
    reader: Callable[[], Any],
    projector: Callable[[Any], tuple[str, Any, str | None]],
) -> dict[str, Any]:
    try:
        availability, summary, reference = projector(reader())
        return _item(
            identifier,
            kind,
            "noc-web",
            _availability(availability),
            reference,
            summary,
        )
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        return _item(identifier, kind, "noc-web", "unavailable")


def _jira_cache_source(local_work: dict[str, Any]) -> dict[str, Any]:
    try:
        health = jira_cache.get_jira_cache_health()
        cache = jira_cache.read_jira_cache()
    except (OSError, UnicodeError, ValueError, TypeError):
        return _item(
            "jira-cache",
            "jira-cache",
            "noc-web",
            "unavailable",
            freshness="unavailable",
        )

    freshness = health.get("freshness")
    if cache is None:
        try:
            exists = jira_cache.CACHE_FILE.is_file()
        except OSError:
            exists = False
        freshness = "malformed" if exists else "unavailable"
    elif freshness not in {"current", "stale"}:
        freshness = "malformed"

    if freshness not in JIRA_FRESHNESS:
        freshness = "malformed"
    availability = {
        "current": "available",
        "stale": "stale",
        "unavailable": "unavailable",
        "malformed": "malformed",
    }[freshness]
    if availability not in {"available", "stale"} or cache is None:
        return _item(
            "jira-cache",
            "jira-cache",
            "noc-web",
            availability,
            freshness=freshness,
        )

    try:
        queue = get_jira_ticket_queue()
        local_summary = local_work.get("summary", [])
        local_by_key = {
            entry["jiraKey"]: entry
            for entry in local_summary
            if isinstance(entry, dict) and isinstance(entry.get("jiraKey"), str)
        }
        tickets = []
        for ticket in queue.get("tickets", []):
            if not isinstance(ticket, dict) or not isinstance(ticket.get("id"), str):
                raise ValueError("Malformed cached Jira ticket")
            local = local_by_key.get(ticket["id"])
            tickets.append({
                "jira": {
                    "id": ticket["id"],
                    "summary": _bounded(ticket.get("summary", "")),
                    "status": _bounded(ticket.get("status", "")),
                    "priority": _bounded(ticket.get("priority", "")),
                },
                "localTracking": {
                    "availability": (
                        "available"
                        if local_work.get("availability") == "available"
                        else local_work.get("availability", "unavailable")
                    ),
                    "tracked": local is not None,
                    "trackingState": local.get("trackingState") if local else None,
                    "nextAction": _bounded(local.get("nextAction", "")) if local else "",
                    "nocNotes": _bounded(local.get("nocNotes", "")) if local else "",
                },
            })
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        return _item(
            "jira-cache",
            "jira-cache",
            "noc-web",
            "malformed",
            freshness="malformed",
        )

    return _item(
        "jira-cache",
        "jira-cache",
        "noc-web",
        availability,
        summary={
            "refreshedAt": health.get("refreshedAt"),
            "count": len(tickets),
            "tickets": tickets,
        },
        freshness=freshness,
    )


def _project_investigations(shift_date: str) -> list[dict[str, Any]]:
    try:
        investigations = get_investigations(shift_date)
    except (OSError, UnicodeError, ValueError, TypeError):
        return [_item("investigations", "investigations", "noc-web", "unavailable")]

    active = []
    reviewed_findings = []
    evidence = []
    for investigation in investigations:
        name = investigation.get("name")
        if not isinstance(name, str) or not name:
            evidence.append(_item("investigation:unavailable", "investigation", "noc-inv", "malformed"))
            continue

        lifecycle = investigation.get("lifecycle", {})
        source = investigation.get("evidence", {})
        review_state = lifecycle.get("reviewState", "unreviewed")
        source_availability = _availability(source.get("availability"))
        provenance = source.get("provenance")
        if provenance not in {"noc-inv", "copilot-mcp"}:
            source_availability = "unavailable"
            provenance = "noc-inv"
        if investigation.get("error", {}).get("code") == "reviewed-context-unavailable":
            source_availability = "malformed"
        summary: dict[str, Any] = {
            "name": name,
            "title": _bounded(investigation.get("title", "")),
            "status": _bounded(lifecycle.get("state", "")),
            "reviewState": review_state,
        }
        finding = investigation.get("reviewedFinding")
        if review_state == "reviewed" and isinstance(finding, dict):
            safe_finding = {
                "investigation": name,
                "finding": _bounded(finding.get("finding", "")),
                "state": _bounded(finding.get("state", "")),
                "evidenceId": f"investigation:{name}",
            }
            summary["reviewedFinding"] = safe_finding
            reviewed_findings.append(safe_finding)

        evidence.append(_item(
            f"investigation:{name}",
            "investigation",
            provenance,
            source_availability,
            _safe_reference(source.get("reference")),
            summary,
        ))
        if _bounded(lifecycle.get("state", "")).casefold() not in {
            "closed", "resolved", "complete", "completed",
        }:
            active.append({
                "name": name,
                "title": summary["title"],
                "status": summary["status"],
                "reviewState": review_state,
            })

    evidence.insert(0, _item(
        "investigations",
        "investigations",
        "noc-web",
        "available",
        summary={"count": len(active), "items": active},
    ))
    evidence.append(_item(
        "reviewed-findings",
        "reviewed-findings",
        "noc-web",
        "available",
        summary=reviewed_findings,
    ))
    return evidence


def collect_context(shift_date: str) -> list[dict[str, Any]]:
    """Collect safe summaries for exactly the supplied shift without performing actions."""
    local_work = _source(
        "local-work",
        "local-work",
        get_operational_work_summary,
        lambda value: (
            _availability(value.get("availability"))
            if value.get("available") else "unavailable",
            [
                {
                    "jiraKey": _bounded(item.get("jiraKey", "")),
                    "trackingState": _bounded(item.get("trackingState", "")),
                    "nextAction": _bounded(item.get("nextAction", "")),
                    "nocNotes": _bounded(item.get("nocNotes", "")),
                }
                for item in value.get("items", [])
                if isinstance(item, dict)
            ],
            None,
        ),
    )
    notes = _source(
        "shift-notes",
        "shift-notes",
        lambda: get_shift_notes(shift_date),
        lambda value: (
            _availability(value.get("availability"))
            if value.get("exists") else "unavailable",
            {
                "exists": bool(value.get("exists")),
                "activity": [
                    entry for entry in value.get("activity", [])[-20:]
                    if isinstance(entry, dict)
                ],
            },
            None,
        ),
    )
    handover = _source(
        "handover",
        "handover",
        lambda: get_handover(shift_date),
        lambda value: (
            _availability(value.get("availability")),
            {
                "exists": bool(value.get("exists")),
                "sections": [
                    {
                        "name": _bounded(section.get("name", ""), 200),
                        "content": _bounded(section.get("content", "")),
                    }
                    for section in value.get("sections", [])
                    if isinstance(section, dict)
                ],
            },
            None,
        ),
    )
    dashboard = _source(
        "dashboard",
        "dashboard",
        lambda: get_dashboard(shift_date),
        lambda value: (
            "available",
            {
                "state": _bounded(value.get("status", "")),
                "investigationCount": value.get("investigations", 0),
                "needsReviewCount": value.get("needsReview", 0),
                "handover": _bounded(value.get("handover", "")),
            },
            None,
        ),
    )
    status = _source(
        "status",
        "status",
        lambda: get_status(shift_date),
        lambda value: (
            "available",
            {
                "shift": {
                    "directoryExists": bool(value.get("shift", {}).get("directoryExists")),
                    "notesAvailable": bool(value.get("shift", {}).get("notesAvailable")),
                    "notesLines": value.get("shift", {}).get("notesLines", 0),
                },
                "needsReview": {
                    "count": value.get("needsReview", {}).get("count", 0),
                },
                "investigations": {
                    "count": value.get("investigations", {}).get("count", 0),
                    "items": [
                        {
                            "name": _bounded(item.get("name", ""), 200),
                            "status": _bounded(item.get("status", ""), 200),
                        }
                        for item in value.get("investigations", {}).get("items", [])
                        if isinstance(item, dict)
                    ],
                },
                "handover": {
                    "created": bool(value.get("handover", {}).get("created")),
                },
                "dependencies": [
                    {
                        "name": _bounded(item.get("name", ""), 100),
                        "available": bool(item.get("available")),
                    }
                    for item in value.get("dependencies", [])
                    if isinstance(item, dict)
                ],
            },
            None,
        ),
    )

    status_summary = status.get("summary")
    handover_summary = handover.get("summary")
    readiness = _item(
        "handover-readiness",
        "handover-readiness",
        "noc-web",
        "available" if status["availability"] == "available" else "unavailable",
        summary={
            "shiftNotesAvailable": (
                status_summary.get("shift", {}).get("notesAvailable", False)
                if status_summary else False
            ),
            "unresolvedReviewCount": (
                status_summary.get("needsReview", {}).get("count", 0)
                if status_summary else None
            ),
            "handoverExists": bool(handover_summary and handover_summary.get("exists")),
            "endShiftPreflightExecuted": False,
            "limitation": "Read-only readiness indicators only; the End Shift preflight was not run.",
        },
    )

    return [
        _jira_cache_source(local_work),
        local_work,
        notes,
        handover,
        dashboard,
        status,
        readiness,
        *_project_investigations(shift_date),
    ]
