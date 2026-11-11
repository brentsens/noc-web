from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


FORMAT_VERSION = "2"
PROVENANCE_FILENAME = "handover-provenance.json"


def build_handover_provenance(
    package: dict[str, Any],
    *,
    provider_identifier: str,
    model: str | None,
    advisory_citations: list[str] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    references = package.get("references")
    if not isinstance(references, dict):
        references = {}
    sanitized_references = {}
    for identifier, item in references.items():
        if not isinstance(identifier, str) or not isinstance(item, dict):
            continue
        sanitized_references[identifier[:200]] = {
            "kind": item.get("kind") if isinstance(item.get("kind"), str) else None,
            "source": item.get("source") if isinstance(item.get("source"), str) else None,
            "availability": (
                item.get("availability")
                if isinstance(item.get("availability"), str)
                else "unavailable"
            ),
            "authoritative": bool(item.get("authoritative", False)),
            **(
                {"freshness": item.get("freshness")[:32]}
                if isinstance(item.get("freshness"), str)
                else {}
            ),
            **(
                {"sourceUrl": item.get("sourceUrl")[:2048]}
                if isinstance(item.get("sourceUrl"), str)
                else {}
            ),
        }
    unavailable = []
    for item in package.get("unavailable", []):
        if not isinstance(item, dict):
            continue
        unavailable.append({
            "id": item.get("id")[:200] if isinstance(item.get("id"), str) else None,
            "kind": item.get("kind")[:64] if isinstance(item.get("kind"), str) else None,
            "error": item.get("error")[:128] if isinstance(item.get("error"), str) else None,
        })
    return {
        "formatVersion": FORMAT_VERSION,
        "shiftDate": package.get("shiftDate"),
        "evidenceDigest": package.get("digest"),
        "availability": package.get("availability"),
        "provider": {
            "configuredProvider": provider_identifier,
            "model": model,
        },
        "advisoryStatus": "completed",
        "advisoryMode": "internal-validation-only",
        "advisoryCitations": sorted({
            citation[:200]
            for citation in (advisory_citations or [])
            if isinstance(citation, str)
        })[:500],
        "references": sanitized_references,
        "unavailable": unavailable,
        "generatedAt": timestamp.isoformat().replace("+00:00", "Z"),
    }


def read_handover_provenance(path) -> dict[str, Any] | None:
    try:
        if not path.is_file() or path.stat().st_size > 1_000_000:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None
