from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from backend.app import app, configure_assistant_provider
from backend.services import assistant
from backend.services.ai_provider import resolve_provider_runtime
from backend.services.copilot_mcp import CopilotProviderUnavailable


SHIFT = "2026-10-29"


@pytest.fixture(autouse=True)
def _configured_provider(monkeypatch):
    monkeypatch.setenv("NOC_WEB_AI_PROVIDER", "github-copilot-cli")
    monkeypatch.setattr(app.state, "assistant_provider", lambda envelope: {})
    monkeypatch.setattr(
        app.state,
        "assistant_provider_identifier",
        "github-copilot-cli",
    )


def _response():
    return {
        "shiftDate": SHIFT, "status": "limited", "facts": [], "reviewedFindings": [],
        "aiObservations": [], "recommendations": [], "evidence": [],
        "limitations": ["Available selected-shift context is insufficient."],
        "provider": "github-copilot-cli",
        "providerInvoked": False,
        "providerStatus": "not-invoked",
    }


def test_question_route_validates_shift_body_and_disclosure(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr("backend.api.assistant.answer", lambda question, **_kwargs: _response())
    response = client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT, "question": "What requires attention?", "providerDisclosureAcknowledged": True,
    })
    assert response.status_code == 200
    assert "reviewedFindings" in response.json()
    assert "reviewed" not in response.json()
    assert response.json()["provider"] == "github-copilot-cli"
    assert response.json()["providerInvoked"] is False
    assert response.json()["providerStatus"] == "not-invoked"
    assert client.post("/api/shifts/nope/assistant/questions", json={
        "shiftDate": "nope", "question": "test", "providerDisclosureAcknowledged": True,
    }).status_code == 400
    assert client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": "2026-10-28", "question": "test", "providerDisclosureAcknowledged": True,
    }).status_code == 400
    assert client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT, "question": "test", "providerDisclosureAcknowledged": False,
    }).status_code == 422
    assert client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT, "question": 123, "providerDisclosureAcknowledged": True,
    }).status_code == 422
    assert client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": 123, "question": "test", "providerDisclosureAcknowledged": True,
    }).status_code == 422


def test_refusal_does_not_invoke_provider_or_action_endpoint(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(assistant, "ask_copilot", lambda envelope: (_ for _ in ()).throw(AssertionError()))
    response = client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT, "question": "run a command", "providerDisclosureAcknowledged": True,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "limited"
    assert body["facts"] == []
    assert "Nothing was changed." in body["limitations"][0]


def test_predefined_action_accepts_not_invoked_insufficient_context(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr("backend.api.assistant.answer", lambda question, **_kwargs: {
        "shiftDate": SHIFT,
        "status": "limited",
        "provider": "github-copilot-cli",
        "providerInvoked": False,
        "providerStatus": "not-invoked",
        "facts": [],
        "reviewedFindings": [],
        "aiObservations": [],
        "recommendations": [],
        "evidence": [],
        "limitations": ["The selected shift has not been initialized."],
    })

    response = client.post(
        f"/api/shifts/{SHIFT}/assistant/actions/summary",
        json={"providerDisclosureAcknowledged": True},
    )

    assert response.status_code == 200
    assert response.json()["assistant"]["providerStatus"] == "not-invoked"
    assert response.json()["assistant"]["providerInvoked"] is False
    assert response.json()["report"] is None
    assert response.json()["reportSaveWarning"] is None


def test_recommendation_route_preserves_shift_and_existing_confirmation(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr("backend.api.assistant.answer", lambda question, **_kwargs: {
        "shiftDate": SHIFT,
        "status": "complete",
        "facts": [],
        "reviewedFindings": [],
        "aiObservations": [],
        "recommendations": [{
            "text": "Review this ticket before acting.",
            "evidenceIds": ["local-work"],
            "route": {
                "label": "Open Tickets",
                "href": f"tickets.html?shift={SHIFT}",
                "requiresConfirmation": True,
            },
        }],
        "evidence": [{
            "id": "local-work",
            "kind": "local-work",
            "provenance": "noc-web",
            "availability": "available",
            "reference": None,
        }],
        "limitations": [],
        "provider": "github-copilot-cli",
        "providerInvoked": True,
        "providerStatus": "success",
    })
    response = client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT,
        "question": "Which tracked tickets need attention?",
        "providerDisclosureAcknowledged": True,
    })
    assert response.status_code == 200
    route = response.json()["recommendations"][0]["route"]
    parsed = urlsplit(route["href"])
    assert parsed.path == "tickets.html"
    assert parse_qs(parsed.query) == {"shift": [SHIFT]}
    assert route["requiresConfirmation"] is True
    assert client.post("/api/tickets/NOC-1/tracking/close", json={}).status_code == 422


def test_provider_failure_does_not_block_existing_read_workflows(
    noc_root,
    monkeypatch,
):
    client = TestClient(app)
    monkeypatch.setattr(assistant, "collect_context", lambda shift_date: [{
        "id": "jira-cache",
        "kind": "jira-cache",
        "provenance": "noc-web",
        "availability": "available",
        "freshness": "current",
        "summary": {"tickets": []},
    }])

    def unavailable(envelope):
        raise CopilotProviderUnavailable("private provider details")

    monkeypatch.setattr(app.state, "assistant_provider", unavailable)
    response = client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT,
        "question": "What should I focus on?",
        "providerDisclosureAcknowledged": True,
    })
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert "private provider details" not in response.text

    paths = [
        "/api/health",
        f"/api/dashboard/{SHIFT}",
        "/api/tickets",
        f"/api/shifts/{SHIFT}/investigations",
        f"/api/shifts/{SHIFT}/notes",
        f"/api/shifts/{SHIFT}/handover",
        f"/api/status/{SHIFT}",
    ]
    assert all(client.get(path).status_code == 200 for path in paths)


