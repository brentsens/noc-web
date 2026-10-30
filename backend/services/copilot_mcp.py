"""The sole, bounded provider boundary for assistant mediation."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any


MAX_TIMEOUT_SECONDS = 60


class CopilotProviderUnavailable(RuntimeError):
    """Raised without provider content when Copilot MCP cannot answer."""

    provider_status = "unavailable"

    def __init__(self, message: str, *, provider_invoked: bool = True) -> None:
        super().__init__(message)
        self.provider_invoked = provider_invoked


class CopilotProviderTimeout(CopilotProviderUnavailable):
    """Raised when the provider exceeds the bounded request timeout."""

    provider_status = "timeout"


class CopilotProviderInvalid(CopilotProviderUnavailable):
    """Raised when the provider returns an unusable response."""

    provider_status = "invalid"

CopilotProvider = Callable[[dict[str, Any]], dict[str, Any]]


class CopilotMcpAdapter:
    """A deliberately narrow adapter with no tools or operational capabilities."""

    def __init__(
        self,
        provider: CopilotProvider | None = None,
        timeout_seconds: int = MAX_TIMEOUT_SECONDS,
    ) -> None:
        self._provider = provider
        self._timeout_seconds = min(max(1, timeout_seconds), MAX_TIMEOUT_SECONDS)

    def ask(self, envelope: dict[str, Any]) -> dict[str, Any]:
        if self._provider is None:
            raise CopilotProviderUnavailable(
                "The assistant provider is not configured.",
                provider_invoked=False,
            )
        if not callable(self._provider):
            raise CopilotProviderUnavailable(
                "The assistant provider configuration is invalid.",
                provider_invoked=False,
            )
        executor = ThreadPoolExecutor(max_workers=1)
        submitted = False
        try:
            future = executor.submit(self._provider, envelope)
            submitted = True
            result = future.result(timeout=self._timeout_seconds)
        except FuturesTimeoutError:
            future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            raise CopilotProviderTimeout(
                "The assistant provider timed out.",
                provider_invoked=True,
            ) from None
        except CopilotProviderTimeout as error:
            executor.shutdown(wait=True, cancel_futures=True)
            raise CopilotProviderTimeout(
                "The assistant provider timed out.",
                provider_invoked=error.provider_invoked,
            ) from None
        except CopilotProviderInvalid as error:
            executor.shutdown(wait=True, cancel_futures=True)
            raise CopilotProviderInvalid(
                "The assistant provider returned an invalid response.",
                provider_invoked=error.provider_invoked,
            ) from None
        except CopilotProviderUnavailable as error:
            executor.shutdown(wait=True, cancel_futures=True)
            raise CopilotProviderUnavailable(
                "The assistant provider is unavailable.",
                provider_invoked=error.provider_invoked,
            ) from None
        except Exception:
            executor.shutdown(wait=True, cancel_futures=True)
            raise CopilotProviderUnavailable(
                "The assistant provider is unavailable.",
                provider_invoked=submitted,
            ) from None
        executor.shutdown(wait=True)
        return result


def ask_copilot(
    envelope: dict[str, Any],
    provider: CopilotProvider | None = None,
) -> dict[str, Any]:
    """Use the injected provider or the default local Copilot CLI adapter."""
    if provider is None:
        from backend.services.copilot_cli import answer_with_copilot_cli

        provider = answer_with_copilot_cli
    return CopilotMcpAdapter(provider).ask(envelope)
