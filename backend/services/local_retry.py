"""In-memory, single-use snapshots for explicit Retry with Local AI."""

from __future__ import annotations

import copy
import secrets
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Mapping


RETRY_TTL_SECONDS = 10 * 60
MAX_RETRY_SNAPSHOTS = 32
RETRY_PROVIDER = "ollama"


class RetrySnapshotError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _iso_timestamp(epoch_seconds: float) -> str:
    return (
        datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


class LocalRetryStore:
    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
        ttl_seconds: int = RETRY_TTL_SECONDS,
        maximum_entries: int = MAX_RETRY_SNAPSHOTS,
    ):
        self._clock = clock or time.time
        self._ttl_seconds = ttl_seconds
        self._maximum_entries = maximum_entries
        self._lock = threading.Lock()
        self._entries: dict[str, dict[str, Any]] = {}

    def _expire_locked(self, now: float) -> None:
        expired = [
            token
            for token, entry in self._entries.items()
            if now >= entry["expiresAt"] or entry["status"] != "active"
        ]
        for token in expired:
            self._entries.pop(token, None)

    def put(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        now = self._clock()
        with self._lock:
            self._expire_locked(now)
            while len(self._entries) >= self._maximum_entries:
                oldest = min(
                    self._entries,
                    key=lambda token: self._entries[token]["createdAt"],
                )
                self._entries.pop(oldest, None)
            token = secrets.token_urlsafe(32)
            entry = {
                **copy.deepcopy(dict(snapshot)),
                "retryToken": token,
                "createdAt": now,
                "expiresAt": now + self._ttl_seconds,
                "expiresAtIso": _iso_timestamp(now + self._ttl_seconds),
                "status": "active",
            }
            self._entries[token] = entry
            return self._public_entry(entry)

    def consume(
        self,
        token: str,
        *,
        workflow: str,
        shift_date: str,
        identity: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(token, str) or not token:
            raise RetrySnapshotError(
                "retry-snapshot-unavailable",
                "The exact failed-request snapshot is unavailable.",
            )
        now = self._clock()
        with self._lock:
            entry = self._entries.get(token)
            if entry is None:
                raise RetrySnapshotError(
                    "retry-snapshot-unavailable",
                    "The exact failed-request snapshot is unavailable.",
                )
            if entry["status"] == "consumed":
                raise RetrySnapshotError(
                    "retry-snapshot-used",
                    "The retry snapshot was already used.",
                )
            if entry["status"] != "active":
                raise RetrySnapshotError(
                    "retry-snapshot-unavailable",
                    "The exact failed-request snapshot is unavailable.",
                )
            if now >= entry["expiresAt"]:
                self._entries.pop(token, None)
                raise RetrySnapshotError(
                    "retry-snapshot-expired",
                    "The retry snapshot expired.",
                )
            if (
                entry.get("workflow") != workflow
                or entry.get("shiftDate") != shift_date
                or (identity is not None and entry.get("identity") != identity)
            ):
                raise RetrySnapshotError(
                    "retry-snapshot-unavailable",
                    "The exact failed-request snapshot is unavailable.",
                )
            entry["status"] = "consumed"
            return copy.deepcopy(entry)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def _public_entry(self, entry: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "available": True,
            "retryToken": entry["retryToken"],
            "expiresAt": entry["expiresAtIso"],
            "provider": entry.get("provider", RETRY_PROVIDER),
            "model": entry.get("model"),
        }


_default_store = LocalRetryStore()


def get_retry_store() -> LocalRetryStore:
    return _default_store


def reset_retry_store_for_tests() -> None:
    _default_store.clear()


def _local_runtime():
    from backend.services.ai_provider import resolve_local_provider_runtime

    return resolve_local_provider_runtime()


def capture_local_retry(
    *,
    workflow: str,
    shift_date: str,
    payload: Mapping[str, Any],
    identity: str | None = None,
    store: LocalRetryStore | None = None,
) -> dict[str, Any] | None:
    """Capture an exact snapshot only when Ollama is statically configured."""
    runtime = _local_runtime()
    readiness = runtime.readiness if isinstance(runtime.readiness, dict) else {}
    if runtime.provider is None or readiness.get("readiness") != "ready":
        return None
    model = readiness.get("model")
    availability = (store or get_retry_store()).put({
        "workflow": workflow,
        "shiftDate": shift_date,
        "identity": identity,
        "provider": RETRY_PROVIDER,
        "model": model,
        "payload": payload,
    })
    return availability


def resolve_retry_runtime():
    """Resolve Ollama explicitly for a confirmed retry without fallback."""
    runtime = _local_runtime()
    readiness = runtime.readiness if isinstance(runtime.readiness, dict) else {}
    if runtime.provider is None:
        if readiness.get("readiness") == "notConfigured":
            code = "provider-not-configured"
            message = "The local AI provider is not configured."
        else:
            code = "provider-not-ready"
            message = "The local AI provider is not ready."
        raise RetrySnapshotError(code, message, status_code=503)
    if readiness.get("readiness") != "ready":
        raise RetrySnapshotError(
            "provider-not-ready",
            "The local AI provider is not ready.",
            status_code=503,
        )
    return runtime
