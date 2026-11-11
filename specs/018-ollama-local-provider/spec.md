# Feature Specification: Ollama Local AI Provider

**Feature Branch**: `018-ollama-local-provider`

**Created**: 2026-11-11

**Status**: Draft

**Input**: User description: "Add Ollama as an operator-selected local AI provider for NOC Web, primarily intended as a backup when the configured DeepSeek API provider is unavailable, timed out, exhausted, or intentionally not used.

The provider must integrate through the existing provider-independent AI architecture created in Features 014, 016, and 017. Existing Assistant, AI Actions, investigation generation, and handover generation validators and safety boundaries must remain authoritative regardless of provider.

Support an Ollama server reachable over the network. The base URL must be configurable and must never be hard-coded because the Ollama host may receive a different DHCP address. Support configuration such as NOC_WEB_OLLAMA_BASE_URL and NOC_WEB_OLLAMA_MODEL.

Use qwen3:8b as the documented initial recommended local model, while keeping the model configurable.

The implementation must consume only Ollama's response field as model output. The thinking field, context arrays, duration metadata, model-loading metadata, and other Ollama response metadata must never enter Assistant responses, investigation content, handovers, prompts returned to clients, persisted operational data, or downstream AI validators.

Local Ollama use must never be an automatic fallback from DeepSeek. A DeepSeek failure must continue to fail closed. The operator may explicitly choose or confirm a Retry with Local AI action after seeing the primary-provider failure.

Do not automatically retry a failed request against Ollama. Local-provider invocation requires an explicit provider selection or explicit operator retry confirmation.

The operator-selected local retry must use the exact same validated evidence snapshot or an explicitly refreshed and re-previewed evidence snapshot according to the existing workflow's stale-preview rules. It must never silently use different evidence than the failed primary-provider request.

Ollama output must pass the same existing response-schema, evidence-ID, citation, freshness, partial-evidence, credential-exclusion, output-size, lifecycle, and provenance validators used by DeepSeek. Local inference receives no additional authority.

Support the Assistant, AI Actions, Feature 016 investigation generation, and Feature 017 handover advisory generation through the local provider without duplicating or weakening their existing validation contracts.

For local investigation and handover generation, exact evidence citations remain mandatory. Unsupported, malformed, unavailable, non-authoritative, partial, or stale evidence must continue to be handled according to the existing Feature 016 and Feature 017 validators.

Provider provenance must explicitly identify ollama and the configured model. Local AI output must never be mislabeled as DeepSeek, Copilot, reviewed operator content, or deterministic system-authored evidence.

Ollama readiness must be distinct from primary-provider readiness. A sleeping, powered-off, unreachable, misconfigured, or model-missing Ollama host must report the local provider as unavailable without making NOC Web core readiness fail when DeepSeek remains usable.

Static application health/readiness pages must not trigger model inference simply to determine local-provider configuration. Network/model availability checks must occur only through an explicit recheck/probe action or when the operator intentionally invokes the local provider.

Bound all Ollama network operations with explicit connection/read deadlines appropriate for LAN inference. Never wait indefinitely for a sleeping or unreachable gaming PC.

Reject redirects and unexpected hosts. The configured Ollama endpoint must be a validated HTTP or HTTPS base URL with no embedded credentials, query string, fragment, or arbitrary request path. Never forward Authorization headers, DeepSeek credentials, Datadog credentials, Microsoft 365 credentials, or other process secrets to Ollama.

No Ollama authentication secret is required for the initial LAN deployment. Do not invent or persist a credential.

Do not expose DEEPSEEK_API_KEY, NOC_WEB_DEEPSEEK_API_KEY, DD_ACCESS_TOKEN, NOC_WEB_DATADOG_ACCESS_TOKEN, Authorization headers, environment values, or unrelated credentials to the Ollama prompt, logs, client responses, errors, or persisted operational files.

