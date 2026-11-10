# Data Model: Direct Read-Only Datadog Evidence Provider

**Feature**: `015-datadog-rest-provider`  
**Date**: 2026-11-10

## Datadog Provider Configuration

Resolved from the process environment at application start.

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `baseUrl` | string | yes | Defaults to `https://api.datadoghq.com`; HTTPS only; Datadog API host under `datadoghq.com`, `datadoghq.eu`, or `ddog-gov.com`; no userinfo, query, fragment, or parent traversal |
| `timeoutSeconds` | integer | yes | 1–120; default 90; bounds each retrieval and the overall refresh deadline |
| `credentialPresent` | boolean | yes | True when `NOC_WEB_DATADOG_ACCESS_TOKEN` is non-empty after trimming |

**Validation rules**:
- The token value is never a field on this entity and is never serialized.
- An absent token yields `notConfigured` readiness; an invalid base URL or
  timeout with a present token yields `notReady`.
- Configuration changes require a process restart.

## Datadog Provider Readiness

A non-secret diagnostic state.

| Field | Type | Rules |
|-------|------|-------|
| `provider` | string | Fixed value `datadog-api` |
| `configuredProvider` | string or null | `datadog-api` when a token is present; null otherwise |
| `baseUrl` | string | Effective non-secret API base |
| `readiness` | enum | `ready`, `notReady`, `notConfigured` |
| `label` | string | Fixed `Datadog API` |
| `credentialPresent` | boolean | Presence only; never the value |
| `impact` | string | Fixed, non-secret operator-facing text |
| `correctiveAction` | string | Safe guidance naming settings, never values |

**State transitions**:

```text
notConfigured ──token present + valid config──────────────────────> ready
notConfigured ──token present + invalid config────────────────────> notReady
notReady ───────corrected config + restart────────────────────────> ready
ready ──────────configuration removed or invalidated + restart────> notConfigured / notReady
```

Readiness performs no Datadog request and does not assert credential validity or
reachability.

## Datadog Incident Search Record

The validated subset of one Datadog incident record used to build the local
projection.

| Field | Source | Type | Rules |
|-------|--------|------|-------|
| `id` | `data.id` | string | Required; 1–128 characters; unique per snapshot |
| `title` | `attributes.title` | string | Required; 1–200 characters |
| `state` | `attributes.state` | string | Required; case-insensitive `ACTIVE` or `STABLE` for inclusion; exact text preserved |
| `severity` | `attributes.severity` | string or null | Optional; 1–32 characters |
| `createdAt` | `attributes.created` | RFC 3339 string or null | Optional; valid timezone-aware timestamp |
| `updatedAt` | `attributes.modified` | RFC 3339 string or null | Optional; valid timezone-aware timestamp |
| `summary` | `attributes.customer_impact_scope` | string or null | Optional; 0–500 characters |
| `url` | derived | string or null | Optional; canonical Datadog app incident URL derived from the configured API host |

**Rejection rules**: duplicate IDs, more than 100 current incidents, a state
outside `ACTIVE`/`STABLE`/`RESOLVED`, malformed timestamps, or unexpected URL
hosts cause the whole refresh to fail. `RESOLVED` records are excluded from the
current-incident projection rather than making the refresh fail.

## Incident Projection

The existing frontend-compatible projection. Field names and semantics are
unchanged.

| Field | Type | Rules |
|-------|------|-------|
| `id` | string | Non-empty, ≤128 characters |
| `title` | string | Non-empty, ≤200 characters |
| `state` | string | Exact Datadog state |
| `severity` | string | Optional, ≤32 characters |
| `createdAt` | string | Optional RFC 3339 |
| `updatedAt` | string | Optional RFC 3339 |
| `summary` | string | Optional, ≤500 characters |
| `url` | string | Optional HTTPS Datadog incident URL, ≤2048 characters |

## Incident Snapshot

The existing cache contract, unchanged.

