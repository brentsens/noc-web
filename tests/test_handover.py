import json
import subprocess

import pytest

from backend.api import handover as handover_api
from backend.app import app
from backend.services import handover
from backend.services import tickets
from fastapi.testclient import TestClient


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


def create_investigation(
    noc_root,
    name,
    title,
    *,
    review_context=None,
    notebook_url=None,
    generated_next_actions=None,
):
    directory = noc_root / SHIFT_DATE / "investigations" / name
    directory.mkdir(parents=True)
    metadata = f"# Investigation: {title}\n- Status: active\n- Source of truth: noc-inv\n"
    if notebook_url:
        metadata += f"- Datadog Notebook: {notebook_url}\n"
    if generated_next_actions:
        metadata += "\n## Next Actions\n" + generated_next_actions + "\n"
    (directory / "investigation.md").write_text(
        metadata,
        encoding="utf-8",
    )
    (directory / "generation-status.json").write_text(
        json.dumps({
            "generationStatus": "completed",
            "validationStatus": "ready_for_review",
            "displayTitle": title,
        }),
        encoding="utf-8",
    )
    if review_context is not None:
        (directory / "reviewed-context.json").write_text(
            json.dumps(review_context),
            encoding="utf-8",
        )
    return directory


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


def test_unreviewed_investigation_preflight_blocks_generation(monkeypatch):
    generation_called = False

    def fake_generate(shift):
        nonlocal generation_called
        generation_called = True
        return {}

    monkeypatch.setattr(
        handover_api,
        "get_end_shift_preflight",
        lambda shift: {
            "generation": {
                "enabled": False,
                "message": "Handover generation is blocked until review items are resolved.",
            },
        },
    )
    monkeypatch.setattr(handover_api, "generate_handover", fake_generate)

    response = TestClient(app).post(
        f"/api/shifts/{SHIFT_DATE}/handover",
        json={"confirmed": True},
    )

    assert response.status_code == 409
    assert generation_called is False


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
    create_investigation(
        noc_root,
        "brinks-bridge-exceptions-stuck-event-timestamp-parse-failure-uspri-prod",
        "BRINKS Bridge Exceptions – stuck event timestamp parse failure (uspri-prod)",
        review_context={
            "reviewState": "reviewed",
            "finding": "Done",
            "state": "Cured",
            "reviewedAt": "PRIVATE_REVIEW_TIMESTAMP",
            "reviewedBy": "PRIVATE_REVIEWER",
        },
        notebook_url=(
            "https://app.datadoghq.com/notebook/15954893/"
            "brinks-bridge-exceptions-%25E2%2580%2593-stuck-event-timestamp-parse-failure-uspri-prod"
        ),
        generated_next_actions=(
            "- Purge or replay the rejected event.\n"
            "- Settle the timestamp format with its owners."
        ),
    )
    create_investigation(
        noc_root,
        "cco-login-cco-sesami-io-frankfurt-latency-2026-10-14",
        "CCO login (cco.sesami.io) Frankfurt latency – 2026-10-14",
        review_context={
            "reviewState": "reviewed",
            "finding": "Done",
            "state": "Cured",
            "reviewedAt": "PRIVATE_REVIEW_TIMESTAMP",
            "reviewedBy": "PRIVATE_REVIEWER",
        },
        notebook_url=(
            "https://app.datadoghq.com/notebook/15916190/"
            "cco-login-cco-sesami-io-frankfurt-latency-%25E2%2580%2593-2026-10-14"
        ),
        generated_next_actions=(
            "- Add OCI load balancers to Datadog.\n"
            "- Tune the monitor threshold."
        ),
    )
    create_investigation(
        noc_root,
        "active-brinks-pickup-follow-up",
        "Active Brinks Pickup Follow-up",
        review_context={
            "reviewState": "reviewed",
            "finding": "Dispatch response is still required.",
            "state": "Active",
        },
        generated_next_actions="- Send the generated dispatch follow-up.",
    )
    create_investigation(
        noc_root,
        "unreviewed-investigation-id",
        "Unreviewed Investigation Title",
    )
    create_investigation(
        noc_root,
        "rejected-investigation-id",
        "Rejected Investigation Title",
        review_context={"reviewState": "rejected"},
    )
    monkeypatch.setattr(handover.shutil, "which", lambda command: "/mock/handover")

    base_handover = """Shift handover

## Summary
No new alerts or recoveries were recorded during this shift. Two reviewed investigations remain unresolved. The BRINKS Bridge Exceptions alert in uspri-prod has a stuck event, and CCO Frankfurt latency has an unconfirmed root cause. Escalated integration and transaction issues remain ongoing.

## Investigation Updates
- **BRINKS Bridge Exceptions – stuck event timestamp parse failure (uspri-prod):**
  Findings are advisory and need operator review. Generated Next Actions say to purge or replay the event. RAW_DATADOG_EVIDENCE
- **CCO login (cco.sesami.io) Frankfurt latency – 2026-10-14:**
  Operator review is required. Generated Next Actions say to request logs and tune the monitor.
- **Active Brinks Pickup Follow-up:** Generated findings are advisory and need operator review.

## Monitoring & Alerting Improvements
- Raise monitor 149458038 to 3,500 ms.
- Require 2 failing locations.
- Add 1 retry.
- Add USPRI and MEXPRI OCI load balancers to Datadog.
- Change retry-failure monitoring for the stuck BRINKS event.

## Open Salesforce Tickets
No open Salesforce tickets.

## Open Jira Tickets
- Operator-reviewed finding: Done (state: Cured).
- State: Cured
- Notebook: https://app.datadoghq.com/notebook/15954893/brinks-bridge-exceptions
  - Reviewed Investigation Context
- NOC-556 — Superior US deposits shown in SES but not received on Wells Fargo/Garda; no NOC next action provided.

## Next Shift Actions
- BRINKS Bridge Exceptions: Purge or replay the rejected message; set the timestamp format with owners.
- CCO login Frankfurt latency: Request access logs and tune monitor 149458038.
- Active Brinks Pickup Follow-up: Confirm response from dispatch.
- Unreviewed Investigation Title: Continue generated remediation.
- Rejected Investigation Title: Continue rejected remediation.
- Apply the proposed monitor and load balancer changes above.

Please tag me if any clarification is needed.
Regards,
NOC Operator
Signature footer

## Active Local NOC Work
- NOC-556
  - Next Action: Next Action not recorded
  - NOC Notes: PRIVATE_LOCAL_WORK
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
    sections = [section["name"] for section in result["sections"]]
    assert "## Active Local NOC Work" not in content
    assert "PRIVATE_LOCAL_WORK" not in content
    assert "## Reviewed Investigation Context" not in content
    assert "brinks-bridge-exceptions-stuck-event-timestamp-parse-failure-uspri-prod" not in content
    assert "cco-login-frankfurt-latency-2026-10-14" not in content
    assert "unreviewed-investigation-id" not in content
    assert "rejected-investigation-id" not in content
    assert "Unreviewed Investigation Title" not in content
    assert "Rejected Investigation Title" not in content
    assert "BRINKS Bridge Exceptions – stuck event timestamp parse failure (uspri-prod)" in content
    assert "CCO login (cco.sesami.io) Frankfurt latency – 2026-10-14" in content
    investigation_updates = {
        section["name"]: section["content"] for section in result["sections"]
    }["Investigation Updates"]
    assert "Operator-reviewed finding: Done; state: Cured." in investigation_updates
    assert "Findings are advisory" not in investigation_updates
    assert "RAW_DATADOG_EVIDENCE" not in investigation_updates
    assert content.count("Operator-reviewed finding:") == 3
    summary = result["sections"][0]["content"]
    assert "Operator review marks BRINKS Bridge Exceptions" in summary
    assert "Operator review marks CCO login" in summary
    assert summary.count("as Cured.") == 2
    assert "remain unresolved" not in summary.casefold()
    assert "cured.." not in content.casefold()
    assert "state: Cured" in content
    assert (
        "https://app.datadoghq.com/notebook/15954893/"
        "brinks-bridge-exceptions-%25E2%2580%2593-stuck-event-timestamp-parse-failure-uspri-prod"
    ) in content
    assert (
        "https://app.datadoghq.com/notebook/15916190/"
        "cco-login-cco-sesami-io-frankfurt-latency-%25E2%2580%2593-2026-10-14"
    ) in content
    assert "PRIVATE_REVIEW_TIMESTAMP" not in content
    assert "PRIVATE_REVIEWER" not in content
    assert "PRIVATE_LOCAL_WORK" not in content
    assert "## Summary" in content
    assert "## Investigation Updates" in content
    assert "## Next Shift Actions" in content
    assert "## Monitoring & Alerting Improvements" not in content
    assert "Raise monitor 149458038 to 3,500 ms." not in content
    assert "Require 2 failing locations." not in content
    assert "Add 1 retry." not in content
    assert "Add USPRI and MEXPRI OCI load balancers to Datadog." not in content
    assert "Change retry-failure monitoring for the stuck BRINKS event." not in content
    assert "Findings are advisory and need operator review" not in content
    assert "RAW_DATADOG_EVIDENCE" not in content
    assert "Operator review is required" not in content
    assert "BRINKS Bridge Exceptions: Purge or replay" not in content
    assert "CCO login Frankfurt latency: Request access logs" not in content
    assert "Unreviewed Investigation Title: Continue generated remediation." not in content
    assert "Rejected Investigation Title: Continue rejected remediation." not in content
    assert "Active Brinks Pickup Follow-up: Confirm response from dispatch." not in content
    assert "Apply the proposed monitor and load balancer changes above." not in content
    assert (
        "Active Brinks Pickup Follow-up**: Operator-reviewed follow-up: "
        "Dispatch response is still required."
    ) in content
    assert "NOC-556:" not in {
        section["name"]: section["content"] for section in result["sections"]
    }["Next Shift Actions"]
    sections_by_name = {section["name"]: section["content"] for section in result["sections"]}
    jira_content = sections_by_name["Open Jira Tickets"]
    assert "no noc next action provided" in jira_content.casefold()
    assert "Operator-reviewed finding" not in jira_content
    assert "Reviewed Investigation Context" not in jira_content
    assert "State: Cured" not in jira_content
    assert "Datadog Notebook" not in jira_content
    assert "app.datadoghq.com" not in jira_content
    assert all(
        not line.strip() or line.lstrip().startswith("- NOC-")
        for line in jira_content.splitlines()
    )
    assert sections == [
        "Summary",
        "Investigation Updates",
        "Open Salesforce Tickets",
        "Open Jira Tickets",
        "Next Shift Actions",
    ]
    assert content.rstrip().endswith("Signature footer")
    assert result["localWork"]["items"][0]["jiraKey"] == "NOC-556"
    assert {
        item["investigation"]
        for item in result["reviewedFindings"]
    } == {
        "brinks-bridge-exceptions-stuck-event-timestamp-parse-failure-uspri-prod",
        "cco-login-cco-sesami-io-frankfurt-latency-2026-10-14",
        "active-brinks-pickup-follow-up",
    }


def test_operator_monitor_change_populates_monitoring_improvements(
    noc_root,
    monkeypatch,
):
    shift_dir = noc_root / SHIFT_DATE
    shift_dir.mkdir(parents=True)
    (shift_dir / "shift-notes.md").write_text(
        "# Shift Notes\n\n"
        "## Changes / Monitor Updates\n"
        "- Operator raised monitor 149458038 to 3,500 ms.\n\n"
        "## Notes for Handover\n"
        "- No other changes.\n",
        encoding="utf-8",
    )
    handover_file = shift_dir / "handover" / f"handover-{SHIFT_DATE}.md"
    generated = """Shift handover

