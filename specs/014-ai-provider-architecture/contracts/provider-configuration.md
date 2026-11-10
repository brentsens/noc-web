# Contract: Provider Configuration

**Feature**: `014-ai-provider-architecture`

Provider configuration is supplied only through the process environment at application start. Changing configuration requires a restart. No provider is selected by default.

## Environment variables

| Variable | Required | Default | Secret | Validation |
|----------|----------|---------|--------|------------|
| `NOC_WEB_AI_PROVIDER` | No | unset (`notConfigured`) | No | Exact value `deepseek-api` or `github-copilot-cli`; unknown/empty-after-trim is not configured or not ready as defined below |
| `NOC_WEB_DEEPSEEK_API_KEY` | When DeepSeek selected | none | Yes | Non-empty; never logged, returned, or persisted |
| `NOC_WEB_DEEPSEEK_MODEL` | No | `deepseek-flash` | No | Non-empty, bounded, no control characters |
| `NOC_WEB_DEEPSEEK_BASE_URL` | No | `https://api.deepseek.com` | No | HTTPS only; non-empty host; no userinfo, query, fragment, or parent traversal |
| `NOC_WEB_AI_TIMEOUT_SECONDS` | No | `55` | No | Integer 1–60; bounds the provider mediation adapter for both providers; the Copilot CLI's internal 55-second subprocess cap remains as a defense-in-depth bound |

## Selection semantics

| State | Condition | Assistant/AI Action behavior |
|-------|-----------|-------------------------------|
| Not configured | `NOC_WEB_AI_PROVIDER` unset or empty | Controlled HTTP 503 `assistant-provider-not-configured`; no report |
| Not ready | Selected provider configuration invalid or required material missing | Controlled HTTP 503 `assistant-provider-not-ready`; no report |
| Ready — DeepSeek | `deepseek-api` selected, key present, URL/model/timeout valid | Use DeepSeek Flash adapter |
| Ready — Copilot | `github-copilot-cli` selected, `copilot` executable present | Use existing Copilot CLI adapter |

## Managed service propagation

The managed systemd user service sanitizes its environment. To make provider settings reach the application:

1. `scripts/run_service.py` MUST copy only the provider allowlist from the invoking environment:
   - `NOC_WEB_AI_PROVIDER`
   - `NOC_WEB_DEEPSEEK_API_KEY`
   - `NOC_WEB_DEEPSEEK_MODEL`
   - `NOC_WEB_DEEPSEEK_BASE_URL`
   - `NOC_WEB_AI_TIMEOUT_SECONDS`
2. It MUST NOT copy unrelated inherited variables such as `COPILOT_TOKEN`.
3. The generated systemd unit MUST include an optional `EnvironmentFile=-<config-dir>/ai-provider.env`.
4. The environment file is operator-managed outside NOC Web application data and MUST have mode `0600` when it contains a credential.
5. Provider secrets MUST NOT be written into the generated unit, NOC Web application data, or logs.

Example operator-managed file (never committed):

```text
NOC_WEB_AI_PROVIDER=deepseek-api
NOC_WEB_DEEPSEEK_API_KEY=<secret>
NOC_WEB_DEEPSEEK_MODEL=deepseek-flash
```

## Rules

1. The system MUST NOT infer a provider from another provider's configuration.
2. The system MUST NOT fall back to another provider when the selected provider is not ready or fails.
3. The system MUST NOT return any credential value, token, key fragment, or reversible representation.
4. Configuration errors MUST name only the affected setting.
5. Readiness MUST distinguish `ready`, `notReady`, and `notConfigured`.
6. DeepSeek readiness MUST NOT assert credential acceptance or reachability.
7. Copilot readiness MUST NOT assert authentication or reachability.
