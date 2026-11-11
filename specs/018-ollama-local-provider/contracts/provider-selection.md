# Contract: Explicit Provider Selection

**Feature**: `018-ollama-local-provider`
**Scope**: Configured default and per-request provider selection across AI workflows

## Selection Modes

| Mode | Meaning |
|------|---------|
| Configured default | `NOC_WEB_AI_PROVIDER` explicitly selects `deepseek-api`, `github-copilot-cli`, or `ollama` |
| Per-request selection | The operator explicitly chooses `deepseek-api` or `ollama` for one workflow request |
| Retry with Local AI | The operator explicitly confirms local retry after a primary-provider failure |

DeepSeek remains the default for existing installations. No automatic migration to Ollama occurs.

## Per-Request Field

Additive optional field:

```json
{
  "provider": "ollama"
}
```

**Allowed values**:
- `deepseek-api`
- `ollama`

`github-copilot-cli` remains available only through existing configured-provider behavior unless the
existing workflow already supports per-request provider choice. An unsupported value fails with a
controlled validation error.

**Rules**:
- Omitting `provider` uses the configured default; no new provider is selected implicitly.
- Explicit `provider: "ollama"` requires a valid Ollama endpoint/model configuration.
- Explicit `provider: "deepseek-api"` requires the existing DeepSeek configuration and credential.
- No provider fallback occurs when the explicitly selected provider is unavailable.
- The selected provider identity/model is recorded in the existing workflow provenance.
- Selection does not change evidence, preview/confirmation, lifecycle, ticket completeness, Datadog
  read-only, or delivery behavior.

## Workflow Application

- Assistant questions/actions: request may include explicit `provider`.
- Investigation preview/create: optional `provider`; preview stores the provider identity/model and
  create validates it has not changed.
- Handover preview/generate/regenerate: optional `provider`; preview/generation records the selected
  provider and existing confirmation/archive rules remain.
- Retry with Local AI uses the retry-specific contract instead of a general provider field.

## UI

- Show the configured default provider.
- Offer per-request provider selection only where the workflow exposes an explicit AI action and the
  local provider is configured.
- Never preselect Ollama after a primary failure.
- Retry with Local AI is a separate explicit confirmation action.
- Show selected/local provider identity and model without exposing secrets.
