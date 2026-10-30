from backend.services import end_shift
from backend.app import app
from fastapi.testclient import TestClient


SHIFT_DATE = "2099-12-31"


def test_handover_api_requires_explicit_confirmation_before_preflight(noc_root):
    client = TestClient(app)

    response = client.post(f"/api/shifts/{SHIFT_DATE}/handover")

    assert response.status_code == 422


def create_workspace(
    noc_root,
    handover=False,
):
    shift_dir = (
        noc_root / SHIFT_DATE
    )

    shift_dir.mkdir(
        parents=True
    )

    (
        shift_dir / "shift-notes.md"
    ).write_text(
        "# Test shift notes\n",
        encoding="utf-8",
    )

    if handover:
        handover_dir = (
            shift_dir / "handover"
        )

        handover_dir.mkdir()

        (
            handover_dir
            / f"handover-{SHIFT_DATE}.md"
        ).write_text(
            "Existing handover\n",
            encoding="utf-8",
        )


def mock_dependencies(
    monkeypatch,
    *,
    review_count=0,
    health_failed=0,
    health_warnings=0,
    jira_synced=True,
):

    monkeypatch.setattr(
        end_shift,
        "get_status",
        lambda date: {
            "openTickets": {
                "count": 5,
            },
            "needsReview": {
                "count": review_count,
            },
            "investigations": {
                "count": 0,
            },
        },
    )

    monkeypatch.setattr(
        end_shift,
        "get_health",
        lambda date: {
            "result": {
                "health": (
                    "UNHEALTHY"
                    if health_failed
                    else (
                        "HEALTHY WITH WARNINGS"
                        if health_warnings
                        else "HEALTHY"
                    )
                ),
                "passed": 36,
                "warnings": health_warnings,
                "failed": health_failed,
            },
        },
    )

    monkeypatch.setattr(
        end_shift,
        "get_ticket_sync_state",
        lambda: {
            "synced": jira_synced,
            "success": jira_synced,
            "startedAt": (
                "2099-12-31T20:00:00-06:00"
                if jira_synced
                else None
            ),
            "completedAt": (
                "2099-12-31T20:01:00-06:00"
                if jira_synced
                else None
            ),
            "output": "",
        },
    )


def test_ready_shift(
    noc_root,
    monkeypatch,
):
    create_workspace(noc_root)
    mock_dependencies(monkeypatch)

    result = (
        end_shift.get_end_shift_preflight(
            SHIFT_DATE
        )
    )

    assert result["ready"] is True
    assert result["blockers"] == []
    assert result["jiraSync"]["synced"] is True
    assert result["generation"]["enabled"] is True


def test_missing_workspace_blocks(
    noc_root,
    monkeypatch,
):
    mock_dependencies(monkeypatch)

    result = (
        end_shift.get_end_shift_preflight(
            SHIFT_DATE
        )
    )

    assert result["ready"] is False

    assert (
        "Shift workspace is missing."
        in result["blockers"]
    )


def test_missing_notes_blocks(
    noc_root,
    monkeypatch,
):
    shift_dir = (
        noc_root / SHIFT_DATE
    )

    shift_dir.mkdir()

    mock_dependencies(monkeypatch)

    result = (
        end_shift.get_end_shift_preflight(
            SHIFT_DATE
        )
    )

    assert result["ready"] is False

    assert (
        "Shift notes are missing."
        in result["blockers"]
    )


def test_missing_jira_sync_blocks(
    noc_root,
    monkeypatch,
):
    create_workspace(noc_root)

    mock_dependencies(
        monkeypatch,
        jira_synced=False,
    )

    result = (
        end_shift.get_end_shift_preflight(
            SHIFT_DATE
        )
    )

    assert result["ready"] is False
    assert result["jiraSync"]["synced"] is False

    assert (
        "A successful Jira sync is required."
        in result["blockers"]
    )


def test_review_items_block(
    noc_root,
    monkeypatch,
):
    create_workspace(noc_root)

    mock_dependencies(
        monkeypatch,
        review_count=2,
    )

    result = (
        end_shift.get_end_shift_preflight(
            SHIFT_DATE
        )
    )

    assert result["ready"] is False
    assert result["tickets"]["needsReview"] == 2


def test_health_failure_blocks(
    noc_root,
    monkeypatch,
):
    create_workspace(noc_root)

    mock_dependencies(
        monkeypatch,
        health_failed=1,
    )

    result = (
        end_shift.get_end_shift_preflight(
            SHIFT_DATE
        )
    )

    assert result["ready"] is False
    assert result["health"]["failed"] == 1


def test_health_warning_allows_generation(
    noc_root,
    monkeypatch,
):
    create_workspace(noc_root)

    mock_dependencies(
        monkeypatch,
        health_warnings=2,
    )

    result = (
        end_shift.get_end_shift_preflight(
            SHIFT_DATE
        )
    )

    assert result["ready"] is True
    assert result["health"]["warnings"] == 2
    assert result["health"]["failed"] == 0
    assert result["generation"]["enabled"] is True


def test_existing_handover_disables_generation(
    noc_root,
    monkeypatch,
):
    create_workspace(
        noc_root,
        handover=True,
    )

    mock_dependencies(monkeypatch)

    result = (
        end_shift.get_end_shift_preflight(
            SHIFT_DATE
        )
    )

    assert result["ready"] is True
    assert result["handover"]["exists"] is True

    assert (
        result["generation"]["enabled"]
        is False
    )

    assert (
        result["generation"]["message"]
        == "Handover already exists."
    )


def test_end_shift_adds_active_local_work_without_changing_preflight(
    noc_root,
    monkeypatch,
):
    create_workspace(noc_root)
    mock_dependencies(monkeypatch)
    ticket_dir = noc_root / "tickets" / "open"
    ticket_dir.mkdir(parents=True)
    (ticket_dir / "NOC-123.json").write_text(
        """{"id":"NOC-123","noc":{"next_action":"Follow up","notes":"Local"},
        "tracking":{"jira_key":"NOC-123","state":"active"}}""",
        encoding="utf-8",
    )

    result = end_shift.get_end_shift_preflight(SHIFT_DATE)

    assert result["ready"] is True
    assert result["localWork"]["items"] == [{
        "jiraKey": "NOC-123",
        "trackingState": "active",
        "nextAction": "Follow up",
        "nocNotes": "Local",
    }]