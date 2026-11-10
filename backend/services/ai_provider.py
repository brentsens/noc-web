"""Provider selection, static readiness, and runtime resolution for AI inference.

Provider settings are read only from the process environment at application start.
No credential value is stored in a serializable field, logged, or returned.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit


PROVIDER_DEEPSEEK = "deepseek-api"
PROVIDER_COPILOT = "github-copilot-cli"
SUPPORTED_PROVIDERS = (PROVIDER_DEEPSEEK, PROVIDER_COPILOT)
PROVIDER_LABELS = {
    PROVIDER_DEEPSEEK: "DeepSeek API",
    PROVIDER_COPILOT: "GitHub Copilot CLI",
}

DEFAULT_DEEPSEEK_MODEL = "deepseek-flash"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_TIMEOUT_SECONDS = 55
MAX_TIMEOUT_SECONDS = 60
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


@dataclass(frozen=True)
class ProviderRuntime:
    identifier: str | None
    provider: AssistantProvider | None
    readiness: dict


def _environment(environ: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if environ is None else environ


def _validate_model(value: str) -> str:
    if not isinstance(value, str):
        raise ProviderConfigurationError("NOC_WEB_DEEPSEEK_MODEL")
    model = value.strip()
    if (
        not model
        or len(model) > MAX_MODEL_LENGTH
        or any(ord(character) < 32 or ord(character) == 127 for character in model)
    ):
        raise ProviderConfigurationError("NOC_WEB_DEEPSEEK_MODEL")
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


def provider_readiness(environ: Mapping[str, str] | None = None) -> dict:
    """Compute static, non-secret readiness; no provider call is made."""
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


def build_deepseek_provider(
    configuration: ProviderConfiguration,
    environ: Mapping[str, str] | None = None,
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
        )

    return provider


def resolve_provider_runtime(
    environ: Mapping[str, str] | None = None,
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
            provider=build_deepseek_provider(configuration, environ),
            readiness=readiness,
        )

    if shutil.which("copilot") is None:
        return ProviderRuntime(
            identifier=configuration.identifier,
            provider=None,
            readiness=readiness,
        )
    from backend.services.copilot_cli import answer_with_copilot_cli

    return ProviderRuntime(
        identifier=configuration.identifier,
        provider=answer_with_copilot_cli,
        readiness=readiness,
    )
