# Feature Specification: Provider-Independent AI Support

**Feature Branch**: `014-ai-provider-architecture`

**Created**: 2026-11-10

**Status**: Draft

**Input**: User description: "Add provider-independent AI support for the NOC Web Assistant and AI Actions. Replace the current hard dependency on GitHub Copilot CLI with a configurable provider architecture supporting DeepSeek API and the existing GitHub Copilot CLI provider. DeepSeek Flash should be supported without changing the existing Assistant response contract, evidence model, read-only AI boundary, operator-reviewed findings, report validation, or safety behavior. Provider credentials must never be returned through APIs, frontend responses, logs, reports, or persisted application data. Provider failures must remain controlled and fail closed. Do not add automatic provider fallback. Expose the configured provider and its readiness through appropriate diagnostic surfaces without leaking secrets. Preserve GitHub Copilot CLI as an optional provider. Scope this feature only to Assistant and AI Actions; do not change Datadog incident retrieval, noc-inv investigation generation, or noc-handover generation."

## Clarifications

### Session 2026-11-10

- Q: How should operators configure the active provider and supply its credentials? → A: Environment variables/process environment only; provider selection and credentials are supplied at process start.
- Q: What should "provider readiness" verify? → A: Static readiness only: provider selection is valid and required credentials are present; no live provider call.
- Q: Which existing diagnostic surface should show the configured provider and its readiness? → A: Both existing readiness and health surfaces; readiness is authoritative, health shows a concise matching state.
- Q: What canonical provider identifiers should the Assistant response and AI Action reports use? → A: Provider-level identifiers `deepseek-api` and `github-copilot-cli`; model remains separate configuration.
- Q: What should happen when no provider is configured? → A: Start normally; Assistant and AI Actions fail closed as unavailable, and diagnostics report "not configured."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Use the Assistant with the configured provider (Priority: P1)

An NOC operator uses the Assistant and the four predefined AI Actions exactly as before, while the configured inference provider is either the DeepSeek API using a DeepSeek Flash model or the existing GitHub Copilot CLI.

**Why this priority**: The value of the feature is provider independence. Operators must receive the same bounded, evidence-grounded behavior regardless of which approved provider supplies inference.

**Independent Test**: Configure each supported provider in turn, run representative Assistant questions and all four AI Actions, and verify that responses, evidence labels, advisory findings, and generated reports keep the same structure, validation outcomes, and safety boundaries.

**Acceptance Scenarios**:

1. **Given** the DeepSeek API with a DeepSeek Flash model is the configured provider, **When** an operator asks a supported question about the selected shift, **Then** the response preserves the existing response contract, evidence model, advisory labels, and limitations behavior.
2. **Given** the GitHub Copilot CLI is the configured provider, **When** an operator runs any predefined AI Action, **Then** the existing behavior, report validation, and report persistence remain unchanged.
3. **Given** the configured provider changes between deployments or explicit configuration updates, **When** the Assistant is used, **Then** every new request uses only the newly configured provider and reports the provider that actually served it.

---

### User Story 2 - Keep provider credentials secret (Priority: P1)

An NOC operator or administrator can configure provider credentials without any credential value appearing in API responses, frontend content, logs, reports, or persisted application data.

**Why this priority**: A credential leak would compromise an external account and violate the project's data-boundary and observability principles. Provider independence must not weaken secret handling.

**Independent Test**: Configure a recognizable sentinel credential for each provider, exercise successful and failing Assistant and AI Action requests, then search all API responses, frontend output, logs, generated reports, and persisted application files for the sentinel value.

**Acceptance Scenarios**:

1. **Given** a configured provider credential, **When** any Assistant or AI Action endpoint returns success, **Then** the response contains no credential value, token, key fragment, or derivable secret.
2. **Given** the selected provider fails authentication, times out, or returns an error containing credential-like content, **When** the failure is presented and logged, **Then** the failure text is sanitized and contains no credential value.
3. **Given** an AI Action completes successfully, **When** its report is persisted, **Then** the report contains no credential value and no provider authentication material.
4. **Given** diagnostic surfaces report provider state, **When** they are viewed, **Then** they identify the configured provider and readiness without exposing any credential value.

---

### User Story 3 - Fail closed without automatic fallback (Priority: P1)

An NOC operator receives a clear, controlled limitation when the configured provider is unavailable, misconfigured, unauthenticated, times out, or returns unusable output, and NOC Web never silently switches to another provider.

**Why this priority**: Silent fallback would obscure which external service handled NOC data and could turn a broken configuration into an apparently healthy Assistant. Failure must remain explicit and attributable.

