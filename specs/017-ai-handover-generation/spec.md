# Feature Specification: Provider-Independent AI Handover Generation

**Feature Branch**: `017-ai-handover-generation`

**Created**: 2026-11-11

**Status**: Draft

**Input**: User description: "Replace the Copilot-dependent noc-handover generation workflow with provider-independent handover generation using NOC Web's validated shift evidence and the configured AI provider.

The feature must work when GitHub Copilot CLI is completely unavailable or its allowance is exhausted. noc-handover and Copilot CLI must not be required for any Feature 017 acceptance criterion.

Build the handover only from validated NOC Web evidence for the selected shift, including shift notes, locally tracked tickets, open tickets, reviewed investigation findings, investigation lifecycle state, current Datadog incident context where already available through the read-only Datadog provider, dashboard/status information, and handover readiness.

ALL open tickets must be included in the handover. This is a mandatory completeness requirement and must not depend on AI judgment about importance.

Separate deterministic source-grounded handover content from AI-generated analysis. NOC Web should assemble mandatory factual sections first and use the configured AI provider only for bounded advisory synthesis where appropriate.

DeepSeek Flash must be supported through the existing provider-independent AI architecture. Do not automatically fall back to Copilot or another provider.

AI output must cite only supplied available evidence identifiers. Preserve the strict fail-closed evidence-reference model used by the Assistant and AI investigation generation. Unsupported, invented, unavailable, or malformed evidence references must cause generation to fail rather than being silently repaired.

Stale or partial evidence must be explicitly identified. The AI must never describe stale, partial, missing, or unavailable evidence as current or complete.

Handover preview must remain read-only and non-generative where practical. Any state-changing generation, regeneration, replacement, or delivery action must require explicit operator confirmation according to the existing NOC Web confirmation model.

Preserve the existing handover record format, selected-shift behavior, End Shift readiness/preflight, delivery preview, delivery confirmation, recipient handling, and local persistence contract unless a spec requirement explicitly needs a versioned compatible extension.

Preserve investigation provenance and reviewed-state boundaries. AI-generated unreviewed investigation findings must not be promoted into authoritative reviewed findings. Reviewed findings must remain distinguishable from advisory AI content.

Do not allow the AI provider to modify tickets, investigations, Datadog resources, shift notes, handover state, recipients, Jira, or any external system. AI generation is advisory and local persistence remains controlled by NOC Web.

Never send provider credentials or Datadog credentials to the AI evidence package. Never expose or persist DEEPSEEK_API_KEY, NOC_WEB_DEEPSEEK_API_KEY, DD_ACCESS_TOKEN, NOC_WEB_DATADOG_ACCESS_TOKEN, Authorization headers, or other credentials in prompts returned to clients, logs, handover Markdown, API responses, frontend output, exceptions, or persisted operational data.

Preserve zero Datadog mutation requests.

Update End Shift, health, readiness, status, and documentation so noc-handover and Copilot are optional compatibility capabilities rather than requirements for core handover generation.

Keep Microsoft 365 handover delivery behavior separate from AI generation. Do not redesign the delivery transport unless required for compatibility with the new generated handover.

Add regression coverage for mandatory inclusion of every open ticket, evidence minimization, valid DeepSeek generation, exact evidence citations, stale/partial evidence qualification, malformed output, invalid citations, provider timeout/unavailability, no automatic fallback, credential non-disclosure, zero noc-handover/Copilot requirement, explicit confirmation, preview behavior, regeneration, persisted handover compatibility, End Shift readiness, and existing delivery workflow compatibility."

## Clarifications

### Session 2026-11-11

- Q: If the configured AI provider is unavailable, times out, or fails during a confirmed handover generation, should the handover fail closed or persist the deterministic mandatory content without advisory synthesis? → A: Fail closed; preserve any existing handover and do not persist a deterministic-only fallback.
- Q: Where should AI-generated advisory synthesis appear in the persisted handover record so deterministic facts and reviewed findings remain clearly separated? → A: It is validated internally and retained only in provenance/internal validation; it is not emitted as an AI-specific section in the final handover.
- Q: Which tickets must count as open for the mandatory complete ticket list when ticket sources are stale, partial, or temporarily unavailable? → A: Include every ticket currently open across all validated local and remote ticket sources, including stale/partial cache entries with explicit qualification; fail closed only if no validated source can establish the open set.
- Q: Should every confirmed handover generation invoke the configured AI provider, or may NOC Web skip AI and persist deterministic content when advisory synthesis is not appropriate? → A: Always invoke the configured provider for internal advisory validation; no deterministic-only path exists outside provider-failure handling.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate a complete handover from validated shift evidence (Priority: P1)

