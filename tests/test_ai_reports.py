import re
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.services import ai_reports
from backend.services.assistant_actions import AI_ACTIONS


SHIFT = "2026-10-29"


def _assistant_response(shift_date=SHIFT):
    return {
        "shiftDate": shift_date,
        "status": "complete",
        "provider": "github-copilot-cli",
        "providerInvoked": True,
        "providerStatus": "success",
        "facts": [{
            "text": "The selected Jira cache contains one open ticket.",
            "evidenceIds": ["jira-cache"],
        }],
        "reviewedFindings": [{
            "text": "Memory remains elevated.",
            "state": "monitoring",
            "evidenceIds": ["investigation:memory"],
        }],
        "aiObservations": [{
            "text": "The tracked ticket has no recorded Next Action.",
            "evidenceIds": ["local-work"],
        }],
        "recommendations": [{
            "text": "Review the ticket and decide whether to record a Next Action.",
            "evidenceIds": ["local-work"],
            "route": {
                "label": "Open Tickets",
                "href": f"tickets.html?shift={shift_date}",
                "requiresConfirmation": True,
            },
        }],
        "evidence": [
            {
                "id": "jira-cache",
                "kind": "jira-cache",
                "provenance": "noc-web",
                "availability": "available",
                "reference": "must-not-be-persisted",
                "freshness": "current",
            },
            {
                "id": "local-work",
                "kind": "local-work",
                "provenance": "noc-web",
                "availability": "available",
                "reference": None,
            },
            {
                "id": "investigation:memory",
                "kind": "investigation",
                "provenance": "noc-inv",
                "availability": "available",
                "reference": None,
            },
        ],
        "limitations": ["The report is advisory and does not change operational records."],
    }