Fail closed on unreachable host, connection refused, timeout, missing configured model, malformed Ollama JSON, missing response field, non-string response, oversized response, unsupported content, or model output rejected by downstream validators.

Do not treat Ollama thinking as usable output or evidence. Ignore it entirely.

Preserve DeepSeek API as the primary configured provider by default. Do not change existing installations to Ollama automatically.

Update provider health/status/UI so operators can distinguish:
- Primary provider: DeepSeek API
- Optional local provider: Ollama
- local endpoint configured/unconfigured
- configured local model
- local availability when explicitly probed
- whether Retry with Local AI is available after a provider failure

Add explicit Retry with Local AI behavior only where safe for the existing workflow and require operator confirmation before invoking the local model after a primary-provider failure.

Preserve all existing preview-before-create, explicit confirmation, read-only Datadog, investigation lifecycle, reviewed/unreviewed boundaries, handover completeness, all-open-ticket requirements, and Microsoft 365 delivery behavior.

Do not modify Datadog resources, Jira, tickets, investigations, shift notes, Microsoft 365 objects, or any external system as a consequence of Ollama inference.

Add regression coverage for endpoint validation, configurable model, qwen3:8b configuration, unreachable/sleeping host, connection refused, timeout, missing model, malformed Ollama response, missing response field, oversized output, thinking-field exclusion, credential non-disclosure, no automatic fallback, explicit local retry confirmation, provenance, Assistant compatibility, investigation compatibility, handover compatibility, exact evidence citations, stale/partial evidence behavior, provider isolation, and DeepSeek remaining the default primary."

## Clarifications

### Session 2026-11-11

- Q: Should Ollama be allowed as an explicitly configured default provider, or only as a per-request/retry choice while DeepSeek remains the configured primary? → A: Ollama may be explicitly configured as the default provider or chosen per request/retry; DeepSeek remains the default for existing installations and no automatic switch occurs.
- Q: Which operational workflows should offer Retry with Local AI after a primary-provider failure? → A: All four workflows: Assistant, AI Actions, Feature 016 investigation generation, and Feature 017 handover advisory generation, using a bounded server-side retry snapshot of the exact failed request evidence.
- Q: What should an explicit Ollama readiness probe verify without performing model inference? → A: Bounded endpoint reachability plus presence of the configured model in Ollama's model list, without inference or model loading.
- Q: How long should the bounded server-side failed-request evidence snapshot remain available for Retry with Local AI? → A: 10 minutes in memory; expired retries require a fresh request or re-preview, and no evidence is persisted to disk for retry.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Explicitly retry a failed primary request with local AI (Priority: P1)

After a configured primary-provider request fails, an operator can explicitly confirm **Retry with Local AI** to run the same workflow against the optional Ollama provider, using the same validated evidence the failed request used. No local inference occurs automatically.

**Why this priority**: This is the operator-value path for the local provider. It must preserve the evidence reviewed by the operator and must never become an invisible fallback.

**Independent Test**: Simulate a primary-provider timeout for Assistant, AI Actions, investigation generation, and handover generation. Verify the failure is fail-closed, a local retry is offered only after the failure, no Ollama request occurs without explicit confirmation, and a confirmed retry uses the same validated evidence snapshot and existing validators.

**Acceptance Scenarios**:

1. **Given** a DeepSeek failure in Assistant, AI Actions, investigation generation, or handover advisory generation, **When** the operator sees the failure, **Then** the workflow remains failed and no Ollama request occurs automatically.
2. **Given** a failed primary request with a usable bounded retry snapshot, **When** the operator explicitly confirms Retry with Local AI, **Then** the local provider is invoked with the same validated evidence snapshot.
3. **Given** the 10-minute retry snapshot is stale or expired, **When** local retry is requested, **Then** the existing stale-preview rules require an explicit refresh and re-preview before local inference.
4. **Given** local inference returns output rejected by the workflow's existing validators, **Then** the retry fails closed and no valid-shaped record is persisted.
5. **Given** local inference succeeds, **Then** provenance identifies `ollama` and the configured model, and the output remains advisory according to the existing workflow rules.