**Independent Test**: Make the configured provider fail in each defined way while another supported provider is also configured and available; verify that no request is sent to the other provider, no report is created, and the operator sees the existing controlled failure category.

**Acceptance Scenarios**:

1. **Given** DeepSeek is the configured provider and its credentials are missing or invalid, **When** an operator uses the Assistant, **Then** the response reports the provider as unavailable and does not invoke or fall back to the Copilot CLI.
2. **Given** the Copilot CLI is the configured provider and it is not installed or not authenticated, **When** an operator runs an AI Action, **Then** the action fails with a clear limitation and no report is saved.
3. **Given** the configured provider times out or returns malformed, partial, or unvalidatable output, **When** an Assistant request completes, **Then** the existing unavailable, timeout, or invalid status is reported, the answer is not presented as successful, and no report is created.
4. **Given** the configured provider is unavailable, **When** the operator continues working, **Then** existing non-Assistant NOC Web views and workflows remain available and unchanged.

---

### User Story 4 - Diagnose provider readiness without secrets (Priority: P2)

An NOC operator or administrator can see which inference provider is configured and whether it is ready for Assistant and AI Action use, along with safe corrective guidance when it is not ready.

**Why this priority**: Provider configuration is now an operational dependency. Without visible readiness, a misconfigured provider could be mistaken for an Assistant outage or a healthy state.

**Independent Test**: Inspect the existing diagnostic surfaces with each provider configured and not configured, with credentials present and absent, and verify accurate provider identity and readiness states with no secret material.

**Acceptance Scenarios**:

1. **Given** a valid provider configuration, **When** the operator views the diagnostic surface, **Then** it identifies the configured provider and reports it as ready without revealing credentials.
2. **Given** a selected provider is missing required credentials or is otherwise invalid, **When** the operator views the diagnostic surface, **Then** it reports a not-ready state and safe corrective guidance for that provider.
3. **Given** no provider is configured, **When** the operator views the diagnostic surface, **Then** it clearly reports that the Assistant provider is not configured and does not claim readiness.
4. **Given** the diagnostic surface itself fails or is stale, **When** the operator views it, **Then** the failure is presented as a limitation and does not substitute an inferred successful provider state.

---

### User Story 5 - Preserve Copilot CLI as an optional provider (Priority: P3)

An NOC operator can continue using the existing authenticated GitHub Copilot CLI when it is explicitly selected, while environments that select DeepSeek are not required to install or authenticate the Copilot CLI.

**Why this priority**: The existing capability must not be removed, but it must stop being a mandatory system-wide dependency.

**Independent Test**: Run Assistant and AI Action acceptance coverage with Copilot CLI selected and available, with Copilot CLI selected and absent, and with DeepSeek selected while Copilot CLI is absent.

**Acceptance Scenarios**:

1. **Given** Copilot CLI is explicitly selected and its authenticated session is available, **When** the operator uses the Assistant, **Then** behavior matches the existing Copilot-backed implementation.
2. **Given** DeepSeek is explicitly selected and Copilot CLI is not installed, **When** the operator uses the Assistant, **Then** the Assistant operates normally and Copilot absence does not affect the selected provider.
3. **Given** Copilot CLI is selected but unavailable, **When** the operator views provider readiness, **Then** Copilot is reported as not ready rather than silently replaced.

---

### Edge Cases

