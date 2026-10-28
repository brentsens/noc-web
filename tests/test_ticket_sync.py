import subprocess

import pytest

from backend.services import ticket_sync


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