An operator ends a shift and requests the official handover for the selected shift. NOC Web assembles the
mandatory factual handover content from validated local evidence, including every open ticket, without
requiring noc-handover, GitHub Copilot CLI, or Datadog MCP.

**Why this priority**: This is the core replacement for the Copilot-dependent handover workflow. A handover
that omits an open ticket or depends on an unavailable tool is operationally unsafe.

**Independent Test**: With a selected shift containing shift notes, locally tracked tickets, multiple open
tickets, reviewed investigation findings, investigation lifecycle state, dashboard/status data, and
available read-only Datadog context, generate the handover with noc-handover and Copilot absent. Verify
every open ticket appears in the mandatory section and the handover is persisted locally.

**Acceptance Scenarios**:

1. **Given** validated shift evidence and open tickets, **When** the operator confirms generation, **Then**
   NOC Web assembles and persists the mandatory factual handover without invoking noc-handover, Copilot CLI,
   or Datadog MCP.
2. **Given** zero open tickets, **When** the handover is generated, **Then** the open-ticket section
   explicitly states that there are no open tickets.
3. **Given** many open tickets, **When** the handover is generated, **Then** every open ticket is included;
   if the volume exceeds the validated bound, generation fails closed rather than omitting or truncating
   tickets.
4. **Given** stale, partial, missing, or unavailable evidence, **When** the handover is generated, **Then**
   the affected evidence is explicitly identified in the handover.
5. **Given** a selected shift, **When** the handover is generated, **Then** the local record uses that
   selected shift and the existing handover persistence contract.

---

### User Story 2 - Keep advisory AI synthesis evidence-grounded and fail closed (Priority: P1)

An operator and reviewer can trust that AI-generated handover analysis is clearly advisory, cites only
supplied available evidence, and fails closed rather than silently repairing invalid output or implying
that stale/partial evidence is complete.

**Why this priority**: Handover content is used to transfer operational responsibility. Invented citations,
missing evidence qualification, or malformed AI output must never become part of an authoritative handover.

**Independent Test**: Supply valid handover evidence and provider outputs containing exact citations,
unsupported identifiers, aliases, URLs, malformed sections, stale/partial claims, and provider failures.
Verify only evidence-grounded advisory output can be persisted, and every invalid case fails closed without
replacing an existing handover.

**Acceptance Scenarios**:

1. **Given** AI output cites only supplied available evidence identifiers, **When** validation runs, **Then**
   the advisory analysis is accepted internally and its citations are retained only in provenance/internal
   validation, not in the final handover body.
2. **Given** AI output cites an unsupported, invented, unavailable, or malformed identifier, **When**
   validation runs, **Then** handover generation fails closed and no new handover is persisted.
3. **Given** evidence is stale, partial, missing, or unavailable, **When** AI output describes it as current
   or complete, **Then** generation fails closed.
4. **Given** the configured AI provider times out, is unavailable, or configuration is incomplete,
   **When** generation is requested, **Then** generation fails closed without provider fallback and the
   existing handover remains intact.
5. **Given** AI output would modify a ticket, investigation, Datadog resource, shift note, handover state,
   recipient, or external system, **Then** it is rejected; AI remains advisory and local persistence is
   controlled by NOC Web.

---

### User Story 3 - Preview, confirm, regenerate, and deliver without changing existing contracts (Priority: P1)

An operator can preview the deterministic handover content without AI generation or state changes, and must
explicitly confirm generation, regeneration, replacement, or delivery. Existing archive, delivery preview,
recipient handling, and Microsoft 365 delivery behavior remain compatible.

**Why this priority**: Handover generation and delivery are state-changing operational actions. Preview and
confirmation preserve human accountability and prevent accidental replacement or delivery.

**Independent Test**: Preview a selected shift and verify deterministic mandatory content is shown with zero
AI calls and zero state changes. Confirm generation, regenerate an existing handover, and exercise delivery
preview/send; verify explicit confirmation, archive/rollback behavior, recipient validation, and unchanged
Microsoft 365 transport behavior.

**Acceptance Scenarios**:

1. **Given** a selected shift, **When** the operator opens handover preview, **Then** the preview is
   read-only, non-generative, and does not create, replace, archive, or deliver a handover.
2. **Given** a valid preview, **When** the operator explicitly confirms generation, **Then** the configured
   AI provider is invoked for internal advisory validation and a new deterministic handover may be persisted.
