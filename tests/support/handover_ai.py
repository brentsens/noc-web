from __future__ import annotations

from types import SimpleNamespace
from typing import Any


SHIFT_DATE = "2099-12-31"


def shift_notes(*, entries=None, exists=True) -> dict[str, Any]:
    items = entries or [
        {"section": "Operational Events", "time": "14:20", "text": "Checkout latency recovered."},
        {"section": "Operational Events", "time": "15:10", "text": "Bridge backlog reduced."},
    ]
    sections = []
    for item in items:
        section = next((s for s in sections if s["name"] == item["section"]), None)
        if section is None:
            section = {"name": item["section"], "entries": []}
            sections.append(section)
        section["entries"].append({"time": item.get("time"), "text": item["text"]})
    return {
        "shiftDate": SHIFT_DATE,
        "exists": exists,
        "sections": sections,
        "activity": items,
        "localWork": {"available": True, "error": None, "count": 0, "items": []},
        "reviewedFindings": [],
    }


def ticket(
    identifier: str,
    *,
    summary: str = "Investigate elevated errors",
    status: str = "In Progress",
    priority: str = "High",
    next_action: str = "Confirm vendor response.",
    tracked: bool = True,
    tracking_state: str = "active",
    needs_review: bool = False,
) -> dict[str, Any]:
    return {
        "id": identifier,
        "summary": summary,
        "status": status,
        "priority": priority,
        "assignee": "NOC Engineer",
        "environment": "uspri-prod",
        "nextAction": next_action,
        "tracked": tracked,
        "trackingState": tracking_state,
        "needsReview": needs_review,
        "browseUrl": f"https://jira.example/browse/{identifier}",
    }


def investigation(
    name: str,
    *,
    display_title: str | None = None,
    reviewed: bool = True,
    finding: str = "Limiter misconfiguration confirmed.",
    state: str = "Monitoring",
    lifecycle: str = "escalated_to_incident",
) -> dict[str, Any]:
    reviewed_value = (
        {"finding": finding, "state": state}
        if reviewed
        else None
    )
    return {
        "name": name,
        "displayTitle": display_title or name.replace("-", " ").title(),
        "lifecycleStatus": lifecycle,
        "reviewedFinding": reviewed_value,
        "validationStatus": "ready_for_review",
        "evidence": {"availability": "available"},
        "sourceReference": {"creationShiftDate": SHIFT_DATE, "investigationName": name},
    }


def reviewed_finding(
    name: str,
    *,
    finding: str = "Limiter misconfiguration confirmed.",
    state: str = "Monitoring",
    lifecycle: str = "escalated_to_incident",
) -> dict[str, Any]:
    return {
        "investigation": name,
        "finding": finding,
        "state": state,
        "lifecycleStatus": lifecycle,
    }


def snapshot(*, incidents=None, freshness: str = "current") -> dict[str, Any]:
    return {
        "incidents": incidents or [],
        "count": len(incidents or []),
        "freshness": freshness,
        "error": None,
    }


def incident(identifier: str = "aadf7955-1945-4ce6-b6ca-41e7fa734a78") -> dict[str, Any]:
    return {
        "id": identifier,
        "title": "Checkout latency elevated",
        "state": "ACTIVE",
        "severity": "SEV-2",
        "url": f"https://app.datadoghq.com/incidents/{identifier}",
    }


def status_summary() -> dict[str, Any]:
    return {"openTickets": {"count": 2}, "investigations": {"count": 1, "needsReview": 0}}


def dashboard_summary() -> dict[str, Any]:
    return {"counts": {"openTickets": 2}, "investigations": {"count": 1}}


def readiness(*, ready: bool = True, blockers=None, warnings=None) -> dict[str, Any]:
    return {
        "ready": ready,
        "blockers": blockers or [],
        "warnings": warnings or [],
        "generation": {"enabled": ready, "message": "End Shift preflight passed." if ready else "Blocked."},
        "health": {"state": "HEALTHY", "failed": 0, "warnings": 0},
        "tickets": {"open": 2, "needsReview": 0},
        "investigations": {"count": 1, "needsReview": 0},
    }


