import pytest

from backend.services import ai_provider


SENTINEL = "test-sentinel-deepseek-key"


def _deepseek(**overrides):
    values = {
        "NOC_WEB_AI_PROVIDER": "deepseek-api",
        "NOC_WEB_DEEPSEEK_API_KEY": SENTINEL,
        "NOC_WEB_DEEPSEEK_MODEL": "deepseek-flash",
        "NOC_WEB_DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "NOC_WEB_AI_TIMEOUT_SECONDS": "55",
    }
    values.update(overrides)
    return values


def test_unset_provider_is_not_configured_without_a_default():
    readiness = ai_provider.provider_readiness({})

    assert set(readiness) == {
        "configuredProvider",
        "readiness",
        "label",
        "model",
        "impact",
        "correctiveAction",
        "primaryProvider",
        "localProvider",
        "localProbe",
    }
    assert readiness["primaryProvider"]["configuredProvider"] == "deepseek-api"
    assert readiness["localProvider"]["configuredProvider"] == "ollama"
    assert readiness["localProvider"]["readiness"] == "notConfigured"
    assert readiness["localProvider"]["endpointConfigured"] is False
    assert readiness["localProbe"] is None
    assert readiness["configuredProvider"] is None
    assert readiness["readiness"] == "notConfigured"
    assert readiness["label"] is None
    assert readiness["model"] is None
    assert "NOC_WEB_AI_PROVIDER" in readiness["correctiveAction"]
    assert ai_provider.resolve_provider_runtime({}).provider is None


def test_unknown_provider_is_not_ready_and_names_only_the_setting():
    readiness = ai_provider.provider_readiness({
        "NOC_WEB_AI_PROVIDER": "unapproved-provider",
    })

    assert readiness["readiness"] == "notReady"
    assert readiness["configuredProvider"] is None
    assert "NOC_WEB_AI_PROVIDER" in readiness["correctiveAction"]
    assert "unapproved-provider" not in str(readiness)
    runtime = ai_provider.resolve_provider_runtime({
        "NOC_WEB_AI_PROVIDER": "unapproved-provider",
    })
    assert runtime.identifier is None
    assert runtime.provider is None


def test_deepseek_without_key_is_not_ready_and_builds_no_callable():
    environ = _deepseek(NOC_WEB_DEEPSEEK_API_KEY="")

    readiness = ai_provider.provider_readiness(environ)
    runtime = ai_provider.resolve_provider_runtime(environ)

    assert readiness["readiness"] == "notReady"
    assert readiness["configuredProvider"] == "deepseek-api"
    assert readiness["model"] == "deepseek-flash"
    assert runtime.identifier == "deepseek-api"
    assert runtime.provider is None


def test_deepseek_ready_reports_identity_and_never_the_credential():
    readiness = ai_provider.provider_readiness(_deepseek())

    assert readiness["readiness"] == "ready"
    assert readiness["configuredProvider"] == "deepseek-api"
    assert readiness["label"] == "DeepSeek API"
    assert readiness["model"] == "deepseek-flash"
    assert SENTINEL not in str(readiness)
    assert "credential" not in readiness
    assert "apiKey" not in readiness


def test_deepseek_runtime_callable_excludes_serializable_credentials():
    runtime = ai_provider.resolve_provider_runtime(_deepseek())

    assert runtime.identifier == "deepseek-api"
    assert callable(runtime.provider)
    assert not hasattr(runtime, "api_key")
    assert SENTINEL not in str(runtime)
    assert set(ai_provider.ProviderRuntime.__dataclass_fields__) == {
        "identifier",
        "provider",
        "readiness",
    }


@pytest.mark.parametrize("base_url", [
    "http://api.deepseek.com",
    "https://user:secret@api.deepseek.com",
    "https://api.deepseek.com?token=secret",
    "https://api.deepseek.com#fragment",
    "https://api.deepseek.com/../admin",
    "not-a-url",
])
def test_invalid_deepseek_base_url_is_not_ready_and_redacted(base_url):
    readiness = ai_provider.provider_readiness(
        _deepseek(NOC_WEB_DEEPSEEK_BASE_URL=base_url)
    )

    assert readiness["readiness"] == "notReady"
    assert "NOC_WEB_DEEPSEEK_BASE_URL" in readiness["correctiveAction"]
    assert base_url not in str(readiness)
    assert "secret" not in str(readiness)