## Summary
Monitor change requested.

## Monitoring & Alerting Improvements
- Raise monitor 149458038 to 3,500 ms and add one retry.

## Open Jira Tickets
No open Jira tickets.

## Next Shift Actions
- No additional actions.

Please tag me if any clarification is needed.
"""
    monkeypatch.setattr(handover.shutil, "which", lambda command: "/mock/handover")

    def fake_run(args, **kwargs):
        handover_file.parent.mkdir(parents=True, exist_ok=True)
        handover_file.write_text(generated, encoding="utf-8")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(handover.subprocess, "run", fake_run)

    result = handover.generate_handover(SHIFT_DATE)
    sections = {section["name"]: section["content"] for section in result["sections"]}

    assert sections["Monitoring & Alerting Improvements"] == (
        "- Operator raised monitor 149458038 to 3,500 ms."
    )
    assert "add one retry" not in sections["Monitoring & Alerting Improvements"]


def test_summary_replaces_unresolved_sentence_that_names_cured_investigations(noc_root):
    create_investigation(
        noc_root,
        "brinks-bridge-exceptions",
        "BRINKS Bridge Exceptions",
        review_context={
            "reviewState": "reviewed",
            "finding": "Done",
            "state": "Cured",
        },
    )
    create_investigation(
        noc_root,
        "cco-frankfurt-latency",
        "CCO Frankfurt latency",
        review_context={
            "reviewState": "reviewed",
            "finding": "Done",
            "state": "Cured",
        },
    )
    generated = """## Summary
