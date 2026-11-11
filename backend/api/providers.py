"""Explicit, operator-triggered provider probes."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter

from backend.services.ai_provider import (
    PROVIDER_OLLAMA,
    ProviderConfigurationError,
    load_provider_configuration,
)
from backend.services.ollama_provider import probe_ollama


router = APIRouter(prefix="/api/providers", tags=["providers"])


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@router.post("/ollama/probe")
def probe_local_provider():
    source = dict(os.environ)
    source["NOC_WEB_AI_PROVIDER"] = PROVIDER_OLLAMA
    try:
        configuration = load_provider_configuration(source)
    except ProviderConfigurationError:
        return {
            "provider": PROVIDER_OLLAMA,
            "endpointConfigured": bool(source.get("NOC_WEB_OLLAMA_BASE_URL", "").strip()),
            "model": None,
            "available": False,
            "reason": "invalid-endpoint",
            "probedAt": _iso_now(),
        }
    result = probe_ollama(
        base_url=configuration.base_url,
        model=configuration.model,
        timeout_seconds=configuration.timeout_seconds,
        connect_timeout_seconds=configuration.connect_timeout_seconds,
    )
    return {**result, "probedAt": _iso_now()}
