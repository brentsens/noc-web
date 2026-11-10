# Contract: Datadog Provider Diagnostics

**Feature**: `015-datadog-rest-provider`

Diagnostics are additive and static. Loading any diagnostic surface must make
zero Datadog requests and must not invoke Copilot or Datadog MCP.

## Shared readiness object

`datadog_provider_readiness()` returns:

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

When the token is absent:

```json
{
  "provider": "datadog-api",
  "configuredProvider": null,
  "baseUrl": "https://api.datadoghq.com",
  "readiness": "notConfigured",
  "label": "Datadog API",
  "credentialPresent": false,
  "impact": "Live Datadog incident and evidence retrieval is not configured.",
  "correctiveAction": "Set NOC_WEB_DATADOG_ACCESS_TOKEN in the process environment and restart NOC Web."
}
```

No field contains a token, token fragment, or reversible representation.

## `/api/health`

Add `datadogProvider` with the shared readiness object. Existing fields are
unchanged.

```json
{
  "status": "healthy",
  "service": "noc-web",
  "version": "0.1.0",
  "aiProvider": {},
  "datadogProvider": {
    "provider": "datadog-api",
    "readiness": "ready"
  }
}
```

The health surface may show a concise subset, but it must not contradict
`/api/readiness`.

## `/api/status/{shift_date}`

Add a top-level `datadogProvider` with the shared readiness object. Existing
fields and dependency entries are unchanged otherwise. This field is static and
must not trigger a Datadog refresh.

## `/api/readiness/{shift_date}`

Add an optional external capability:

```json
{
  "id": "external.datadog",
  "category": "external",
  "capability": "Datadog API evidence retrieval",
  "status": "ready",
  "installationStatus": "ready",
  "required": false,
  "impact": "Live Datadog incident and evidence retrieval is configured.",
  "correctiveAction": "No action required.",
  "checkedAt": "2026-11-10T20:00:00+00:00",
  "providerReadiness": "ready",
  "configuredProvider": "datadog-api",
  "baseUrl": "https://api.datadoghq.com",
  "credentialPresent": true
}
```

| Readiness | External status | Installation status |
|-----------|-----------------|---------------------|
| `ready` | `ready` | `ready` |
| `notReady` | `setup_required` | `setup_required` |
| `notConfigured` | `setup_required` | `setup_required` |

`providerReadiness` preserves the precise static state. The capability is
`required: false` so it cannot block unrelated workflows.

Remove the old `external.datadogMcp` probe from readiness. It must not run
`copilot mcp list`. Keep `external.copilot` for the separate AI provider
capability.

## Bootstrap status

Bootstrap readiness reports `external.datadog` instead of
`external.datadogMcp` for Datadog evidence. Any remaining Datadog MCP
provisioning is outside this feature and must not be required by Feature 015
acceptance.

## Guarantees

- Zero Datadog network calls.
- Zero Copilot subprocess calls for the Datadog provider check.
- Zero Datadog MCP tool calls.
- No credential value or reversible representation.
- Accurate distinction among ready, not ready, and not configured.
- No claim that credentials were authenticated or Datadog was reached.
