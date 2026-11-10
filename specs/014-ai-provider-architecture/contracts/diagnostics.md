# Contract: Provider Diagnostics

**Feature**: `014-ai-provider-architecture`

Provider diagnostics expose identity and static readiness only. They never expose credential values, tokens, key fragments, or reversible representations.

## `GET /api/health`

Additive, non-secret field:

```json
{
  "status": "healthy",
  "service": "noc-web",
  "version": "0.1.0",
  "aiProvider": {
    "configuredProvider": "deepseek-api | github-copilot-cli | null",
    "readiness": "ready | notReady | notConfigured",
    "label": "DeepSeek API | GitHub Copilot CLI | null",
    "model": "deepseek-flash | null",
    "impact": "Safe operator-facing description.",
    "correctiveAction": "Safe guidance naming settings, never values."
  }
}
```

## `GET /api/health/{shift_date}`

The response gains an `AI Provider` section check:

```json
{
  "section": "AI Provider",
  "state": "pass | warning | fail",
  "message": "Non-secret provider identity, readiness, and safe guidance."
}
```

State mapping:
- `ready` → `pass`
- `notConfigured` → `warning`
- `notReady` → `warning`

The AI Provider check MUST NOT use `fail`, because shift health failures are End Shift/handover blockers and provider readiness is out of scope for those workflows. `copilot` is no longer an unconditional required tool. A DeepSeek-selected deployment without Copilot MUST NOT be unhealthy solely because Copilot is absent.

## `GET /api/readiness/{shift_date}`

`externalCapabilities` gains:

```json
{
  "id": "external.aiProvider",
  "category": "external",
  "capability": "AI inference provider (DeepSeek API | GitHub Copilot CLI | not configured)",
  "status": "ready | setup_required | unavailable | notConfigured",
  "installationStatus": "ready | setup_required | unavailable | notConfigured",
  "required": false,
  "impact": "Safe operator-facing description.",
  "correctiveAction": "Safe guidance naming settings, never values.",
  "checkedAt": "ISO-8601 UTC",
  "configuredProvider": "deepseek-api | github-copilot-cli | null",
  "model": "deepseek-flash | null",
  "providerReadiness": "ready | notReady | notConfigured"
}
```

Rules:
- `required` MUST be `false`; provider readiness MUST NOT block unrelated workflows.
- Readiness MUST be static: no inference/model request.
- Readiness MUST NOT claim credential acceptance or reachability.
- The readiness surface is authoritative for provider identity/readiness; health must not contradict it.
- `external.copilot` remains a Copilot-specific integration capability and is distinct from active provider readiness.

## Redaction rules

- No credential value or reversible representation in any diagnostic field.
- Configuration errors name only the affected setting.
- Upstream provider error bodies and headers are never surfaced.
- Diagnostic output may identify the provider, model, readiness state, and safe corrective action only.
