# Implementation Plan: Provider-Independent AI Support

**Branch**: `014-ai-provider-architecture` | **Date**: 2026-11-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/014-ai-provider-architecture/spec.md`

## Summary

Replace the Assistant's hard-wired GitHub Copilot CLI default with an explicit, environment-selected inference provider supporting `deepseek-api` (DeepSeek Flash) and `github-copilot-cli`. The existing bounded provider adapter, Assistant response contract, evidence minimization, operator-reviewed findings, report validation, read-only boundary, and safety behavior remain intact. Provider credentials are read only from the process environment, are captured inside a non-serializable provider closure, and never enter responses, logs, reports, or persisted data. Every failure mode fails closed with no automatic fallback. Provider identity and static readiness are exposed through the existing health and readiness diagnostics without secrets.

## Technical Context

**Language/Version**: Python 3.10+ (existing FastAPI backend; WSL/Linux workstation runtime)

**Primary Dependencies**: FastAPI 0.162.0, Pydantic 2.14.1, Uvicorn 0.54.0; Python standard library `urllib.request` for the DeepSeek HTTPS call; pytest 9.1.1 for tests. No new runtime dependency is introduced.

**Storage**: Filesystem-backed NOC Web operational data remains unchanged. AI Action reports continue to be written under the selected shift's existing `reports/` directory. Provider credentials are never persisted.

**Testing**: `pytest` with `fastapi.testclient.TestClient`, existing `noc_root` and provider-injection fixtures, plus new provider/deepseek/diagnostic/frontend tests.

**Target Platform**: Single-operator Linux/WSL workstation serving a FastAPI backend and static HTML/CSS/JavaScript frontend.

**Project Type**: Web application (backend service + static frontend).

**Performance Goals**: Provider requests remain bounded by the existing 60-second mediation cap (default 55 seconds). Static provider readiness adds no network or model call and completes within normal diagnostics latency. Non-Assistant workflows keep their current latency.

**Constraints**: Exactly one explicit provider per process; no automatic provider fallback; no credentials in API responses, frontend output, logs, reports, or persisted data; no live readiness probe; no change to Datadog incident retrieval, noc-inv investigation generation, or noc-handover generation. Provider settings must survive the managed-service environment sanitization without copying unrelated inherited variables.

**Scale/Scope**: Single workstation, one active provider, four predefined AI Actions, existing bounded selected-shift evidence volumes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Result |
|-----------|------------|--------|
| I. Preserve Operational Data Integrity | Credentials stay out of persisted data; report validation, collision-safe naming, and shift ownership are unchanged; the only report change is a non-secret provider label derived from the validated response. | PASS |
| II. Fail Safely and Explain Failures | Missing/invalid configuration, auth failure, timeout, malformed output, and validation failure all produce explicit controlled failures; no success-shaped fallback; no automatic provider switch. | PASS |
| III. Maintain API and UI Contract Consistency | The Assistant response schema is unchanged; the provider field is extended to the two canonical identifiers; backend validators, frontend validators, diagnostics, and report rendering are updated together. | PASS |
| IV. Test Operational Workflows | Focused pytest coverage is added for provider selection, DeepSeek request/response handling, no fallback, credential non-disclosure, diagnostics, report attribution, and existing Assistant safety behavior. | PASS |
| V. Prefer Simple, Observable Changes | Reuses the existing provider adapter, Assistant service, report service, and diagnostic surfaces; uses the standard library for one HTTPS JSON request; readiness is explicit and non-secret. | PASS |
| VI. Require Deliberate Operational Execution | No new operational action is introduced; the AI boundary remains read-only and advisory; no state-changing workflow or confirmation gate is altered. | PASS |

**Gate result**: PASS. No violations or exceptions required.

## Project Structure

### Documentation (this feature)

```text
specs/014-ai-provider-architecture/
├── plan.md                      # This file
├── research.md                  # Phase 0 output
├── data-model.md                # Phase 1 output
├── quickstart.md                # Phase 1 output
├── contracts/
│   ├── assistant-api.md
│   ├── diagnostics.md
│   ├── deepseek-http.md
│   └── provider-configuration.md
├── checklists/
│   └── requirements.md
└── tasks.md                     # Phase 2 output (/speckit.tasks - not created here)
```

### Source Code (repository root)

```text
backend/
├── app.py                              # Provider runtime resolution and state wiring
├── api/
│   ├── assistant.py                    # Pass provider identifier; 503 when not configured
│   ├── health.py                       # Shift health route (AI Provider section)
│   └── readiness.py                    # Readiness route (external.aiProvider)
└── services/
    ├── ai_provider.py                  # New: canonical IDs, env selection, readiness, runtime
    ├── deepseek_provider.py            # New: DeepSeek Flash HTTPS JSON adapter
    ├── copilot_cli.py                  # Existing Copilot CLI adapter (unchanged behavior)
    ├── copilot_mcp.py                  # Existing bounded timeout adapter / error taxonomy
    ├── assistant.py                    # Provider-aware attribution; preserve contract/validation
    ├── assistant_actions.py            # Unchanged
    ├── assistant_context.py            # Unchanged
    ├── ai_reports.py                   # Provider label in reports; unchanged validation
    ├── health.py                       # Optional Copilot; add AI Provider check
    └── dependency_readiness.py         # Add external.aiProvider capability