def test_runtime_injected_provider_receives_bounded_question_and_returns_valid_schema(
    monkeypatch,
    fake_assistant_provider,
):
    client = TestClient(app)
    evidence = {
        "id": "jira-cache",
        "kind": "jira-cache",
        "provenance": "noc-web",
        "availability": "available",
        "reference": None,
        "freshness": "current",
        "summary": {"tickets": []},
    }
    monkeypatch.setattr(assistant, "collect_context", lambda shift_date: [evidence])
    calls = fake_assistant_provider({
        "aiObservations": [{
            "text": "The selected Jira cache currently has no open tickets.",
            "evidenceIds": ["jira-cache"],
        }],
        "recommendations": [],
    })
    response = client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT,
        "question": "What should I focus on right now?",
        "providerDisclosureAcknowledged": True,
    })

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert body["providerInvoked"] is True
    assert body["providerStatus"] == "success"
    assert body["aiObservations"][0]["evidenceIds"] == ["jira-cache"]
    assert len(calls) == 1
    assert calls[0]["shiftDate"] == SHIFT
    assert calls[0]["question"] == "What should I focus on right now?"
    assert [item["id"] for item in calls[0]["evidence"]] == ["jira-cache"]
    assert "summary" not in body["evidence"][0]


@pytest.mark.parametrize("provider", [None, object()])
def test_selected_provider_without_callable_is_not_ready(monkeypatch, provider):
    client = TestClient(app)
    configure_assistant_provider(provider, "github-copilot-cli")

    response = client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT,
        "question": "What should I focus on right now?",
        "providerDisclosureAcknowledged": True,
    })

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "assistant-provider-not-ready"


def test_no_configured_provider_fails_closed_as_not_configured(monkeypatch):
    client = TestClient(app)
    monkeypatch.delenv("NOC_WEB_AI_PROVIDER", raising=False)
    configure_assistant_provider(None, None)

    response = client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT,
        "question": "What should I focus on right now?",
        "providerDisclosureAcknowledged": True,
    })

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "assistant-provider-not-configured"
    assert "assistant" not in response.json()


def test_configure_without_identifier_is_not_configured():
    configure_assistant_provider(None)

    assert app.state.assistant_provider is None
    assert app.state.assistant_provider_identifier is None


def test_injected_provider_exception_is_redacted(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(assistant, "collect_context", lambda shift_date: [{
        "id": "jira-cache",
        "kind": "jira-cache",
        "provenance": "noc-web",
        "availability": "available",
        "reference": None,
        "freshness": "current",
        "summary": {"tickets": []},
    }])

    def provider(envelope):
        raise RuntimeError("sensitive provider diagnostic")

    configure_assistant_provider(provider, "github-copilot-cli")
    response = client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT,
        "question": "What should I focus on right now?",
        "providerDisclosureAcknowledged": True,
    })

    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["providerStatus"] == "unavailable"
    assert response.json()["providerInvoked"] is True
    assert "sensitive provider diagnostic" not in response.text


