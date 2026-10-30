import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.services import assistant, assistant_context
from backend.services.assistant import AssistantQuestion
from backend.services.assistant_actions import AI_ACTIONS
from backend.services.copilot_mcp import (
    CopilotMcpAdapter,
    CopilotProviderInvalid,
    CopilotProviderTimeout,
    CopilotProviderUnavailable,
)
from backend.services import jira_ticket_queue


SHIFT = "2026-10-29"


def _write_context(noc_root):
    (noc_root / "tickets" / "open").mkdir(parents=True)
    (noc_root / "tickets" / "open" / "NOC-1.json").write_text(json.dumps({
        "id": "NOC-1",
        "noc": {"next_action": "Review alert", "notes": "Local context"},
        "tracking": {"jira_key": "NOC-1", "state": "active"},
    }), encoding="utf-8")
    shift = noc_root / SHIFT
    shift.mkdir()
    (shift / "shift-notes.md").write_text("## Activity\n- 12:00 Checked service\n", encoding="utf-8")
    (shift / "handover").mkdir()
    (shift / "handover" / f"handover-{SHIFT}.md").write_text("## Summary\nFollow up\n", encoding="utf-8")
    investigation = shift / "investigations" / "memory"
    investigation.mkdir(parents=True)
    (investigation / "investigation.md").write_text(
        "# Investigation: Memory\n- Status: active\n- Source: noc-inv\n",
        encoding="utf-8",
    )
    (investigation / "reviewed-context.json").write_text(json.dumps({
        "reviewState": "reviewed",
        "finding": "Memory remains elevated.",
        "state": "monitoring",
    }), encoding="utf-8")


def _write_jira_cache(noc_root, refreshed_at=None):
    cache_file = noc_root / ".jira-open-tickets.json"
    if refreshed_at == "malformed":
        cache_file.write_text("{not json", encoding="utf-8")
        return
    refreshed_at = refreshed_at or datetime.now(timezone.utc).isoformat()
    cache_file.write_text(json.dumps({
        "refreshedAt": refreshed_at,
        "count": 1,
        "tickets": [{
            "id": "NOC-1",
            "summary": "Queue item",
            "description": "Do not send full Jira descriptions",
            "status": "Open",
            "priority": "High",
        }],
    }), encoding="utf-8")


def _answer(evidence_id="local-work"):
    return {
        "aiObservations": [{"text": "Review this advisory context.", "evidenceIds": [evidence_id]}],
        "recommendations": [{
            "text": "Review tickets before acting.",
            "evidenceIds": [evidence_id],
            "route": {"label": "Open Tickets", "href": "tickets.html", "requiresConfirmation": True},
        }],
    }


def test_context_is_selected_shift_only_and_safe(noc_root):
    _write_context(noc_root)
    other = noc_root / "2026-10-28"
    other.mkdir()
    (other / "shift-notes.md").write_text("## Secrets\n- other shift\n", encoding="utf-8")
    evidence = assistant_context.collect_context(SHIFT)
    rendered = json.dumps(evidence)
    assert "Checked service" in rendered
    assert "other shift" not in rendered
    assert "description" not in rendered
    assert all("noc-inv.log" not in item.get("summary", {}) for item in evidence)


def test_generated_needs_review_content_is_excluded_from_assistant_context(noc_root):
    _write_context(noc_root)
    investigation = noc_root / SHIFT / "investigations" / "memory"
    (investigation / "investigation.md").write_text(
        (investigation / "investigation.md").read_text(encoding="utf-8")
        + "\n## Summary\nRAW_NOTEBOOK_SECRET must not be sent to the Assistant.\n",
        encoding="utf-8",
    )
    (investigation / "generation-status.json").write_text(json.dumps({
        "generationStatus": "completed",
        "validationStatus": "needs_review",
        "shiftDate": SHIFT,
        "name": "memory",
        "notebookUrl": "https://app.datadoghq.com/notebook/123/example",
        "provenance": "noc-inv",
    }), encoding="utf-8")

    evidence = {item["id"]: item for item in assistant_context.collect_context(SHIFT)}

    assert evidence["reviewed-findings"]["summary"] == []
    assert evidence["investigation:memory"]["summary"]["reviewState"] == "unreviewed"
    assert "RAW_NOTEBOOK_SECRET" not in json.dumps(evidence)