3. **Given** an existing handover, **When** regeneration is confirmed, **Then** the previous handover is
   archived and restored if regeneration fails.
4. **Given** a generated handover, **When** delivery is previewed or sent, **Then** existing recipient
   validation, delivery confirmation, and Microsoft 365 transport behavior remain unchanged and separate
   from AI generation.
5. **Given** an existing handover record, **When** the new workflow is used, **Then** the record remains
   readable and deliverable under the existing local persistence contract.

---

### User Story 4 - Preserve investigation review boundaries and operational compatibility (Priority: P2)

Reviewed findings remain authoritative while AI-generated or unreviewed content remains clearly advisory.
End Shift readiness, health, readiness, status, selected-shift behavior, and documentation no longer require
noc-handover or Copilot for core handover generation.

**Why this priority**: The new generation path must not blur reviewed operational evidence with advisory AI
content or regress the operational checks operators rely on.

**Independent Test**: Generate a handover containing reviewed and unreviewed investigation findings. Verify
reviewed findings appear as authoritative evidence, unreviewed/AI content is clearly advisory, and End Shift
readiness/health/status remain usable with noc-handover and Copilot absent.

**Acceptance Scenarios**:

1. **Given** reviewed investigation findings, **When** the handover is generated, **Then** they remain
   authoritative and distinguishable from AI advisory content.
2. **Given** unreviewed investigation findings or AI-generated investigation analysis, **When** the
   handover is generated, **Then** they are labeled advisory and are not promoted into reviewed findings.
3. **Given** noc-handover and Copilot are unavailable, **When** End Shift readiness, health, readiness,
   status, and documentation are reviewed, **Then** they describe those tools as optional compatibility
   capabilities rather than requirements for handover generation.
4. **Given** the selected shift changes, **When** a preview or generation is requested, **Then** the
   selected-shift association remains correct.
5. **Given** the existing delivery workflow, **When** this feature is delivered, **Then** Microsoft 365
   delivery behavior and recipient handling remain unchanged.

---

### Edge Cases

- There are no open tickets, duplicate ticket identifiers, stale ticket cache entries, partial ticket
  data, or no validated ticket source able to establish the open set.
- The number of open tickets exceeds the validated evidence/request bound.
- Shift notes are missing, empty, or contain malformed content.
- Reviewed investigation findings are absent while unreviewed findings or advisory AI content exist.
- Datadog incident context is stale, partial, unavailable, or absent.
- Dashboard/status information is unavailable or stale.
- Handover readiness or End Shift preflight blocks generation.
- An existing handover is present; regeneration or replacement is requested without confirmation.
- AI output is empty, malformed, missing a required section, over-bound, or cites unsupported, invented,
  unavailable, or malformed evidence.
- AI output claims stale/partial/missing/unavailable evidence is current or complete.
- The configured AI provider is not configured, times out, is unavailable, or fails.
- The operation is retried while another generation is in progress.
- Regeneration archive verification or rollback fails.
- Microsoft 365 delivery is unavailable after a handover is generated.
- Credential-like content appears in evidence, AI output, logs, or persisted handover data.
- The selected shift changes between preview and confirmation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Handover generation MUST obtain evidence only from validated NOC Web evidence for the selected
  shift, including shift notes, locally tracked tickets, open tickets, reviewed investigation findings,
  investigation lifecycle state, already-available read-only Datadog incident context, dashboard/status
  information, and handover readiness.
- **FR-002**: The handover MUST include every ticket currently open across all validated local and remote
  ticket sources in a mandatory deterministic section, including stale or partial cache entries with
  explicit qualification. Ticket inclusion MUST NOT depend on AI judgment about importance, severity, or
  narrative relevance. If no validated source can establish the open set, generation MUST fail closed.
- **FR-003**: NOC Web MUST assemble mandatory factual handover sections deterministically before invoking AI.
  The configured AI provider MAY be used only for bounded advisory analysis that is validated internally.
  AI MUST NOT author or modify the mandatory factual sections or ticket list, and AI advisory text and
  citations MUST NOT be emitted into the final user-facing handover body.
- **FR-004**: The evidence package MUST be bounded, minimized, validated, and limited to information required
  for handover generation and citation. It MUST exclude credentials, Authorization headers, unrelated
  environment values, raw provider payloads, and unsupported fields.