| Field | Type | Rules |
|-------|------|-------|
| `schemaVersion` | integer | Fixed `1` |
| `incidents` | array | Up to 100 incident projections |
| `lastAttemptedAt` | RFC 3339 string or null | Updated on every attempt |
| `lastSuccessfulAt` | RFC 3339 string or null | Set only on success; preserved on failure |
| `freshness` | enum | Persisted value `current`, `stale`, or `unavailable`; the API may report `refreshing` |
| `error` | enum or null | `copilot-unavailable`, `provider-unavailable`, `timeout`, `invalid-response`, `cache-unavailable`, or null |

**State transitions**:

```text
unavailable ──successful refresh──> current
current ──────failed refresh──────> stale (preserve incidents + lastSuccessfulAt)
current ──────age ≥ 60s───────────> stale
current ──────refresh in progress─> refreshing (transient API state)
stale/unavailable ──successful refresh──> current (or current with zero incidents)
```

The success with an empty incident list is authoritative. Failure never produces
an empty successful snapshot.

## Incident Detail Evidence

Normalized, on-demand, non-persistent detail for one incident.

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `id` | string | yes | Matches the requested incident ID |
| `title` | string | yes | Bounded to 200 characters |
| `state` | string | yes | Exact Datadog state |
| `severity` | string or null | no | ≤32 characters |
| `createdAt` | RFC 3339 string or null | no | Valid timestamp |
| `updatedAt` | RFC 3339 string or null | no | Valid timestamp |
| `resolvedAt` | RFC 3339 string or null | no | Valid timestamp |
| `detectedAt` | RFC 3339 string or null | no | Valid timestamp |
| `impactScope` | string or null | no | ≤500 characters |
| `customerImpacted` | boolean or null | no | Boolean only |
| `fields` | object | no | Up to 50 string keys; each value is a bounded string or list of ≤20 bounded strings |
| `sourceUrl` | string | yes | Constructed Datadog app incident URL |
| `references` | array | yes | Evidence reference entries |
| `unavailableReferences` | array | yes | Explicit reference failures |

**Validation rules**:
- `data.type` must identify an incident and the ID must match the request.
- Field names and values are bounded; unsupported value types are rejected.
- No raw payload is returned or persisted.

## Notebook Evidence

Normalized, on-demand, non-persistent notebook representation.

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `id` | string | yes | Matches the requested notebook ID |
| `title` | string or null | no | ≤200 characters |
| `sourceUrl` | string | yes | Datadog app notebook URL |
| `cells` | array | yes | 1–200 supported cell entries in provider order |
| `omittedCellTypes` | object | yes | Map of unsupported cell type → omitted count; no content |
| `metadata` | object | no | Bounded primitive metadata such as author/created/modified where available |

**Notebook cell evidence**:

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `index` | integer | yes | Provider order, 0-based |
| `type` | enum | yes | `markdown`, `timeseries`, `toplist`, `heatmap`, `distribution`, or `log_stream` |
| `markdown` | string | markdown only | Bounded Markdown text |
| `title` | string or null | no | ≤200 characters |
| `description` | string or null | no | ≤500 characters |
| `timeRange` | object or null | no | Bounded primitive time fields when supplied |
| `queries` | array of strings | no | Up to 20 bounded query/metric/expression strings |

**Rejection rules**: missing/invalid cells list, no supported cells, more than
200 cells, an ID mismatch, a cell that is not an object, or a supported cell
whose required definition is malformed. Unsupported cell types are omitted and
counted, not rejected.

## Monitor Evidence

Normalized, on-demand, non-persistent monitor representation.

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `id` | string | yes | Numeric monitor ID as a string; matches the request |
| `name` | string | yes | 1–200 characters |
| `type` | string | yes | 1–64 characters |
| `query` | string | yes | 0–2000 characters; preserved exactly |
| `thresholds` | object | no | Up to 20 entries; primitive values or bounded lists |
| `tags` | array of strings | no | Up to 100 tags, each ≤200 characters |
| `state` | string or null | no | Current `overall_state`/`state` text, exact |
| `message` | string or null | no | ≤2000 characters |
| `sourceUrl` | string | yes | Datadog app monitor URL |
| `assets` | array | no | Up to 20 bounded asset references; notebook assets become notebook references |
| `createdAt` | RFC 3339 string or null | no | Valid timestamp |
| `modifiedAt` | RFC 3339 string or null | no | Valid timestamp |

