# Contract: Datadog Evidence Service

**Feature**: `015-datadog-rest-provider`

This is an internal backend contract for on-demand Datadog evidence. It adds no
HTTP route and writes no persistent evidence cache.

## Functions

```python
get_incident_evidence(incident_id: str, *, client: DatadogClient | None = None) -> dict
get_notebook_evidence(notebook_id: str, *, client: DatadogClient | None = None) -> dict
get_monitor_evidence(monitor_id: str, *, client: DatadogClient | None = None) -> dict
```

All functions use the configured Datadog provider when `client` is omitted. They
raise a controlled `DatadogEvidenceFailure(code)` for incident-level or direct
retrieval failure. Reference-level failures are returned as unavailable entries
and do not invalidate usable incident evidence.

## Incident evidence bundle

```json
{
  "incident": {
    "id": "00000000-0000-0000-1234-000000000000",
    "title": "Checkout latency",
    "state": "ACTIVE",
    "severity": "SEV-2",
    "createdAt": "2026-11-10T10:00:00Z",
    "updatedAt": "2026-11-10T10:12:00Z",
    "resolvedAt": null,
    "detectedAt": "2026-11-10T09:58:00Z",
    "impactScope": "Elevated checkout errors in us-east-1.",
    "customerImpacted": true,
    "fields": {
      "service": "checkout",
      "runbook": "https://app.datadoghq.com/notebook/12345/checkout-runbook"
    },
    "sourceUrl": "https://app.datadoghq.com/incidents/00000000-0000-0000-1234-000000000000",
    "references": [
      {
        "kind": "notebook",
        "id": "12345",
        "source": "incident_field",
        "sourceUrl": "https://app.datadoghq.com/notebook/12345/checkout-runbook",
        "status": "available",
        "error": null
      }
    ],
    "unavailableReferences": []
  },
  "notebooks": [
    {
      "reference": {
        "kind": "notebook",
        "id": "12345",
        "source": "incident_field",
        "sourceUrl": "https://app.datadoghq.com/notebook/12345/checkout-runbook",
        "status": "available",
        "error": null
      },
      "status": "available",
      "evidence": {
        "id": "12345",
        "title": "Checkout runbook",
        "sourceUrl": "https://app.datadoghq.com/notebook/12345/checkout-runbook",
        "cells": [],
        "omittedCellTypes": {},
        "metadata": {}
      }
    }
  ],
  "monitors": [],
  "relationships": {
    "incidentId": "00000000-0000-0000-1234-000000000000",
    "notebookIds": ["12345"],
    "monitorIds": [],
    "sources": {
      "notebook:12345": "incident_field"
    }
  },
  "status": "complete",
  "error": null
}
```

`status` is `complete` when every discovered reference resolved and `partial`
when at least one reference is unavailable. `error` is null for a usable bundle.

## Reference discovery

Only structured values are inspected:

| Source | Accepted shape | Result |
|--------|----------------|--------|
| Incident link attachment | `included[]` attachment with `attachment_type: link` and a Datadog notebook/monitor `documentUrl` | Reference |
| Incident user-defined field | Entire value is a supported Datadog notebook/monitor URL or `notebook:<id>` / `monitor:<id>`, or a bounded narrative value containing exact Datadog-relative `/notebook/<id>` or `/monitors/<id>` paths | Reference |
| Monitor asset | `assets[]` with `resource_type: notebook`, using `resource_key` or `url` | Notebook reference |
| Notebook cell | Normalized Markdown text or a supported cell definition containing exact Datadog-relative `/monitors/<id>` paths | Monitor reference with `source: notebook` |

Rules:

1. Free-text is only scanned for the exact trusted relative paths
   `/notebook/<numeric-id>` and `/monitors/<numeric-id>` inside bounded incident
   field values, and for exact `/monitors/<numeric-id>` paths inside normalized
   Markdown and supported notebook cell definitions; arbitrary relative URLs,
   other hosts, and other substrings are never accepted.
2. Numeric IDs are validated with the shared Datadog identifier validator, and
   discovered references use the configured Datadog app base for `sourceUrl`.
3. Do not list all notebooks or monitors.
4. Deduplicate by `kind` + `id` across incident, monitor-asset, and notebook
   sources.
5. Discovery depth is bounded to the Feature 015 evidence graph: incident to
   notebooks/monitors, monitor assets to notebooks, and notebook cells to
   monitors. References discovered from notebook cells are not followed
   recursively.
6. More than 10 references of one kind fails the request as `invalid-response`.
7. A reference that is not found, forbidden, malformed, or times out is reported
   with `status: unavailable` and a controlled error code.

## Notebook normalization

- Require `data.id` matching the request and `data.attributes.cells` as a list.
- Reject more than 200 cells or an invalid cell structure.
- Preserve provider order and 0-based indices.
- Supported types: `markdown`, `timeseries`, `toplist`, `heatmap`,
  `distribution`, `log_stream`.
- Markdown cells preserve bounded `definition.text`.
- Other supported cells expose title/description, time range, and up to 20
  query/metric/expression strings extracted from known definition fields.
- Unsupported cell types are omitted and counted in `omittedCellTypes`; no raw
  content is returned.
- Reject a notebook with no supported cells.

## Monitor normalization

- Require matching `id`, non-empty `name` and `type`, and a string `query`.
- Expose `thresholds` from `options.thresholds`, up to 20 entries.
- Expose up to 100 string `tags`.
- Preserve exact current state from `overall_state` or `state`.
- Expose bounded `message` and up to 20 `assets`.
- Construct `sourceUrl` from the configured app base.
- Reject malformed tags, thresholds, assets, timestamps, or ID mismatch.

## Failure behavior

| Failure | Result |
|---------|--------|
| Incident detail unavailable/timeout/invalid | Raise controlled failure; no bundle |
| Reference not found/forbidden | `status: unavailable` on that reference; bundle may be `partial` |
| Reference malformed/oversized | `status: unavailable` with `invalid-response`; bundle may be `partial` |
| Reference timeout | `status: unavailable` with `timeout`; bundle may be `partial` |
| More than 10 references of one kind | Raise `invalid-response` |
| Any evidence request | No cache write, no Datadog mutation, no AI call |

Responses never include the bearer token, raw Datadog payloads, request traces,
or provider error bodies.
