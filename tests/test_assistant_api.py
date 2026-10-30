from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from backend.app import app, configure_assistant_provider
from backend.services import copilot_cli
from backend.services import assistant
from backend.services.copilot_mcp import CopilotProviderUnavailable


SHIFT = "2026-10-29"


def _response():
    return {
        "shiftDate": SHIFT, "status": "limited", "facts": [], "reviewedFindings": [],
        "aiObservations": [], "recommendations": [], "evidence": [],
        "limitations": ["Available selected-shift context is insufficient."],
        "provider": "github-copilot-cli",
        "providerInvoked": False,
        "providerStatus": "unavailable",
    }


def test_question_route_validates_shift_body_and_disclosure(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(app.state, "assistant_provider", None)
    monkeypatch.setattr("backend.api.assistant.answer", lambda question: _response())
    response = client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT, "question": "What requires attention?", "providerDisclosureAcknowledged": True,
    })
    assert response.status_code == 200
    assert "reviewedFindings" in response.json()
    assert "reviewed" not in response.json()
    assert response.json()["provider"] == "github-copilot-cli"
    assert response.json()["providerInvoked"] is False
    assert response.json()["providerStatus"] == "unavailable"
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


def test_recommendation_route_preserves_shift_and_existing_confirmation(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(app.state, "assistant_provider", None)
    monkeypatch.setattr("backend.api.assistant.answer", lambda question: {
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
    monkeypatch.setattr(app.state, "assistant_provider", None)
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

    monkeypatch.setattr(assistant, "ask_copilot", unavailable)
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
def test_absent_or_invalid_runtime_provider_is_assistant_unavailable(
    monkeypatch,
    provider,
):
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
    monkeypatch.setattr(app.state, "assistant_provider", None)
    if provider is None:
        monkeypatch.setattr(copilot_cli.shutil, "which", lambda name: None)
    configure_assistant_provider(provider)

    response = client.post(f"/api/shifts/{SHIFT}/assistant/questions", json={
        "shiftDate": SHIFT,
        "question": "What should I focus on right now?",
        "providerDisclosureAcknowledged": True,
    })

    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["providerStatus"] == "unavailable"
    assert response.json()["providerInvoked"] is False
    assert "provider" in " ".join(response.json()["limitations"]).casefold()


def test_default_runtime_provider_is_github_copilot_cli():
    configure_assistant_provider(None)

    assert app.state.assistant_provider is copilot_cli.answer_with_copilot_cli


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

    monkeypatch.setattr(app.state, "assistant_provider", None)
    configure_assistant_provider(provider)
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
    monkeypatch.setattr(app.state, "assistant_provider", None)
    configure_assistant_provider(lambda envelope: {"aiObservations": "not-an-array"})

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
    assert "GitHub Copilot CLI or another configured inference provider may apply its own handling or retention" in page
    assert "disabled" in page and "provider-disclosure" in page
    assert "localStorage" not in page and "sessionStorage" not in page and "console." not in page
    assert "pagehide" in page and "clearTransientDom" in page
    assert "reviewedFindings" in page
    assert "requireExplicitShift: true" in page
    assert "requireExplicitShift" in workflow
    assert "askAssistant" in api
    assert "assistant.html" in workflow