No new alerts were reported. Two earlier investigations remain unresolved: the BRINKS state event still fails on retries, and CCO Frankfurt latency has an unconfirmed root cause. Other customer issues remain open.

## Investigation Updates
- Generated content.
"""

    corrected = handover._correct_resolved_investigation_summary(
        generated,
        handover.get_investigations(SHIFT_DATE),
    )
    summary = corrected.split("## Summary\n", 1)[1].split("\n## ", 1)[0]

    assert "remain unresolved" not in summary.casefold()
    assert summary.count("as Cured.") == 2
    assert "BRINKS Bridge Exceptions" in summary
    assert "CCO Frankfurt latency" in summary
    assert "still fails on retries" not in summary
    assert "unconfirmed root cause" not in summary


def test_summary_always_includes_resolved_review_states(noc_root):
    create_investigation(
        noc_root,
        "brinks-bridge-exceptions",
        "BRINKS Bridge Exceptions",
        review_context={
            "reviewState": "reviewed",
            "finding": "Done",
            "state": "Cured",
        },
    )
    create_investigation(
        noc_root,
        "cco-frankfurt-latency",
        "CCO Frankfurt latency",
        review_context={
            "reviewState": "reviewed",
            "finding": "Done",
            "state": "Cured",
        },
    )
    generated = """## Summary
