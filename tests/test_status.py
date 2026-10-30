from datetime import datetime, timezone

from backend.services import (
    jira_cache,
    jira_ticket_queue,
    status,
)


SHIFT_DATE = "2099-12-31"


def mock_status_dependencies(
    monkeypatch,
    jira_cache_health,
):
    monkeypatch.setattr(
        status,
        "get_jira_ticket_queue",
        lambda: {
            "tickets": [],
        },
    )
    monkeypatch.setattr(
        status,
        "get_jira_cache_health",
        lambda: jira_cache_health,
    )


def test_status_adds_jira_cache_without_changing_existing_fields(
    noc_root,
    monkeypatch,
):
    jira_cache_health = {
        "available": True,
        "refreshedAt": (
            "2099-12-31T12:00:00+00:00"
        ),
        "freshness": "current",
    }
    mock_status_dependencies(
        monkeypatch,
        jira_cache_health,
    )

    result = status.get_status(SHIFT_DATE)

    assert result["jiraCache"] == jira_cache_health
    assert {
        "shiftDate",
        "shift",
        "openTickets",
        "needsReview",
        "investigations",
        "handover",
        "dependencies",
        "readOnly",
    } <= result.keys()


def test_status_exposes_unavailable_jira_cache(
    noc_root,
    monkeypatch,
):
    jira_cache_health = {
        "available": False,
        "refreshedAt": None,
        "freshness": "unavailable",
    }
    mock_status_dependencies(
        monkeypatch,
        jira_cache_health,
    )

    result = status.get_status(SHIFT_DATE)

    assert result["jiraCache"] == jira_cache_health


def test_status_lists_generated_investigation_awaiting_review(noc_root, monkeypatch):
    mock_status_dependencies(monkeypatch, {
        "available": True,
        "refreshedAt": None,
        "freshness": "current",
    })
    directory = noc_root / SHIFT_DATE / "investigations" / "generated"
    directory.mkdir(parents=True)
    (directory / "investigation.md").write_text(
        "# Investigation: Generated\n"
        "- Investigation Name: generated\n"
        "- Shift Date: 2099-12-31\n"
        "- Evidence Provenance: noc-inv\n"
        "\n## Summary\nAdvisory text.\n",
        encoding="utf-8",
    )
    (directory / "generation-status.json").write_text(
        '{"generationStatus":"completed","validationStatus":"ready_for_review",'
        '"shiftDate":"2099-12-31","name":"generated",'
        '"notebookUrl":"https://app.datadoghq.com/notebook/123/example",'
        '"provenance":"noc-inv"}',
        encoding="utf-8",
    )

    result = status.get_status(SHIFT_DATE)

    assert result["investigations"]["needsReview"] == 1
    assert result["needsReview"]["items"][-1]["id"] == "investigation:generated"
    assert result["reviewedFindings"] == []


def test_status_cache_health_has_no_refresh_or_cache_write(
    noc_root,
    monkeypatch,
):
    cache_file = noc_root / ".jira-open-tickets.json"
    monkeypatch.setattr(
        jira_cache,
        "CACHE_FILE",
        cache_file,
    )
    cache_file.write_text(
        (
            '{"refreshedAt": "'
            f'{datetime.now(timezone.utc).isoformat()}'
            '", "tickets": []}'
        ),
        encoding="utf-8",
    )
    original_contents = cache_file.read_text(
        encoding="utf-8"
    )
    ticket_file = (
        noc_root
        / "tickets"
        / "open"
        / "NOC-100.json"
    )
    ticket_file.parent.mkdir(
        parents=True
    )
    ticket_file.write_text(
        '{"id": "NOC-100", "jira": {}, "noc": {}}',
        encoding="utf-8",
    )
    original_ticket = ticket_file.read_text(
        encoding="utf-8"
    )
    monkeypatch.setattr(
        jira_ticket_queue,
        "get_open_jira_tickets",
        lambda: (_ for _ in ()).throw(
            AssertionError("Jira refresh called")
        ),
    )
    monkeypatch.setattr(
        status,
        "get_jira_ticket_queue",
        lambda: {"tickets": []},
    )

    result = status.get_status(SHIFT_DATE)

    assert result["jiraCache"]["available"] is True
    assert cache_file.read_text(
        encoding="utf-8"
    ) == original_contents
    assert ticket_file.read_text(
        encoding="utf-8"
    ) == original_ticket


def test_status_adds_active_local_work_and_excludes_closed_records(
    noc_root,
    monkeypatch,
):
    mock_status_dependencies(monkeypatch, {
        "available": True,
        "refreshedAt": None,
        "freshness": "current",
    })
    ticket_dir = noc_root / "tickets" / "open"
    ticket_dir.mkdir(parents=True)
    (ticket_dir / "NOC-100.json").write_text(
        """{"id":"NOC-100","noc":{"next_action":"Check","notes":"Local"},
        "tracking":{"jira_key":"NOC-100","state":"active"}}""",
        encoding="utf-8",
    )
    (ticket_dir / "NOC-101.json").write_text(
        """{"id":"NOC-101","noc":{"next_action":"Closed","notes":"Old"},
        "tracking":{"jira_key":"NOC-101","state":"closed"}}""",
        encoding="utf-8",
    )

    result = status.get_status(SHIFT_DATE)

    assert result["localWork"]["count"] == 1
    assert result["localWork"]["items"][0]["jiraKey"] == "NOC-100"