**Rejection rules**: missing/invalid ID, name, type, query, tags, thresholds, or
assets; more than 100 tags; more than 20 threshold entries; invalid timestamps;
or an ID mismatch.

## Evidence Reference

An explicit link from an incident or monitor to another evidence object.

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `kind` | enum | yes | `notebook` or `monitor` |
| `id` | string | yes | Bounded Datadog notebook/monitor identifier |
| `source` | enum | yes | `incident_attachment`, `incident_field`, `monitor_asset`, or `notebook` |
| `sourceUrl` | string or null | no | Valid Datadog URL |
| `status` | enum | yes | `available`, `unavailable`, or `rejected` |
| `error` | enum or null | no | `not-found`, `forbidden`, `invalid-response`, `timeout`, or `provider-unavailable` |

**Discovery rules**:
- Incident link attachments with a supported Datadog notebook/monitor URL.
- Incident user-defined fields whose entire value is a supported Datadog
  notebook/monitor URL or `kind:id` value.
- Monitor assets with `resource_type: notebook`, using `resource_key` or `url`.
- Notebook Markdown and supported cell definitions containing exact Datadog
  `/monitors/<numeric-id>` paths; these monitor references use `source: notebook`.
- Deduplicate by `kind` + `id` across incident, monitor-asset, and notebook
  sources; fail the evidence request if more than 10 references of one kind are
  discovered.
- Traversal is bounded to the Feature 015 evidence graph and does not recurse
  through notebook-discovered monitor assets.
- No org-wide listing, tag/name inference, or scanning of unsupported cell
  content.

## Evidence Bundle

The internal return value for an on-demand incident evidence request.

| Field | Type | Rules |
|-------|------|-------|
| `incident` | Incident Detail Evidence | Required; absent only when the request fails |
| `notebooks` | array | Up to 10 entries, each `{reference, status, evidence}` |
| `monitors` | array | Up to 10 entries, each `{reference, status, evidence}` |
| `relationships` | object | Maps incident ID to resolved notebook/monitor IDs and reference sources |
| `status` | enum | `complete` when all references resolved, `partial` when some references are unavailable |
| `error` | enum or null | Incident-level failure; references use their own status |

**Rules**:
- No bundle is persisted.
- A reference failure yields `partial`; it does not invalidate usable incident
  evidence.
- An incident-level failure is explicit and never returns a success-shaped empty
  bundle.

## Retrieval Failure

A controlled, sanitized failure.

| Code | Meaning | Incident effect | Evidence effect |
|------|---------|-----------------|-----------------|
| `provider-unavailable` | Missing/invalid configuration, auth failure, 401/403/429/5xx, network failure, or refused redirect | Preserve previous snapshot, mark stale/unavailable | Raise controlled failure |
| `timeout` | Deadline exceeded | Preserve previous snapshot, mark stale/unavailable | Raise controlled failure |
| `invalid-response` | Malformed JSON/schema, duplicate IDs, over-bound data, invalid IDs/URLs | Preserve previous snapshot, mark stale/unavailable | Raise controlled failure; reference-level invalid data marks that reference unavailable |
| `cache-unavailable` | Cache read/write/lock failure | Preserve prior runtime snapshot where possible, report cache failure | Not applicable |

No failure path includes raw response text, token material, provider payloads, or
credentials.

## Bounds Summary

| Bound | Value |
|-------|-------|
| Datadog response bytes | 1,000,000 bytes |
| Current incidents per snapshot | 100 |
| Incident search page size | 100 |
| References per kind per incident | 10 |
| Notebook cells | 200 |
| Query definitions per cell | 20 |
| Monitor tags | 100 |
| Monitor threshold entries | 20 |
| Incident fields | 50 keys, 20 list values per key |
| Overall retrieval deadline | 90 seconds (configurable 1–120) |

## Out of Scope

No AI provider receives Datadog evidence; no DeepSeek analysis; no `noc-inv`
investigation generation changes; no `noc-handover` generation changes; no new
HTTP evidence route; no frontend evidence display; no persistent evidence cache.
