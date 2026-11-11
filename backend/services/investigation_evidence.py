from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable

from backend.services.datadog_evidence import (
    DatadogEvidenceFailure,
    get_incident_evidence,
)


MAX_PACKAGE_BYTES = 256 * 1024
MAX_NOTEBOOKS = 10
MAX_MONITORS = 10
MAX_NOTEBOOK_MARKDOWN_BYTES = 16 * 1024
MAX_TOTAL_NOTEBOOK_MARKDOWN_BYTES = 64 * 1024
MAX_MONITOR_QUERY_BYTES = 2 * 1024
MAX_MONITOR_MESSAGE_BYTES = 2 * 1024
CURRENT_INCIDENT_STATES = frozenset({"ACTIVE", "STABLE"})

_SENSITIVE_KEY_PATTERN = re.compile(
    r"^(authorization|api[_-]?key|apikey|access[_-]?token|token|secret|"
    r"password|credential|credentials)$",
    re.IGNORECASE,
)
_SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)(bearer\s+[a-z0-9._~+/=-]{8,}|"
    r"deepseek_api_key|noc_web_deepseek_api_key|"
    r"dd_access_token|noc_web_datadog_access_token|"
    r"authorization\s*:)"
)


class InvestigationEvidenceError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _digest(package: dict[str, Any]) -> str:
    body = {
        key: value
        for key, value in package.items()
        if key not in {"digest", "sizeBytes"}
    }
    return "sha256:" + hashlib.sha256(_canonical_bytes(body)).hexdigest()


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _stable_id(kind: str, identifier: Any) -> str:
    return f"{kind}:{identifier}"