---

### User Story 2 - Configure and validate the local provider safely (Priority: P1)

An operator can configure an Ollama base URL and model, explicitly probe local availability, and receive actionable failures when the local host is unreachable, sleeping, timed out, missing the model, or returns malformed output.

**Why this priority**: The local provider is a LAN dependency. Configuration, endpoint validation, bounded networking, and fail-closed behavior must be correct before any workflow depends on it.

**Independent Test**: Using fake Ollama servers, verify configurable endpoint/model and `qwen3:8b` default recommendation; reject invalid endpoints, redirects, unexpected hosts, credentials, query strings, fragments, and arbitrary paths; verify unreachable/refused/timeout/missing-model/malformed/missing-response/non-string/oversized cases fail closed; verify explicit probe behavior and no inference from static health/readiness.

**Acceptance Scenarios**:

1. **Given** a valid configured endpoint and model, **When** the local provider is explicitly selected or probed, **Then** it uses that endpoint and model.
2. **Given** no Ollama endpoint or model is configured, **Then** the local provider is reported unavailable without changing the primary provider or core readiness.
3. **Given** an invalid, credentialed, query-bearing, fragment-bearing, path-bearing, redirecting, or unexpected-host endpoint, **Then** local invocation fails closed.
4. **Given** a sleeping, unreachable, refused, timed-out, or model-missing host, **Then** local invocation fails closed within the configured LAN deadlines.
5. **Given** malformed JSON, a missing or non-string response field, unsupported content, or oversized output, **Then** the local provider fails closed and ignores all non-response metadata.
6. **Given** an explicit local probe, **Then** it checks endpoint reachability and configured model presence without inference.
7. **Given** static health/readiness pages, **Then** they do not trigger model inference or network probing.

---

### User Story 3 - Preserve every existing validator and safety boundary (Priority: P1)

Assistant, AI Actions, Feature 016 investigation generation, and Feature 017 handover advisory generation use the same validation, citation, freshness, partial-evidence, credential, size, lifecycle, and provenance rules regardless of provider.

**Why this priority**: Local inference must not become a weaker path or gain authority that DeepSeek does not have.

**Independent Test**: Run the same valid, malformed, unsupported-citation, stale, partial, unavailable, oversized, and credential-bearing fixtures through DeepSeek and Ollama. Verify both providers receive identical validator outcomes, and local output cannot bypass any existing fail-closed rule.

**Acceptance Scenarios**:

1. **Given** Assistant or AI Actions local output, **When** validation runs, **Then** the existing Assistant schema, evidence, credential, and size rules remain authoritative.
2. **Given** investigation local output with unsupported or fabricated citations, **Then** Feature 016 validation rejects it exactly as it would DeepSeek output.
3. **Given** handover local output with an unqualified stale/partial claim or invalid count claim, **Then** Feature 017 validation rejects it exactly as it would DeepSeek output.
4. **Given** local investigation output, **Then** it cannot modify lifecycle, reviewed/unreviewed state, or provenance boundaries.
5. **Given** local handover output, **Then** all open tickets remain deterministically included and local AI text cannot become the final deterministic handover content.

---

### User Story 4 - Distinguish primary and local provider readiness and availability (Priority: P2)

Operators can distinguish the primary DeepSeek provider from the optional Ollama provider, see the configured local endpoint/model, explicitly probe local availability, and know whether Retry with Local AI is available after a failure.

**Why this priority**: Operators need clear, non-secret visibility without making an optional LAN dependency part of core readiness.

**Independent Test**: Render health/status/UI with DeepSeek configured, Ollama unconfigured, Ollama configured but sleeping, Ollama probed unavailable, and Ollama probed available. Verify the primary and local states are distinct and core readiness remains usable when DeepSeek is healthy.

**Acceptance Scenarios**:

1. **Given** DeepSeek and Ollama are configured, **Then** health/status distinguish primary provider and optional local provider.
2. **Given** Ollama is unconfigured or unavailable, **Then** the primary provider remains the default and core readiness does not fail solely because Ollama is unavailable.
3. **Given** an explicit local probe, **Then** the probe result reports local availability without exposing credentials or running model inference.
4. **Given** a primary-provider failure, **Then** the UI indicates whether Retry with Local AI is available and requires explicit confirmation.
5. **Given** existing installations, **Then** they remain on DeepSeek and are not automatically changed to Ollama. An operator MAY explicitly configure Ollama as the default provider.

---

### Edge Cases

- DeepSeek times out, is unavailable, exhausted, or intentionally not used.
- The operator declines or cancels Retry with Local AI.
- Ollama is sleeping, powered off, unreachable, refusing connections, or exceeding LAN deadlines.
- Ollama is configured but the model is missing or still loading.
- Ollama returns malformed JSON, missing `response`, non-string `response`, empty output, unsupported content, or oversized output.
- Ollama returns only `thinking` or thinking plus metadata without usable `response`.
- Ollama returns valid `response` plus thinking/context/duration/model metadata that must be ignored.
- The local endpoint includes credentials, a query, a fragment, a non-root path, redirects, or an unexpected host.
- The local endpoint is configured but unavailable; the primary provider remains healthy.
- The local retry is requested after the evidence snapshot expired or changed.
- Local output cites unsupported, unavailable, non-authoritative, partial, or stale evidence.
- Local output contains credentialed or secret-like content.
- Both primary and local providers are unavailable.
- Static readiness/health is viewed while Ollama is sleeping.
- An operator attempts to use local AI as an implicit fallback without confirmation.
- Local provider output would exceed size or schema bounds.
- Local provider output attempts to alter tickets, investigations, handover state, or deliverable content.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST add Ollama as an operator-selected provider through the existing provider-independent AI architecture used by Features 014, 016, and 017.
- **FR-002**: DeepSeek API MUST remain the default provider for existing installations. Ollama MAY be explicitly configured as the default provider by an operator, but existing installations MUST NOT be changed to Ollama automatically.
- **FR-003**: A DeepSeek failure MUST continue to fail closed. The system MUST NOT automatically fall back or retry the failed request against Ollama.
- **FR-004**: Local-provider invocation MUST require either an explicit operator-configured default provider selection, an explicit per-request provider selection, or explicit Retry with Local AI confirmation after the primary-provider failure. No automatic Ollama request is permitted.
- **FR-005**: An operator-confirmed local retry MUST use the exact validated evidence snapshot used by the failed primary request or an explicitly refreshed and re-previewed snapshot under the existing stale-preview rules. It MUST NOT silently use different evidence.
- **FR-037**: All four retry-capable workflows MUST retain the exact failed request evidence in a bounded in-memory server-side retry snapshot for 10 minutes; an expired or unavailable snapshot MUST fail closed and require a fresh request or re-preview, and retry evidence MUST NOT be persisted to disk.
- **FR-006**: The Ollama base URL and model MUST be configurable through existing environment configuration, including `NOC_WEB_OLLAMA_BASE_URL` and `NOC_WEB_OLLAMA_MODEL`. The existing provider-selection configuration MAY explicitly select Ollama as the default. The base URL MUST NOT be hard-coded.
- **FR-007**: `qwen3:8b` MUST be documented as the initial recommended local model while remaining configurable.
- **FR-008**: The configured Ollama endpoint MUST be a validated HTTP or HTTPS base URL with no embedded credentials, query string, fragment, or arbitrary request path. Redirects and unexpected hosts MUST be rejected.
- **FR-009**: The system MUST NOT require, invent, or persist an Ollama authentication secret for the initial LAN deployment.
- **FR-010**: The system MUST consume only Ollama's `response` field as model output. `thinking`, context arrays, duration metadata, model-loading metadata, and all other Ollama metadata MUST be ignored and MUST NOT enter client responses, investigation content, handovers, prompts, persisted operational data, or downstream validators.
- **FR-011**: The system MUST fail closed on unreachable host, connection refused, timeout, missing configured model, malformed Ollama JSON, missing response field, non-string response, oversized response, unsupported content, or downstream validator rejection.
- **FR-012**: All Ollama network operations MUST use explicit connection/read deadlines appropriate for LAN inference and MUST NOT wait indefinitely.
- **FR-013**: The system MUST NOT forward Authorization headers, DeepSeek credentials, Datadog credentials, Microsoft 365 credentials, environment values, or other process secrets to Ollama.
- **FR-014**: The system MUST NOT expose DeepSeek keys, Datadog tokens, Authorization headers, environment values, Ollama response metadata, or unrelated credentials in client responses, logs, errors, prompts, or persisted operational files.
- **FR-015**: Ollama output MUST pass the same Assistant and AI Actions response-schema, evidence, credential, and size validators used by DeepSeek.
- **FR-016**: Ollama investigation output MUST pass the same Feature 016 citation, freshness, partial-evidence, lifecycle, provenance, and fail-closed validators used by DeepSeek.
- **FR-017**: Ollama handover advisory output MUST pass the same Feature 017 evidence-ID, bracketed citation, stale/partial qualification, count-claim, advisory-boundary, and fail-closed validators used by DeepSeek.
- **FR-018**: Local inference MUST receive no additional authority. It MUST NOT modify Datadog, Jira, tickets, investigations, shift notes, handover state, Microsoft 365 objects, recipients, or any external system.
- **FR-019**: Provider provenance MUST explicitly identify `ollama` and the configured model. Local output MUST NOT be mislabeled as DeepSeek, Copilot, reviewed operator content, or deterministic system-authored evidence.
- **FR-020**: Ollama readiness MUST be distinct from primary-provider readiness. Sleeping, powered-off, unreachable, misconfigured, or model-missing local hosts MUST report the local provider unavailable without making core readiness fail when DeepSeek remains usable.
- **FR-021**: Static health/readiness pages MUST NOT trigger model inference or network probing merely to determine local-provider configuration. Network/model checks MAY occur only through an explicit recheck/probe action or intentional local invocation.
- **FR-038**: An explicit local probe MUST perform a bounded endpoint reachability check and verify the configured model is present in Ollama's model list, without model inference or token generation.
- **FR-022**: Provider health/status/UI MUST distinguish the primary provider, optional local provider, configured/unconfigured local endpoint, configured local model, local availability after explicit probe, and whether Retry with Local AI is available.
- **FR-023**: Retry with Local AI MUST be offered for Assistant, AI Actions, Feature 016 investigation generation, and Feature 017 handover advisory generation where the failure leaves a usable bounded retry snapshot, and MUST require explicit operator confirmation. It MUST NOT be automatically triggered by primary-provider failure.
- **FR-024**: Existing preview-before-create, explicit confirmation, stale-preview invalidation, read-only Datadog, investigation lifecycle, reviewed/unreviewed boundaries, handover completeness, all-open-ticket inclusion, deterministic counts, and Microsoft 365 delivery behavior MUST be preserved.
- **FR-025**: Local investigation and handover generation MUST continue to require exact evidence citations internally, even if the final operational handover does not display internal citation markers.
- **FR-026**: Local handover output MUST NOT override deterministic counts or mandatory deterministic sections; all open tickets remain deterministically included regardless of local AI output.
- **FR-027**: Local provider failures MUST preserve existing records, prior handovers, investigation state, and provenance. A failed local retry MUST NOT replace or corrupt prior valid output.
- **FR-028**: The system MUST reject local output containing credentials, secret-like values, unsupported content, malformed sections, or over-bound data.
- **FR-029**: The local provider MUST be isolated from the primary provider's credentials, readiness, retry policy, and fallback behavior. Local configuration MUST NOT silently change the primary provider.
- **FR-030**: The system MUST preserve the existing provider-independent validator contracts without duplicating or weakening them for Ollama.
- **FR-031**: The system MUST include regression coverage for endpoint validation, configurable model, `qwen3:8b`, unreachable/sleeping/refused/timeout/missing-model cases, malformed/missing/non-string/oversized response, thinking/metadata exclusion, credential non-disclosure, no automatic fallback, explicit local retry confirmation, provenance, Assistant compatibility, investigation compatibility, handover compatibility, exact citations, stale/partial behavior, provider isolation, and DeepSeek remaining the default primary.
- **FR-032**: Local provider invocation MUST be observable through the existing status/error mechanisms without exposing secrets or operational evidence contents.
- **FR-033**: Local retry MUST fail closed if the operator cancels confirmation, if the evidence snapshot is unavailable, or if the local provider is unavailable.
- **FR-034**: The local provider MUST NOT receive prompts containing unrelated environment values, provider metadata, or operational data beyond the minimized evidence required by the workflow.
- **FR-035**: Existing Assistant, AI Actions, investigation, and handover UI/API contracts MUST remain consistent when local-provider selection, retry, and readiness fields are added.
- **FR-036**: Local provider response parsing MUST ignore Ollama thinking, context, duration, model-loading, and other metadata even when present alongside a valid `response`.

