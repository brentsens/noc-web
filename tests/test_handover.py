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
            """Regenerated handover

## Active Local NOC Work

- NOC-123
  - Next Action: Duplicate local output
""",
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


def test_generated_handover_uses_local_context_without_standalone_section(
    noc_root,
    monkeypatch,
):
    handover_file = (
        noc_root / SHIFT_DATE / "handover" / f"handover-{SHIFT_DATE}.md"
    )
    ticket_dir = noc_root / "tickets" / "open"
    ticket_dir.mkdir(parents=True)
    (ticket_dir / "NOC-123.json").write_text(
        """{"id":"NOC-556","noc":{"next_action":"","notes":"Awaiting reviewer confirmation"},
        "tracking":{"jira_key":"NOC-556","state":"active"}}""",
        encoding="utf-8",
    )
    monkeypatch.setattr(handover.shutil, "which", lambda command: "/mock/handover")
    monkeypatch.setattr(
        handover,
        "get_reviewed_findings",
        lambda shift_date: [{
            "investigation": "Datadog latency review",
            "finding": "Elevated latency was operator-confirmed.",
            "state": "confirmed",
        }],
    )

    base_handover = """Shift handover

## Summary
NOC-556 remains open. Operator context: Awaiting reviewer confirmation.

## Open Jira Tickets
- NOC-556 — Review required

## Next Shift Actions
- NOC-556: Next Action not recorded; confirm with the operator.

## Salesforce Context
- Salesforce case SF-77 is awaiting an owner.

Regards,
NOC Operator

## Active Local NOC Work
- NOC-556
  - Next Action:
  - NOC Notes: Awaiting reviewer confirmation
"""

    def fake_run(args, **kwargs):
        handover_file.parent.mkdir(parents=True, exist_ok=True)
        handover_file.write_text(base_handover, encoding="utf-8")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        handover.subprocess,
        "run",
        fake_run,
    )

    result = handover.generate_handover(SHIFT_DATE)

    content = handover_file.read_text(encoding="utf-8")
    assert "## Active Local NOC Work" not in content
    assert "NOC Notes:" not in content
    assert "NOC-556" in content
    assert "Next Action not recorded" in content
    assert "Awaiting reviewer confirmation" in content
    assert "## Open Jira Tickets" in content
    assert "## Next Shift Actions" in content
    assert "Salesforce case SF-77 is awaiting an owner." in content
    assert "## Reviewed Investigation Context" in content
    assert "Elevated latency was operator-confirmed." in content
    assert result["localWork"]["items"][0]["jiraKey"] == "NOC-556"


def test_malformed_local_work_does_not_overwrite_handover(noc_root):
    handover_file = create_handover(noc_root, "Existing safe handover\n")
    ticket_dir = noc_root / "tickets" / "open"
    ticket_dir.mkdir(parents=True)
    (ticket_dir / "bad.json").write_text("{", encoding="utf-8")

    with pytest.raises(ValueError, match="Local tracking data is unavailable"):
        handover.regenerate_handover(SHIFT_DATE)

    assert handover_file.read_text(encoding="utf-8") == "Existing safe handover\n"
