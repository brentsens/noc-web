import subprocess

import pytest

from backend.services import handover
from backend.services import tickets


SHIFT_DATE = "2099-12-31"


def create_handover(
    noc_root,
    content="Original handover\n",
):
    handover_dir = (
        noc_root
        / SHIFT_DATE
        / "handover"
    )

    handover_dir.mkdir(
        parents=True
    )

    handover_file = (
        handover_dir
        / f"handover-{SHIFT_DATE}.md"
    )

    handover_file.write_text(
        content,
        encoding="utf-8",
    )

    return handover_file


def test_missing_handover(
    noc_root,
):
    result = handover.get_handover(
        SHIFT_DATE
    )

    assert result["exists"] is False


def test_generate_refuses_existing(
    noc_root,
):
    create_handover(
        noc_root
    )

    with pytest.raises(
        FileExistsError
    ):
        handover.generate_handover(
            SHIFT_DATE
        )


def test_regeneration_archives_original(
    noc_root,
    monkeypatch,
):
    handover_file = create_handover(
        noc_root,
        "Original handover\n",
    )

    monkeypatch.setattr(
        handover.shutil,
        "which",
        lambda command: "/mock/noc-handover",
    )

    def fake_run(*args, **kwargs):
        handover_file.write_text(
            "Regenerated handover\n",
            encoding="utf-8",
        )

        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="success",
            stderr="",
        )

    monkeypatch.setattr(
        handover.subprocess,
        "run",
        fake_run,
    )

    result = handover.regenerate_handover(
        SHIFT_DATE
    )

    archives = list(
        (
            handover_file.parent
            / "archive"
        ).glob("*.md")
    )

    assert result["regenerated"] is True
    assert len(archives) == 1

    assert archives[0].read_text(
        encoding="utf-8"
    ) == "Original handover\n"

    assert handover_file.read_text(
        encoding="utf-8"
    ) == "Regenerated handover\n"


def test_regeneration_uses_force(
    noc_root,
    monkeypatch,
):
    handover_file = create_handover(
        noc_root
    )

    captured = {}

    monkeypatch.setattr(
        handover.shutil,
        "which",
        lambda command: "/mock/noc-handover",
    )

    def fake_run(args, **kwargs):
        captured["args"] = args

        handover_file.write_text(
            "New handover\n",
            encoding="utf-8",
        )

        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="success",
            stderr="",
        )

    monkeypatch.setattr(
        handover.subprocess,
        "run",
        fake_run,
    )

    handover.regenerate_handover(
        SHIFT_DATE
    )

    assert "--force" in captured["args"]
    assert "--date" in captured["args"]
    assert SHIFT_DATE in captured["args"]


def test_failed_regeneration_restores_original(
    noc_root,
    monkeypatch,
):
    handover_file = create_handover(
        noc_root,
        "Original safe version\n",
    )

    monkeypatch.setattr(
        handover.shutil,
        "which",
        lambda command: "/mock/noc-handover",
    )

    def fake_run(*args, **kwargs):
        handover_file.write_text(
            "Broken replacement\n",
            encoding="utf-8",
        )

        return subprocess.CompletedProcess(
            args=args[0],
            returncode=1,
            stdout="",
            stderr="generation failed",
        )

    monkeypatch.setattr(
        handover.subprocess,
        "run",
        fake_run,
    )

    with pytest.raises(
        RuntimeError
    ):
        handover.regenerate_handover(
            SHIFT_DATE
        )

    assert handover_file.read_text(
        encoding="utf-8"
    ) == "Original safe version\n"


def test_timeout_restores_original(
    noc_root,
    monkeypatch,
):
    handover_file = create_handover(
        noc_root,
        "Original timeout-safe version\n",
    )

    monkeypatch.setattr(
        handover.shutil,
        "which",
        lambda command: "/mock/noc-handover",
    )

    def fake_run(*args, **kwargs):
        handover_file.write_text(
            "Partial output\n",
            encoding="utf-8",
        )

        raise subprocess.TimeoutExpired(
            cmd="noc-handover",
            timeout=300,
        )

    monkeypatch.setattr(
        handover.subprocess,
        "run",
        fake_run,
    )

    with pytest.raises(
        subprocess.TimeoutExpired
    ):
        handover.regenerate_handover(
            SHIFT_DATE
        )

    assert handover_file.read_text(
        encoding="utf-8"
    ) == "Original timeout-safe version\n"


def test_closed_local_tracking_is_excluded_from_open_ticket_consumers(
    noc_root,
):
    ticket_dir = noc_root / "tickets" / "open"
    ticket_dir.mkdir(parents=True)
    (ticket_dir / "NOC-123.json").write_text(
        """{
  "id": "NOC-123",
  "jira": {"summary": "Handover-compatible"},
  "noc": {"next_action": "Continue", "notes": "Retain context"}
}
""",
        encoding="utf-8",
    )

    assert tickets.get_open_tickets()[0]["localTracking"]["nocNotes"] == (
        "Retain context"
    )
    tickets.close_tracking("NOC-123", True)

    assert tickets.get_open_tickets() == []
    closed = tickets.get_ticket("NOC-123")
    assert closed["trackingState"] == "closed"
    assert closed["localTracking"]["nocNotes"] == "Retain context"