### Security and Privacy Constraints

- Credentials in scope include DeepSeek keys (`DEEPSEEK_API_KEY`,
  `NOC_WEB_DEEPSEEK_API_KEY`), Datadog tokens (`DD_ACCESS_TOKEN`,
  `NOC_WEB_DATADOG_ACCESS_TOKEN`), Authorization headers, Microsoft 365 credentials, and unrelated
  process environment values.
- Ollama MUST receive only the minimized workflow evidence and instructions authorized by the
  existing Feature 014/016/017 architecture.
- No Ollama authentication secret is required; the system MUST NOT invent, request, or persist one.
- The local endpoint MUST reject embedded credentials, query strings, fragments, arbitrary paths,
  redirects, and unexpected hosts.
- Secrets and Ollama metadata MUST NOT appear in client responses, logs, errors, prompts,
  investigation records, handover Markdown, provenance sidecars, archives, or other persisted data.

### Key Entities *(include if feature involves data)*

- **Local Provider Configuration**: Operator-selected Ollama endpoint and model, with recommended
  `qwen3:8b`, configuration presence, and static readiness.
- **Provider Selection / Retry Confirmation**: The explicit operator action authorizing local
  inference after a primary-provider failure; never inferred automatically.
- **Evidence Snapshot Reference**: The exact validated evidence snapshot used by the failed primary
  request, retained in a 10-minute in-memory retry snapshot, or the refreshed and re-previewed
  snapshot required by stale-preview rules.