def _scan_credentials(value: Any, path: str = "package") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if _SENSITIVE_KEY_PATTERN.fullmatch(str(key)):
                raise InvestigationEvidenceError(
                    "evidence-credential-detected",
                    "The evidence package contained credential-like content.",
                )
            _scan_credentials(item, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _scan_credentials(item, f"{path}[{index}]")
        return
    if isinstance(value, str) and _SENSITIVE_VALUE_PATTERN.search(value):
        raise InvestigationEvidenceError(
            "evidence-credential-detected",
            "The evidence package contained credential-like content.",
        )


def _incident_item(detail: dict[str, Any]) -> dict[str, Any]:
    incident_id = _text(detail.get("id"))
    return {
        "id": _stable_id("incident", incident_id),
        "kind": "incident",
        "sourceUrl": detail.get("sourceUrl"),
        "source": "incident_detail",
        "availability": "available",
        "title": detail.get("title"),
        "state": detail.get("state"),
        "severity": detail.get("severity"),
        "createdAt": detail.get("createdAt"),
        "updatedAt": detail.get("updatedAt"),
        "resolvedAt": detail.get("resolvedAt"),
        "detectedAt": detail.get("detectedAt"),
        "impactScope": detail.get("impactScope"),
        "customerImpacted": detail.get("customerImpacted"),
        "fields": detail.get("fields"),
    }


def _notebook_item(
    reference: dict[str, Any],
    evidence: dict[str, Any],
    *,
    markdown_budget: int,
) -> tuple[dict[str, Any], int]:
    notebook_id = _text(evidence.get("id"))
    markdown_parts: list[str] = []
    queries: list[str] = []
    time_ranges: list[dict[str, Any]] = []
    for cell in evidence.get("cells", []):
        if not isinstance(cell, dict):
            continue
        if cell.get("type") == "markdown":
            markdown = _text(cell.get("markdown")).strip()
            if markdown:
                markdown_parts.append(markdown)
            continue
        queries.extend(
            query for query in cell.get("queries", [])
            if isinstance(query, str)
        )
        time_range = cell.get("timeRange")
        if isinstance(time_range, dict):
            time_ranges.append(time_range)
    markdown = "\n\n".join(markdown_parts)
    markdown_bytes = len(markdown.encode("utf-8"))
    if markdown_bytes > MAX_NOTEBOOK_MARKDOWN_BYTES:
        raise InvestigationEvidenceError(
            "evidence-too-large",
            "The evidence package exceeded notebook bounds.",
        )
    if markdown_bytes > markdown_budget:
        raise InvestigationEvidenceError(
            "evidence-too-large",
            "The evidence package exceeded notebook bounds.",
        )
    item = {
        "id": _stable_id("notebook", notebook_id),
        "kind": "notebook",
        "sourceUrl": evidence.get("sourceUrl"),
        "source": reference.get("source") or "monitor_asset",
        "availability": "available",
        "title": evidence.get("title"),
        "markdown": markdown,
        "queries": queries,
        "timeRanges": time_ranges,
        "metadata": evidence.get("metadata") if isinstance(
            evidence.get("metadata"), dict
        ) else {},
    }
    return item, markdown_bytes


def _monitor_item(
    reference: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    monitor_id = _text(evidence.get("id"))
    query = _text(evidence.get("query"))
    message = _text(evidence.get("message"))
    if len(query.encode("utf-8")) > MAX_MONITOR_QUERY_BYTES:
        raise InvestigationEvidenceError(
            "evidence-too-large",
            "The evidence package exceeded monitor bounds.",
        )
    if len(message.encode("utf-8")) > MAX_MONITOR_MESSAGE_BYTES:
        raise InvestigationEvidenceError(
            "evidence-too-large",
            "The evidence package exceeded monitor bounds.",
        )
    return {
        "id": _stable_id("monitor", monitor_id),
        "kind": "monitor",
        "sourceUrl": evidence.get("sourceUrl"),
        "source": reference.get("source") or "incident_field",
        "availability": "available",
        "name": evidence.get("name"),
        "type": evidence.get("type"),
        "query": query,
        "thresholds": evidence.get("thresholds") if isinstance(
            evidence.get("thresholds"), dict
        ) else {},
        "tags": evidence.get("tags") if isinstance(
            evidence.get("tags"), list
        ) else [],
        "state": evidence.get("state"),
        "message": message,
    }


def _reference_record(
    *,
    kind: str,
    identifier: str,
    reference: dict[str, Any],
    availability: str,
    error: str | None = None,
) -> dict[str, Any]:
    record = {
        "id": _stable_id(kind, identifier),
        "kind": kind,
        "sourceUrl": reference.get("sourceUrl"),
        "source": reference.get("source"),
        "availability": availability,
    }
    if error is not None:
        record["error"] = error
    return record


def build_evidence_package(
    incident_id: str,
    *,
    evidence_loader: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    loader = evidence_loader or get_incident_evidence
    try:
        bundle = loader(incident_id)
    except DatadogEvidenceFailure as error:
        if error.code == "timeout":
            raise InvestigationEvidenceError(
                "evidence-timeout",
                "Datadog evidence retrieval timed out.",
            ) from None
        if error.code == "invalid-response":
            raise InvestigationEvidenceError(
                "evidence-invalid",
                "Datadog evidence is invalid.",
            ) from None
        raise InvestigationEvidenceError(
            "evidence-unavailable",
            "Datadog evidence is unavailable.",
        ) from None
    except (TypeError, ValueError):
        raise InvestigationEvidenceError(
            "evidence-invalid",
            "Datadog evidence is invalid.",
        ) from None
    if not isinstance(bundle, dict):
        raise InvestigationEvidenceError(
            "evidence-invalid",
            "Datadog evidence is invalid.",
        )
    detail = bundle.get("incident")
    if not isinstance(detail, dict):
        raise InvestigationEvidenceError(
            "evidence-invalid",
            "Datadog incident evidence is invalid.",
        )
    state = _text(detail.get("state")).upper()
    if state not in CURRENT_INCIDENT_STATES:
        raise InvestigationEvidenceError(
            "incident-not-current",
            "Only current ACTIVE or STABLE Datadog incidents can generate investigations.",
        )
    incident_id_value = _text(detail.get("id"))
    if not incident_id_value or incident_id_value != incident_id:
        raise InvestigationEvidenceError(
            "evidence-invalid",
            "Datadog incident evidence is invalid.",
        )

    references: dict[str, dict[str, Any]] = {}
    incident = _incident_item(detail)
    references[incident["id"]] = _reference_record(
        kind="incident",
        identifier=incident_id_value,
        reference=incident,
        availability="available",
    )

    notebooks: list[dict[str, Any]] = []
    monitors: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    markdown_budget = MAX_TOTAL_NOTEBOOK_MARKDOWN_BYTES

    notebook_entries = bundle.get("notebooks")
    if not isinstance(notebook_entries, list):
        raise InvestigationEvidenceError(
            "evidence-invalid",
            "Datadog notebook evidence is invalid.",
        )
    for entry in notebook_entries:
        if not isinstance(entry, dict):
            continue
        reference = entry.get("reference")
        if not isinstance(reference, dict):
            continue
        identifier = _text(reference.get("id"))
        if not identifier:
            continue
        evidence = entry.get("evidence")
        if entry.get("status") == "available" and isinstance(evidence, dict):
            item, markdown_bytes = _notebook_item(
                reference,
                evidence,
                markdown_budget=markdown_budget,
            )
            markdown_budget -= markdown_bytes
            notebooks.append(item)
            references[item["id"]] = _reference_record(
                kind="notebook",
                identifier=identifier,
                reference=reference,
                availability="available",
            )
        else:
            record = _reference_record(
                kind="notebook",
                identifier=identifier,
                reference=reference,
                availability="unavailable",
                error=_text(entry.get("error")) or "invalid-response",
            )
            references[record["id"]] = record
            unavailable.append(record)

    monitor_entries = bundle.get("monitors")
    if not isinstance(monitor_entries, list):
        raise InvestigationEvidenceError(
            "evidence-invalid",
            "Datadog monitor evidence is invalid.",
        )
    for entry in monitor_entries:
        if not isinstance(entry, dict):
            continue
        reference = entry.get("reference")
        if not isinstance(reference, dict):
            continue
        identifier = _text(reference.get("id"))
        if not identifier:
            continue
        evidence = entry.get("evidence")
        if entry.get("status") == "available" and isinstance(evidence, dict):
            item = _monitor_item(reference, evidence)
            monitors.append(item)
            references[item["id"]] = _reference_record(
                kind="monitor",
                identifier=identifier,
                reference=reference,
                availability="available",
            )
        else:
            record = _reference_record(
                kind="monitor",
                identifier=identifier,
                reference=reference,
                availability="unavailable",
                error=_text(entry.get("error")) or "invalid-response",
            )
            references[record["id"]] = record
            unavailable.append(record)

    if len(notebooks) > MAX_NOTEBOOKS or len(monitors) > MAX_MONITORS:
        raise InvestigationEvidenceError(
            "evidence-too-large",
            "The evidence package exceeded reference bounds.",
        )

    availability = (
        "partial"
        if unavailable or bundle.get("status") == "partial"
        else "complete"
    )
    package: dict[str, Any] = {
        "packageVersion": "1",
        "incident": incident,
        "notebooks": notebooks,
        "monitors": monitors,
        "references": references,
        "unavailable": unavailable,
        "availability": availability,
        "relationships": bundle.get("relationships")
        if isinstance(bundle.get("relationships"), dict)
        else {},
    }
    _scan_credentials(package)
    size_bytes = len(_canonical_bytes(package))
    if size_bytes > MAX_PACKAGE_BYTES:
        raise InvestigationEvidenceError(
            "evidence-too-large",
            "The evidence package exceeded its size bound.",
        )
    package["sizeBytes"] = size_bytes
    package["digest"] = _digest(package)
    if len(_canonical_bytes(package)) > MAX_PACKAGE_BYTES:
        raise InvestigationEvidenceError(
            "evidence-too-large",
            "The evidence package exceeded its size bound.",
        )
    return package


def package_digest(package: dict[str, Any]) -> str:
    return _digest(package)


def evidence_summary(package: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": package.get("availability"),
        "incidentId": package.get("incident", {}).get("id"),
        "notebookCount": len(package.get("notebooks", [])),
        "monitorCount": len(package.get("monitors", [])),
        "unavailable": [
            {
                "id": item.get("id"),
                "kind": item.get("kind"),
                "error": item.get("error"),
            }
            for item in package.get("unavailable", [])
            if isinstance(item, dict)
        ],
        "references": {
            identifier: {
                "kind": item.get("kind"),
                "sourceUrl": item.get("sourceUrl"),
                "source": item.get("source"),
                "availability": item.get("availability"),
            }
            for identifier, item in package.get("references", {}).items()
            if isinstance(item, dict)
        },
    }