def test_injected_provider_malformed_response_is_unavailable(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(assistant, "collect_context", lambda shift_date: [{
        "id": "jira-cache",
        "kind": "jira-cache",
        "provenance": "noc-web",
        "availability": "available",
        "reference": None,
        "freshness": "current",
        "summary": {"tickets": []},
    }])
    configure_assistant_provider(
        lambda envelope: {"aiObservations": "not-an-array"},
        "github-copilot-cli",
    )

    response = client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT,
        "question": "What should I focus on right now?",
        "providerDisclosureAcknowledged": True,
    })

    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["providerStatus"] == "invalid"
    assert response.json()["providerInvoked"] is True
    assert response.json()["aiObservations"] == []
    assert "invalid response" in " ".join(response.json()["limitations"]).casefold()


def test_assistant_static_contract_and_navigation_are_transient():
    from pathlib import Path
    frontend = Path(__file__).parents[1] / "frontend"
    page = (frontend / "assistant.html").read_text(encoding="utf-8")
    api = (frontend / "js" / "api.js").read_text(encoding="utf-8")
    workflow = (frontend / "js" / "workflow-context.js").read_text(encoding="utf-8")
    assert "does not persist or log" in page
    assert "assistant-provider-disclosure" in page
    assert "assistantProviderDisclosure" in page
    assert "getProviderHealth" in page
    assert "disabled" in page and "provider-disclosure" in page
    assert "localStorage" not in page and "sessionStorage" not in page and "console." not in page
    assert "pagehide" in page and "clearTransientDom" in page
    assert "reviewedFindings" in page
    assert "requireExplicitShift: true" in page
    assert "requireExplicitShift" in workflow
    assert "askAssistant" in api
    assert "assistant.html" in workflow


@pytest.mark.parametrize("identifier", ["deepseek-api", "github-copilot-cli"])
def test_each_provider_serves_questions_and_all_actions(
    noc_root,
    monkeypatch,
    fake_assistant_provider,
    identifier,
):
    client = TestClient(app)
    (noc_root / SHIFT / "reports").mkdir(parents=True)
    evidence = {
        "id": "jira-cache",
        "kind": "jira-cache",
        "provenance": "noc-web",
        "availability": "available",
        "reference": None,
        "freshness": "current",
        "summary": {"tickets": []},
    }
    monkeypatch.setattr(assistant, "collect_context", lambda shift_date: [evidence])
    monkeypatch.setattr(
        assistant,
        "_has_question_sufficient_context",
        lambda question, context: True,
    )
    calls = fake_assistant_provider({
        "aiObservations": [{
            "text": "The selected shift has one bounded observation.",
            "evidenceIds": ["jira-cache"],
        }],
        "recommendations": [],
    }, identifier)

    question = client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT,
        "question": "What should I focus on right now?",
        "providerDisclosureAcknowledged": True,
    })
    assert question.status_code == 200
    assert question.json()["provider"] == identifier
    assert set(question.json()) == {
        "shiftDate", "status", "provider", "providerInvoked", "providerStatus",
        "facts", "reviewedFindings", "aiObservations", "recommendations",
        "evidence", "limitations",
    }

    for action in ("analysis", "summary", "followups", "handover"):
        response = client.post(
            f"/api/shifts/{SHIFT}/assistant/actions/{action}",
            json={"providerDisclosureAcknowledged": True},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["assistant"]["provider"] == identifier
        assert body["assistant"]["providerStatus"] == "success"
        assert body["report"] is not None

    assert len(calls) == 5


def test_provider_change_is_reflected_by_the_next_request(
    noc_root,
    monkeypatch,
    fake_assistant_provider,
):
    client = TestClient(app)
    evidence = {
        "id": "jira-cache",
        "kind": "jira-cache",
        "provenance": "noc-web",
        "availability": "available",
        "reference": None,
        "freshness": "current",
        "summary": {"tickets": []},
    }
    monkeypatch.setattr(assistant, "collect_context", lambda shift_date: [evidence])
    provider_result = {
        "aiObservations": [{
            "text": "Bounded observation.",
            "evidenceIds": ["jira-cache"],
        }],
        "recommendations": [],
    }

    fake_assistant_provider(provider_result, "deepseek-api")
    first = client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT,
        "question": "What should I focus on right now?",
        "providerDisclosureAcknowledged": True,
    })
    assert first.json()["provider"] == "deepseek-api"

    fake_assistant_provider(provider_result, "github-copilot-cli")
    second = client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT,
        "question": "What should I focus on right now?",
        "providerDisclosureAcknowledged": True,
    })
    assert second.json()["provider"] == "github-copilot-cli"