@pytest.mark.parametrize("model", ["", "   ", "x" * 129, "bad\u0000model"])
def test_invalid_deepseek_model_is_not_ready(model):
    readiness = ai_provider.provider_readiness(
        _deepseek(NOC_WEB_DEEPSEEK_MODEL=model)
    )

    assert readiness["readiness"] == "notReady"
    assert "NOC_WEB_DEEPSEEK_MODEL" in readiness["correctiveAction"]


@pytest.mark.parametrize("timeout", ["0", "61", "not-a-number", "-1"])
def test_invalid_timeout_is_not_ready(timeout):
    readiness = ai_provider.provider_readiness(
        _deepseek(NOC_WEB_AI_TIMEOUT_SECONDS=timeout)
    )

    assert readiness["readiness"] == "notReady"
    assert "NOC_WEB_AI_TIMEOUT_SECONDS" in readiness["correctiveAction"]


def test_provider_timeout_seconds_applies_to_the_mediation_boundary():
    assert ai_provider.provider_timeout_seconds(
        _deepseek(NOC_WEB_AI_TIMEOUT_SECONDS="17")
    ) == 17
    assert ai_provider.provider_timeout_seconds(
        {"NOC_WEB_AI_PROVIDER": "github-copilot-cli", "NOC_WEB_AI_TIMEOUT_SECONDS": "12"}
    ) == 12
    assert ai_provider.provider_timeout_seconds({}) == 55
    assert ai_provider.provider_timeout_seconds(
        _deepseek(NOC_WEB_AI_TIMEOUT_SECONDS="999")
    ) == 55


def test_copilot_readiness_uses_executable_presence_only(monkeypatch):
    monkeypatch.setattr(ai_provider.shutil, "which", lambda command: "/usr/bin/copilot")
    ready = ai_provider.provider_readiness({
        "NOC_WEB_AI_PROVIDER": "github-copilot-cli",
    })

    assert ready["readiness"] == "ready"
    assert ready["configuredProvider"] == "github-copilot-cli"
    assert ready["label"] == "GitHub Copilot CLI"
    assert "not verified" in ready["impact"]

    monkeypatch.setattr(ai_provider.shutil, "which", lambda command: None)
    missing = ai_provider.provider_readiness({
        "NOC_WEB_AI_PROVIDER": "github-copilot-cli",
    })

    assert missing["readiness"] == "notReady"
    assert "GitHub Copilot CLI" in missing["impact"]
    assert "Install" in missing["correctiveAction"]


def test_deepseek_selection_does_not_require_copilot(monkeypatch):
    monkeypatch.setattr(ai_provider.shutil, "which", lambda command: None)

    readiness = ai_provider.provider_readiness(_deepseek())

    assert readiness["readiness"] == "ready"
    assert readiness["configuredProvider"] == "deepseek-api"


def test_no_automatic_fallback_when_selected_provider_is_not_ready(monkeypatch):
    monkeypatch.setattr(ai_provider.shutil, "which", lambda command: "/usr/bin/copilot")

    runtime = ai_provider.resolve_provider_runtime(
        _deepseek(NOC_WEB_DEEPSEEK_API_KEY="")
    )

    assert runtime.identifier == "deepseek-api"
    assert runtime.provider is None
    assert runtime.readiness["readiness"] == "notReady"