- **FR-005**: The system MUST use the configured AI provider established by Feature 014 and MUST support
  DeepSeek Flash through the existing DeepSeek provider configuration. Every confirmed generation MUST
  invoke the configured provider for the dedicated advisory synthesis section.
- **FR-006**: The system MUST NOT automatically fall back between DeepSeek, Copilot, or any other provider.
  A failure of the configured provider MUST fail closed with a sanitized operator-visible error.
- **FR-007**: AI output MUST cite only supplied available evidence identifiers using the exact bracketed
  format `[evidence:<stable-id>]`. The system MUST preserve the strict fail-closed evidence-reference
  model used by the Assistant and AI investigation generation.
- **FR-008**: Unsupported, invented, unavailable, malformed, shortened, aliased, URL-form, or otherwise
  non-canonical evidence references MUST cause generation to fail. The system MUST NOT repair, remap, fuzzy
  match, or post-process invalid citations into valid ones.
- **FR-009**: Every AI-generated advisory item MUST contain at least one supplied available evidence
  citation in the exact `[evidence:<stable-id>]` format. If no supplied evidence supports a claim, the
  claim MUST be omitted.
- **FR-010**: Stale, partial, missing, or unavailable evidence MUST be explicitly identified in deterministic
  handover content and in advisory output. Every advisory item that relies on stale evidence MUST say
  "stale"; every item that relies on partial evidence MUST say "partial" or otherwise clearly qualify
  incompleteness in the same item. AI MUST NOT describe such evidence as current, complete,
  verified-current, comprehensive, or fully available.
- **FR-011**: AI output MUST remain advisory and internal to validation and provenance. It MUST NOT be
  emitted into the final user-facing handover as AI-specific sections or internal citation syntax. It MUST
  NOT modify tickets, investigations, Datadog resources, shift notes, handover state, recipients, Jira, or
  any external system.
- **FR-012**: Local persistence MUST remain controlled by NOC Web. AI output MUST NOT directly create,
  replace, archive, or deliver a handover.
- **FR-013**: Handover preview MUST be read-only and non-generative where practical. Preview MUST NOT invoke
  AI, persist a handover, replace an existing record, or deliver anything.
- **FR-014**: Generation, regeneration, replacement, and delivery MUST require explicit operator confirmation
  according to the existing confirmation model. Confirmation MUST NOT be inferred from preview or AI output.
- **FR-015**: The existing handover record format, section structure, selected-shift association, local
  persistence, and archive contract MUST be preserved. The provenance sidecar and internal advisory
  validation metadata MUST be versioned and backward compatible with existing handover records.
- **FR-016**: The system MUST preserve existing End Shift readiness/preflight, delivery preview, delivery
  confirmation, recipient handling, and Microsoft 365 delivery behavior, separate from AI generation.
- **FR-017**: Reviewed investigation findings MUST remain authoritative and distinguishable from advisory AI
  content. Unreviewed or AI-generated investigation content MUST NOT be promoted into reviewed findings.
- **FR-018**: The system MUST NOT expose or persist provider credentials, Datadog credentials, API keys,
  access tokens, Authorization headers, or other secrets in prompts returned to clients, logs, handover
  Markdown, API responses, frontend output, exceptions, or persisted operational data.
- **FR-019**: The workflow MUST issue zero Datadog mutation requests. It MUST use only already-available
  read-only Datadog incident context and MUST NOT alter Feature 015 retrieval behavior.
- **FR-020**: noc-handover, GitHub Copilot CLI, and Datadog MCP MUST NOT be required for any handover
  generation acceptance criterion. Generation MUST work when noc-handover and Copilot are completely
  unavailable or their allowances are exhausted.
- **FR-021**: End Shift, health, readiness, status, and documentation MUST describe noc-handover and Copilot
  as optional compatibility capabilities rather than requirements for core handover generation.
- **FR-022**: Handover readiness MUST gate generation. Missing, invalid, or unavailable required evidence
  MUST fail closed with an actionable, sanitized error.
- **FR-023**: The mandatory deterministic content MUST include shift notes, all open tickets, reviewed
  findings and investigation lifecycle context, available Datadog/dashboard/status context, evidence
  availability, and handover readiness.
- **FR-024**: If the number of open tickets or any mandatory evidence item exceeds the validated bound,
  generation MUST fail closed rather than omit, truncate, or silently summarize any ticket. If no validated
  ticket source can establish the open ticket set, generation MUST also fail closed.
- **FR-025**: AI output MUST use a bounded, required structure. Missing sections, malformed output,
  placeholder-only content, or over-bound output MUST fail closed.