- **Ollama Response**: The bounded model output derived only from the `response` field; all thinking,
  context, duration, model-loading, and other metadata are ignored.
- **Local Provider Probe Result**: Explicit operator-triggered availability result for the local
  endpoint/model, without model inference on static health/readiness.
- **Provider Provenance**: Provider identity (`ollama`) and configured model retained with generated
  advisory output and operational records.
- **Existing Workflow Outputs**: Assistant response, AI Actions output, investigation record, and
  handover advisory/deterministic record, all validated by their existing contracts.
- **Local Provider Failure**: Unreachable, refused, timeout, missing model, malformed, missing or
  non-string response, oversized, unsupported, credential-bearing, or validator-rejected output that
  must fail closed.
- **Primary Provider State**: DeepSeek remains primary and default; its failure is surfaced without
  automatic fallback.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of local-provider invocations occur only after explicit operator selection or
  explicit Retry with Local AI confirmation; 0 automatic fallback or automatic retry events occur.
- **SC-002**: 100% of local retries use the exact failed-request evidence snapshot or an explicitly
  refreshed and re-previewed snapshot; 0 silent evidence substitutions occur.
- **SC-003**: 100% of valid local outputs pass the same existing workflow validators as primary-provider
  outputs; 0 weaker validation paths exist.
