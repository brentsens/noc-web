import json

from fastapi.testclient import TestClient

from backend.app import app
from backend.services import assistant
from backend.services import ollama_provider
from tests.support.ollama_provider import generation_body, install_fake_transport


SHIFT = "2099-12-31"
QUESTION = "What should I focus on?"


def _evidence():
    return [{
        "id": "jira-cache",
        "kind": "jira-cache",
        "provenance": "noc-web",
        "availability": "available",
        "freshness": "current",
        "summary": {"tickets": []},
    }]


def _configure(monkeypatch, response):
    monkeypatch.setenv("NOC_WEB_OLLAMA_BASE_URL", "http://ollama.lan:11434")
    monkeypatch.setenv("NOC_WEB_OLLAMA_MODEL", "qwen3:8b")
    monkeypatch.setattr(assistant, "collect_context", lambda _shift: _evidence())
    calls = []
    install_fake_transport(
        monkeypatch,
        body=generation_body(response=response),
        calls=calls,
    )
    return calls


def _ask():
    return TestClient(app).post(
        f"/api/shifts/{SHIFT}/assistant/questions",
        json={
            "shiftDate": SHIFT,
            "question": QUESTION,
            "providerDisclosureAcknowledged": True,
            "provider": "ollama",
        },
    )


def test_qwen_wrapper_output_fails_closed_without_repair(monkeypatch, caplog):
    calls = _configure(monkeypatch, {
        "result": {
            "aiObservations": [],
            "recommendations": [],
        },
        "metadata": {
            "model": "qwen3:8b",
            "reasoning": "PRIVATE_PROVIDER_TEXT",
        },
    })
    caplog.set_level("WARNING", logger=assistant.__name__)

    response = _ask()

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "ollama"
    assert body["providerStatus"] == "invalid"
    assert body["status"] == "unavailable"
    assert body["aiObservations"] == []
    assert body["recommendations"] == []
    assert "localRetry" not in body
    assert len(calls) == 1
    assert "result" in json.loads(calls[0]["body"])["system"]
    diagnostics = [
        record.getMessage()
        for record in caplog.records
        if record.name == assistant.__name__
    ]
    assert diagnostics == [
        "Assistant provider result rejected: rule=unexpected_top_level_keys "
        "keys=['metadata', 'result']"
    ]
    assert "PRIVATE_PROVIDER_TEXT" not in caplog.text
    assert "qwen3:8b" not in caplog.text


def test_live_evidence_status_output_fails_closed(monkeypatch, caplog):
    _configure(monkeypatch, {
        "aiObservations": [],
        "evidence_status": "stale",
        "recommendations": [],
    })
    caplog.set_level("WARNING", logger=assistant.__name__)

    response = _ask()

    body = response.json()
    assert body["provider"] == "ollama"
    assert body["providerStatus"] == "invalid"
    assert body["status"] == "unavailable"
    assert body["aiObservations"] == []
    assert body["recommendations"] == []
    diagnostics = [
        record.getMessage()
        for record in caplog.records
        if record.name == assistant.__name__
    ]
    assert diagnostics == [
        "Assistant provider result rejected: rule=unexpected_top_level_keys "
        "keys=['aiObservations', 'evidence_status', 'recommendations']"
    ]
    assert "stale" not in caplog.text


def test_additional_top_level_metadata_fails_closed(monkeypatch):
    _configure(monkeypatch, {
        "aiObservations": [],
        "recommendations": [],
        "status": "complete",
    })

    body = _ask().json()

    assert body["providerStatus"] == "invalid"
    assert body["status"] == "unavailable"


def test_exact_two_key_output_is_accepted(monkeypatch):
    calls = _configure(monkeypatch, {
        "aiObservations": [],
        "recommendations": [],
    })

    response = _ask()

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "ollama"
    assert body["providerStatus"] == "success"
    assert body["status"] == "complete"
    assert body["aiObservations"] == []
    assert body["recommendations"] == []
    request_body = json.loads(calls[0]["body"])
    assert request_body["format"] == ollama_provider.ASSISTANT_RESPONSE_SCHEMA
    schema = request_body["format"]
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["aiObservations", "recommendations"]
    assert set(schema["properties"]) == {"aiObservations", "recommendations"}
    observation_items = schema["properties"]["aiObservations"]["items"]
    assert observation_items["additionalProperties"] is False
    assert observation_items["required"] == ["text", "evidenceIds"]
    assert observation_items["properties"]["evidenceIds"]["minItems"] == 1
    recommendation_items = schema["properties"]["recommendations"]["items"]
    assert recommendation_items["additionalProperties"] is False
    assert set(recommendation_items["properties"]) == {
        "text", "evidenceIds", "route"
    }
    route = recommendation_items["properties"]["route"]
    assert route["additionalProperties"] is False
    assert route["required"] == ["label", "href", "requiresConfirmation"]
    assert route["properties"]["requiresConfirmation"] == {"type": "boolean"}
    system_prompt = request_body["system"]
    assert "exactly these two" in system_prompt
    assert "aiObservations" in system_prompt
    assert "recommendations" in system_prompt
    assert "wrapper object" in system_prompt
    assert '"result"' in system_prompt
    assert (
        "NOC Web, not the model, determines evidence availability, freshness, "
        "status, and provenance."
    ) in system_prompt
    for forbidden in (
        "evidence_status",
        "evidenceStatus",
        "evidence",
        "status",
        "freshness",
        "availability",
        "provenance",
        "confidence",
        "limitations",
        "metadata",
    ):
        assert f'"{forbidden}"' in system_prompt
    assert (
        "The first character must begin the exact two-key object and the only "
        'top-level property names permitted are "aiObservations" and '
        '"recommendations".'
    ) in system_prompt
    assert '{"aiObservations":[],"recommendations":[]}' in system_prompt
    assert (
        '{"aiObservations":[],"evidence_status":"stale","recommendations":[]}'
    ) in system_prompt


def test_ollama_metadata_never_reaches_assistant_validation(monkeypatch):
    calls = _configure(monkeypatch, {
        "aiObservations": [],
        "recommendations": [],
    })

    response = _ask()

    assert response.json()["providerStatus"] == "success"
    assert "thinking" not in response.text
    assert "total_duration" not in response.text
    assert "private chain of thought" not in response.text
