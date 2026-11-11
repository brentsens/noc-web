from __future__ import annotations

import secrets
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable


MAX_PREVIEWS = 32
PREVIEW_TTL_SECONDS = 10 * 60


class PreviewStoreError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _iso_timestamp(epoch_seconds: float) -> str:
    return (
        datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


class InvestigationPreviewStore:
    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
        ttl_seconds: int = PREVIEW_TTL_SECONDS,
        maximum_entries: int = MAX_PREVIEWS,
    ):
        self._clock = clock or time.time
        self._ttl_seconds = ttl_seconds
        self._maximum_entries = maximum_entries
        self._lock = threading.Lock()
        self._entries: dict[str, dict[str, Any]] = {}

    def _expire_locked(self, now: float) -> None:
        expired = [
            preview_id
            for preview_id, entry in self._entries.items()
            if now >= entry["expiresAt"] or entry["status"] != "active"
        ]
        for preview_id in expired:
            self._entries.pop(preview_id, None)

    def put(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        now = self._clock()
        with self._lock:
            self._expire_locked(now)
            while len(self._entries) >= self._maximum_entries:
                oldest = min(
                    self._entries,
                    key=lambda preview_id: self._entries[preview_id]["createdAt"],
                )
                self._entries.pop(oldest, None)
            preview_id = secrets.token_urlsafe(32)
            entry = {
                **snapshot,
                "previewId": preview_id,
                "createdAt": now,
                "expiresAt": now + self._ttl_seconds,
                "expiresAtIso": _iso_timestamp(now + self._ttl_seconds),
                "status": "active",
            }
            self._entries[preview_id] = entry
            return self._public_entry(entry)

    def consume(self, preview_id: str) -> dict[str, Any]:
        if not isinstance(preview_id, str) or not preview_id:
            raise PreviewStoreError(
                "preview-required",
                "An active investigation preview is required.",
            )
        now = self._clock()
        with self._lock:
            entry = self._entries.get(preview_id)
            if entry is None:
                raise PreviewStoreError(
                    "preview-required",
                    "The investigation preview is unavailable or already used.",
                )
            if entry["status"] != "active":
                raise PreviewStoreError(
                    "preview-used",
                    "The investigation preview was already used.",
                )
            if now >= entry["expiresAt"]:
                self._entries.pop(preview_id, None)
                raise PreviewStoreError(
                    "preview-expired",
                    "The investigation preview expired.",
                )
            entry["status"] = "consumed"
            return entry

    def invalidate(self, preview_id: str) -> None:
        with self._lock:
            entry = self._entries.get(preview_id)
            if entry is not None:
                entry["status"] = "invalidated"
                self._entries.pop(preview_id, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def _public_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        return dict(entry)


_default_store = InvestigationPreviewStore()


def get_preview_store() -> InvestigationPreviewStore:
    return _default_store


def reset_preview_store_for_tests() -> None:
    _default_store.clear()