frontend/
├── assistant.html                      # Provider label + dynamic disclosure
├── ai-actions.html                     # Provider label + dynamic disclosure
├── health.html                         # AI Provider diagnostic panel
└── js/
    └── api.js                          # Accept both provider IDs; provider label/health helpers

tests/
├── test_ai_provider.py                 # New
├── test_deepseek_provider.py           # New
├── test_assistant.py                   # Update provider attribution coverage
├── test_assistant_api.py               # Update provider state/no-config coverage
├── test_ai_reports.py                  # Update provider label coverage
├── test_dependency_readiness.py        # Update external.aiProvider coverage
├── test_readiness_api.py               # Update diagnostic contract coverage
├── test_frontend_modules.py            # Update provider/UI contract coverage
└── test_runtime_service.py             # Update provider env propagation coverage

scripts/
└── run_service.py                      # Allowlist provider env propagation

systemd/
└── noc-web.service.in                  # Optional operator-managed provider EnvironmentFile
```

**Structure Decision**: Keep the existing web-application layout. Provider selection and readiness live in a new `backend/services/ai_provider.py`; the DeepSeek-specific transport lives in `backend/services/deepseek_provider.py`. Existing Assistant, report, health, and readiness boundaries are extended rather than replaced.

## Phase 0: Research Summary

Full decisions and alternatives are in [research.md](./research.md). Key outcomes:

- Use exact environment-based selection with `NOC_WEB_AI_PROVIDER`; unset means "not configured," never an implicit Copilot default.
- Use DeepSeek's OpenAI-compatible `POST https://api.deepseek.com/chat/completions` with `model: deepseek-flash`, JSON output mode, thinking disabled, and a bounded `max_tokens`.
- Use the Python standard library for the HTTPS request to avoid adding a runtime dependency.
- Reuse the existing timeout adapter and failure taxonomy: success, unavailable, timeout, invalid, not-invoked.
- Map HTTP/authentication/rate-limit/network failures to `unavailable`, timeouts to `timeout`, and blank/truncated/malformed JSON to `invalid`.
- Never retry, never fall back, and never log request/response bodies or credentials.
- Attribute responses and reports with canonical identifiers `deepseek-api` and `github-copilot-cli`; model choice remains separate.
- Expose static readiness on `/api/health`, `/api/health/{shift}`, and `/api/readiness/{shift}`; no readiness model call.

## Phase 1: Design Summary

### Provider selection and runtime

- `ai_provider.py` owns canonical identifiers, display labels, environment parsing, redacted configuration errors, static readiness, and runtime construction.
- `resolve_provider_runtime()` returns the selected identifier and a provider callable or `None`. `provider_readiness()` computes the non-secret ready/not-ready/not-configured state from the same effective process configuration. Invalid configuration never prevents application startup; it produces a not-ready runtime that fails Assistant requests closed.
- `app.state.assistant_provider` and `app.state.assistant_provider_identifier` hold the resolved runtime. Diagnostics call `provider_readiness()` against the same process environment, so they agree. The test helper must accept an explicit identifier, and tests that inject a fake provider must set both state fields; a missing identifier is treated as not configured rather than defaulting to Copilot.
- When no provider is configured, Assistant and AI Action routes return a controlled 503 (`assistant-provider-not-configured`); a selected but invalid/incomplete provider returns a distinct controlled 503 (`assistant-provider-not-ready`). No response contract object is fabricated and no report is saved.

### DeepSeek adapter

- Build one non-streaming JSON-mode request with a system prompt containing the existing analysis rules, stale-evidence qualification, route allowlist, exact response schema, and the literal word "JSON" required by DeepSeek JSON mode.
- Send the bounded request envelope as the user message. Keep the credential only in the `Authorization` header and inside a closure; never log headers, body, URL query, or upstream error text.
- Enforce HTTPS, validated host/path, no userinfo/query/fragment, bounded response size, strict UTF-8, dict-only JSON, non-empty content, and rejection of `finish_reason: "length"`.
- Return only the parsed provider object to the existing Assistant validation path.

### Assistant and report integration

