"""On-demand, normalized, read-only Datadog evidence retrieval."""

from __future__ import annotations

import re
from typing import Any, Iterable
from urllib.parse import urlsplit

from backend.services.datadog_provider import (
    DatadogClient,
    DatadogForbidden,
    DatadogProviderError,
    DatadogProviderTimeout,
    DatadogProviderUnavailable,
    DatadogResourceNotFound,
    DatadogResponseInvalid,
    build_datadog_client,
)
from backend.services.datadog_validation import (
    DatadogValidationError,
    bounded_list,
    bounded_mapping,
    bounded_text,
    is_datadog_host,
    optional_text,
    timestamp,
    validate_datadog_identifier,
    validate_numeric_identifier,
)


MAX_REFERENCES_PER_KIND = 10
MAX_NOTEBOOK_CELLS = 200
MAX_QUERY_DEFINITIONS = 20
MAX_MONITOR_TAGS = 100
MAX_MONITOR_THRESHOLDS = 20
MAX_MONITOR_ASSETS = 20
MAX_INCIDENT_FIELDS = 50
MAX_FIELD_LIST_VALUES = 20
MAX_INCIDENT_FIELD_LENGTH = 500
MAX_INCIDENT_NARRATIVE_FIELD_LENGTH = 10_000
MAX_NOTEBOOK_MARKDOWN_LENGTH = 100_000
MAX_EVIDENCE_STRING_DEPTH = 16
_RELATIVE_REFERENCE_PATTERN = re.compile(
    r"(?<![\w./:-])"
    r"/(?P<kind>notebook|monitors)/"
    r"(?P<id>[1-9][0-9]{0,18})"
    r"(?![\w/?#%\\])"
    r"(?!\.\S)"
)
_INCIDENT_NARRATIVE_FIELDS = frozenset(
    {
        "summary",
        "description",
        "details",
        "impact",
        "customer_impact",
        "customer_impact_scope",
        "root_cause",
        "remediation",
        "resolution",
        "postmortem",
        "notes",
        "timeline",
    }
)
SUPPORTED_NOTEBOOK_CELL_TYPES = {
    "markdown",
    "timeseries",
    "toplist",
    "heatmap",
    "distribution",
    "log_stream",
}
_QUERY_KEYS = {"q", "query", "formula", "metric", "search"}


class DatadogEvidenceFailure(RuntimeError):
    """A controlled, sanitized evidence retrieval failure."""

    _CODES = {"provider-unavailable", "timeout", "invalid-response"}

    def __init__(self, code: str) -> None:
        self.code = code if code in self._CODES else "provider-unavailable"
        super().__init__(self.code)


def _invalid(rule: str) -> DatadogValidationError:
    return DatadogValidationError(rule)


def _bounded(value: Any, *, maximum: int, rule: str, allow_empty: bool = False) -> str:
    return bounded_text(
        value,
        maximum=maximum,
        rule=rule,
        allow_empty=allow_empty,
    )


def _optional(value: Any, *, maximum: int, rule: str) -> str | None:
    return optional_text(value, maximum=maximum, rule=rule)


def _optional_timestamp(value: Any, *, rule: str) -> str | None:
    if value is None:
        return None
    text = _bounded(value, maximum=40, rule=rule)
    if timestamp(text) is None:
        raise _invalid(rule)
    return text


def _app_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def _normalize_primitive(value: Any, *, rule: str) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _bounded(value, maximum=500, rule=rule, allow_empty=True)
    if isinstance(value, list):
        if len(value) > MAX_FIELD_LIST_VALUES:
            raise _invalid(rule)
        return [_normalize_primitive(item, rule=rule) for item in value]
    raise _invalid(rule)


def _normalize_mapping(value: Any, *, maximum: int, rule: str) -> dict[str, Any]:
    mapping = bounded_mapping(value, maximum=maximum, rule=rule)
    normalized: dict[str, Any] = {}
    for key, item in mapping.items():
        normalized[_bounded(key, maximum=100, rule=rule)] = _normalize_primitive(
            item,
            rule=rule,
        )
    return normalized