def loaders(
    *,
    notes=None,
    local_tickets=None,
    local_summary=None,
    remote_queue=None,
    remote_health=None,
    investigations=None,
    reviewed_findings=None,
    datadog_snapshot=None,
    status_value=None,
    dashboard_value=None,
    readiness_value=None,
):
    return {
        "shift_notes_loader": lambda _shift: notes if notes is not None else shift_notes(),
        "local_tickets_loader": lambda: local_tickets if local_tickets is not None else [ticket("NOC-556")],
        "local_summary_loader": lambda: local_summary if local_summary is not None else {
            "available": True,
            "error": None,
            "count": len(local_tickets or [ticket("NOC-556")]),
            "items": [],
        },
        "remote_queue_loader": lambda: remote_queue if remote_queue is not None else {
            "tickets": [ticket("NOC-557", summary="Remote open ticket", tracked=False, tracking_state="jira-only")],
            "cacheAvailable": True,
            "count": 1,
            "refreshedAt": "2099-12-31T15:00:00Z",
        },
        "remote_health_loader": lambda: remote_health if remote_health is not None else {
            "available": True,
            "freshness": "current",
            "refreshedAt": "2099-12-31T15:00:00Z",
        },
        "investigations_loader": lambda _shift: investigations if investigations is not None else [
            investigation("checkout-latency"),
        ],
        "reviewed_findings_loader": lambda _shift: reviewed_findings if reviewed_findings is not None else [
            reviewed_finding("checkout-latency"),
        ],
        "datadog_snapshot_loader": lambda **_kwargs: datadog_snapshot if datadog_snapshot is not None else snapshot(incidents=[incident()]),
        "status_loader": lambda _shift: status_value if status_value is not None else status_summary(),
        "dashboard_loader": lambda _shift: dashboard_value if dashboard_value is not None else dashboard_summary(),
        "readiness_loader": lambda _shift: readiness_value if readiness_value is not None else readiness(),
    }


def valid_advisory(package: dict[str, Any]) -> dict[str, list[str]]:
    allowed = [
        identifier
        for identifier, item in package.get("references", {}).items()
        if isinstance(item, dict)
        and item.get("availability") == "available"
        and item.get("authoritative") is True
    ]
    if not allowed:
        raise ValueError("no allowed evidence ids")
    ticket_id = next((item for item in allowed if item.startswith("ticket:")), allowed[0])
    investigation_id = next((item for item in allowed if item.startswith("investigation:")), allowed[0])
    status_id = next((item for item in allowed if item.startswith("status:")), allowed[0])
    readiness_id = next((item for item in allowed if item.startswith("readiness:")), allowed[0])
    def describe(identifier: str, label: str) -> str:
        reference = package["references"].get(identifier, {})
        freshness = reference.get("freshness")
        if freshness == "stale":
            return f"Stale evidence; {label} [evidence:{identifier}]."
        if freshness == "partial":
            return f"Partial evidence; {label} [evidence:{identifier}]."
        return f"{label} [evidence:{identifier}]."

    return {
        "advisorySummary": [describe(ticket_id, "Open ticket context is available")],
        "operationalRisks": [describe(investigation_id, "Reviewed investigation context remains relevant")],
        "recommendedFocus": [describe(status_id, "Review current shift status")],
        "watchItems": [describe(readiness_id, "Confirm handover readiness")],
    }


def fake_runtime(
    *,
    identifier: str = "deepseek-api",
    model: str = "deepseek-flash",
    readiness_value: str = "ready",
    output: dict[str, Any] | None = None,
    error: BaseException | None = None,
    calls: list[dict[str, Any]] | None = None,
):
    if calls is None:
        calls = []

    def provider(envelope):
        calls.append(envelope)
        if error is not None:
            raise error
        if output is not None:
            return output
        return valid_advisory(envelope.get("evidence", {}))

    return SimpleNamespace(
        identifier=identifier,
        provider=provider,
        readiness={
            "configuredProvider": identifier,
            "readiness": readiness_value,
            "label": "DeepSeek API",
            "model": model,
        },
        calls=calls,
    )


def fake_loader(package: dict[str, Any]):
    def load(_shift_date: str):
        return package
    return load


class Clock:
    def __init__(self, value: float = 1000.0):
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds
