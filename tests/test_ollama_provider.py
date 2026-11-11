import json

import pytest

from backend.services import ollama_provider
from backend.services.copilot_mcp import (
    CopilotProviderInvalid,
    CopilotProviderTimeout,
    CopilotProviderUnavailable,
)
from tests.support.ollama_provider import (
    generation_body,
    install_fake_transport,
    ollama_env,
    sentinel_timeout,
    tags_body,
    valid_assistant_output,
)


def _generate(fake, **overrides):
    values = {
        "base_url": "http://ollama.lan:11434",
        "model": "qwen3:8b",
        "timeout_seconds": 120,
        "connect_timeout_seconds": 5,
    }
    values.update(overrides)
    return ollama_provider.answer_with_ollama({"question": "status"}, **values)


def test_generation_consumes_only_response_field(monkeypatch):
    calls = []
    install_fake_transport(
        monkeypatch,
        body=generation_body(response=valid_assistant_output()),
        calls=calls,
    )

    result = _generate(None, system_prompt="workflow prompt")

    assert result == valid_assistant_output()
    assert calls[0]["method"] == "POST"
    assert calls[0]["path"] == "/api/generate"
    assert "Authorization" not in calls[0]["headers"]
    request = json.loads(calls[0]["body"])
    assert request["model"] == "qwen3:8b"
    assert request["stream"] is False
    assert request["format"] == "json"
    assert request["system"] == "workflow prompt"
    assert json.loads(request["prompt"]) == {"question": "status"}


def test_assistant_default_uses_strict_json_schema(monkeypatch):
    calls = []
    install_fake_transport(
        monkeypatch,
        body=generation_body(response={"aiObservations": [], "recommendations": []}),
        calls=calls,
    )

    result = ollama_provider.answer_with_ollama(
        {"question": "status"},
        base_url="http://ollama.lan:11434",
        model="qwen3:8b",
        timeout_seconds=120,
        connect_timeout_seconds=5,
    )

    assert result == {"aiObservations": [], "recommendations": []}
    request = json.loads(calls[0]["body"])
    assert request["format"] == ollama_provider.ASSISTANT_RESPONSE_SCHEMA
    assert request["format"]["additionalProperties"] is False


def test_metadata_never_enters_output(monkeypatch):
    install_fake_transport(
        monkeypatch,
        body=generation_body(
            response={"ok": True},
            thinking="secret reasoning",
            context=[9, 9],
            total_duration=999,
            model="other-model",
        ),
    )

    result = _generate(None)

    serialized = json.dumps(result)
    assert result == {"ok": True}
    assert "secret reasoning" not in serialized
    assert "other-model" not in serialized


@pytest.mark.parametrize("body", [
    generation_body(include_response=False),
    generation_body(response=""),
    generation_body(response=None),
    generation_body(response=[1, 2]),
    json.dumps({"response": "not json"}).encode(),
    json.dumps({"response": "[1,2]"}).encode(),
    json.dumps({"response": 42}).encode(),
    b"not-json",
])
def test_missing_or_invalid_response_fails_closed(monkeypatch, body):
    install_fake_transport(monkeypatch, body=body)

    with pytest.raises(CopilotProviderInvalid):
        _generate(None)


def test_thinking_only_output_fails_closed(monkeypatch):
    install_fake_transport(
        monkeypatch,
        body=generation_body(include_response=False, thinking="only thinking"),
    )

    with pytest.raises(CopilotProviderInvalid):
        _generate(None)


def test_oversized_response_fails_closed(monkeypatch):
    install_fake_transport(monkeypatch, body=b"x" * (ollama_provider.MAX_RESPONSE_BYTES + 1))

    with pytest.raises(CopilotProviderInvalid):
        _generate(None)


def test_missing_model_status_raises_model_missing(monkeypatch):
    install_fake_transport(monkeypatch, status=404, body=b"{}")

    with pytest.raises(ollama_provider.OllamaModelMissing):
        _generate(None)


def test_redirect_is_rejected(monkeypatch):
    install_fake_transport(monkeypatch, status=302, body=b"{}")

    with pytest.raises(CopilotProviderUnavailable):
        _generate(None)


def test_connection_and_read_timeouts_fail_closed(monkeypatch):
    install_fake_transport(monkeypatch, connect_error=ConnectionRefusedError())
    with pytest.raises(CopilotProviderUnavailable):
        _generate(None)

    install_fake_transport(monkeypatch, read_error=sentinel_timeout())
    with pytest.raises(CopilotProviderTimeout):
        _generate(None)


