from backend.services import dashboard
from backend.services import status


SHIFT_DATE = "2099-12-31"


def test_dashboard_adds_active_local_work_without_jira_fields(
    noc_root,
    monkeypatch,
):
    ticket_dir = noc_root / "tickets" / "open"
    ticket_dir.mkdir(parents=True)
    (ticket_dir / "NOC-123.json").write_text(
        """{
  "id": "NOC-123",
  "jira": {"summary": "Jira-only detail"},
  "noc": {"next_action": "Collect logs", "notes": "Local note"},
  "tracking": {"jira_key": "NOC-123", "state": "active"}
}""",
        encoding="utf-8",
    )
    monkeypatch.setattr(dashboard, "get_jira_ticket_queue", lambda: {
        "tickets": [],
    })

    result = dashboard.get_dashboard(SHIFT_DATE)

    assert result["localWork"]["items"] == [{
        "jiraKey": "NOC-123",
        "trackingState": "active",
        "nextAction": "Collect logs",
        "nocNotes": "Local note",
    }]
    assert "summary" not in result["localWork"]["items"][0]


def test_dashboard_reports_unavailable_local_tracking_without_jira_fallback(
    noc_root,
    monkeypatch,
):
    ticket_dir = noc_root / "tickets" / "open"
    ticket_dir.mkdir(parents=True)
    (ticket_dir / "bad.json").write_text("{", encoding="utf-8")
    monkeypatch.setattr(dashboard, "get_jira_ticket_queue", lambda: {
        "tickets": [],
    })

    result = dashboard.get_dashboard(SHIFT_DATE)

    assert result["localWork"]["available"] is False
    assert result["localWork"]["items"] == []


def test_dashboard_adds_read_only_jira_cache_health(
    noc_root,
    monkeypatch,
):
    monkeypatch.setattr(dashboard, "get_jira_ticket_queue", lambda: {
        "tickets": [],
    })
    monkeypatch.setattr(dashboard, "get_jira_cache_health", lambda: {
        "available": True,
        "freshness": "stale",
        "refreshedAt": "2026-10-29T00:00:00+00:00",
    })

    result = dashboard.get_dashboard(SHIFT_DATE)

    assert result["jiraCache"]["freshness"] == "stale"


def test_dashboard_and_status_share_operator_lifecycle_projection(
    investigation_factory, monkeypatch
):
    investigation_factory(
        shift_date=SHIFT_DATE,
        name="escalated",
        generation={
            "generationStatus": "completed",
            "validationStatus": "ready_for_review",
        },
        reviewed_context={
            "reviewState": "reviewed",
            "lifecycleStatus": "escalated_to_incident",
            "finding": "Operator-reviewed finding",
            "state": "legacy free-form state",
            "lastLifecycleChangedAt": "2099-12-31T12:00:00+00:00",
            "lastLifecycleChangedShiftDate": SHIFT_DATE,
        },
    )
    monkeypatch.setattr(dashboard, "get_jira_ticket_queue", lambda: {"tickets": []})
    monkeypatch.setattr(status, "get_jira_ticket_queue", lambda: {"tickets": []})
    monkeypatch.setattr(status, "get_jira_cache_health", lambda: {"freshness": "current"})

    dashboard_result = dashboard.get_dashboard(SHIFT_DATE)
    status_result = status.get_status(SHIFT_DATE)

    dashboard_item = dashboard_result["investigationLifecycle"][0]
    status_item = status_result["investigations"]["items"][0]
    assert dashboard_item["lifecycleStatus"] == "escalated_to_incident"
    assert status_item["lifecycleStatus"] == dashboard_item["lifecycleStatus"]
    assert status_item["lifecycleLabel"] == "Escalated to Incident"
    assert status_item["validationStatus"] == "ready_for_review"