@pytest.mark.parametrize(
    ("action", "report_slug"),
    [
        ("analysis", "shift-analysis"),
        ("summary", "shift-summary"),
        ("followups", "followups"),
        ("handover", "handover-review"),
    ],
)
def test_successful_ai_action_saves_one_advisory_report_and_opens_it(
    noc_root,
    monkeypatch,
    action,
    report_slug,
):
    monkeypatch.setattr(ai_reports, "NOC_ROOT", noc_root)
    monkeypatch.setattr(app.state, "assistant_provider", None)
    (noc_root / SHIFT / "reports").mkdir(parents=True)
    calls = []

    def answer(question):
        calls.append(question)
        return _assistant_response()

    monkeypatch.setattr("backend.api.assistant.answer", answer)
    client = TestClient(app)
    response = client.post(
        f"/api/shifts/{SHIFT}/assistant/actions/{action}",
        json={"providerDisclosureAcknowledged": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["assistant"]["providerStatus"] == "success"
    assert body["reportSaveWarning"] is None
    report = body["report"]
    assert report["available"] is True
    assert report["title"] == AI_ACTIONS[action].title
    assert re.fullmatch(
        rf"ai-{report_slug}-\d{{8}}T\d{{12}}Z-[0-9a-f]{{8}}\.md",
        report["file"],
    )
    assert report["name"] == report["file"]
    assert len(calls) == 1
    assert calls[0].shift_date == SHIFT
    assert calls[0].question == AI_ACTIONS[action].question

    report_path = noc_root / SHIFT / "reports" / report["file"]
    assert report_path.is_file()
    content = report_path.read_text(encoding="utf-8")
    assert f"Selected shift: {SHIFT}" in content
    assert f"AI Action: {AI_ACTIONS[action].title}" in content
    assert "Provider: GitHub Copilot CLI" in content
    assert "Advisory / non-authoritative" in content
    assert "Generated: " in content
    assert "Source-grounded facts" in content
    assert "Operator-reviewed investigation findings" in content
    assert "AI-generated observations" in content
    assert "Recommendations" in content
    assert "Evidence and source status" in content
    assert "jira-cache" in content and "freshness: current" in content
    assert "The tracked ticket has no recorded Next Action." in content
    assert "Memory remains elevated." in content
    assert "Limitations" in content
    assert "must-not-be-persisted" not in content
    assert "rawProviderOutput" not in content
    assert "context.json" not in content

    listed = client.get(f"/api/shifts/{SHIFT}/ai-reports")
    assert listed.status_code == 200
    assert report in listed.json()["reports"]
    opened = client.get(
        f"/api/shifts/{SHIFT}/ai-reports/{report['name']}"
    )
    assert opened.status_code == 200
    assert opened.json()["content"] == content.strip()


@pytest.mark.parametrize(
    ("provider_status", "invoked"),
    [
        ("unavailable", False),
        ("timeout", True),
        ("invalid", True),
    ],
)
def test_failed_or_invalid_provider_results_do_not_create_reports(
    noc_root,
    monkeypatch,
    provider_status,
    invoked,
):
    monkeypatch.setattr(ai_reports, "NOC_ROOT", noc_root)
    monkeypatch.setattr(app.state, "assistant_provider", None)
    result = _assistant_response()
    result.update(
        status="unavailable",
        providerInvoked=invoked,
        providerStatus=provider_status,
        facts=[],
        reviewedFindings=[],
        aiObservations=[],
        recommendations=[],
    )
    monkeypatch.setattr("backend.api.assistant.answer", lambda question: result)

    response = TestClient(app).post(
        f"/api/shifts/{SHIFT}/assistant/actions/summary",
        json={"providerDisclosureAcknowledged": True},
    )

    assert response.status_code == 200
    assert response.json()["assistant"]["providerStatus"] == provider_status
    assert response.json()["report"] is None
    assert response.json()["reportSaveWarning"] is None
    assert not list(noc_root.rglob("ai-*.md"))


def test_ai_action_requires_explicit_disclosure_and_rejects_operator_prompts(
    noc_root,
    monkeypatch,
):
    monkeypatch.setattr(ai_reports, "NOC_ROOT", noc_root)
    monkeypatch.setattr(app.state, "assistant_provider", None)
    monkeypatch.setattr(
        "backend.api.assistant.answer",
        lambda question: pytest.fail("invalid action request must not invoke Assistant"),
    )
    client = TestClient(app)

    missing_ack = client.post(
        f"/api/shifts/{SHIFT}/assistant/actions/summary",
        json={"providerDisclosureAcknowledged": False},
    )
    arbitrary_prompt = client.post(
        f"/api/shifts/{SHIFT}/assistant/actions/summary",
        json={
            "providerDisclosureAcknowledged": True,
            "question": "unbounded operator input",
        },
    )
    unsupported_action = client.post(
        f"/api/shifts/{SHIFT}/assistant/actions/freeform",
        json={"providerDisclosureAcknowledged": True},
    )

    assert missing_ack.status_code == 422
    assert arbitrary_prompt.status_code == 422
    assert unsupported_action.status_code == 404
    assert not list(noc_root.rglob("ai-*.md"))


def test_generic_assistant_question_remains_transient(
    noc_root,
    monkeypatch,
):
    monkeypatch.setattr(ai_reports, "NOC_ROOT", noc_root)
    monkeypatch.setattr(app.state, "assistant_provider", None)
    (noc_root / SHIFT / "reports").mkdir(parents=True)
    monkeypatch.setattr(
        "backend.api.assistant.answer",
        lambda question: _assistant_response(),
    )

    response = TestClient(app).post(
        f"/api/shifts/{SHIFT}/assistant/questions",
        json={
            "shiftDate": SHIFT,
            "question": "What requires attention?",
            "providerDisclosureAcknowledged": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["providerStatus"] == "success"
    assert not list((noc_root / SHIFT / "reports").glob("ai-*.md"))


def test_malformed_success_response_is_rejected_without_report(noc_root, monkeypatch):
    monkeypatch.setattr(ai_reports, "NOC_ROOT", noc_root)
    monkeypatch.setattr(app.state, "assistant_provider", None)
    malformed = _assistant_response()
    malformed["rawProviderOutput"] = "private output"
    monkeypatch.setattr("backend.api.assistant.answer", lambda question: malformed)

    response = TestClient(app).post(
        f"/api/shifts/{SHIFT}/assistant/actions/summary",
        json={"providerDisclosureAcknowledged": True},
    )

    assert response.status_code == 502
    assert "private output" not in response.text
    assert not list(noc_root.rglob("ai-*.md"))


def test_report_save_failure_keeps_successful_analysis_and_warns_separately(
    noc_root,
    monkeypatch,
):
    monkeypatch.setattr(ai_reports, "NOC_ROOT", noc_root)
    monkeypatch.setattr(app.state, "assistant_provider", None)
    monkeypatch.setattr(
        "backend.api.assistant.answer",
        lambda question: _assistant_response(),
    )

    def fail_save(*args, **kwargs):
        raise ai_reports.AIReportPersistenceError

    monkeypatch.setattr(ai_reports, "persist_ai_action_report", fail_save)
    response = TestClient(app).post(
        f"/api/shifts/{SHIFT}/assistant/actions/summary",
        json={"providerDisclosureAcknowledged": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["assistant"]["aiObservations"][0]["text"].startswith(
        "The tracked ticket"
    )
    assert body["report"] is None
    assert body["reportSaveWarning"]


def test_historical_action_writes_only_to_selected_shift(noc_root, monkeypatch):
    historical_shift = "2026-10-15"
    monkeypatch.setattr(ai_reports, "NOC_ROOT", noc_root)
    monkeypatch.setattr(app.state, "assistant_provider", None)
    (noc_root / historical_shift / "reports").mkdir(parents=True)
    monkeypatch.setattr(
        "backend.api.assistant.answer",
        lambda question: _assistant_response(historical_shift),
    )

    response = TestClient(app).post(
        f"/api/shifts/{historical_shift}/assistant/actions/summary",
        json={"providerDisclosureAcknowledged": True},
    )

    assert response.status_code == 200
    assert list((noc_root / historical_shift / "reports").glob("ai-*.md"))
    assert not (noc_root / SHIFT / "reports").exists()


def test_missing_existing_reports_directory_surfaces_save_warning(
    noc_root,
    monkeypatch,
):
    monkeypatch.setattr(ai_reports, "NOC_ROOT", noc_root)
    monkeypatch.setattr(app.state, "assistant_provider", None)
    monkeypatch.setattr(
        "backend.api.assistant.answer",
        lambda question: _assistant_response(),
    )

    response = TestClient(app).post(
        f"/api/shifts/{SHIFT}/assistant/actions/summary",
        json={"providerDisclosureAcknowledged": True},
    )

    assert response.status_code == 200
    assert response.json()["assistant"]["status"] == "complete"
    assert response.json()["report"] is None
    assert response.json()["reportSaveWarning"]
    assert not (noc_root / SHIFT).exists()


def test_collision_safe_report_name_never_overwrites_existing_file(
    noc_root,
    monkeypatch,
):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 29, tzinfo=timezone.utc)

    monkeypatch.setattr(ai_reports, "NOC_ROOT", noc_root)
    monkeypatch.setattr(ai_reports, "datetime", FixedDatetime)
    tokens = iter(["a1b2c3d4", "a1b2c3d4", "e5f6a7b8"])
    monkeypatch.setattr(ai_reports.secrets, "token_hex", lambda size: next(tokens))
    reports_dir = noc_root / SHIFT / "reports"
    reports_dir.mkdir(parents=True)
    existing = reports_dir / "ai-shift-summary-20261029T000000000000Z-a1b2c3d4.md"
    existing.write_text("existing report", encoding="utf-8")

    saved = ai_reports.persist_ai_action_report(
        SHIFT,
        "summary",
        _assistant_response(),
    )

    assert existing.read_text(encoding="utf-8") == "existing report"
    assert saved["file"].endswith("-e5f6a7b8.md")
    assert len(list(reports_dir.glob("ai-*.md"))) == 2


def test_ordinary_jira_salesforce_correlation_is_not_routed_to_investigations(
    noc_root,
    monkeypatch,
):
    from backend.services import assistant
    from backend.services.assistant import AssistantQuestion

    jira_evidence = [{
        "id": "jira-cache",
        "kind": "jira-cache",
        "provenance": "noc-web",
        "availability": "available",
        "freshness": "current",
        "summary": {"tickets": [{
            "jira": {"id": "SF-17", "status": "Open", "priority": "Low"},
        }]},
    }]
    monkeypatch.setattr(assistant, "collect_context", lambda shift_date: jira_evidence)
    monkeypatch.setattr(
        assistant,
        "ask_copilot",
        lambda envelope: {
            "aiObservations": [],
            "recommendations": [{
                "text": "Investigate the Jira/Salesforce ticket correlation.",
                "evidenceIds": ["jira-cache"],
                "route": {
                    "label": "Open Investigations",
                    "href": "investigations.html",
                    "requiresConfirmation": True,
                },
            }],
        },
    )

    response = assistant.answer(
        AssistantQuestion(SHIFT, "What requires attention in the ticket queue?", True)
    )

    assert response["providerStatus"] == "invalid"
    assert response["recommendations"] == []


def test_investigations_route_requires_available_noc_inv_provenance(monkeypatch):
    from backend.services import assistant
    from backend.services.assistant import AssistantQuestion

    evidence = [{
        "id": "investigation:dd-monitor-1",
        "kind": "investigation",
        "provenance": "noc-inv",
        "availability": "available",
        "summary": {"title": "Monitor investigation"},
    }, {
        "id": "investigations",
        "kind": "investigations",
        "provenance": "noc-web",
        "availability": "available",
        "summary": {"count": 1, "items": []},
    }]
    monkeypatch.setattr(assistant, "collect_context", lambda shift_date: evidence)
    monkeypatch.setattr(
        assistant,
        "ask_copilot",
        lambda envelope: {
            "aiObservations": [],
            "recommendations": [{
                "text": "Review the Datadog monitor investigation.",
                "evidenceIds": ["investigation:dd-monitor-1"],
                "route": {
                    "label": "Open Investigations",
                    "href": "investigations.html",
                    "requiresConfirmation": True,
                },
            }],
        },
    )

    response = assistant.answer(
        AssistantQuestion(SHIFT, "Review the active NOC investigation.", True)
    )

    assert response["providerStatus"] == "success"
    assert response["recommendations"][0]["route"]["href"] == (
        f"investigations.html?shift={SHIFT}"
    )
