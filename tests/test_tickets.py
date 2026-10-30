import json

from fastapi.testclient import TestClient

from backend.app import app
from backend.services import jira_cache, tickets


def write_local_ticket(noc_root, filename, ticket):
    ticket_dir = noc_root / "tickets" / "open"
    ticket_dir.mkdir(parents=True, exist_ok=True)
    (ticket_dir / filename).write_text(
        json.dumps(ticket),
        encoding="utf-8",
    )


def test_operational_work_summary_is_active_local_only_and_unique(noc_root):
    write_local_ticket(noc_root, "NOC-123.json", {
        "id": "NOC-123",
        "jira": {
            "summary": "Must not be exposed",
            "priority": "High",
        },
        "noc": {
            "next_action": "Collect logs",
            "notes": "Await maintenance window",
        },
        "tracking": {"jira_key": "NOC-123", "state": "active"},
    })
    write_local_ticket(noc_root, "NOC-999.json", {
        "id": "NOC-999",
        "noc": {"next_action": "Historical", "notes": "Closed"},
        "tracking": {"jira_key": "NOC-999", "state": "closed"},
    })

    summary = tickets.get_operational_work_summary()

    assert summary == {
        "available": True,
        "error": None,
        "count": 1,
        "items": [{
            "jiraKey": "NOC-123",
            "trackingState": "active",
            "nextAction": "Collect logs",
            "nocNotes": "Await maintenance window",
        }],
    }


def test_operational_work_summary_reports_malformed_or_duplicate_local_data(
    noc_root,
):
    write_local_ticket(noc_root, "NOC-123.json", {
        "id": "NOC-123",
        "noc": {"next_action": "", "notes": ""},
        "tracking": {"jira_key": "NOC-123", "state": "active"},
    })
    write_local_ticket(noc_root, "duplicate.json", {
        "id": "NOC-124",
        "noc": {"next_action": "", "notes": ""},
        "tracking": {"jira_key": "NOC-123", "state": "active"},
    })

    summary = tickets.get_operational_work_summary()

    assert summary["available"] is False
    assert summary["items"] == []
    assert "duplicate active jiraKey: NOC-123" in summary["error"]


def write_cache(noc_root, ticket_id="NOC-123"):
    jira_cache.write_jira_cache({
        "tickets": [{
            "id": ticket_id,
            "summary": "Cached Jira summary",
            "description": "Jira description",
            "status": "Support Team",
            "assignee": "Operator",
            "priority": "High",
        }],
    })


def test_legacy_open_ticket_projects_active_tracking(noc_root):
    ticket_dir = noc_root / "tickets" / "open"
    ticket_dir.mkdir(parents=True)
    (ticket_dir / "NOC-123.json").write_text(json.dumps({
        "id": "NOC-123",
        "jira": {"summary": "Legacy ticket"},
        "noc": {
            "environment": "prod",
            "next_action": "Check logs",
            "notes": "Legacy note",
        },
        "metadata": {"source": "legacy"},
    }), encoding="utf-8")

    ticket = tickets.get_open_ticket("NOC-123")

    assert ticket["trackingState"] == "active"
    assert ticket["localTracking"] == {
        "nextAction": "Check logs",
        "nocNotes": "Legacy note",
        "closedAt": None,
    }


def test_create_requires_confirmed_cached_jira_ticket(noc_root):
    write_cache(noc_root)

    with __import__("pytest").raises(ValueError):
        tickets.create_tracking("NOC-123", "Investigate", "Notes", False)

    created = tickets.create_tracking(
        "NOC-123", "Investigate", "Notes", True
    )

    assert created["trackingState"] == "active"
    assert created["localTracking"]["nextAction"] == "Investigate"
    raw = json.loads(
        (noc_root / "tickets" / "open" / "NOC-123.json").read_text(
            encoding="utf-8"
        )
    )
    assert raw["tracking"]["jira_key"] == "NOC-123"
    assert raw["jira"]["summary"] == "Cached Jira summary"


def test_create_rejects_duplicate_and_unknown_jira_ticket(noc_root):
    write_cache(noc_root)
    tickets.create_tracking("NOC-123", "", "", True)

    with __import__("pytest").raises(FileExistsError):
        tickets.create_tracking("NOC-123", "", "", True)
    with __import__("pytest").raises(LookupError):
        tickets.create_tracking("NOC-999", "", "", True)
    with __import__("pytest").raises(ValueError):
        tickets.create_tracking("not-a-key", "", "", True)


def test_update_and_lifecycle_are_local_only(noc_root):
    write_cache(noc_root)
    tickets.create_tracking("NOC-123", "Initial", "Initial notes", True)

    updated = tickets.update_tracking(
        "NOC-123", "New action", "New notes", True
    )
    closed = tickets.close_tracking("NOC-123", True)

    assert updated["localTracking"]["nocNotes"] == "New notes"
    assert closed["trackingState"] == "closed"
    assert closed["localTracking"]["closedAt"]
    assert tickets.get_open_tickets() == []
    assert tickets.get_ticket("NOC-123")["trackingState"] == "closed"

    reopened = tickets.reactivate_tracking("NOC-123", True)

    assert reopened["trackingState"] == "active"
    assert reopened["localTracking"]["closedAt"] is None


def test_tracking_api_requires_confirmed_true_and_preserves_record(noc_root):
    write_cache(noc_root)
    client = TestClient(app)

    missing = client.post("/api/tickets/tracking", json={
        "jiraKey": "NOC-123",
    })
    cancelled = client.post("/api/tickets/tracking", json={
        "jiraKey": "NOC-123",
        "confirmed": False,
    })

    assert missing.status_code == 422
    assert cancelled.status_code == 422
    assert tickets.get_ticket("NOC-123") is None

    created = client.post("/api/tickets/tracking", json={
        "jiraKey": "NOC-123",
        "nextAction": "Check",
        "nocNotes": "Keep local",
        "confirmed": True,
    })
    assert created.status_code == 200
    assert created.json()["trackingState"] == "active"

    rejected = client.patch("/api/tickets/NOC-123/tracking", json={
        "nextAction": "Must not save",
        "nocNotes": "Must not save",
        "confirmed": False,
    })
    assert rejected.status_code == 422
    assert tickets.get_ticket("NOC-123")["nextAction"] == "Check"