- `assistant.answer()` receives or resolves the active canonical provider identifier and stamps every response, including refusals, insufficient-context, and failure responses. It never defaults to Copilot; existing direct-call tests must pass an explicit identifier or configure the environment.
- The legacy `ask_copilot` entry point remains as a compatibility alias but resolves the active environment provider when no callable is injected; it does not select Copilot implicitly.
- `validate_assistant_response()` accepts only the two canonical identifiers and optionally verifies the expected active provider.
- Report rendering replaces the hard-coded "GitHub Copilot CLI" line with the validated provider's display label. Report validation, normalization, persistence, and read-only viewing are otherwise unchanged.
- No automatic fallback exists at any layer.

### Diagnostics and frontend

- `/api/health` gains a non-secret `aiProvider` object.
- Shift health gains an "AI Provider" section; Copilot is removed from unconditional required tools so a DeepSeek deployment without Copilot can be healthy. The AI Provider check is warning-only for `notConfigured` and `notReady` states so a provider problem cannot become an End Shift/handover blocker, preserving the out-of-scope noc-handover workflow.
- Readiness gains an `external.aiProvider` capability with provider identity, model, readiness, impact, and corrective guidance; it remains optional so it does not block unrelated workflows.
- Existing `external.copilot` remains a Copilot-specific integration capability and is clearly distinct from active provider readiness.
- Frontend accepts both provider identifiers, renders the correct provider label, and generates the pre-submission disclosure from the configured provider without exposing secrets. If the lightweight health lookup fails, the disclosure states that provider identity could not be verified and the request path remains fail-closed.

### Managed-service configuration propagation

- Extend `scripts/run_service.py` `build_service_environment()` to copy only the provider allowlist (`NOC_WEB_AI_PROVIDER`, `NOC_WEB_DEEPSEEK_API_KEY`, `NOC_WEB_DEEPSEEK_MODEL`, `NOC_WEB_DEEPSEEK_BASE_URL`, `NOC_WEB_AI_TIMEOUT_SECONDS`) from the invoking environment. Do not copy unrelated inherited variables such as `COPILOT_TOKEN`.
- Add an optional `EnvironmentFile=-<config-dir>/ai-provider.env` to the generated systemd unit so an operator can supply provider settings to the user service from a mode-0600 file outside NOC Web application data.
- Never write provider secrets into the generated unit file, NOC Web data, or logs.
- Document the environment file format and permissions in the operational quickstart/README.

### Post-Design Constitution Re-check

| Principle | Post-Design Assessment | Result |
|-----------|------------------------|--------|
| I. Preserve Operational Data Integrity | Report content changes only by provider label; credentials remain runtime-only; report validation and path safety unchanged. | PASS |
| II. Fail Safely and Explain Failures | All provider error paths map to controlled statuses; no retry or fallback; not-configured returns 503. | PASS |
| III. Maintain API and UI Contract Consistency | Response schema unchanged; provider enum extended; backend, frontend, diagnostics, and report consumers updated together. | PASS |
| IV. Test Operational Workflows | New and updated tests cover both providers and all failure/secret/diagnostic paths. | PASS |
| V. Prefer Simple, Observable Changes | No new runtime dependency; readiness and failures are observable; existing boundaries reused. | PASS |
| VI. Require Deliberate Operational Execution | No operational writes or actions added; read-only advisory boundary preserved. | PASS |

## Complexity Tracking

No constitution violations or unjustified complexity. The only new modules are a provider-selection/readiness module and a DeepSeek transport adapter, which isolate external-provider concerns from the existing Assistant and report services.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| DeepSeek JSON output returns blank or truncated content | Reject whitespace-only content and `finish_reason: "length"` as `invalid`; no partial answer or report. |
| Credential leakage through exception text or debug output | Fixed public error messages; no upstream body/header logging; redacted configuration errors; credential captured in a closure only. |
| Accidental fallback or implicit Copilot default | Explicit identifier resolution; no fallback code path; not-configured API returns 503; tests assert the non-selected provider is never called. |
| Readiness falsely implying authentication | Static readiness text explicitly states authentication/reachability are not verified; diagnostics distinguish ready, not-ready, and not-configured. |
| Existing Copilot deployments lose Assistant access after upgrade | Document `NOC_WEB_AI_PROVIDER=github-copilot-cli` as the required explicit setting; readiness guidance names the missing setting. |
| Existing health tests assume Copilot is mandatory | Update health/readiness tests and remove Copilot from unconditional required tools; retain Copilot integration visibility separately. |
| Provider change requires restart but environment changes at runtime | Document that provider configuration is read at process start; diagnostics reflect the effective process configuration. |
| Managed service sanitizes its environment and drops provider settings | Allowlist provider variables in `build_service_environment()` and add an optional mode-0600 systemd `EnvironmentFile`; update runtime-service tests. |
