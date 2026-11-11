# Contract: Primary and Local Provider Readiness

**Feature**: `018-ollama-local-provider`
**Scope**: Static health/status readiness, explicit Ollama probe, and operator UI visibility

## Static Readiness

Health, status, and readiness responses MUST expose additive primary/local provider information
without contacting either provider.

```json
{
  "configuredProvider": "deepseek-api",
  "readiness": "ready",
  "label": "DeepSeek API",
  "model": "deepseek-flash",
  "primaryProvider": {
    "configuredProvider": "deepseek-api",
    "readiness": "ready",
    "label": "DeepSeek API",
    "model": "deepseek-flash"
  },
  "localProvider": {
    "configuredProvider": "ollama",
    "readiness": "ready",
    "label": "Ollama",
    "model": "qwen3:8b",
    "endpointConfigured": true,
    "probe": null
  }
}
```

**Rules**:
- Existing fields remain compatible; primary/local fields are additive.
- `primaryProvider` describes DeepSeek/default primary configuration.
- `localProvider` describes optional Ollama endpoint/model configuration.
- Local `readiness` is static configuration state, not network/model availability.
- No Datadog, Ollama, DeepSeek, or Copilot network request is made.
- No model inference occurs.
- Ollama unavailability does not make core readiness fail when DeepSeek remains usable.
- No credentials or environment values are exposed.

## Explicit Local Probe

`POST /api/providers/ollama/probe`

**Purpose**: Operator-triggered local availability check.

**Rules**:
- Performs a bounded Ollama model-list request.
- Verifies endpoint reachability and configured model presence.
- Performs no inference, token generation, or model loading.
- Rejects redirects and unexpected hosts.
- Returns sanitized `OllamaProbeResult`.
- Does not change core readiness or the configured provider.
- Does not persist secrets or raw Ollama response metadata.

### Probe Response

```json
{
  "provider": "ollama",
  "endpointConfigured": true,
  "model": "qwen3:8b",
  "available": true,
  "reason": null,
  "probedAt": "2026-11-11T16:20:00Z"
}
```

### Probe Failures

Sanitized reasons: `unconfigured`, `invalid-endpoint`, `unreachable`, `refused`, `timeout`,
`model-missing`, `malformed`.

## UI Contract

- Show the active/configured provider and model.
- Show primary DeepSeek state separately from optional local Ollama state.
- Show local endpoint configured/unconfigured.
- Show configured local model.
- Show last explicit probe result and a **Probe local provider** action.
- Never probe automatically on page load or static health/readiness refresh.
- Show Retry with Local AI only after a primary-provider failure and only when a valid retry snapshot
  exists.
- Retry action requires explicit operator confirmation.
- Do not expose credentials, evidence contents, prompts, or Ollama metadata.
- No UI path may automatically invoke Ollama after a DeepSeek failure.

## Compatibility

- Existing health/status/readiness consumers continue to receive their existing fields.
- New fields are additive.
- Existing provider labels remain unchanged.
- Local provider labels/provenance use `ollama` and the configured model.
- Microsoft 365, Datadog read-only behavior, investigation lifecycle, reviewed boundaries, and
  handover completeness are unchanged.
