from backend.services import dashboard


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