def normalize_incident_detail(
    payload: Any,
    *,
    incident_id: str,
    app_base_url: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise _invalid("invalid_incident_detail")
    data = payload.get("data")
    if not isinstance(data, dict) or data.get("type") != "incidents":
        raise _invalid("invalid_incident_detail")
    actual_id = validate_datadog_identifier(
        data.get("id"),
        rule="invalid_incident_id",
    )
    if actual_id != incident_id:
        raise _invalid("incident_id_mismatch")
    attributes = data.get("attributes")
    if not isinstance(attributes, dict):
        raise _invalid("invalid_incident_detail")

    detail: dict[str, Any] = {
        "id": actual_id,
        "title": _bounded(
            attributes.get("title"),
            maximum=200,
            rule="invalid_incident_title",
        ),
        "state": _bounded(
            attributes.get("state"),
            maximum=64,
            rule="invalid_incident_state",
        ),
        "severity": _optional(
            attributes.get("severity"),
            maximum=32,
            rule="invalid_incident_severity",
        ),
        "createdAt": _optional_timestamp(
            attributes.get("created"),
            rule="invalid_incident_createdAt",
        ),
        "updatedAt": _optional_timestamp(
            attributes.get("modified"),
            rule="invalid_incident_updatedAt",
        ),
        "resolvedAt": _optional_timestamp(
            attributes.get("resolved"),
            rule="invalid_incident_resolvedAt",
        ),
        "detectedAt": _optional_timestamp(
            attributes.get("detected"),
            rule="invalid_incident_detectedAt",
        ),
        "impactScope": _optional(
            attributes.get("customer_impact_scope"),
            maximum=500,
            rule="invalid_incident_impact",
        ),
        "customerImpacted": _optional_bool(
            attributes.get("customer_impacted"),
            rule="invalid_incident_customer_impacted",
        ),
        "fields": _normalize_incident_fields(attributes.get("fields")),
        "sourceUrl": _app_url(app_base_url, f"/incidents/{actual_id}"),
        "references": [],
        "unavailableReferences": [],
    }
    return detail


def _optional_bool(value: Any, *, rule: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise _invalid(rule)
    return value


def _field_strings(
    value: Any,
    *,
    rule: str,
    maximum: int = MAX_INCIDENT_FIELD_LENGTH,
) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [_bounded(value, maximum=maximum, rule=rule, allow_empty=True)]
    if isinstance(value, list):
        if len(value) > MAX_FIELD_LIST_VALUES:
            raise _invalid(rule)
        return [
            _bounded(item, maximum=maximum, rule=rule, allow_empty=True)
            for item in value
        ]
    if isinstance(value, dict):
        for key in ("value", "values"):
            if key in value:
                return _field_strings(value[key], rule=rule, maximum=maximum)
    raise _invalid(rule)


def _incident_field_length(name: str) -> int:
    if name.casefold() in _INCIDENT_NARRATIVE_FIELDS:
        return MAX_INCIDENT_NARRATIVE_FIELD_LENGTH
    return MAX_INCIDENT_FIELD_LENGTH


def _normalize_incident_fields(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, list):
        if len(value) > MAX_INCIDENT_FIELDS:
            raise _invalid("invalid_incident_fields")
        normalized: dict[str, Any] = {}
        for item in value:
            if not isinstance(item, dict) or "name" not in item:
                raise _invalid("invalid_incident_fields")
            if "value" not in item:
                raise _invalid("invalid_incident_fields")
            name = _bounded(item["name"], maximum=100, rule="invalid_incident_fields")
            strings = _field_strings(
                item["value"],
                rule="invalid_incident_fields",
                maximum=_incident_field_length(name),
            )
            if not strings:
                continue
            normalized[name] = strings[0] if len(strings) == 1 else strings
        if len(normalized) > MAX_INCIDENT_FIELDS:
            raise _invalid("invalid_incident_fields")
        return normalized
    mapping = bounded_mapping(
        value,
        maximum=MAX_INCIDENT_FIELDS,
        rule="invalid_incident_fields",
    )
    normalized = {}
    for key, item in mapping.items():
        name = _bounded(key, maximum=100, rule="invalid_incident_fields")
        strings = _field_strings(
            item,
            rule="invalid_incident_fields",
            maximum=_incident_field_length(name),
        )
        if not strings:
            continue
        normalized[name] = strings[0] if len(strings) == 1 else strings
    return normalized


def _exact_reference_from_text(
    text: str,
    *,
    source: str,
    app_base_url: str,
) -> dict[str, Any] | None:
    if not text or len(text) > 2048:
        return None
    lowered = text.casefold()
    for prefix, kind in (("notebook:", "notebook"), ("monitor:", "monitor")):
        if lowered.startswith(prefix):
            identifier = text[len(prefix):].strip()
            try:
                identifier = validate_numeric_identifier(
                    identifier,
                    rule="invalid_reference",
                )
            except DatadogValidationError:
                return None
            return _reference(kind, identifier, source, app_base_url)
    try:
        parsed = urlsplit(text)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or not is_datadog_host(parsed.hostname)
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or parsed.query
        or parsed.fragment
    ):
        return None
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 2:
        return None
    if segments[0] == "notebook":
        kind = "notebook"
    elif segments[0] == "monitors":
        kind = "monitor"
    else:
        return None
    try:
        identifier = validate_numeric_identifier(
            segments[1],
            rule="invalid_reference",
        )
    except DatadogValidationError:
        return None
    return _reference(kind, identifier, source, app_base_url)


def _references_from_text(
    value: Any,
    *,
    source: str,
    app_base_url: str,
    maximum: int = 2048,
) -> list[dict[str, Any]]:
    if not isinstance(value, str):
        return []
    text = value.strip()
    if not text or len(text) > maximum:
        return []
    exact = _exact_reference_from_text(
        text,
        source=source,
        app_base_url=app_base_url,
    )
    if exact is not None:
        return [exact]
    references: list[dict[str, Any]] = []
    for match in _RELATIVE_REFERENCE_PATTERN.finditer(text):
        kind = "notebook" if match.group("kind") == "notebook" else "monitor"
        try:
            identifier = validate_numeric_identifier(
                match.group("id"),
                rule="invalid_reference",
            )
        except DatadogValidationError:
            continue
        references.append(_reference(kind, identifier, source, app_base_url))
    return references


def _reference(
    kind: str,
    identifier: str,
    source: str,
    app_base_url: str,
) -> dict[str, Any]:
    path = f"/notebook/{identifier}" if kind == "notebook" else f"/monitors/{identifier}"
    return {
        "kind": kind,
        "id": identifier,
        "source": source,
        "sourceUrl": _app_url(app_base_url, path),
        "status": "available",
        "error": None,
    }


def _iter_strings(value: Any, depth: int = 0) -> Iterable[str]:
    if depth > MAX_EVIDENCE_STRING_DEPTH:
        return
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _iter_strings(item, depth + 1)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item, depth + 1)