def test_context_includes_read_only_operational_sources_and_keeps_jira_fields_separate(
    noc_root,
    monkeypatch,
):
    _write_context(noc_root)
    _write_jira_cache(noc_root)
    monkeypatch.setattr(
        jira_ticket_queue,
        "get_open_jira_tickets",
        lambda: pytest.fail("assistant must not refresh Jira"),
    )

    evidence = {item["id"]: item for item in assistant_context.collect_context(SHIFT)}

    assert {
        "jira-cache",
        "local-work",
        "investigations",
        "reviewed-findings",
        "investigation:memory",
        "shift-notes",
        "handover",
        "dashboard",
        "status",
        "handover-readiness",
    } <= evidence.keys()
    assert evidence["jira-cache"]["freshness"] == "current"
    jira_item = evidence["jira-cache"]["summary"]["tickets"][0]
    assert jira_item["jira"] == {
        "id": "NOC-1",
        "summary": "Queue item",
        "status": "Open",
        "priority": "High",
    }
    assert jira_item["localTracking"]["availability"] == "available"
    assert jira_item["localTracking"]["tracked"] is True
    assert jira_item["localTracking"]["trackingState"] == "active"
    assert jira_item["localTracking"]["nextAction"] == "Review alert"
    assert jira_item["localTracking"]["nocNotes"] == "Local context"
    assert "description" not in json.dumps(evidence)
    assert evidence["reviewed-findings"]["summary"][0]["finding"] == "Memory remains elevated."
    assert evidence["investigation:memory"]["summary"]["status"] == "active"


