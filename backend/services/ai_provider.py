"""Provider selection, static readiness, and runtime resolution for AI inference.

Provider settings are read only from the process environment at application start.
No credential value is stored in a serializable field, logged, or returned.
"""

from __future__ import annotations

import functools
import os
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from backend.services.copilot_mcp import (
    ProviderInvalid,
    ProviderTimeout,
    ProviderUnavailable,
)


PROVIDER_DEEPSEEK = "deepseek-api"
PROVIDER_COPILOT = "github-copilot-cli"
PROVIDER_OLLAMA = "ollama"
SUPPORTED_PROVIDERS = (PROVIDER_DEEPSEEK, PROVIDER_COPILOT, PROVIDER_OLLAMA)
PROVIDER_LABELS = {
    PROVIDER_DEEPSEEK: "DeepSeek API",
    PROVIDER_COPILOT: "GitHub Copilot CLI",
    PROVIDER_OLLAMA: "Ollama",
}

DEFAULT_DEEPSEEK_MODEL = "deepseek-flash"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_OLLAMA_MODEL = "qwen3:8b"
DEFAULT_TIMEOUT_SECONDS = 55
MAX_TIMEOUT_SECONDS = 60
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 120
MAX_OLLAMA_TIMEOUT_SECONDS = 300
DEFAULT_CONNECT_TIMEOUT_SECONDS = 5
DEFAULT_OLLAMA_CONNECT_TIMEOUT_SECONDS = 5
MAX_OLLAMA_CONNECT_TIMEOUT_SECONDS = 10
MAX_MODEL_LENGTH = 128

READY = "ready"
NOT_READY = "notReady"
NOT_CONFIGURED = "notConfigured"

AssistantProvider = Callable[[dict], dict]


class ProviderConfigurationError(ValueError):
    """A provider setting is invalid; the message never includes the value."""

    def __init__(self, setting: str) -> None:
        super().__init__(f"The {setting} setting is invalid.")
        self.setting = setting


@dataclass(frozen=True)
class ProviderConfiguration:
    identifier: str | None
    model: str | None
    base_url: str | None
    timeout_seconds: int
    credential_present: bool
    connect_timeout_seconds: int = DEFAULT_CONNECT_TIMEOUT_SECONDS


@dataclass(frozen=True)
class ProviderRuntime:
    identifier: str | None
    provider: AssistantProvider | None
    readiness: dict


def _environment(environ: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if environ is None else environ


def _validate_model(value: str, setting: str = "NOC_WEB_DEEPSEEK_MODEL") -> str:
    if not isinstance(value, str):
        raise ProviderConfigurationError(setting)
    model = value.strip()
    if (
        not model
        or len(model) > MAX_MODEL_LENGTH
        or any(ord(character) < 32 or ord(character) == 127 for character in model)
    ):
        raise ProviderConfigurationError(setting)
    return model


def _validate_base_url(value: str) -> str:
    if not isinstance(value, str):
        raise ProviderConfigurationError("NOC_WEB_DEEPSEEK_BASE_URL")
    candidate = value.strip().rstrip("/")
    if not candidate:
        raise ProviderConfigurationError("NOC_WEB_DEEPSEEK_BASE_URL")
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        raise ProviderConfigurationError("NOC_WEB_DEEPSEEK_BASE_URL") from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or ".." in parsed.path.split("/")
    ):
        raise ProviderConfigurationError("NOC_WEB_DEEPSEEK_BASE_URL")
    return candidate


def _validate_ollama_base_url(value: str) -> str | None:
    if not isinstance(value, str):
        raise ProviderConfigurationError("NOC_WEB_OLLAMA_BASE_URL")
    candidate = value.strip().rstrip("/")
    if not candidate:
        return None
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError:
        raise ProviderConfigurationError("NOC_WEB_OLLAMA_BASE_URL") from None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or port is not None and not 1 <= port <= 65535
        or any(ord(character) < 32 or ord(character) == 127 for character in candidate)
    ):
        raise ProviderConfigurationError("NOC_WEB_OLLAMA_BASE_URL")
    return candidate