- **FR-026**: Evidence packages and AI requests and responses MUST be bounded. Over-bound content MUST fail
  closed rather than be silently truncated.
- **FR-027**: Availability disclosure for stale, partial, missing, or unavailable evidence MUST be
  system-authored and persisted with the handover. AI output that contradicts it MUST be rejected.
- **FR-028**: A confirmed generation MUST persist the handover atomically using the existing local storage
  contract. An existing handover MUST NOT be overwritten without the existing conflict/regeneration rules.
- **FR-029**: Regeneration MUST require explicit confirmation, archive the previous handover, and restore it
  if generation fails or produces no valid replacement.
- **FR-030**: Delivery preview and delivery MUST remain separate from AI generation. Recipient validation,
  delivery confirmation, and Microsoft 365 transport behavior MUST remain unchanged.
- **FR-031**: The AI provider MUST NOT be granted tools or authority to modify tickets, investigations,
  Datadog resources, shift notes, handover state, recipients, Jira, or external systems.
- **FR-032**: Existing investigation inspection, lifecycle, reviewed-finding publication, provenance,
  Datadog links, and selected-shift navigation MUST remain compatible.
- **FR-033**: Existing handover records MUST remain readable, previewable, and deliverable after this feature
  is introduced.
- **FR-034**: The system MUST include regression coverage for mandatory open-ticket inclusion, evidence
  minimization, valid DeepSeek generation, exact citations, stale/partial qualification, malformed output,
  invalid citations, provider timeout/unavailability, no automatic fallback, credential non-disclosure,
  zero noc-handover/Copilot requirement, explicit confirmation, preview behavior, regeneration, persisted
  handover compatibility, End Shift readiness, and delivery compatibility.
- **FR-035**: If the configured AI provider is unavailable, times out, or fails, generation MUST fail closed
  and MUST NOT persist a partially generated or deterministic-only handover as a fallback. The existing
  handover MUST remain intact.
- **FR-036**: A preview or pending generation MUST be invalidated when the selected shift, evidence, or
  handover target changes.
- **FR-037**: AI output MUST NOT contain or cause the handover to contain credentials, secret-like values,
  Authorization headers, or unrelated environment values.
- **FR-038**: The feature MUST NOT redesign Microsoft 365 delivery or mix delivery responsibilities into the
  AI provider.

### Security and Privacy Constraints

- Credentials in scope include DeepSeek API keys (`DEEPSEEK_API_KEY`,
  `NOC_WEB_DEEPSEEK_API_KEY`), Datadog access tokens (`DD_ACCESS_TOKEN`,
  `NOC_WEB_DATADOG_ACCESS_TOKEN`), Authorization headers, raw provider credentials, and unrelated process
  environment values.
- The AI provider request MUST contain only the bounded, minimized handover evidence package and the
  instructions required for advisory synthesis.
- Credentials MUST NOT appear in client-returned prompts, logs, reports, handover Markdown, API responses,
  frontend output, exceptions, archives, or persisted operational data.
- Error responses and logs MUST be sanitized before they reach operators or persisted records.
- AI output MUST be treated as untrusted text and MUST NOT become an authoritative or executable operational
  instruction.

### Key Entities *(include if feature involves data)*

- **Handover Evidence Package**: The bounded, minimized, validated evidence for the selected shift, including
  shift notes, all open tickets, reviewed findings, investigation lifecycle state, available Datadog/status
  context, dashboard/readiness information, source identifiers, provenance, and availability states.
- **Mandatory Handover Content**: The deterministic, system-authored factual sections and complete open-ticket
  list that NOC Web assembles before AI generation.
- **Advisory AI Synthesis**: Bounded AI-generated analysis that is validated internally, cites only supplied
  available evidence identifiers, and cannot modify mandatory content, appear as AI-specific sections in the
  final handover, or modify external systems.
- **Handover Evidence Reference**: A stable identifier, source link, provenance, and availability state for a
  supplied evidence item. AI citations must exactly match available references.
- **Handover Availability Disclosure**: System-authored metadata and operator-visible text identifying stale,
  partial, missing, or unavailable evidence independently of AI output.
- **Handover Preview**: A read-only, non-generative view of deterministic content, evidence availability, and
  intended generation inputs.
- **Operator Confirmation**: The explicit action authorizing generation, regeneration, replacement, or
  delivery; it cannot be inferred.
- **Persisted Handover Record**: The existing local handover file, sections, archive, delivery metadata, and
  selected-shift association, extended only in a versioned backward-compatible way if required.