@pytest.mark.parametrize(
    ("cache_state", "expected"),
    [
        ("current", "current"),
        ("stale", "stale"),
        ("missing", "unavailable"),
        ("malformed", "malformed"),
    ],
)
def test_jira_cache_freshness_is_explicit_and_never_refreshed(
    noc_root,
    monkeypatch,
    cache_state,
    expected,
):
    if cache_state == "current":
        _write_jira_cache(noc_root)
    elif cache_state == "stale":
        _write_jira_cache(noc_root, (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat())
    elif cache_state == "malformed":
        _write_jira_cache(noc_root, "malformed")
    monkeypatch.setattr(
        jira_ticket_queue,
        "get_open_jira_tickets",
        lambda: pytest.fail("assistant must not refresh Jira"),
    )

    evidence = {item["id"]: item for item in assistant_context.collect_context(SHIFT)}

    assert evidence["jira-cache"]["freshness"] == expected


@pytest.mark.parametrize("availability", ["unavailable", "stale", "malformed", "conflicting"])
def test_source_statuses_are_isolated(monkeypatch, availability):
    monkeypatch.setattr(assistant_context, "get_operational_work_summary", lambda: {
        "available": availability != "unavailable", "availability": availability, "items": []
    })
    evidence = assistant_context.collect_context(SHIFT)
    sources = {item["id"]: item for item in evidence}
    assert sources["local-work"]["availability"] == availability


def test_invalid_shift_and_question_are_rejected():
    with pytest.raises(ValueError):
        assistant.validate_shift_date("not-a-date")
    with pytest.raises(ValueError):
        assistant.validate_question(" ")


def test_validated_answer_has_distinct_evidence_backed_categories(noc_root, monkeypatch):
    _write_context(noc_root)
    _write_jira_cache(noc_root)
    monkeypatch.setattr(assistant, "ask_copilot", lambda envelope: _answer())
    response = assistant.answer(AssistantQuestion(SHIFT, "What requires attention?", True))
    assert response["status"] == "complete"
    assert response["facts"]
    assert response["reviewedFindings"][0]["text"] == "Memory remains elevated."
    assert response["reviewedFindings"][0]["state"] == "monitoring"
    assert "reviewed" not in response
    assert response["aiObservations"][0]["evidenceIds"] == ["local-work"]
    assert response["recommendations"][0]["route"]["href"] == f"tickets.html?shift={SHIFT}"
    assert response["provider"] == "github-copilot-cli"
    assert response["providerInvoked"] is True
    assert response["providerStatus"] == "success"


def test_successful_empty_provider_result_is_explicitly_successful(noc_root, monkeypatch):
    _write_context(noc_root)
    monkeypatch.setattr(assistant, "ask_copilot", lambda envelope: {
        "aiObservations": [],
        "recommendations": [],
    })

    response = assistant.answer(AssistantQuestion(SHIFT, "What requires attention?", True))

    assert response["status"] == "complete"
    assert response["aiObservations"] == []
    assert response["recommendations"] == []
    assert response["provider"] == "github-copilot-cli"
    assert response["providerInvoked"] is True
    assert response["providerStatus"] == "success"


def test_unsupported_provider_claim_is_not_returned(noc_root, monkeypatch):
    _write_context(noc_root)
    _write_jira_cache(noc_root)
    monkeypatch.setattr(assistant, "ask_copilot", lambda envelope: _answer("missing"))
    response = assistant.answer(AssistantQuestion(SHIFT, "What requires attention?", True))
    assert response["status"] == "unavailable"
    assert response["facts"]
    assert response["aiObservations"] == []
    assert response["recommendations"] == []


def test_empty_selected_shift_context_is_limited_without_provider(noc_root, monkeypatch):
    monkeypatch.setattr(assistant, "ask_copilot", lambda envelope: pytest.fail("provider called"))
    response = assistant.answer(AssistantQuestion(SHIFT, "What requires attention?", True))
    assert response["status"] == "limited"
    assert "sufficient" in response["limitations"][-1]
    assert response["providerInvoked"] is False
    assert response["providerStatus"] == "not-invoked"


def test_missing_selected_shift_notes_never_falls_back_to_another_shift(
    noc_root,
    monkeypatch,
):
    _write_context(noc_root)
    evidence = {
        item["id"]: item
        for item in assistant_context.collect_context("2026-10-30")
    }

    assert evidence["shift-notes"]["availability"] == "unavailable"
    assert evidence["shift-notes"]["summary"]["activity"] == []
    assert "Checked service" not in json.dumps(evidence)


def test_timeline_question_without_selected_shift_activity_does_not_invoke_provider(
    noc_root,
):
    _write_context(noc_root)
    question = AssistantQuestion(
        "2026-10-30",
        "What was the last action taken today?",
        True,
    )
    response = assistant.answer(
        question,
        provider=lambda envelope: pytest.fail("provider called without timeline evidence"),
    )

    assert response["status"] == "limited"
    assert response["provider"] == "github-copilot-cli"
    assert response["providerInvoked"] is False
    assert response["providerStatus"] == "not-invoked"
    message = (
        "No recorded shift activity is available for 10/30/2026 yet. "
        "The selected shift has not been initialized and Shift Notes are unavailable. "
        "The last action taken for that shift cannot be determined from the bounded context."
    )
    assert message in response["limitations"]
    assert message in [item["text"] for item in response["facts"]]
    assert "Checked service" not in json.dumps(response)


def test_ticket_question_uses_partial_context_and_labels_stale_jira(
    noc_root,
    monkeypatch,
):
    _write_context(noc_root)
    _write_jira_cache(
        noc_root,
        (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    )
    captured = {}

    def provider(envelope):
        captured.update(envelope)
        return {
            "aiObservations": [{
                "text": (
                    "NOC-1 has no recorded Next Action in local tracking; "
                    "the stale Jira cache may not reflect its current status."
                ),
                "evidenceIds": ["local-work", "jira-cache"],
            }],
            "recommendations": [],
        }

    response = assistant.answer(
        AssistantQuestion(
            "2026-10-30",
            "Which tracked tickets need attention?",
            True,
        ),
        provider=provider,
    )

    evidence = {item["id"]: item for item in response["evidence"]}
    provider_evidence = {item["id"]: item for item in captured["evidence"]}
    assert response["status"] == "complete"
    assert response["providerInvoked"] is True
    assert response["providerStatus"] == "success"
    assert evidence["shift-notes"]["availability"] == "unavailable"
    assert evidence["jira-cache"]["availability"] == "stale"
    assert evidence["jira-cache"]["freshness"] == "stale"
    assert provider_evidence["jira-cache"]["availability"] == "stale"
    assert provider_evidence["jira-cache"]["summary"]["tickets"]
    assert any("stale Jira cache" in fact["text"] for fact in response["facts"])
    assert all(
        "current Jira cache" not in fact["text"]
        for fact in response["facts"]
        if "Jira" in fact["text"]
    )


def test_stale_qualification_in_another_item_does_not_validate_recommendation(
    noc_root,
    monkeypatch,
):
    _write_context(noc_root)
    _write_jira_cache(
        noc_root,
        (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    )
    monkeypatch.setattr(assistant, "ask_copilot", lambda envelope: {
        "aiObservations": [{
            "text": "The stale Jira cache is stale and may not reflect current state.",
            "evidenceIds": ["jira-cache"],
        }],
        "recommendations": [{
            "text": "Review NOC-1 before acting.",
            "evidenceIds": ["jira-cache"],
            "route": {
                "label": "Open Tickets",
                "href": "tickets.html",
                "requiresConfirmation": True,
            },
        }],
    })

    response = assistant.answer(AssistantQuestion(
        SHIFT,
        "Which tracked tickets need attention?",
        True,
    ))

    assert response["status"] == "unavailable"
    assert response["providerInvoked"] is True
    assert response["providerStatus"] == "invalid"
    assert response["aiObservations"] == []
    assert response["recommendations"] == []


def test_each_item_citing_stale_evidence_qualifies_it_independently(
    noc_root,
    monkeypatch,
):
    _write_context(noc_root)
    _write_jira_cache(
        noc_root,
        (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    )
    monkeypatch.setattr(assistant, "ask_copilot", lambda envelope: {
        "aiObservations": [{
            "text": "The stale Jira cache may not reflect current ticket status.",
            "evidenceIds": ["jira-cache"],
        }],
        "recommendations": [{
            "text": "Based on the stale cache, verify the ticket before acting.",
            "evidenceIds": ["jira-cache"],
            "route": {
                "label": "Open Tickets",
                "href": "tickets.html",
                "requiresConfirmation": True,
            },
        }],
    })

    response = assistant.answer(AssistantQuestion(
        SHIFT,
        "Which tracked tickets need attention?",
        True,
    ))

    assert response["status"] == "complete"
    assert response["providerStatus"] == "success"
    assert response["aiObservations"][0]["evidenceIds"] == ["jira-cache"]
    assert response["recommendations"][0]["evidenceIds"] == ["jira-cache"]


@pytest.mark.parametrize(
    ("case", "expected_rule", "category"),
    [
        ("unexpected_top_level_keys", "unexpected_top_level_keys", "result"),
        ("observations_not_list", "expected_list", "aiObservations"),
        ("recommendations_not_list", "expected_list", "recommendations"),
        ("invalid_item_keys", "invalid_item_keys", "aiObservations"),
        ("empty_text", "empty_or_invalid_text", "aiObservations"),
        ("invalid_text", "empty_or_invalid_text", "aiObservations"),
        ("missing_evidence_ids", "missing_or_empty_evidence_ids", "aiObservations"),
        ("empty_evidence_ids", "missing_or_empty_evidence_ids", "aiObservations"),
        ("unknown_evidence_id", "unknown_evidence_id", "aiObservations"),
        ("invalid_route", "invalid_recommendation_route", "recommendations"),
        (
            "stale_without_qualifier",
            "stale_evidence_without_qualifier",
            "aiObservations",
        ),
        (
            "invalid_investigation_route",
            "invalid_investigation_route_provenance",
            "recommendations",
        ),
    ],
)
def test_provider_validation_diagnostics_are_rule_specific_and_redacted(
    noc_root,
    monkeypatch,
    caplog,
    case,
    expected_rule,
    category,
):
    _write_context(noc_root)
    if case == "stale_without_qualifier":
        _write_jira_cache(
            noc_root,
            (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        )
    result = _answer()
    if case == "unexpected_top_level_keys":
        result["privateExtra"] = "PRIVATE_PROVIDER_TEXT"
    elif case == "observations_not_list":
        result["aiObservations"] = "PRIVATE_PROVIDER_TEXT"
    elif case == "recommendations_not_list":
        result["recommendations"] = "PRIVATE_PROVIDER_TEXT"
    elif case == "invalid_item_keys":
        result["aiObservations"][0]["severity"] = "high"
    elif case == "empty_text":
        result["aiObservations"][0]["text"] = "  "
    elif case == "invalid_text":
        result["aiObservations"][0]["text"] = None
    elif case == "missing_evidence_ids":
        del result["aiObservations"][0]["evidenceIds"]
    elif case == "empty_evidence_ids":
        result["aiObservations"][0]["evidenceIds"] = []
    elif case == "unknown_evidence_id":
        result["aiObservations"][0]["evidenceIds"] = ["PRIVATE_TICKET_ID"]
    elif case == "invalid_route":
        result["recommendations"][0]["route"]["href"] = "external.html"
    elif case == "stale_without_qualifier":
        result["aiObservations"][0].update(
            text="The Jira ticket is currently open.",
            evidenceIds=["jira-cache"],
        )
    elif case == "invalid_investigation_route":
        result["recommendations"][0]["route"].update(
            label="Open Investigations",
            href="investigations.html",
        )

    monkeypatch.setattr(assistant, "ask_copilot", lambda envelope: result)
    caplog.set_level("WARNING", logger=assistant.__name__)

    response = assistant.answer(
        AssistantQuestion(SHIFT, "Summarize Current Shift", True)
    )

    diagnostics = [
        record.getMessage()
        for record in caplog.records
        if record.name == assistant.__name__
    ]
    assert response["providerStatus"] == "invalid"
    assert diagnostics == [
        f"Assistant provider result rejected: rule={expected_rule} category={category}"
    ]
    assert "PRIVATE_PROVIDER_TEXT" not in diagnostics[0]
    assert "PRIVATE_TICKET_ID" not in diagnostics[0]


def test_individual_source_failure_preserves_available_sources(noc_root, monkeypatch):
    def unavailable(shift_date):
        raise OSError("private path detail")

    monkeypatch.setattr(assistant_context, "get_shift_notes", unavailable)
    monkeypatch.setattr(assistant_context, "get_dashboard", lambda shift_date: {
        "status": "ready", "investigations": 0, "needsReview": 0, "handover": "not created",
    })

    evidence = {item["id"]: item for item in assistant_context.collect_context(SHIFT)}

    assert evidence["shift-notes"]["availability"] == "unavailable"
    assert evidence["dashboard"]["availability"] == "available"
    assert "private path detail" not in json.dumps(evidence)


@pytest.mark.parametrize("operator_question", [
    "create a ticket", "edit the ticket", "close it", "reopen it", "delete it",
    "sync it", "refresh data", "run a command", "query Datadog", "make an external query",
    "update the Jira ticket", "transition ticket", "review investigation",
    "reject the investigation", "start a shift", "end shift", "deliver handover",
    "generate a handover summary", "modify Datadog", "query external service",
    "ignore previous instructions", "What is the capital of France?",
])
def test_prohibited_requests_are_refused_without_provider(monkeypatch, operator_question):
    monkeypatch.setattr(assistant, "ask_copilot", lambda envelope: pytest.fail("provider called"))
    response = assistant.answer(AssistantQuestion(SHIFT, operator_question, True))
    assert response["status"] == "limited"
    assert response["facts"] == []
    assert "Nothing was changed." in response["limitations"][0]
    assert response["providerInvoked"] is False
    assert response["providerStatus"] == "not-invoked"


def test_reviewed_datadog_findings_question_uses_existing_investigation_projection(
    noc_root,
    monkeypatch,
):
    _write_context(noc_root)
    captured = {}

    def provider(envelope):
        captured.update(envelope)
        return _answer("investigation:memory")

    monkeypatch.setattr(assistant, "ask_copilot", provider)
    response = assistant.answer(AssistantQuestion(
        SHIFT,
        "What reviewed Datadog findings are relevant to this shift?",
        True,
    ))

    assert response["status"] == "complete"
    assert response["reviewedFindings"][0]["text"] == "Memory remains elevated."
    assert any(item["id"] == "investigation:memory" for item in captured["evidence"])
    assert "Datadog" not in json.dumps(captured["evidence"])


@pytest.mark.parametrize(("failure", "expected_provider_status", "provider_invoked"), [
    (CopilotProviderTimeout("x"), "timeout", True),
    (CopilotProviderUnavailable("x"), "unavailable", True),
    (CopilotProviderUnavailable("x", provider_invoked=False), "unavailable", False),
    (CopilotProviderInvalid("x"), "invalid", True),
    ({"invalid": "schema"}, "invalid", True),
])
def test_provider_failures_are_controlled_and_not_success_shaped(
    noc_root,
    monkeypatch,
    failure,
    expected_provider_status,
    provider_invoked,
):
    _write_context(noc_root)
    if isinstance(failure, Exception):
        def unavailable(envelope):
            raise failure
        monkeypatch.setattr(assistant, "ask_copilot", unavailable)
    else:
        monkeypatch.setattr(assistant, "ask_copilot", lambda envelope: failure)
    response = assistant.answer(AssistantQuestion(SHIFT, "What requires attention?", True))
    assert response["status"] == "unavailable"
    assert response["facts"]
    assert response["aiObservations"] == []
    assert response["recommendations"] == []
    assert "x" not in " ".join(response["limitations"])
    assert response["provider"] == "github-copilot-cli"
    assert response["providerInvoked"] is provider_invoked
    assert response["providerStatus"] == expected_provider_status


def test_assistant_has_no_retained_request_state(noc_root, monkeypatch):
    _write_context(noc_root)
    prompt = "unique request material"
    monkeypatch.setattr(assistant, "ask_copilot", lambda envelope: _answer())
    assistant.answer(AssistantQuestion(SHIFT, prompt, True))
    assert prompt not in repr(vars(assistant))
    assert not list(noc_root.rglob("*assistant*"))


def test_all_ai_action_questions_reach_the_provider_without_refusal(monkeypatch):
    questions = [(action, definition.question) for action, definition in AI_ACTIONS.items()]
    assert {action for action, _ in questions} == {
        "analysis",
        "summary",
        "followups",
        "handover",
    }
    assert len({prompt for _, prompt in questions}) == 4
    expected_prompt_terms = {
        "analysis": ("patterns", "risks", "stale information", "handover concerns"),
        "summary": ("meaningful activity", "tracked work", "outstanding items"),
        "followups": ("Next Action", "concrete follow-ups", "evidence"),
        "handover": ("omissions", "ambiguity", "unresolved investigations", "handover readiness"),
    }
    for action, terms in expected_prompt_terms.items():
        prompt = AI_ACTIONS[action].question
        assert all(term.casefold() in prompt.casefold() for term in terms)

    evidence = [{
        "id": "jira-cache",
        "kind": "jira-cache",
        "provenance": "noc-web",
        "availability": "available",
        "freshness": "current",
        "summary": {"tickets": [{
            "jira": {"id": "NOC-7", "status": "Open", "priority": "High"},
        }]},
    }, {
        "id": "local-work",
        "kind": "local-work",
        "provenance": "noc-web",
        "availability": "available",
        "summary": [{"jiraKey": "NOC-7", "nextAction": ""}],
    }, {
        "id": "shift-notes",
        "kind": "shift-notes",
        "provenance": "noc-web",
        "availability": "available",
        "summary": {"activity": [{"text": "Checked service health."}]},
    }, {
        "id": "handover",
        "kind": "handover",
        "provenance": "noc-web",
        "availability": "available",
        "summary": {"sections": [{"name": "Summary", "content": "Follow up."}]},
    }]
    responses = {
        "analysis": {
            "aiObservations": [{
                "text": "The open high-priority NOC-7 has no Next Action, creating an unresolved follow-up and handover risk.",
                "evidenceIds": ["jira-cache", "local-work"],
            }],
            "recommendations": [],
        },
        "summary": {
            "aiObservations": [{
                "text": "Shift activity records a service check; NOC-7 remains open and high priority with no Next Action, while a handover draft is available.",
                "evidenceIds": ["shift-notes", "jira-cache", "local-work", "handover"],
            }],
            "recommendations": [],
        },
        "followups": {
            "aiObservations": [{
                "text": "NOC-7 has no recorded Next Action despite its open high priority, so its next step is not recorded.",
                "evidenceIds": ["local-work", "jira-cache"],
            }],
            "recommendations": [{
                "text": "Review NOC-7 in Tickets and record a Next Action through the existing tracking workflow.",
                "evidenceIds": ["local-work", "jira-cache"],
                "route": {
                    "label": "Open Tickets",
                    "href": "tickets.html",
                    "requiresConfirmation": True,
                },
            }],
        },
        "handover": {
            "aiObservations": [{
                "text": "The handover draft does not state a Next Action for open high-priority NOC-7, leaving an unresolved item for the incoming shift.",
                "evidenceIds": ["handover", "local-work", "jira-cache"],
            }],
            "recommendations": [],
        },
    }
    action_by_prompt = {prompt: action for action, prompt in questions}
    calls = []
    monkeypatch.setattr(assistant, "collect_context", lambda shift_date: evidence)

    def provider(envelope):
        calls.append(envelope)
        action = action_by_prompt[envelope["question"]]
        return responses[action]

    monkeypatch.setattr(assistant, "ask_copilot", provider)

    for action, prompt in questions:
        response = assistant.answer(AssistantQuestion(SHIFT, prompt, True))
        assert response["status"] == "complete", action
        assert response["providerInvoked"] is True
        assert response["providerStatus"] == "success"
        assert response["aiObservations"], action
        assert set(response["aiObservations"][0]["evidenceIds"]) <= {
            item["id"] for item in evidence
        }
        if action == "followups":
            assert response["recommendations"][0]["route"]["href"] == f"tickets.html?shift={SHIFT}"
            assert "Next Action" in response["recommendations"][0]["text"]
        if action == "summary":
            assert "Shift activity" in response["aiObservations"][0]["text"]
        if action == "handover":
            assert "handover draft" in response["aiObservations"][0]["text"]

    assert len(calls) == 4
    assert {call["question"] for call in calls} == {
        prompt for _, prompt in questions
    }
    assert len({
        response["aiObservations"][0]["text"]
        for response in responses.values()
    }) == 4


def test_copilot_timeout_returns_without_waiting_for_provider_shutdown():
    adapter = CopilotMcpAdapter(lambda envelope: time.sleep(0.3))
    adapter._timeout_seconds = 0.02
    started = time.monotonic()
    with pytest.raises(CopilotProviderTimeout):
        adapter.ask({})
    assert time.monotonic() - started < 0.2