def test_selected_not_ready_provider_never_falls_back_to_copilot(
    noc_root,
    monkeypatch,
):
    from backend.services import copilot_cli

    client = TestClient(app)
    monkeypatch.setenv("NOC_WEB_AI_PROVIDER", "deepseek-api")
    monkeypatch.delenv("NOC_WEB_DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(
        copilot_cli,
        "answer_with_copilot_cli",
        lambda envelope: pytest.fail("Copilot must not be called"),
    )
    runtime = resolve_provider_runtime()
    monkeypatch.setattr(app.state, "assistant_provider", runtime.provider)
    monkeypatch.setattr(
        app.state,
        "assistant_provider_identifier",
        runtime.identifier,
    )

    response = client.post(
        f"/api/shifts/{SHIFT}/assistant/actions/analysis",
        json={"providerDisclosureAcknowledged": True},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "assistant-provider-not-ready"
    assert not list(noc_root.rglob("ai-*.md"))


def test_copilot_selected_but_absent_fails_closed_without_report(
    noc_root,
    monkeypatch,
):
    from backend.services import ai_provider

    client = TestClient(app)
    monkeypatch.setenv("NOC_WEB_AI_PROVIDER", "github-copilot-cli")
    monkeypatch.setattr(ai_provider.shutil, "which", lambda command: None)
    runtime = resolve_provider_runtime()
    monkeypatch.setattr(app.state, "assistant_provider", runtime.provider)
    monkeypatch.setattr(
        app.state,
        "assistant_provider_identifier",
        runtime.identifier,
    )

    response = client.post(
        f"/api/shifts/{SHIFT}/assistant/actions/summary",
        json={"providerDisclosureAcknowledged": True},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "assistant-provider-not-ready"
    assert not list(noc_root.rglob("ai-*.md"))


def test_api_responses_never_include_the_configured_credential(
    noc_root,
    monkeypatch,
):
    sentinel = "test-sentinel-deepseek-key"
    client = TestClient(app)
    monkeypatch.setenv("NOC_WEB_AI_PROVIDER", "deepseek-api")
    monkeypatch.setenv("NOC_WEB_DEEPSEEK_API_KEY", sentinel)
    evidence = {
        "id": "jira-cache",
        "kind": "jira-cache",
        "provenance": "noc-web",
        "availability": "available",
        "reference": None,
        "freshness": "current",
        "summary": {"tickets": []},
    }
    monkeypatch.setattr(assistant, "collect_context", lambda shift_date: [evidence])
    monkeypatch.setattr(
        assistant,
        "_has_question_sufficient_context",
        lambda question, context: True,
    )

    def success(envelope):
        return {
            "aiObservations": [{
                "text": "Bounded observation.",
                "evidenceIds": ["jira-cache"],
            }],
            "recommendations": [],
        }

    configure_assistant_provider(success, "deepseek-api")
    success_response = client.post(
        f"/api/shifts/{SHIFT}/assistant/questions",
        json={
            "shiftDate": SHIFT,
            "question": "What should I focus on right now?",
            "providerDisclosureAcknowledged": True,
        },
    )
    assert success_response.status_code == 200
    assert sentinel not in success_response.text

    def failure(envelope):
        raise CopilotProviderUnavailable(f"credential {sentinel} rejected")

    configure_assistant_provider(failure, "deepseek-api")
    failure_response = client.post(
        f"/api/shifts/{SHIFT}/assistant/questions",
        json={
            "shiftDate": SHIFT,
            "question": "What should I focus on right now?",
            "providerDisclosureAcknowledged": True,
        },
    )
    assert failure_response.status_code == 200
    assert failure_response.json()["providerStatus"] == "unavailable"
    assert sentinel not in failure_response.text