def extract_incident_references(
    payload: Any,
    *,
    app_base_url: str,
) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    if not isinstance(payload, dict):
        return references

    included = payload.get("included")
    if isinstance(included, list):
        for item in included:
            if not isinstance(item, dict):
                continue
            attributes = item.get("attributes")
            if not isinstance(attributes, dict):
                continue
            attachment = attributes.get("attachment")
            if not isinstance(attachment, dict):
                attachment = attributes
            attachment_type = attachment.get("attachment_type") or attachment.get(
                "attachmentType"
            )
            if attachment_type not in {None, "link"}:
                continue
            url = attachment.get("documentUrl") or attachment.get("document_url")
            references.extend(
                _references_from_text(
                    url,
                    source="incident_attachment",
                    app_base_url=app_base_url,
                )
            )

    data = payload.get("data")
    if isinstance(data, dict):
        attributes = data.get("attributes")
        if isinstance(attributes, dict):
            fields = attributes.get("fields")
            if isinstance(fields, dict):
                values = fields.values()
            elif isinstance(fields, list):
                values = [
                    item.get("value")
                    for item in fields
                    if isinstance(item, dict)
                ]
            else:
                values = []
            for value in values:
                for text in _iter_strings(value):
                    references.extend(
                        _references_from_text(
                            text,
                            source="incident_field",
                            app_base_url=app_base_url,
                            maximum=MAX_INCIDENT_NARRATIVE_FIELD_LENGTH,
                        )
                    )
    return _bounded_references(references)