- **Investigation Review Boundary**: The distinction between authoritative reviewed findings and unreviewed
  or advisory AI-generated investigation content.
- **Handover Readiness**: The existing End Shift/preflight state that determines whether generation is
  allowed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of confirmed handover generations complete without noc-handover, Copilot CLI, or Datadog
  MCP calls.
- **SC-002**: 100% of open tickets across validated local and remote sources, including stale/partial entries
  with qualification, appear in the mandatory handover section; 0 open tickets are omitted or filtered by AI
  judgment.
- **SC-003**: Mandatory factual sections are assembled before AI invocation in 100% of generations, and 0
  mandatory sections are AI-authored or AI-modified.
- **SC-004**: With DeepSeek Flash configured, 100% of valid confirmed handover generations complete within
  the configured provider timeout and persist a handover.
- **SC-005**: 100% of AI advisory items cite at least one supplied available evidence identifier; 0
  unsupported, invented, unavailable, or malformed references are accepted.
- **SC-006**: 100% of stale, partial, missing, or unavailable evidence is explicitly labeled; 0 AI outputs
  describe it as current or complete.
- **SC-007**: 100% of malformed, missing-section, over-bound, invalid-citation, provider-timeout, and
  provider-unavailable cases fail closed with 0 new handovers persisted and existing handovers intact.
- **SC-008**: 0 automatic provider fallback events occur in failure tests.
- **SC-009**: Credential scans across prompts, logs, handover Markdown, API responses, frontend output,
  exceptions, archives, and persisted data report 0 exposed credentials.
- **SC-010**: The workflow issues 0 Datadog mutation requests.
- **SC-011**: Preview invokes the AI provider in 0 cases and performs 0 state-changing handover actions.
- **SC-012**: 100% of generation, regeneration, replacement, and delivery actions require explicit operator
  confirmation.
- **SC-013**: Existing handover format, archive/regeneration, delivery preview/send, recipient validation,
  and Microsoft 365 compatibility tests pass unchanged.
- **SC-014**: 100% of reviewed findings remain authoritative and distinguishable; 0 unreviewed or AI-generated
  findings are promoted to reviewed findings.
- **SC-015**: End Shift, health, readiness, status, and documentation contain 0 statements that noc-handover
  or Copilot are required for core handover generation.
- **SC-016**: Existing persisted handovers remain readable, previewable, and deliverable under the unchanged
  local persistence contract.
- **SC-017**: 0 AI advisory text, AI-specific sections, or internal `[evidence:...]` citation markers appear
  in the final user-facing handover; validated AI citations are retained only in provenance/internal
  validation.
- **SC-018**: 100% of final handovers use deterministic ticket counts; 0 AI-generated count claims are
  accepted or emitted.

## Assumptions

- The existing local handover format, section structure, archive behavior, and delivery contract remain
  authoritative; the provenance sidecar and internal advisory validation metadata are versioned and
  backward compatible.
- Existing ticket, open-ticket, shift-note, investigation, Datadog, dashboard/status, and readiness sources
  are validated and remain authoritative for evidence assembly.
- "All open tickets" means every ticket currently open across validated local and remote ticket sources,
  including stale or partial cache entries with explicit qualification. If no validated source can
  establish the open set, generation fails closed. Over-bound ticket volume fails closed rather than
  omitting tickets.
- Datadog incident context is used only where already available through the existing read-only provider;
  this feature does not add Datadog mutations or change Feature 015 retrieval behavior.
- Feature 014 provides the configured AI provider abstraction and existing DeepSeek Flash configuration; no
  provider is selected by default and no automatic fallback is permitted.
- Preview is deterministic and non-generative; every final generation invokes the configured AI provider for
  bounded advisory validation that is not emitted into the final handover body. Provider failure fails closed
  and preserves the existing handover; there is no deterministic-only final-generation path.
- Reviewed investigation findings are the only authoritative investigation findings in mandatory handover
  content. Unreviewed or AI-generated investigation content may appear only as clearly labeled advisory
  synthesis.
- Microsoft 365 delivery remains a separate post-handover operation with its existing preview, confirmation,
  recipient, and transport behavior.
- Existing handover readiness and End Shift preflight gates remain in force.
- The feature does not add new credential stores or external integrations. Private local NOC notes are
  excluded from handover and AI evidence while their tickets remain mandatory in the open-ticket list.
- `noc-handover` and GitHub Copilot CLI remain optional compatibility capabilities for other workflows, if
  any, but are not required by this feature.