- **SC-004**: 100% of invalid citations, stale/partial contradictions, malformed output, oversized
  output, and credential-bearing output fail closed for both providers.
- **SC-005**: 100% of local provider provenance identifies `ollama` and the configured model; 0 local
  output is mislabeled as DeepSeek, Copilot, reviewed content, or deterministic system content.
- **SC-006**: 0 secrets, Authorization headers, provider credentials, environment values, or Ollama
  thinking/metadata appear in client responses, logs, errors, prompts, persisted data, or final
  handover Markdown.
- **SC-007**: 100% of invalid, credentialed, query-bearing, fragment-bearing, path-bearing,
  redirecting, or unexpected-host endpoints are rejected.
- **SC-008**: 100% of unreachable, refused, timed-out, missing-model, malformed, missing-response,
  non-string, and oversized local requests fail closed within configured LAN deadlines.
- **SC-009**: Static health/readiness pages invoke 0 local model requests and 0 implicit network
  probes.
- **SC-010**: Ollama unavailability causes 0 core-readiness failures when DeepSeek remains usable.
- **SC-011**: DeepSeek remains the default provider in 100% of existing configurations; 0 automatic
  migrations to Ollama occur, while explicit Ollama default selection is honored.
- **SC-012**: Existing Assistant, AI Actions, investigation, and handover regression suites pass with
  the local provider enabled or unavailable.
- **SC-013**: All open handover tickets remain deterministically included in 100% of local-provider
  handovers; 0 AI/local count claims override deterministic counts.
- **SC-014**: 0 external systems are modified as a consequence of Ollama inference.
- **SC-015**: Operators can distinguish primary/local provider state, configured endpoint/model,
  explicit probe availability, and Retry with Local AI availability.
- **SC-016**: 100% of local retries that are declined, cancelled, stale, or unavailable fail closed
  without replacing existing valid records.
- **SC-017**: 100% of failed-request retry snapshots expire within 10 minutes and 0 retry evidence is
  persisted to disk.
- **SC-018**: 100% of explicit local probes verify endpoint reachability and configured model presence
  without inference; 0 static health/readiness views trigger probing.

## Assumptions

- The provider-independent architecture from Features 014, 016, and 017 supports adding a local
  provider without changing the existing workflow validators.
- DeepSeek remains the default provider for existing installations. Ollama is optional and may be
  explicitly configured as the default, selected per request, or confirmed through Retry with Local
  AI; no automatic provider switch occurs.
- The Ollama server is reachable on a configurable HTTP/HTTPS LAN base URL and requires no
  authentication secret for the initial deployment. The configured URL is treated as a base origin
  with an empty or root path; reverse-proxy subpaths are out of scope for the initial deployment.
- `qwen3:8b` is the documented recommended initial model; operators may configure another model.
- Ollama exposes a `response` field for usable output and may also expose thinking/context/duration/
  model metadata that must be ignored.
- Existing evidence-snapshot, preview, confirmation, and stale-preview rules remain authoritative.
  Failed-request evidence may be retained in a bounded in-memory server-side retry snapshot for 10
  minutes across all four retry-capable workflows, with no retry evidence persisted to disk.
- Existing Assistant, AI Actions, Feature 016, and Feature 017 validators remain authoritative.
- Static readiness checks configuration only; explicit probes check endpoint reachability and
  configured model presence without inference.
- Local provider readiness is optional and separate from core readiness when DeepSeek is usable.
- Microsoft 365 delivery, read-only Datadog behavior, investigation lifecycle, reviewed/unreviewed
  boundaries, handover completeness, and all-open-ticket rules remain unchanged.
- No new credential store or Ollama authentication secret is introduced.
- Local inference remains advisory and cannot modify external systems.
