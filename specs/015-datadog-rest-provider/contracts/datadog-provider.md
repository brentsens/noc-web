# Contract: Datadog Provider

**Feature**: `015-datadog-rest-provider`

This contract covers configuration, static readiness, transport, read-only
operations, and failure behavior of the direct Datadog provider. It is an
internal backend contract; no new public HTTP route is introduced.

## Environment configuration

| Variable | Required | Default | Secret | Validation |
|----------|----------|---------|--------|------------|
| `NOC_WEB_DATADOG_ACCESS_TOKEN` | For retrieval | none | Yes | Non-empty after trimming; never logged, returned, serialized, or persisted |
| `NOC_WEB_DATADOG_BASE_URL` | No | `https://api.datadoghq.com` | No | HTTPS; host under `datadoghq.com`, `datadoghq.eu`, or `ddog-gov.com`; no userinfo, query, fragment, or parent traversal |
| `NOC_WEB_DATADOG_TIMEOUT_SECONDS` | No | `90` | No | Integer 1–120; bounds each request and the overall retrieval deadline |

Configuration is read from the process environment at application start.
Changing it requires a restart.

## Static readiness

`datadog_provider_readiness()` returns a non-secret object and makes no network
request.

```json
{
  "provider": "datadog-api",
  "configuredProvider": "datadog-api",
  "baseUrl": "https://api.datadoghq.com",
  "readiness": "ready",
  "label": "Datadog API",
  "credentialPresent": true,
  "impact": "Live Datadog incident and evidence retrieval is configured.",
  "correctiveAction": "No action required."
}
```

| State | Condition | Retrieval behavior |
|-------|-----------|--------------------|
| `ready` | Token present; base URL and timeout valid | Retrieval may be attempted |
| `notReady` | Token present; base URL or timeout invalid | Fail closed as `provider-unavailable` |
| `notConfigured` | Token absent | Fail closed as `provider-unavailable`; incidents show stale/unavailable |

Readiness never asserts token validity or Datadog reachability.

## App URL derivation

The operator-facing app base is derived from the API base by replacing a
leading `api.` host label with `app.`:

| API base | App base |
|----------|----------|
| `https://api.datadoghq.com` | `https://app.datadoghq.com` |
| `https://api.datadoghq.eu` | `https://app.datadoghq.eu` |
| `https://api.us3.datadoghq.com` | `https://app.us3.datadoghq.com` |
| `https://api.ddog-gov.com` | `https://app.ddog-gov.com` |

Incident URLs use `/incidents/{id}`; monitor URLs use `/monitors/{id}`. Notebook
URLs use `/notebook/{id}` when constructing a reference link.

## Read-only operation allowlist

Only these logical operations may reach the transport:

| Operation | Method | Path | Query/body | Purpose |
|-----------|--------|------|------------|---------|
| `search_incidents` | GET | `/api/v2/incidents/search` | `query=state:(active OR stable)`, `page[size]=100`, optional `page[offset]` | Current incident snapshot |
| `get_incident` | GET | `/api/v2/incidents/{incident_id}` | `include=attachments` | Incident detail evidence |
| `get_notebook` | GET | `/api/v1/notebooks/{notebook_id}` | none | Notebook evidence |
| `get_monitor` | GET | `/api/v1/monitor/{monitor_id}` | `group_states=all`, `with_assets=true` | Monitor evidence and notebook assets |

Rules:

1. Any operation not in the table is rejected before transport.
2. No create, update, acknowledge, mute, resolve, delete, or other mutation
   operation exists in the client.
3. Incident IDs are bounded Datadog identifiers; notebook and monitor IDs are
   positive decimal integers. IDs are URL-encoded and cannot alter the path.
4. A non-mutating query may use POST only if added to this allowlist with a
   documented read-only purpose. No such operation is required today.
5. Redirects are refused so the bearer token is never forwarded.

## Transport

- HTTPS only.
- `Authorization: Bearer <token>` header only.
- `Accept: application/json`.
- No token in URLs, query strings, bodies, logs, or exceptions.
- Explicit timeout for each request and an overall monotonic deadline for a
  refresh/evidence operation.
- Read at most 1,000,000 bytes plus one byte; reject larger responses.
- Accept status 200 only.
- Accept `application/json` or `application/vnd.api+json` (Datadog JSON:API)
  when a content type is present; reject other media types.
- Decode strict UTF-8 and parse JSON; reject non-object roots.
- No automatic retries. A failure is reported, not retried or silently
  switched to another provider.

## Failure mapping

| Condition | Code |
|-----------|------|
| Missing/invalid configuration | `provider-unavailable` |
| 401, 403, 429, 5xx | `provider-unavailable` |
| Network, TLS, connection, or refused redirect | `provider-unavailable` |
| Deadline or socket timeout | `timeout` |
| Malformed JSON, wrong schema, duplicate IDs, over-limit data, invalid IDs/URLs | `invalid-response` |
| Cache read/write/lock failure | `cache-unavailable` |

Failure messages are fixed and sanitized. They never include response bodies,
stderr, request URLs with credentials, or token fragments.

## Managed service propagation

`scripts/run_service.py` must copy only this allowlist from the invoking
environment:

- `NOC_WEB_DATADOG_ACCESS_TOKEN`
- `NOC_WEB_DATADOG_BASE_URL`
- `NOC_WEB_DATADOG_TIMEOUT_SECONDS`

The generated systemd unit loads an optional, operator-managed
`<config-dir>/datadog-provider.env` with `EnvironmentFile=-`. The file lives
outside NOC Web operational data and must be mode `0600` when it contains a
credential. The token must never appear in the unit file, `runtime.json`,
application data, or logs.

```text
NOC_WEB_DATADOG_ACCESS_TOKEN=<secret>
NOC_WEB_DATADOG_BASE_URL=https://api.datadoghq.com
NOC_WEB_DATADOG_TIMEOUT_SECONDS=90
```