No new alerts were reported. BRINKS continues failing timestamp parsing, and CCO root cause is unconfirmed. Escalations remain open.

## Investigation Updates
- Generated content.
"""

    corrected = handover._correct_resolved_investigation_summary(
        generated,
        handover.get_investigations(SHIFT_DATE),
    )
    summary = corrected.split("## Summary\n", 1)[1].split("\n\n## ", 1)[0]

    assert summary.count("as Cured.") == 2
    assert "remain unresolved" not in summary.casefold()
    assert "continues failing timestamp parsing" not in summary
    assert "CCO root cause is unconfirmed" not in summary
    assert "Escalations remain open." in summary


def test_active_reviewed_monitor_followup_only_uses_reviewed_context(
    noc_root,
    monkeypatch,
):
    create_investigation(
        noc_root,
        "active-monitor-149458038",
        "Active monitor 149458038 follow-up",
        review_context={
            "reviewState": "reviewed",
            "finding": "Require 2 failing locations for monitor 149458038.",
            "state": "Active",
        },
        generated_next_actions=(
            "- Raise the threshold to 3,500 ms.\n"
            "- Add 1 retry."
        ),
    )
    handover_file = (
        noc_root / SHIFT_DATE / "handover" / f"handover-{SHIFT_DATE}.md"
    )
    generated = """Shift handover

## Summary
Monitor follow-up remains active.

## Monitoring & Alerting Improvements
- Raise the threshold to 3,500 ms and add 1 retry.

## Investigation Updates
- Generated finding: requires operator review.

## Next Shift Actions
- Active monitor 149458038 follow-up: raise threshold and add retry.

Please tag me if any clarification is needed.
"""
    monkeypatch.setattr(handover.shutil, "which", lambda command: "/mock/handover")

    def fake_run(args, **kwargs):
        handover_file.parent.mkdir(parents=True, exist_ok=True)
        handover_file.write_text(generated, encoding="utf-8")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(handover.subprocess, "run", fake_run)

    result = handover.generate_handover(SHIFT_DATE)
    sections = {section["name"]: section["content"] for section in result["sections"]}

    assert sections["Monitoring & Alerting Improvements"] == (
        "- **Active monitor 149458038 follow-up**: Operator-reviewed follow-up: "
        "Require 2 failing locations for monitor 149458038."
    )
    assert "3,500 ms" not in result["content"]
    assert "Add 1 retry" not in result["content"]
    assert (
        "Operator-reviewed follow-up: Require 2 failing locations for monitor 149458038."
        in sections["Next Shift Actions"]
    )


def test_malformed_local_work_does_not_overwrite_handover(noc_root):
    handover_file = create_handover(noc_root, "Existing safe handover\n")
    ticket_dir = noc_root / "tickets" / "open"
    ticket_dir.mkdir(parents=True)
    (ticket_dir / "bad.json").write_text("{", encoding="utf-8")

    with pytest.raises(ValueError, match="Local tracking data is unavailable"):
        handover.regenerate_handover(SHIFT_DATE)

    assert handover_file.read_text(encoding="utf-8") == "Existing safe handover\n"