def test_investigation_system_prompt_is_passed_to_selected_provider(monkeypatch):
    from backend.services import deepseek_provider

    captured = {}

    def answer(envelope, **kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(deepseek_provider, "answer_with_deepseek_api", answer)
    runtime = ai_provider.resolve_provider_runtime(
        _deepseek(),
        system_prompt="Investigation prompt profile",
    )

    assert runtime.provider({"evidence": []}) == {"ok": True}
    assert captured["system_prompt"] == "Investigation prompt profile"
    assert captured["model"] == "deepseek-flash"


def test_handover_system_prompt_is_passed_to_selected_provider(monkeypatch):
    from backend.services import deepseek_provider

    captured = {}

    def answer(envelope, **kwargs):
        captured.update(kwargs)
        return {"advisorySummary": [], "operationalRisks": [], "recommendedFocus": [], "watchItems": []}

    monkeypatch.setattr(deepseek_provider, "answer_with_deepseek_api", answer)
    runtime = ai_provider.resolve_provider_runtime(
        _deepseek(),
        system_prompt="Handover prompt profile",
    )

    assert runtime.provider({"evidence": []})["advisorySummary"] == []
    assert captured["system_prompt"] == "Handover prompt profile"
    assert captured["model"] == "deepseek-flash"


def _ollama(**overrides):
    values = {
        "NOC_WEB_AI_PROVIDER": "ollama",
        "NOC_WEB_OLLAMA_BASE_URL": "http://ollama.lan:11434",
        "NOC_WEB_OLLAMA_MODEL": "qwen3:8b",
        "NOC_WEB_OLLAMA_TIMEOUT_SECONDS": "120",
        "NOC_WEB_OLLAMA_CONNECT_TIMEOUT_SECONDS": "5",
    }
    values.update(overrides)
    return values


def test_ollama_requires_an_explicit_endpoint_and_defaults_model():
    missing = ai_provider.provider_readiness(_ollama(NOC_WEB_OLLAMA_BASE_URL=""))
    configured = ai_provider.provider_readiness(
        _ollama(NOC_WEB_OLLAMA_MODEL="")
    )

    assert missing["readiness"] == "notConfigured"
    assert missing["localProvider"]["endpointConfigured"] is False
    assert configured["readiness"] == "ready"
    assert configured["configuredProvider"] == "ollama"
    assert configured["label"] == "Ollama"
    assert configured["model"] == "qwen3:8b"
    assert configured["localProvider"]["endpointConfigured"] is True


@pytest.mark.parametrize("base_url", [
    "http://ollama.lan:11434/path",
    "http://user:secret@ollama.lan:11434",
    "http://ollama.lan:11434?token=secret",
    "http://ollama.lan:11434#fragment",
    "ftp://ollama.lan:11434",
    "not-a-url",
])
def test_invalid_ollama_endpoint_is_not_ready_and_redacted(base_url):
    readiness = ai_provider.provider_readiness(
        _ollama(NOC_WEB_OLLAMA_BASE_URL=base_url)
    )

    assert readiness["readiness"] == "notReady"
    assert base_url not in str(readiness)
    assert "secret" not in str(readiness)
    assert "NOC_WEB_OLLAMA_BASE_URL" in readiness["correctiveAction"]


@pytest.mark.parametrize(("setting", "value"), [
    ("NOC_WEB_OLLAMA_TIMEOUT_SECONDS", "0"),
    ("NOC_WEB_OLLAMA_TIMEOUT_SECONDS", "301"),
    ("NOC_WEB_OLLAMA_CONNECT_TIMEOUT_SECONDS", "0"),
    ("NOC_WEB_OLLAMA_CONNECT_TIMEOUT_SECONDS", "11"),
    ("NOC_WEB_OLLAMA_TIMEOUT_SECONDS", "nan"),
])
def test_ollama_timeouts_are_bounded(setting, value):
    readiness = ai_provider.provider_readiness(_ollama(**{setting: value}))

    assert readiness["readiness"] == "notReady"
    assert setting in readiness["correctiveAction"]


def test_ollama_runtime_is_explicit_and_never_falls_back(monkeypatch):
    runtime = ai_provider.resolve_local_provider_runtime(_ollama())
    unavailable = ai_provider.resolve_local_provider_runtime(
        _ollama(NOC_WEB_OLLAMA_BASE_URL="")
    )

    assert runtime.identifier == "ollama"
    assert callable(runtime.provider)
    assert runtime.readiness["model"] == "qwen3:8b"
    assert unavailable.identifier == "ollama"
    assert unavailable.provider is None
    assert unavailable.readiness["readiness"] == "notConfigured"


def test_primary_and_local_readiness_are_distinct_and_never_network(monkeypatch):
    monkeypatch.setattr(
        ai_provider,
        "build_ollama_provider",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network")),
    )
    readiness = ai_provider.provider_readiness(_ollama())

    assert readiness["configuredProvider"] == "ollama"
    assert readiness["primaryProvider"]["configuredProvider"] == "deepseek-api"
    assert readiness["primaryProvider"]["readiness"] == "notReady"
    assert readiness["localProvider"]["readiness"] == "ready"
    assert readiness["localProvider"]["model"] == "qwen3:8b"


def test_ollama_configuration_bounds_are_available_to_the_adapter():
    configuration = ai_provider.load_provider_configuration(_ollama(
        NOC_WEB_OLLAMA_TIMEOUT_SECONDS="300",
        NOC_WEB_OLLAMA_CONNECT_TIMEOUT_SECONDS="10",
    ))

    assert configuration.timeout_seconds == 300
    assert configuration.connect_timeout_seconds == 10
    assert ai_provider.provider_timeout_seconds(_ollama()) == 120
