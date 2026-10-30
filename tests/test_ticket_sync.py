import subprocess

import pytest

from backend.services import ticket_sync
from backend.services import jira_cache, tickets


def test_missing_tix_command(
    noc_root,
    monkeypatch,
):
    monkeypatch.setattr(
        ticket_sync.shutil,
        "which",
        lambda command: None,
    )

    with pytest.raises(
        FileNotFoundError
    ):
        ticket_sync.sync_all_tickets()


def test_sync_runs_tix_sync_all(
    noc_root,
    monkeypatch,
):
    captured = {}

    monkeypatch.setattr(
        ticket_sync.shutil,
        "which",
        lambda command: "/mock/tix",
    )

    def fake_run(args, **kwargs):
        captured["args"] = args

        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="Sync complete",
            stderr="",
        )

    monkeypatch.setattr(
        ticket_sync.subprocess,
        "run",
        fake_run,
    )

    result = ticket_sync.sync_all_tickets()

    assert captured["args"] == [
        "/mock/tix",
        "sync",
        "--all",
    ]

    assert result["success"] is True


def test_successful_sync_persists_state(
    noc_root,
    monkeypatch,
):
    monkeypatch.setattr(
        ticket_sync.shutil,
        "which",
        lambda command: "/mock/tix",
    )

    monkeypatch.setattr(
        ticket_sync.subprocess,
        "run",
        lambda *args, **kwargs:
            subprocess.CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="Checked: 5",
                stderr="",
            ),
    )

    result = ticket_sync.sync_all_tickets()

    state = ticket_sync.get_ticket_sync_state()

    assert result["success"] is True
    assert state["synced"] is True
    assert state["success"] is True
    assert state["completedAt"] is not None
    assert state["output"] == "Checked: 5"


def test_missing_state_returns_unsynced(
    noc_root,
):
    state = ticket_sync.get_ticket_sync_state()

    assert state["synced"] is False
    assert state["success"] is False
    assert state["completedAt"] is None


def test_failed_sync_does_not_write_state(
    noc_root,
    monkeypatch,
):
    monkeypatch.setattr(
        ticket_sync.shutil,
        "which",
        lambda command: "/mock/tix",
    )

    monkeypatch.setattr(
        ticket_sync.subprocess,
        "run",
        lambda *args, **kwargs:
            subprocess.CompletedProcess(
                args=args[0],
                returncode=1,
                stdout="",
                stderr="Jira unavailable",
            ),
    )

    with pytest.raises(
        RuntimeError
    ):
        ticket_sync.sync_all_tickets()

    state = ticket_sync.get_ticket_sync_state()

    assert state["synced"] is False


def test_local_ticket_sync_requires_confirmation_and_no_subprocess(
    noc_root,
    monkeypatch,
):
    jira_cache.write_jira_cache({
        "tickets": [{
            "id": "NOC-123",
            "summary": "Before refresh",
            "status": "Support Team",
        }],
    })
    tickets.create_tracking(
        "NOC-123",
        "Keep this action",
        "Keep these notes",
        True,
    )
    jira_cache.write_jira_cache({
        "tickets": [{
            "id": "NOC-123",
            "summary": "Refreshed Jira summary",
            "status": "Escalated",
        }],
    })
    monkeypatch.setattr(
        ticket_sync.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail(
            "Local sync must not invoke a subprocess."
        ),
    )

    with pytest.raises(ValueError):
        ticket_sync.sync_local_ticket("NOC-123", False)

    refreshed = ticket_sync.sync_local_ticket(
        "NOC-123",
        True,
    )

    assert refreshed["summary"] == "Refreshed Jira summary"
    assert refreshed["localTracking"]["nextAction"] == (
        "Keep this action"
    )
    assert refreshed["localTracking"]["nocNotes"] == (
        "Keep these notes"
    )


def test_local_ticket_sync_failure_preserves_context(
    noc_root,
):
    jira_cache.write_jira_cache({
        "tickets": [{"id": "NOC-123", "summary": "Available"}],
    })
    tickets.create_tracking("NOC-123", "Action", "Notes", True)
    (noc_root / ".jira-open-tickets.json").unlink()

    with pytest.raises(LookupError):
        ticket_sync.sync_local_ticket("NOC-123", True)

    preserved = tickets.get_ticket("NOC-123")
    assert preserved["localTracking"]["nextAction"] == "Action"
    assert preserved["localTracking"]["nocNotes"] == "Notes"