def extract_monitor_references(
    payload: Any,
    *,
    app_base_url: str,
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    monitor = payload.get("data") if "id" not in payload else payload
    if not isinstance(monitor, dict):
        return []
    assets = monitor.get("assets")
    if not isinstance(assets, list):
        return []
    references: list[dict[str, Any]] = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        resource_type = asset.get("resource_type") or asset.get("resourceType")
        if resource_type != "notebook":
            continue
        value = (
            asset.get("resource_key")
            or asset.get("resourceKey")
            or asset.get("url")
        )
        if isinstance(value, int) and not isinstance(value, bool):
            value = str(value)
        if isinstance(value, str) and value.strip().isdigit():
            references.append(
                _reference(
                    "notebook",
                    validate_numeric_identifier(
                        value.strip(),
                        rule="invalid_reference",
                    ),
                    "monitor_asset",
                    app_base_url,
                )
            )
            continue
        references.extend(
            _references_from_text(
                value,
                source="monitor_asset",
                app_base_url=app_base_url,
            )
        )
    return _bounded_references(references)


def _bounded_references(references: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    counts = {"notebook": 0, "monitor": 0}
    for reference in references:
        key = (reference["kind"], reference["id"])
        if key in seen:
            continue
        seen.add(key)
        counts[reference["kind"]] += 1
        if counts[reference["kind"]] > MAX_REFERENCES_PER_KIND:
            raise _invalid("too_many_references")
        unique.append(reference)
    return unique


def _notebook_reference_values(notebook: dict[str, Any]) -> Iterable[Any]:
    cells = notebook.get("cells")
    if isinstance(cells, list):
        yield from cells
        return
    data = notebook.get("data")
    if not isinstance(data, dict):
        return
    attributes = data.get("attributes")
    if not isinstance(attributes, dict):
        return
    raw_cells = attributes.get("cells")
    if not isinstance(raw_cells, list):
        return
    for cell in raw_cells:
        if not isinstance(cell, dict):
            continue
        cell_attributes = cell.get("attributes")
        if not isinstance(cell_attributes, dict):
            continue
        definition = cell_attributes.get("definition")
        if not isinstance(definition, dict):
            continue
        if definition.get("type") not in SUPPORTED_NOTEBOOK_CELL_TYPES:
            continue
        yield definition


def extract_notebook_references(
    notebook: Any,
    *,
    app_base_url: str,
) -> list[dict[str, Any]]:
    if not isinstance(notebook, dict):
        return []
    references: list[dict[str, Any]] = []
    for value in _notebook_reference_values(notebook):
        for text in _iter_strings(value):
            for reference in _references_from_text(
                text,
                source="notebook",
                app_base_url=app_base_url,
                maximum=MAX_NOTEBOOK_MARKDOWN_LENGTH,
            ):
                if reference["kind"] == "monitor":
                    references.append(reference)
    return _bounded_references(references)


def _normalize_time_range(definition: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("time", "timeframe", "time_range", "timeRange"):
        value = definition.get(key)
        if value is None:
            continue
        if not isinstance(value, dict):
            raise _invalid("invalid_notebook_time_range")
        return _normalize_mapping(
            value,
            maximum=10,
            rule="invalid_notebook_time_range",
        )
    return None


def _extract_queries(definition: dict[str, Any]) -> list[str]:
    queries: list[str] = []

    def walk(value: Any, depth: int) -> None:
        if depth > 6:
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if key in _QUERY_KEYS and isinstance(item, str):
                    text = _bounded(
                        item,
                        maximum=2000,
                        rule="invalid_notebook_query",
                        allow_empty=True,
                    )
                    if text and text not in queries:
                        if len(queries) >= MAX_QUERY_DEFINITIONS:
                            raise _invalid("invalid_notebook_query")
                        queries.append(text)
                elif isinstance(item, (dict, list)):
                    walk(item, depth + 1)
        elif isinstance(value, list):
            for item in value:
                walk(item, depth + 1)

    walk(definition, 0)
    return queries


def normalize_notebook(
    payload: Any,
    *,
    notebook_id: str,
    app_base_url: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise _invalid("invalid_notebook")
    data = payload.get("data")
    if not isinstance(data, dict) or data.get("type") != "notebooks":
        raise _invalid("invalid_notebook")
    actual_id = validate_numeric_identifier(data.get("id"), rule="invalid_notebook_id")
    if actual_id != notebook_id:
        raise _invalid("notebook_id_mismatch")
    attributes = data.get("attributes")
    if not isinstance(attributes, dict):
        raise _invalid("invalid_notebook")
    raw_cells = attributes.get("cells")
    if not isinstance(raw_cells, list) or len(raw_cells) > MAX_NOTEBOOK_CELLS:
        raise _invalid("invalid_notebook_cells")

    cells: list[dict[str, Any]] = []
    omitted: dict[str, int] = {}
    for index, cell in enumerate(raw_cells):
        if not isinstance(cell, dict):
            raise _invalid("invalid_notebook_cell")
        cell_attributes = cell.get("attributes")
        if not isinstance(cell_attributes, dict):
            raise _invalid("invalid_notebook_cell")
        definition = cell_attributes.get("definition")
        if not isinstance(definition, dict):
            raise _invalid("invalid_notebook_cell")
        cell_type = definition.get("type")
        if not isinstance(cell_type, str) or not cell_type.strip():
            raise _invalid("invalid_notebook_cell_type")
        cell_type = _bounded(
            cell_type,
            maximum=64,
            rule="invalid_notebook_cell_type",
        )
        if cell_type not in SUPPORTED_NOTEBOOK_CELL_TYPES:
            omitted[cell_type] = omitted.get(cell_type, 0) + 1
            continue
        if cell_type == "markdown":
            cells.append({
                "index": index,
                "type": "markdown",
                "markdown": _bounded(
                    definition.get("text"),
                    maximum=MAX_NOTEBOOK_MARKDOWN_LENGTH,
                    rule="invalid_notebook_markdown",
                    allow_empty=True,
                ),
            })
            continue
        cells.append({
            "index": index,
            "type": cell_type,
            "title": _optional(
                definition.get("title"),
                maximum=200,
                rule="invalid_notebook_cell_title",
            ),
            "description": _optional(
                definition.get("description"),
                maximum=500,
                rule="invalid_notebook_cell_description",
            ),
            "timeRange": _normalize_time_range(definition),
            "queries": _extract_queries(definition),
        })

    if not cells:
        raise _invalid("notebook_without_supported_cells")

    metadata: dict[str, Any] = {}
    for key in ("created", "modified"):
        value = attributes.get(key)
        if value is not None:
            metadata[key] = _optional_timestamp(
                value,
                rule=f"invalid_notebook_{key}",
            )
    status = attributes.get("status")
    if status is not None:
        metadata["status"] = _bounded(
            status,
            maximum=64,
            rule="invalid_notebook_status",
            allow_empty=True,
        )

    return {
        "id": actual_id,
        "title": _optional(
            attributes.get("name") or attributes.get("title"),
            maximum=200,
            rule="invalid_notebook_title",
        ),
        "sourceUrl": _app_url(app_base_url, f"/notebook/{actual_id}"),
        "cells": cells,
        "omittedCellTypes": omitted,
        "metadata": metadata,
    }


def normalize_monitor(
    payload: Any,
    *,
    monitor_id: str,
    app_base_url: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise _invalid("invalid_monitor")
    monitor = payload.get("data") if "id" not in payload else payload
    if not isinstance(monitor, dict):
        raise _invalid("invalid_monitor")
    actual_id = validate_numeric_identifier(monitor.get("id"), rule="invalid_monitor_id")
    if actual_id != monitor_id:
        raise _invalid("monitor_id_mismatch")

    options = monitor.get("options")
    if options is None:
        options = {}
    if not isinstance(options, dict):
        raise _invalid("invalid_monitor_thresholds")
    thresholds = options.get("thresholds")
    if thresholds is None:
        thresholds = {}
    tags = monitor.get("tags")
    if tags is None:
        tags = []
    assets = monitor.get("assets")
    if assets is None:
        assets = []

    return {
        "id": actual_id,
        "name": _bounded(
            monitor.get("name"),
            maximum=200,
            rule="invalid_monitor_name",
        ),
        "type": _bounded(
            monitor.get("type"),
            maximum=64,
            rule="invalid_monitor_type",
        ),
        "query": _bounded(
            monitor.get("query"),
            maximum=2000,
            rule="invalid_monitor_query",
            allow_empty=True,
        ),
        "thresholds": _normalize_mapping(
            thresholds,
            maximum=MAX_MONITOR_THRESHOLDS,
            rule="invalid_monitor_thresholds",
        ),
        "tags": [
            _bounded(tag, maximum=200, rule="invalid_monitor_tags")
            for tag in bounded_list(
                tags,
                maximum=MAX_MONITOR_TAGS,
                rule="invalid_monitor_tags",
            )
        ],
        "state": _optional(
            monitor.get("overall_state") or monitor.get("state"),
            maximum=64,
            rule="invalid_monitor_state",
        ),
        "message": _optional(
            monitor.get("message"),
            maximum=2000,
            rule="invalid_monitor_message",
        ),
        "sourceUrl": _app_url(app_base_url, f"/monitors/{actual_id}"),
        "assets": _normalize_monitor_assets(assets),
        "createdAt": _optional_timestamp(
            monitor.get("created"),
            rule="invalid_monitor_createdAt",
        ),
        "modifiedAt": _optional_timestamp(
            monitor.get("modified"),
            rule="invalid_monitor_modifiedAt",
        ),
    }


def _normalize_monitor_assets(value: Any) -> list[dict[str, Any]]:
    assets = bounded_list(
        value,
        maximum=MAX_MONITOR_ASSETS,
        rule="invalid_monitor_assets",
    )
    normalized = []
    for asset in assets:
        if not isinstance(asset, dict):
            raise _invalid("invalid_monitor_assets")
        item: dict[str, Any] = {}
        for source_names, target, maximum in (
            (("resource_type", "resourceType"), "resourceType", 64),
            (("resource_key", "resourceKey"), "resourceKey", 128),
            (("url", "url"), "url", 2048),
            (("name", "name"), "name", 200),
        ):
            raw = next(
                (asset[name] for name in source_names if asset.get(name) is not None),
                None,
            )
            if raw is not None:
                item[target] = _bounded(
                    raw,
                    maximum=maximum,
                    rule="invalid_monitor_assets",
                    allow_empty=True,
                )
        normalized.append(item)
    return normalized


def _reference_error(error: BaseException) -> str:
    if isinstance(error, DatadogResourceNotFound):
        return "not-found"
    if isinstance(error, DatadogForbidden):
        return "forbidden"
    if isinstance(error, DatadogProviderTimeout):
        return "timeout"
    if isinstance(error, DatadogResponseInvalid):
        return "invalid-response"
    if isinstance(error, DatadogValidationError):
        return "invalid-response"
    if isinstance(error, DatadogProviderError):
        return "provider-unavailable"
    return "provider-unavailable"


def _retrieval_error(error: BaseException) -> DatadogEvidenceFailure:
    if isinstance(error, DatadogProviderTimeout):
        return DatadogEvidenceFailure("timeout")
    if isinstance(error, DatadogResponseInvalid):
        return DatadogEvidenceFailure("invalid-response")
    if isinstance(error, DatadogValidationError):
        return DatadogEvidenceFailure("invalid-response")
    if isinstance(error, DatadogProviderUnavailable):
        return DatadogEvidenceFailure("provider-unavailable")
    if isinstance(error, DatadogProviderError):
        return DatadogEvidenceFailure("provider-unavailable")
    return DatadogEvidenceFailure("provider-unavailable")


def _reference_entry(reference: dict[str, Any]) -> dict[str, Any]:
    return {
        "reference": reference,
        "status": reference["status"],
        "error": reference["error"],
        "evidence": None,
    }


def get_notebook_evidence(
    notebook_id: str | int,
    *,
    client: DatadogClient | None = None,
) -> dict[str, Any]:
    effective = client or build_datadog_client()
    try:
        identifier = validate_numeric_identifier(
            notebook_id,
            rule="invalid_notebook_id",
        )
        payload = effective.get_notebook(identifier)
        return normalize_notebook(
            payload,
            notebook_id=identifier,
            app_base_url=effective.app_base_url,
        )
    except (DatadogProviderError, DatadogValidationError) as error:
        raise _retrieval_error(error) from None


def get_monitor_evidence(
    monitor_id: str | int,
    *,
    client: DatadogClient | None = None,
) -> dict[str, Any]:
    effective = client or build_datadog_client()
    try:
        identifier = validate_numeric_identifier(
            monitor_id,
            rule="invalid_monitor_id",
        )
        payload = effective.get_monitor(identifier)
        return normalize_monitor(
            payload,
            monitor_id=identifier,
            app_base_url=effective.app_base_url,
        )
    except (DatadogProviderError, DatadogValidationError) as error:
        raise _retrieval_error(error) from None


def get_incident_evidence(
    incident_id: str,
    *,
    client: DatadogClient | None = None,
) -> dict[str, Any]:
    effective = client or build_datadog_client()
    try:
        identifier = validate_datadog_identifier(
            incident_id,
            rule="invalid_incident_id",
        )
        detail_payload = effective.get_incident(identifier)
        detail = normalize_incident_detail(
            detail_payload,
            incident_id=identifier,
            app_base_url=effective.app_base_url,
        )
    except (DatadogProviderError, DatadogValidationError) as error:
        raise _retrieval_error(error) from None

    try:
        references = extract_incident_references(
            detail_payload,
            app_base_url=effective.app_base_url,
        )
        monitor_references = [
            reference for reference in references if reference["kind"] == "monitor"
        ]
        notebook_references = [
            reference for reference in references if reference["kind"] == "notebook"
        ]

        monitor_entries = []
        for reference in monitor_references:
            try:
                monitor_payload = effective.get_monitor(reference["id"])
                evidence = normalize_monitor(
                    monitor_payload,
                    monitor_id=reference["id"],
                    app_base_url=effective.app_base_url,
                )
                reference["status"] = "available"
                reference["error"] = None
                monitor_entries.append({
                    "reference": reference,
                    "status": "available",
                    "error": None,
                    "evidence": evidence,
                })
                for asset_reference in extract_monitor_references(
                    monitor_payload,
                    app_base_url=effective.app_base_url,
                ):
                    if not any(
                        item["kind"] == asset_reference["kind"]
                        and item["id"] == asset_reference["id"]
                        for item in notebook_references
                    ):
                        notebook_references.append(asset_reference)
            except (DatadogProviderError, DatadogValidationError) as error:
                code = _reference_error(error)
                reference["status"] = "unavailable"
                reference["error"] = code
                monitor_entries.append(_reference_entry(reference))

        notebook_references = _bounded_references(notebook_references)
        notebook_entries = []
        notebook_monitor_references: list[dict[str, Any]] = []
        for reference in notebook_references:
            try:
                notebook_payload = effective.get_notebook(reference["id"])
                evidence = normalize_notebook(
                    notebook_payload,
                    notebook_id=reference["id"],
                    app_base_url=effective.app_base_url,
                )
            except (DatadogProviderError, DatadogValidationError) as error:
                code = _reference_error(error)
                reference["status"] = "unavailable"
                reference["error"] = code
                notebook_entries.append(_reference_entry(reference))
                continue
            reference["status"] = "available"
            reference["error"] = None
            notebook_entries.append({
                "reference": reference,
                "status": "available",
                "error": None,
                "evidence": evidence,
            })
            notebook_monitor_references.extend(
                extract_notebook_references(
                    notebook_payload,
                    app_base_url=effective.app_base_url,
                )
            )

        combined_monitor_references = _bounded_references(
            [*monitor_references, *notebook_monitor_references]
        )
        retrieved_monitor_ids = {
            reference["id"] for reference in monitor_references
        }
        for reference in combined_monitor_references:
            if reference["id"] in retrieved_monitor_ids:
                continue
            try:
                monitor_payload = effective.get_monitor(reference["id"])
                evidence = normalize_monitor(
                    monitor_payload,
                    monitor_id=reference["id"],
                    app_base_url=effective.app_base_url,
                )
                reference["status"] = "available"
                reference["error"] = None
                monitor_entries.append({
                    "reference": reference,
                    "status": "available",
                    "error": None,
                    "evidence": evidence,
                })
            except (DatadogProviderError, DatadogValidationError) as error:
                code = _reference_error(error)
                reference["status"] = "unavailable"
                reference["error"] = code
                monitor_entries.append(_reference_entry(reference))
        monitor_references = combined_monitor_references
    except DatadogValidationError as error:
        raise DatadogEvidenceFailure("invalid-response") from None

    all_references = [
        *monitor_references,
        *notebook_references,
    ]
    detail["references"] = all_references
    detail["unavailableReferences"] = [
        reference
        for reference in all_references
        if reference["status"] == "unavailable"
    ]
    complete = not detail["unavailableReferences"]
    return {
        "incident": detail,
        "notebooks": notebook_entries,
        "monitors": monitor_entries,
        "relationships": {
            "incidentId": identifier,
            "notebookIds": [reference["id"] for reference in notebook_references],
            "monitorIds": [reference["id"] for reference in monitor_references],
            "sources": {
                f"{reference['kind']}:{reference['id']}": reference["source"]
                for reference in all_references
            },
        },
        "status": "complete" if complete else "partial",
        "error": None,
    }
