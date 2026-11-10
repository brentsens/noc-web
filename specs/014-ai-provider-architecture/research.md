# Research: Provider-Independent AI Support

**Feature**: `014-ai-provider-architecture`  
**Date**: 2026-11-10

## Decision 1: Explicit environment-based provider selection

**Decision**: Select exactly one provider from `NOC_WEB_AI_PROVIDER` with the exact canonical values `deepseek-api` or `github-copilot-cli`. An unset or empty value means "not configured"; it never implies a Copilot default. Provider changes require a process restart.

**Rationale**: The clarification chose environment variables/process environment only. This keeps credentials and selection outside NOC Web's persisted data, avoids an in-app admin surface, and makes the no-fallback rule explicit. An implicit Copilot default would violate the clarified not-configured behavior.

**Alternatives considered**:
- Default to Copilot when unset: rejected because it creates an implicit provider selection and hides missing configuration.
- Runtime configuration file: rejected because the clarification selected process environment and credentials must not be persisted.
- In-app provider switcher: rejected as out of scope and a wider security surface.

## Decision 2: DeepSeek Flash endpoint and model

**Decision**: Use the OpenAI-compatible endpoint `POST https://api.deepseek.com/chat/completions` with model `deepseek-flash`. Allow the base URL and model to be overridden by environment for deployment flexibility, but default to those values.

**Rationale**: The DeepSeek API documentation identifies `deepseek-flash` as the current model name and `https://api.deepseek.com` as the OpenAI-compatible base URL. The model is served by the current Flash backend while keeping the calling method stable.

**Alternatives considered**:
- Hard-code the underlying backend model name: rejected because the published API name `deepseek-flash` is the stable contract.
- Use `deepseek-chat`/`deepseek-reasoner` legacy names: not the requested model family and not guaranteed to map to Flash.

**Sources**:
- https://api-docs.deepseek.com/
- https://api-docs.deepseek.com/api/create-chat-completion

## Decision 3: JSON output mode with deterministic settings

**Decision**: Send `response_format: {"type": "json_object"}`, include explicit "JSON" wording in the system prompt, set `thinking: {"type": "disabled"}`, `stream: false`, `temperature: 0.2`, and a bounded `max_tokens` (4096). Reject blank content, non-dict JSON, and `finish_reason: "length"` as invalid.

**Rationale**: DeepSeek JSON mode guarantees valid JSON only when the prompt instructs JSON output. Disabling thinking keeps latency predictable and avoids returning chain-of-thought content. A bounded token limit prevents unbounded responses; truncation must fail closed rather than produce a partial advisory result. The DeepSeek system prompt reuses the existing Copilot analysis rules, stale-evidence qualification, route allowlist, and exact `aiObservations`/`recommendations` schema, adapted to embed the bounded envelope as a user message and to include the word "JSON."

**Alternatives considered**:
- Thinking mode enabled: rejected for latency and because reasoning content is not part of the Assistant contract.
- Streaming: rejected because the existing provider boundary returns one complete dict.
- Prompt-only JSON with no response format: rejected because it is less reliable than JSON mode.

**Sources**:
- https://api-docs.deepseek.com/guides/json_mode
- https://api-docs.deepseek.com/guides/thinking_mode

## Decision 4: Standard-library HTTPS transport

**Decision**: Use `urllib.request` with an explicit timeout, HTTPS-only URL validation, a bounded response read (1 MiB), strict UTF-8 decoding, and an opener that refuses HTTP redirects so the authorization header is never forwarded to another host.

**Rationale**: The runtime dependency set is intentionally small. A single non-streaming HTTPS JSON request does not justify adding an HTTP client dependency. The standard library is already used elsewhere for bounded runtime checks.

**Alternatives considered**:
- Add `httpx`/`httpx2` to runtime requirements: rejected to avoid a new production dependency; `httpx2` is currently a test-only dependency for `TestClient`.
- Use the OpenAI SDK: rejected as a larger dependency and unnecessary abstraction for one endpoint.

## Decision 5: Reuse the existing bounded adapter and failure taxonomy