- The configured provider name is unknown, unsupported, empty, or malformed; the system fails closed with a clear configuration limitation and no fallback.
- Both providers are configured and available, or both are configured and failing; only the explicitly selected provider is ever used per request.
- Provider credentials are present but expired or rejected; static readiness may report ready based on presence, but Assistant requests fail closed, and diagnostics do not claim credential validity or provider reachability.
- Provider credentials are absent; the system distinguishes "not configured" from "configured but failing," starts normally, keeps non-Assistant workflows available, and fails Assistant and AI Actions closed without selecting a default provider.
- The selected provider returns a response that violates the Assistant contract; the response is rejected, the operator sees a controlled failure, and no report is saved.
- The selected provider echoes prompt content, evidence content, or credential-like strings in an error; only sanitized failure information is surfaced.
- Provider configuration changes while the application is running; behavior is predictable, and diagnostics reflect the effective configuration rather than a stale assumption.
- A request times out at the provider boundary; the operator receives the existing timeout category and no partial answer or report.
- Context is insufficient and the provider is never invoked; the existing not-invoked/limited behavior is preserved and is not reported as provider unavailability.
- A required source is stale or unavailable while the selected provider works; existing evidence and limitation behavior is unchanged.
- Diagnostic output is requested by a surface that must not expose secrets; provider identity and readiness are shown but no credential value or reversible representation is included.
- The selected provider is ready but returns empty arrays for evidence-rich input; existing report and response validation rules still decide whether the result is acceptable, independent of provider.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST support explicit configuration of exactly one active inference provider for the Assistant and the four predefined AI Actions, choosing between at least the DeepSeek API and the GitHub Copilot CLI.
- **FR-002**: The system MUST support a DeepSeek Flash model through the DeepSeek API while preserving the existing Assistant behavior, response structure, evidence model, and advisory semantics.
- **FR-003**: The system MUST keep inference behind a provider-neutral boundary so that Assistant and AI Action behavior does not depend on provider-specific request or response conventions.
- **FR-004**: The Assistant response contract MUST remain structurally and semantically unchanged: the same response fields, status values, evidence references, advisory categories, limitation behavior, and validation rules apply regardless of provider. The value that identifies the serving provider MUST accurately reflect the active provider and MUST be one of the canonical provider identifiers `deepseek-api` or `github-copilot-cli`.
- **FR-005**: The system MUST preserve the read-only AI boundary for every provider: no provider may receive operational records as command arguments, have tools available, execute commands, access external systems, refresh data, or perform operational actions.
- **FR-006**: The system MUST supply only the existing bounded, minimized selected-shift evidence to the configured provider and MUST NOT widen the evidence model, raw-evidence boundary, or Datadog investigation mediation pathway.
- **FR-007**: Operator-reviewed findings MUST continue to come only from existing operator-reviewed investigation context; no provider, including DeepSeek, may author, infer, or alter them.
- **FR-008**: AI Action report validation, normalization, collision-safe persistence, and read-only viewing MUST remain unchanged in behavior; reports MUST identify the provider that generated the advisory result using the canonical provider identifier without including prompts, raw provider output, credentials, tokens, or raw evidence.
- **FR-009**: Provider selection and provider credentials MUST be supplied only through environment variables/process environment at application start and MUST NOT be returned through any API, included in frontend responses, written to logs, embedded in reports, or persisted in NOC Web application data.
- **FR-010**: No credential value, token, key fragment, or reversible secret representation may appear in provider identity values, readiness details, failure messages, validation errors, or diagnostic output.
- **FR-011**: The system MUST fail closed for every provider failure mode, including missing or invalid credentials, unsupported provider selection, unavailability, authentication failure, timeout, malformed response, schema violation, and validation failure. A failure MUST NOT produce a success-shaped answer or a saved AI Action report.
- **FR-012**: The system MUST NOT automatically fall back from the configured provider to any other provider, including when another provider is configured, available, or already authenticated.
- **FR-013**: The system MUST preserve the existing distinction between provider unavailability and context insufficiency, including the not-invoked/limited behavior when the provider is not called.
- **FR-014**: The system MUST expose the configured provider and its readiness through the existing readiness diagnostic surface and the existing health diagnostic surface, distinguishing at least ready, not ready, and not configured states, with safe corrective guidance when not ready. The readiness surface MUST be authoritative for configured provider identity and readiness, and the health surface MUST show a concise state that does not contradict it. Readiness MUST be determined from static configuration validity and required credential presence and MUST NOT make a live provider request.
- **FR-015**: Provider readiness reporting MUST be accurate for the effective static configuration, MUST NOT require or expose credentials to the viewer, MUST NOT claim that credentials were authenticated or that the provider is reachable, and MUST NOT claim readiness based only on the existence of a different provider.
- **FR-016**: The system MUST preserve GitHub Copilot CLI as an optional provider: selecting DeepSeek MUST NOT require Copilot installation or authentication, and selecting Copilot MUST preserve the existing authenticated-session behavior.
- **FR-017**: The system MUST define and enforce explicit provider timeout, failure, and stale/unknown readiness behavior before the provider is used in an operator workflow.
- **FR-018**: Provider selection changes MUST be explicit and deliberate; the system MUST NOT infer, alternate between, or randomly select providers per request.
- **FR-019**: Before submission, the operator-facing provider disclosure MUST accurately identify the configured provider and state that provider-controlled handling or retention may apply, without exposing credentials.
- **FR-020**: The system MUST isolate provider failures from the rest of NOC Web so that existing non-Assistant views, workflows, confirmations, and error handling remain usable and unchanged.
- **FR-021**: This feature MUST NOT change Datadog incident retrieval, noc-inv investigation generation, noc-handover generation, or the existing noc-inv/Copilot MCP investigation evidence pathway.
- **FR-022**: The system MUST include acceptance coverage for each supported provider covering the preserved response contract, evidence and advisory labeling, read-only boundary, prohibited actions, operator-reviewed findings, report validation and persistence, credential non-disclosure, controlled failure, absence of fallback, readiness diagnostics, and scope isolation.
- **FR-023**: When no provider is configured, the application MUST start normally, non-Assistant NOC Web workflows MUST remain available, Assistant and AI Actions MUST fail closed as unavailable, diagnostics MUST report the provider as not configured, and the system MUST NOT select any default provider.