def _validate_ollama_timeout(value: str | None) -> int:
    if value is None or not str(value).strip():
        return DEFAULT_OLLAMA_TIMEOUT_SECONDS
    try:
        timeout = int(str(value).strip())
    except (TypeError, ValueError):
        raise ProviderConfigurationError("NOC_WEB_OLLAMA_TIMEOUT_SECONDS") from None
    if not 1 <= timeout <= MAX_OLLAMA_TIMEOUT_SECONDS:
        raise ProviderConfigurationError("NOC_WEB_OLLAMA_TIMEOUT_SECONDS")
    return timeout


def _validate_ollama_connect_timeout(value: str | None) -> int:
    if value is None or not str(value).strip():
        return DEFAULT_OLLAMA_CONNECT_TIMEOUT_SECONDS
    try:
        timeout = int(str(value).strip())
    except (TypeError, ValueError):
        raise ProviderConfigurationError("NOC_WEB_OLLAMA_CONNECT_TIMEOUT_SECONDS") from None
    if not 1 <= timeout <= MAX_OLLAMA_CONNECT_TIMEOUT_SECONDS:
        raise ProviderConfigurationError("NOC_WEB_OLLAMA_CONNECT_TIMEOUT_SECONDS")
    return timeout


def _validate_timeout(value: str | None) -> int:
    if value is None or not str(value).strip():
        return DEFAULT_TIMEOUT_SECONDS
    try:
        timeout = int(str(value).strip())
    except (TypeError, ValueError):
        raise ProviderConfigurationError("NOC_WEB_AI_TIMEOUT_SECONDS") from None
    if not 1 <= timeout <= MAX_TIMEOUT_SECONDS:
        raise ProviderConfigurationError("NOC_WEB_AI_TIMEOUT_SECONDS")
    return timeout