**Decision**: Keep the existing `CopilotMcpAdapter` timeout wrapper and `CopilotProviderUnavailable`, `CopilotProviderTimeout`, and `CopilotProviderInvalid` classes. Add generic aliases/docstrings so both providers use the same taxonomy. The DeepSeek adapter raises these same exceptions.

**Rationale**: The Assistant already maps these exceptions to the contract statuses `unavailable`, `timeout`, and `invalid`. Reusing them preserves the response contract and avoids a parallel error model. `NOC_WEB_AI_TIMEOUT_SECONDS` bounds the mediation adapter for both providers; the Copilot CLI's internal 55-second subprocess cap remains as a defense-in-depth bound. Renaming the module and classes would create unnecessary churn and test risk.

**Alternatives considered**:
- New provider-specific exception hierarchy: rejected because it would require duplicate mapping in the Assistant.
- Rename `copilot_mcp.py` to a generic module: deferred; behavior is provider-neutral despite the legacy name.

## Decision 6: Provider identity propagation

**Decision**: Use canonical provider-level identifiers `deepseek-api` and `github-copilot-cli` in responses and reports. Keep the model separate. Resolve the active identifier once per process and pass it through the Assistant service; validate it against the supported set and, at the API boundary, against the expected active provider.

**Rationale**: The existing `provider` field is already part of the response contract. Provider-level identifiers avoid contract churn when the model changes. Passing the identifier alongside the callable prevents the service from guessing or defaulting to Copilot.

**Alternatives considered**:
- Include the model in the identifier: rejected because a model upgrade would change the contract.
- Remove or rename the provider field: rejected because the contract must remain unchanged.
- Derive the identifier from the callable name: rejected as fragile.

## Decision 7: Not-configured behavior

**Decision**: The application starts normally with no provider configured. Diagnostics report `notConfigured`. Assistant and AI Action routes return a controlled HTTP 503 (`assistant-provider-not-configured`) and save no report. A selected but invalid or incomplete provider returns a distinct controlled HTTP 503 (`assistant-provider-not-ready`). No provider is selected by default, and the Assistant service layer must not default to Copilot when no identifier is supplied.

**Rationale**: This preserves non-Assistant workflows, honors the clarified behavior, distinguishes not-configured from not-ready, and avoids fabricating a provider identity in the response contract. The 503 is a controlled fail-closed path rather than a success-shaped answer.

**Alternatives considered**:
- Return a 200 response with a synthetic provider identifier: rejected because no canonical provider served the request and the contract would be misleading.
- Refuse application startup: rejected because it would block unrelated NOC Web workflows.
- Default the service layer to Copilot: rejected because it would create an implicit provider selection and could hide misconfiguration.

## Decision 8: Static readiness without credentials exposure

**Decision**: Readiness reports:
- `ready` when the selected provider's static configuration is valid and required material is present (DeepSeek API key present; Copilot executable present).
- `notReady` when the selected provider is invalid, unsupported, missing credentials, or missing its executable.
- `notConfigured` when no provider is selected.

Readiness makes no model/inference request, does not assert DeepSeek credential acceptance or reachability, and never returns any credential value or reversible representation.

**Rationale**: This follows the clarification and avoids turning diagnostics into an external network dependency. For Copilot, executable presence is the static equivalent of required material; authentication is not asserted by the static provider check. The separate existing Copilot integration diagnostic continues to report authentication for Copilot-specific integrations such as Datadog MCP.

**Alternatives considered**:
- Live `/models` or authentication probe: rejected by the clarification and would add latency/failure modes to diagnostics.
- Treat missing auth as not ready for Copilot: rejected for consistency with the static-readiness decision; the existing Copilot integration capability still reports auth state separately.

## Decision 9: Diagnostic surfaces

**Decision**:
- Extend the lightweight `/api/health` root response with a non-secret `aiProvider` object.
- Replace the shift health "Copilot" panel with an "AI Provider" panel that reports the effective provider and static readiness; remove Copilot from unconditional required tools so DeepSeek deployments do not become unhealthy solely because Copilot is absent. Make the AI Provider check warning-only for not-configured and not-ready states so it does not add an End Shift/handover blocker, preserving the out-of-scope noc-handover workflow.
- Add `external.aiProvider` to `/api/readiness/{shift}` with provider identity, model, readiness state, impact, and safe corrective guidance. It is optional (`required: false`) so it does not block unrelated workflows.
- Keep `external.copilot` as a Copilot-specific integration capability, clearly separate from active provider readiness.