def test_unexpected_host_is_not_contacted(monkeypatch):
    calls = []
    install_fake_transport(monkeypatch, calls=calls)

    with pytest.raises(CopilotProviderUnavailable):
        _generate(None, base_url="ftp://unexpected.example")

    assert calls == []


def test_probe_checks_model_presence_without_generation(monkeypatch):
    calls = []
    install_fake_transport(
        monkeypatch,
        body=tags_body("qwen3:8b", "llama3:8b"),
        calls=calls,
    )

    result = ollama_provider.probe_ollama(
        base_url="http://ollama.lan:11434",
        model="qwen3:8b",
        timeout_seconds=120,
        connect_timeout_seconds=5,
    )

    assert result["available"] is True
    assert result["reason"] is None
    assert calls[0]["method"] == "GET"
    assert calls[0]["path"] == "/api/tags"
    assert calls[0]["body"] is None


@pytest.mark.parametrize(("body", "reason"), [
    (tags_body("llama3:8b"), "model-missing"),
    (b"not-json", "malformed"),
    (json.dumps({"models": "nope"}).encode(), "malformed"),
])
def test_probe_failure_reasons_are_sanitized(monkeypatch, body, reason):
    install_fake_transport(monkeypatch, body=body)

    result = ollama_provider.probe_ollama(
        base_url="http://ollama.lan:11434",
        model="qwen3:8b",
        timeout_seconds=120,
        connect_timeout_seconds=5,
    )

    assert result["available"] is False
    assert result["reason"] == reason


def test_probe_unconfigured_does_not_contact_network(monkeypatch):
    calls = []
    install_fake_transport(monkeypatch, body=tags_body("qwen3:8b"), calls=calls)

    result = ollama_provider.probe_ollama(
        base_url=None,
        model="qwen3:8b",
        timeout_seconds=120,
        connect_timeout_seconds=5,
    )

    assert result["reason"] == "unconfigured"
    assert calls == []


@pytest.mark.parametrize(("status", "body", "stage"), [
    (200, b"not-json", "response-envelope-invalid"),
    (200, b"{}", "response-field-missing"),
    (200, b'{"response": ""}', "response-field-empty"),
    (200, b'{"response": "not-json"}', "response-json-invalid"),
    (200, b'{"response": "[]"}', "response-object-required"),
    (200, b"x" * (ollama_provider.MAX_RESPONSE_BYTES + 1), "response-over-bound"),
    (500, b"{}", "http-status-invalid"),
    (400, b"{}", "structured-format-rejected"),
])
def test_failure_logs_one_safe_fixed_stage(monkeypatch, caplog, status, body, stage):
    install_fake_transport(monkeypatch, status=status, body=body)
    caplog.set_level("WARNING", logger=ollama_provider.__name__)

    with pytest.raises((CopilotProviderInvalid, CopilotProviderUnavailable)):
        _generate(None)

    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == ollama_provider.__name__
    ]
    assert messages == [
        f"Ollama provider rejected response: stage={stage} format=json-schema"
    ]


def test_failure_log_uses_json_format_for_explicit_workflow_prompt(monkeypatch, caplog):
    install_fake_transport(monkeypatch, body=b'{"response": "not-json"}')
    caplog.set_level("WARNING", logger=ollama_provider.__name__)

    with pytest.raises(CopilotProviderInvalid):
        _generate(None, system_prompt="workflow prompt")

    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == ollama_provider.__name__
    ]
    assert messages == [
        "Ollama provider rejected response: "
        "stage=response-json-invalid format=json"
    ]


def test_failure_log_never_contains_response_text_or_metadata(monkeypatch, caplog):
    sentinel = "PRIVATE_MODEL_OUTPUT"
    install_fake_transport(
        monkeypatch,
        body=generation_body(
            response=sentinel,
            thinking=sentinel,
            context=[sentinel],
        ),
    )
    caplog.set_level("WARNING", logger=ollama_provider.__name__)

    with pytest.raises(CopilotProviderInvalid):
        _generate(None)

    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == ollama_provider.__name__
    ]
    assert messages
    assert all(sentinel not in message for message in messages)
    assert "thinking" not in " ".join(messages)
    assert "context" not in " ".join(messages)