def load_provider_configuration(
    environ: Mapping[str, str] | None = None,
) -> ProviderConfiguration:
    """Resolve the explicit provider configuration without selecting a default."""
    source = _environment(environ)
    raw_identifier = source.get("NOC_WEB_AI_PROVIDER")
    identifier = raw_identifier.strip() if isinstance(raw_identifier, str) else ""
    if not identifier:
        return ProviderConfiguration(
            identifier=None,
            model=None,
            base_url=None,
            timeout_seconds=_validate_timeout(source.get("NOC_WEB_AI_TIMEOUT_SECONDS")),
            credential_present=False,
        )
    if identifier not in SUPPORTED_PROVIDERS:
        raise ProviderConfigurationError("NOC_WEB_AI_PROVIDER")

    if identifier == PROVIDER_OLLAMA:
        model = _validate_model(
            source.get("NOC_WEB_OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL,
            setting="NOC_WEB_OLLAMA_MODEL",
        )
        base_url = _validate_ollama_base_url(
            source.get("NOC_WEB_OLLAMA_BASE_URL", "")
        )
        return ProviderConfiguration(
            identifier=identifier,
            model=model,
            base_url=base_url,
            timeout_seconds=_validate_ollama_timeout(
                source.get("NOC_WEB_OLLAMA_TIMEOUT_SECONDS")
            ),
            credential_present=False,
            connect_timeout_seconds=_validate_ollama_connect_timeout(
                source.get("NOC_WEB_OLLAMA_CONNECT_TIMEOUT_SECONDS")
            ),
        )

    timeout_seconds = _validate_timeout(source.get("NOC_WEB_AI_TIMEOUT_SECONDS"))
    if identifier == PROVIDER_DEEPSEEK:
        model = _validate_model(
            source.get("NOC_WEB_DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)
        )
        base_url = _validate_base_url(
            source.get("NOC_WEB_DEEPSEEK_BASE_URL", DEFAULT_DEEPSEEK_BASE_URL)
        )
        api_key = source.get("NOC_WEB_DEEPSEEK_API_KEY", "")
        return ProviderConfiguration(
            identifier=identifier,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            credential_present=bool(api_key.strip()),
        )
    return ProviderConfiguration(
        identifier=identifier,
        model=None,
        base_url=None,
        timeout_seconds=timeout_seconds,
        credential_present=False,
    )


def active_provider_identifier(
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """Return the selected canonical identifier, or None; never a default."""
    try:
        return load_provider_configuration(environ).identifier
    except ProviderConfigurationError:
        return None


def provider_timeout_seconds(
    environ: Mapping[str, str] | None = None,
) -> int:
    """Return the validated mediation timeout, defaulting safely when invalid."""
    try:
        return load_provider_configuration(environ).timeout_seconds
    except ProviderConfigurationError:
        return DEFAULT_TIMEOUT_SECONDS


def provider_timeout_seconds_for(
    identifier: str,
    environ: Mapping[str, str] | None = None,
) -> int:
    """Return the timeout for one explicitly selected provider."""
    source = dict(_environment(environ))
    source["NOC_WEB_AI_PROVIDER"] = identifier
    try:
        return load_provider_configuration(source).timeout_seconds
    except ProviderConfigurationError:
        if identifier == PROVIDER_OLLAMA:
            return DEFAULT_OLLAMA_TIMEOUT_SECONDS
        return DEFAULT_TIMEOUT_SECONDS


def _readiness(
    *,
    configured_provider: str | None,
    readiness: str,
    label: str | None,
    model: str | None,
    impact: str,
    corrective_action: str,
) -> dict:
    return {
        "configuredProvider": configured_provider,
        "readiness": readiness,
        "label": label,
        "model": model,
        "impact": impact,
        "correctiveAction": corrective_action,
    }


def _active_provider_readiness(environ: Mapping[str, str] | None = None) -> dict:
    """Compute static, non-secret readiness for the active provider; no call is made."""
    try:
        configuration = load_provider_configuration(environ)
    except ProviderConfigurationError as error:
        if error.setting == "NOC_WEB_AI_PROVIDER":
            return _readiness(
                configured_provider=None,
                readiness=NOT_READY,
                label=None,
                model=None,
                impact="The Assistant and AI Actions are unavailable because the provider setting is unsupported.",
                corrective_action=(
                    "Set NOC_WEB_AI_PROVIDER to deepseek-api or github-copilot-cli "
                    "and restart NOC Web."
                ),
            )
        return _readiness(
            configured_provider=None,
            readiness=NOT_READY,
            label=None,
            model=None,
            impact=(
                "The Assistant and AI Actions are unavailable because a provider "
                "setting is invalid."
            ),
            corrective_action=(
                f"Correct {error.setting} and restart NOC Web. Readiness reports "
                "configuration only; it does not verify credential acceptance or reachability."
            ),
        )

    if configuration.identifier is None:
        return _readiness(
            configured_provider=None,
            readiness=NOT_CONFIGURED,
            label=None,
            model=None,
            impact=(
                "The Assistant and AI Actions are unavailable because no provider "
                "is configured."
            ),
            corrective_action=(
                "Set NOC_WEB_AI_PROVIDER to deepseek-api or github-copilot-cli "
                "and restart NOC Web. No default provider is selected."
            ),
        )

    if configuration.identifier == PROVIDER_DEEPSEEK:
        if not configuration.credential_present:
            return _readiness(
                configured_provider=PROVIDER_DEEPSEEK,
                readiness=NOT_READY,
                label=PROVIDER_LABELS[PROVIDER_DEEPSEEK],
                model=configuration.model,
                impact=(
                    "The Assistant and AI Actions are unavailable because the "
                    "DeepSeek API key is missing."
                ),
                corrective_action=(
                    "Set NOC_WEB_DEEPSEEK_API_KEY and restart NOC Web. Readiness "
                    "does not verify credential acceptance or provider reachability."
                ),
            )
        return _readiness(
            configured_provider=PROVIDER_DEEPSEEK,
            readiness=READY,
            label=PROVIDER_LABELS[PROVIDER_DEEPSEEK],
            model=configuration.model,
            impact=(
                "The Assistant and AI Actions use the DeepSeek API. Required "
                "configuration is present; authentication and reachability are not verified."
            ),
            corrective_action="No action required.",
        )

    if configuration.identifier == PROVIDER_OLLAMA:
        if not configuration.base_url:
            return _readiness(
                configured_provider=PROVIDER_OLLAMA,
                readiness=NOT_CONFIGURED,
                label=PROVIDER_LABELS[PROVIDER_OLLAMA],
                model=configuration.model,
                impact=(
                    "The optional local Ollama provider is not configured because "
                    "NOC_WEB_OLLAMA_BASE_URL is missing."
                ),
                corrective_action=(
                    "Set NOC_WEB_OLLAMA_BASE_URL and restart NOC Web. Readiness reports "
                    "configuration only; it does not verify reachability or model presence."
                ),
            )
        return _readiness(
            configured_provider=PROVIDER_OLLAMA,
            readiness=READY,
            label=PROVIDER_LABELS[PROVIDER_OLLAMA],
            model=configuration.model,
            impact=(
                "The optional local Ollama provider is configured. Required "
                "configuration is present; reachability and model presence are not "
                "verified until an explicit probe or intentional local invocation."
            ),
            corrective_action="No action required.",
        )

    if shutil.which("copilot") is None:
        return _readiness(
            configured_provider=PROVIDER_COPILOT,
            readiness=NOT_READY,
            label=PROVIDER_LABELS[PROVIDER_COPILOT],
            model=None,
            impact=(
                "The Assistant and AI Actions are unavailable because the GitHub "
                "Copilot CLI executable is not present."
            ),
            corrective_action=(
                "Install GitHub Copilot CLI using its approved setup and restart "
                "NOC Web. Readiness does not verify authentication or reachability."
            ),
        )
    return _readiness(
        configured_provider=PROVIDER_COPILOT,
        readiness=READY,
        label=PROVIDER_LABELS[PROVIDER_COPILOT],
        model=None,
        impact=(
            "The Assistant and AI Actions use the GitHub Copilot CLI. The executable "
            "is present; authentication and reachability are not verified."
        ),
        corrective_action="No action required.",
    )


def _configured_readiness_for(
    identifier: str,
    environ: Mapping[str, str] | None,
) -> dict:
    source = dict(_environment(environ))
    source["NOC_WEB_AI_PROVIDER"] = identifier
    readiness = _active_provider_readiness(source)
    if readiness.get("configuredProvider") is None:
        readiness["configuredProvider"] = identifier
        readiness["label"] = PROVIDER_LABELS.get(identifier)
    if identifier == PROVIDER_OLLAMA:
        try:
            readiness["endpointConfigured"] = bool(
                _validate_ollama_base_url(source.get("NOC_WEB_OLLAMA_BASE_URL", ""))
            )
        except ProviderConfigurationError:
            readiness["endpointConfigured"] = False
        try:
            readiness["model"] = _validate_model(
                source.get("NOC_WEB_OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL,
                setting="NOC_WEB_OLLAMA_MODEL",
            )
        except ProviderConfigurationError:
            readiness["model"] = None
        readiness["probe"] = None
    return readiness


def provider_readiness(environ: Mapping[str, str] | None = None) -> dict:
    """Compute static primary/local/active readiness; no provider call is made."""
    readiness = _active_provider_readiness(environ)
    readiness["primaryProvider"] = _configured_readiness_for(
        PROVIDER_DEEPSEEK,
        environ,
    )
    readiness["localProvider"] = _configured_readiness_for(
        PROVIDER_OLLAMA,
        environ,
    )
    readiness["localProbe"] = None
    return readiness


def resolve_provider_runtime_for(
    identifier: str,
    environ: Mapping[str, str] | None = None,
    *,
    system_prompt: str | None = None,
) -> ProviderRuntime:
    """Resolve one explicitly named provider without fallback."""
    if identifier not in SUPPORTED_PROVIDERS:
        return ProviderRuntime(identifier=None, provider=None, readiness={
            **_configured_readiness_for(PROVIDER_DEEPSEEK, environ),
            "readiness": NOT_READY,
        })
    source = dict(_environment(environ))
    source["NOC_WEB_AI_PROVIDER"] = identifier
    runtime = resolve_provider_runtime(source, system_prompt=system_prompt)
    if identifier == PROVIDER_OLLAMA:
        runtime.readiness["endpointConfigured"] = bool(
            runtime.readiness.get("configuredProvider") == PROVIDER_OLLAMA
            and runtime.provider is not None
        )
    return runtime


def resolve_local_provider_runtime(
    environ: Mapping[str, str] | None = None,
    *,
    system_prompt: str | None = None,
) -> ProviderRuntime:
    """Resolve Ollama explicitly for an operator-confirmed local retry."""
    return resolve_provider_runtime_for(
        PROVIDER_OLLAMA,
        environ,
        system_prompt=system_prompt,
    )


def build_ollama_provider(
    configuration: ProviderConfiguration,
    *,
    system_prompt: str | None = None,
) -> AssistantProvider:
    """Build a bounded local Ollama callable with no credentials."""
    model = configuration.model or DEFAULT_OLLAMA_MODEL
    base_url = configuration.base_url
    read_timeout = configuration.timeout_seconds
    connect_timeout = configuration.connect_timeout_seconds

    def provider(envelope: dict) -> dict:
        from backend.services.ollama_provider import (
            ASSISTANT_RESPONSE_SCHEMA,
            answer_with_ollama,
        )

        return answer_with_ollama(
            envelope,
            base_url=base_url,
            model=model,
            timeout_seconds=read_timeout,
            connect_timeout_seconds=connect_timeout,
            system_prompt=system_prompt,
            response_format=(
                ASSISTANT_RESPONSE_SCHEMA
                if system_prompt is None
                else "json"
            ),
        )

    return provider


def build_deepseek_provider(
    configuration: ProviderConfiguration,
    environ: Mapping[str, str] | None = None,
    *,
    system_prompt: str | None = None,
) -> AssistantProvider:
    """Build a callable that keeps the credential inside a closure only."""
    source = _environment(environ)
    api_key = source.get("NOC_WEB_DEEPSEEK_API_KEY", "").strip()
    model = configuration.model or DEFAULT_DEEPSEEK_MODEL
    base_url = configuration.base_url or DEFAULT_DEEPSEEK_BASE_URL
    timeout_seconds = configuration.timeout_seconds

    def provider(envelope: dict) -> dict:
        from backend.services.deepseek_provider import answer_with_deepseek_api

        return answer_with_deepseek_api(
            envelope,
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            system_prompt=system_prompt,
        )

    return provider


def resolve_provider_runtime(
    environ: Mapping[str, str] | None = None,
    *,
    system_prompt: str | None = None,
) -> ProviderRuntime:
    """Resolve the selected provider and callable; never falls back."""
    readiness = provider_readiness(environ)
    try:
        configuration = load_provider_configuration(environ)
    except ProviderConfigurationError:
        return ProviderRuntime(identifier=None, provider=None, readiness=readiness)

    if configuration.identifier is None:
        return ProviderRuntime(identifier=None, provider=None, readiness=readiness)

    if configuration.identifier == PROVIDER_DEEPSEEK:
        if not configuration.credential_present:
            return ProviderRuntime(
                identifier=configuration.identifier,
                provider=None,
                readiness=readiness,
            )
        return ProviderRuntime(
            identifier=configuration.identifier,
            provider=build_deepseek_provider(
                configuration,
                environ,
                system_prompt=system_prompt,
            ),
            readiness=readiness,
        )

    if configuration.identifier == PROVIDER_OLLAMA:
        if not configuration.base_url:
            return ProviderRuntime(
                identifier=configuration.identifier,
                provider=None,
                readiness=readiness,
            )
        return ProviderRuntime(
            identifier=configuration.identifier,
            provider=build_ollama_provider(
                configuration,
                system_prompt=system_prompt,
            ),
            readiness=readiness,
        )

    if shutil.which("copilot") is None:
        return ProviderRuntime(
            identifier=configuration.identifier,
            provider=None,
            readiness=readiness,
        )
    from backend.services.copilot_cli import answer_with_copilot_cli

    provider = (
        functools.partial(answer_with_copilot_cli, prompt=system_prompt)
        if system_prompt
        else answer_with_copilot_cli
    )
    return ProviderRuntime(
        identifier=configuration.identifier,
        provider=provider,
        readiness=readiness,
    )