### Key Entities

- **Provider Configuration**: The explicit selection of one active inference provider, its supported model choice, and its bounded operational settings; it determines which external service may handle Assistant and AI Action inference.
- **Provider Identifier**: The canonical, non-secret value used to attribute an Assistant response or AI Action report to its serving provider: `deepseek-api` or `github-copilot-cli`. The model choice is separate from the identifier.
- **Provider Credential**: A secret value used to authenticate with a provider, held outside application responses, logs, reports, and persistent NOC Web data.
- **Provider Readiness Status**: A non-secret statement of the effective provider identity and whether it is ready, not ready, or not configured, including safe corrective guidance.
- **Provider Request Envelope**: The existing bounded selected-shift evidence and question material submitted to the active provider; its content and minimization rules do not vary by provider.
- **Assistant Response**: The existing transient operator-facing result that separates source-grounded facts, operator-reviewed findings, AI observations, recommendations, evidence, and limitations, now attributable to the active provider.
- **Assistant Action Report**: The existing validated, normalized, advisory selected-shift report, now additionally identifying the active provider without exposing secrets or raw provider material.
- **Provider Failure**: A controlled, sanitized indication that the active provider was unavailable, misconfigured, unauthenticated, timed out, returned invalid output, or failed validation, with no successful substitute.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Across representative Assistant questions and all four AI Actions, 100% of acceptance scenarios pass with each supported provider, with no change to response structure, evidence labels, advisory categories, or report validation outcomes.
- **SC-002**: In credential-scanning checks covering successful and failing requests, API responses, frontend content, logs, generated reports, and persisted application data contain 0 credential values or reversible secret representations.
- **SC-003**: In failure scenarios covering missing credentials, invalid credentials, unsupported provider selection, unavailability, timeout, malformed output, and validation failure, 100% fail closed with a controlled limitation and 0 requests are sent to a non-selected provider.
- **SC-004**: In static readiness checks for each provider and for the unconfigured state, 100% of readiness and health diagnostic results identify the effective provider and the correct ready/not-ready/not-configured state, agree with each other, and expose no secrets or live provider call.
- **SC-005**: In regression coverage, 100% of the existing Assistant and AI Action safety behaviors—read-only boundary, prohibited actions, operator-reviewed findings, report validation, report persistence, and no-fallback expectations—remain satisfied.
- **SC-006**: In scope regression coverage, 0 changes occur to Datadog incident retrieval, noc-inv investigation generation, noc-handover generation, or the existing investigation evidence boundary.
- **SC-007**: Operators can complete the same representative Assistant and AI Action tasks with either supported provider without additional steps beyond the existing disclosure acknowledgement.
- **SC-008**: With no provider configured, 100% of non-Assistant workflows remain usable, 100% of Assistant and AI Action attempts fail closed with a not-configured limitation, and 0 requests are sent to any default provider.

## Assumptions

- The active provider is chosen by explicit operator-managed configuration rather than a per-request provider selector or automatic detection; this feature does not add an in-app provider-switching UI.
- Provider selection and credentials are supplied only through environment variables/process environment at application start; NOC Web reads them at runtime and does not persist them.
- DeepSeek Flash is supported as a DeepSeek model family, with the exact model identifier configurable. Supporting it does not require a different Assistant response schema.
- Provider readiness reports static configuration validity and required credential presence without making a live provider request. Readiness does not assert that credentials are accepted or that the provider is reachable, consistent with the existing precedent of not executing external network calls during diagnostics.
- The existing feature 006 Assistant and AI Action behavior is the regression baseline and is not expanded, removed, or reinterpreted by this feature.
- The existing authenticated GitHub Copilot CLI remains available as an optional provider and is not required for a DeepSeek-selected deployment.
- When no provider is configured, the application still starts and non-Assistant workflows remain available; only Assistant and AI Actions are unavailable, with no default provider selected.
- Provider-controlled handling and retention remain outside NOC Web's control and must continue to be disclosed rather than represented as absent.
- Existing confirmation-gated workflows remain the only path for state-changing operational work; provider selection does not affect them.
- Only Assistant and AI Action inference paths are in scope; Datadog incident retrieval, noc-inv investigation generation, and noc-handover generation retain their current implementation and contracts.