**Rationale**: The clarification requires both readiness and health surfaces, with readiness authoritative. Health is a concise operator view; readiness carries corrective detail. Making the provider optional in readiness preserves unrelated workflows.

**Alternatives considered**:
- New dedicated provider-diagnostics endpoint/page: rejected in favor of existing surfaces.
- Health-only or readiness-only reporting: rejected by the clarification.

## Decision 10: Secret handling

**Decision**: Read the DeepSeek key only from the process environment, capture it in a provider closure, and never place it in a dataclass field that is serialized, logged, or returned. Use fixed public failure messages. Redacted configuration errors name only the setting, never the value. DeepSeek sends the key only in the `Authorization` header. Copilot continues to use its existing authenticated session and environment allowlist.

**Rationale**: This directly satisfies the credential non-disclosure requirements and the constitution's data-boundary principle.

**Alternatives considered**:
- Store the key in `app.state`: rejected because application state could be inspected or serialized.
- Pass the key as a command argument or URL parameter: rejected because it would appear in process lists, logs, or caches.

## Decision 11: Frontend provider awareness

**Decision**: Extend the frontend provider set to both canonical identifiers, render provider labels from the validated response, and build the pre-submission disclosure from the non-secret `/api/health` `aiProvider` object. If the provider is not configured, not ready, or the health lookup fails, the disclosure says so and the request path remains fail-closed.

**Rationale**: The existing frontend hard-codes Copilot in provenance and disclosure. Provider-aware labels and disclosure are required for accurate attribution and the pre-submission disclosure requirement.

**Alternatives considered**:
- Keep a generic "configured provider" label: rejected because the disclosure must accurately identify the configured provider.
- Fetch full readiness on Assistant pages: rejected because readiness runs multiple workstation probes; the lightweight health object is sufficient.

## Decision 12: Report attribution

**Decision**: Render the report provider line from the validated canonical response identifier using a display-label mapping. Keep all other report validation, normalization, filename, path, and persistence behavior unchanged.

**Rationale**: The report must accurately identify the provider without secrets, while preserving the existing report contract and storage behavior.

**Alternatives considered**:
- Keep the Copilot label for all reports: rejected as inaccurate for DeepSeek.
- Store the raw provider payload: rejected for secret and raw-output reasons.

## Decision 13: Test strategy

**Decision**: Add focused tests for provider resolution/readiness, DeepSeek request construction and error mapping, no-fallback behavior, not-configured behavior, credential non-disclosure, report attribution, diagnostics contracts, and frontend provider handling. Update existing tests that hard-code Copilot as the only provider or as the implicit default. Run the full pytest suite.

**Rationale**: The constitution requires focused successful and failure-path coverage and preservation of existing workflows. Provider switching touches the API/frontend contract, so both sides need contract tests.

**Alternatives considered**:
- Only add DeepSeek tests: rejected because the shared contract and diagnostics change for both providers.

## Decision 14: Managed-service environment propagation

**Decision**: Extend `build_service_environment()` to copy only an explicit provider allowlist from the invoking environment, and add an optional `EnvironmentFile=-<config-dir>/ai-provider.env` to the generated systemd user unit. The environment file is operator-managed outside NOC Web application data and must be mode 0600. Never write provider secrets into the unit file, application data, or logs.

**Rationale**: The existing managed service deliberately sanitizes its environment and copies only approved settings. Without an allowlist and an optional environment file, the new provider settings would never reach the application under systemd. Restricting the allowlist preserves the existing security property that unrelated inherited variables such as `COPILOT_TOKEN` are not copied.

**Alternatives considered**:
- Copy the whole inherited environment: rejected because it would widen secret propagation and break the existing sanitization test.
- Put the key directly in the unit file: rejected because unit files are readable and are application-adjacent.
- Store provider settings in `runtime.json`: rejected because credentials must not be persisted in NOC Web application data.

## Open Questions

None. All `NEEDS CLARIFICATION` items from the specification were resolved during the clarification session, and the remaining decisions are implementation-level choices documented above.
