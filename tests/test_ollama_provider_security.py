import json

import pytest

from backend.services import ai_provider, ollama_provider
from backend.services.copilot_mcp import CopilotProviderUnavailable
from tests.support.ollama_provider import (
    generation_body,
    install_fake_transport,
    ollama_env,
    valid_assistant_output,
)


def test_no_authorization_or_process_secret_is_sent(monkeypatch):
    sentinel = "do-not-send-this-secret"
    monkeypatch.setenv("NOC_WEB_DEEPSEEK_API_KEY", sentinel)
    monkeypatch.setenv("NOC_WEB_DATADOG_ACCESS_TOKEN", sentinel)
    monkeypatch.setenv("NOC_WEB_M365_CLIENT_SECRET", sentinel)
    calls = []
    install_fake_transport(
        monkeypatch,
        body=generation_body(response=valid_assistant_output()),
        calls=calls,
    )

    ollama_provider.answer_with_ollama(
        {"question": "status", "evidence": []},
        base_url="http://ollama.lan:11434",
        model="qwen3:8b",
        timeout_seconds=120,
        connect_timeout_seconds=5,
        system_prompt="neutral prompt",
    )

    headers = calls[0]["headers"]
    assert "Authorization" not in headers
    assert "authorization" not in {key.lower() for key in headers}
    assert sentinel not in calls[0]["body"].decode("utf-8")
    assert sentinel not in json.dumps(headers)


def test_ollama_configuration_has_no_invented_auth_secret():
    configuration = ai_provider.load_provider_configuration(ollama_env())

    assert configuration.credential_present is False
    assert not hasattr(configuration, "api_key")
    assert not hasattr(configuration, "credential")


@pytest.mark.parametrize("base_url", [
    "http://user:secret@ollama.lan:11434",
    "http://ollama.lan:11434/path",
    "http://ollama.lan:11434?token=secret",
    "http://ollama.lan:11434#fragment",
    "ftp://ollama.lan:11434",
])
def test_invalid_endpoint_is_never_contacted(monkeypatch, base_url):
    calls = []
    install_fake_transport(monkeypatch, calls=calls)
    configuration_error = None
    try:
        ai_provider.load_provider_configuration(ollama_env(NOC_WEB_OLLAMA_BASE_URL=base_url))
    except ai_provider.ProviderConfigurationError as error:
        configuration_error = error
    assert configuration_error is not None
    assert calls == []


def test_redirect_does_not_follow_to_unexpected_host(monkeypatch):
    calls = []
    install_fake_transport(monkeypatch, status=302, body=b"{}", calls=calls)

    with pytest.raises(CopilotProviderUnavailable):
        ollama_provider.answer_with_ollama(
            {"question": "status"},
            base_url="http://ollama.lan:11434",
            model="qwen3:8b",
            timeout_seconds=120,
            connect_timeout_seconds=5,
        )

    assert len(calls) == 1
    assert calls[0]["path"] == "/api/generate"


def test_probe_and_generation_use_only_the_configured_origin(monkeypatch):
    calls = []
    install_fake_transport(
        monkeypatch,
        body=generation_body(response={"ok": True}),
        calls=calls,
    )

    ollama_provider.answer_with_ollama(
        {"question": "status"},
        base_url="http://ollama.lan:11434",
        model="qwen3:8b",
        timeout_seconds=120,
        connect_timeout_seconds=5,
        system_prompt="prompt",
    )

    assert calls[0]["path"] == "/api/generate"
    assert calls[0]["method"] == "POST"
