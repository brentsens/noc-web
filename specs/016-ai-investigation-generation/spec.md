# Feature Specification: Provider-Independent AI Investigation Generation

**Feature Branch**: `016-ai-investigation-generation`

**Created**: 2026-11-10

**Status**: Draft

**Input**: User description: "Replace the Copilot-dependent Datadog investigation-generation workflow with provider-independent investigation generation using Feature 015's validated read-only Datadog evidence and Feature 014's configured AI provider.

When an operator selects Create Investigation for a current Datadog incident, NOC Web must obtain the incident evidence exclusively through Feature 015. This includes validated incident details, referenced notebooks, referenced monitors, provenance, availability, relationship metadata, and partial/unavailable evidence states.

Pass only a bounded, minimized, validated evidence package to the configured AI provider. DeepSeek Flash must be supported through the existing DeepSeek provider configuration. DeepSeek must never receive the Datadog access token, Authorization headers, raw provider credentials, or unrelated process environment values.

Remove noc-inv, GitHub Copilot CLI, and Datadog MCP as requirements for this Datadog investigation-generation workflow. Feature 016 must work when Copilot CLI is completely unavailable or its allowance is exhausted.

Preserve preview-before-create behavior. Preview must remain non-generative and read-only. AI generation may occur only after the operator explicitly confirms creation.

AI output is advisory only. It must not modify Datadog, Jira, tickets, monitors, notebooks, incidents, shift records, or any external system. Feature 015 must remain structurally read-only toward Datadog.

Generated investigations must use the existing local investigation persistence, collision protection, provenance, lifecycle, review, and validation rules. Do not silently accept malformed or partially valid AI output.

Generated findings and conclusions must reference supplied evidence. Unsupported evidence identifiers, fabricated references, missing required sections, malformed output, provider timeout, unavailable provider, invalid evidence, or incomplete required configuration must fail closed.

Partial or unavailable Datadog evidence must remain explicitly identified as partial or unavailable and must never be presented by the AI as complete/current evidence.

Do not automatically fall back between DeepSeek and Copilot providers.

Preserve existing investigation inspection, lifecycle, reviewed findings, Datadog links, incident attachment behavior, and selected-shift synchronization.

Update Investigations UI wording so it describes the new read-only Datadog REST evidence and configured AI provider architecture rather than noc-inv and Copilot MCP.

Never expose or persist DEEPSEEK_API_KEY, NOC_WEB_DEEPSEEK_API_KEY, DD_ACCESS_TOKEN, NOC_WEB_DATADOG_ACCESS_TOKEN, Authorization headers, or other credentials in prompts returned to clients, logs, reports, generated Markdown, API responses, frontend output, exceptions, or persisted operational data.

Do not change noc-handover generation in this feature.

Add regression coverage for evidence minimization, successful DeepSeek generation, evidence-reference validation, partial evidence handling, malformed AI output, provider timeout/unavailability, credential non-disclosure, no automatic fallback, zero noc-inv/Copilot/MCP dependency, preview remaining non-generative, explicit operator confirmation, local investigation persistence, provenance, lifecycle compatibility, and zero Datadog mutation requests."

## Clarifications

### Session 2026-11-10

- Q: What is the minimum validated Datadog evidence required before the AI may generate an investigation rather than failing closed? → A: Validated incident detail only; missing or unavailable referenced notebooks and monitors are labeled partial rather than blocking generation.
- Q: How should generated findings and conclusions reference supplied evidence so validation can deterministically reject fabricated references? → A: Inline stable evidence identifiers such as `incident:<id>`, `notebook:<id>`, and `monitor:<id>`, with a persisted provenance map to source links and availability.
- Q: How should partial or unavailable Datadog evidence be disclosed in a generated investigation so the AI cannot misrepresent it as complete? → A: System-authored availability metadata and an operator-visible disclosure outside AI-authored content, persisted with the record; AI output that contradicts it is rejected.
- Q: When the operator confirms creation, should the AI use the exact Datadog evidence snapshot reviewed in Preview, or re-fetch and require the evidence to still match? → A: Use the exact previewed snapshot, revalidate its availability before generation, and invalidate the preview if the snapshot is no longer valid or has changed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Generate an investigation from validated incident evidence (Priority: P1)

An operator selects Create Investigation for a current Datadog incident. NOC Web gathers
the incident's validated read-only evidence through Feature 015 and, after the operator
confirms creation, asks the configured AI provider to produce an advisory investigation.
The workflow succeeds without noc-inv, GitHub Copilot CLI, or Datadog MCP, including when
Copilot is unavailable or its allowance is exhausted.

**Why this priority**: This is the core replacement for the Copilot-dependent workflow.
Without it, operators cannot generate an investigation from current Datadog evidence when
Copilot is unavailable.

**Independent Test**: With a current incident fixture, a valid Feature 015 evidence bundle,
and a configured DeepSeek Flash provider, complete Preview and then confirm creation. Verify
the investigation is generated from the Feature 015 evidence and persisted locally while
Copilot, noc-inv, and Datadog MCP are absent.

**Acceptance Scenarios**:

1. **Given** a current Datadog incident with valid Feature 015 evidence and a valid configured
   AI provider, **When** the operator confirms creation, **Then** the investigation is
   generated from that evidence and persisted using the existing local investigation rules, with
   the full Datadog title preserved as display metadata and a safe local identifier.
2. **Given** GitHub Copilot CLI is absent or its allowance is exhausted, **When** the operator
   confirms creation with DeepSeek Flash configured, **Then** generation proceeds without
   invoking Copilot, noc-inv, or Datadog MCP.
3. **Given** the operator opens Preview, **When** the operator has not explicitly confirmed
   creation, **Then** no AI generation occurs and no investigation record is created.
4. **Given** the operator has selected a shift, **When** the investigation is created, **Then**
   the local record uses that selected shift and retains its evidence provenance.
5. **Given** Feature 015 returns partial or unavailable evidence, **When** the investigation is
   generated, **Then** system-authored availability metadata and operator-facing disclosure
   identify the missing or unavailable evidence rather than presenting the evidence as complete.

---

### User Story 2 - Keep generated output evidence-grounded and fail closed (Priority: P1)

An operator and reviewer can trust that an AI-generated investigation is advisory, cites only
evidence that was supplied, and is rejected rather than silently accepted when the evidence,
provider, configuration, or output is invalid.

**Why this priority**: Advisory investigations are used in operational decisions. Unsupported
references or malformed output must never become authoritative operational records.

**Independent Test**: Supply a valid evidence bundle and multiple provider outputs: one valid,
one with an unsupported evidence identifier, one missing a required section, one malformed, and
one where a provider timeout or unavailable-provider error occurs. Verify only the valid output
can be persisted and every invalid case fails closed with an actionable error.

**Acceptance Scenarios**:

1. **Given** AI output cites only stable evidence identifiers supplied in the minimized package,
   **When** validation runs, **Then** the investigation may be persisted for operator review.
2. **Given** AI output cites an unsupported, unknown, fabricated, or non-canonical evidence
   identifier, **When** validation runs, **Then** generation fails closed and no investigation is
   persisted.
3. **Given** AI output is missing a required section, is malformed, or exceeds bounds,
   **When** validation runs, **Then** generation fails closed without silently repairing or
   accepting the output.
4. **Given** Feature 015 cannot provide valid incident detail, **When** generation is requested,
   **Then** generation fails closed; unavailable referenced notebooks and monitors are instead
   labeled partial when incident detail is valid.
5. **Given** the configured AI provider times out, is unavailable, or required configuration is
   incomplete, **When** generation is requested, **Then** the workflow fails closed without
   automatically falling back to another provider.
6. **Given** evidence is partial but sufficient for advisory output, **When** generation
   succeeds, **Then** system-authored availability disclosure names the missing evidence and every
   generated finding and conclusion remains bounded by that partial evidence state.

---

### User Story 3 - Preview and explicitly confirm before generation (Priority: P1)

An operator can inspect a non-generative preview of the evidence and investigation target before
any AI work occurs, and must explicitly confirm creation before the AI provider is called.

**Why this priority**: Preview and confirmation preserve human accountability and prevent
unintended AI generation or operational records.

**Independent Test**: Open Preview for a current incident and verify that no AI provider request
or persistence occurs. Change the selected shift, evidence, name, or notebook URL, and verify the
preview is invalidated. Confirm creation and verify generation starts only after the explicit
confirmation action.

**Acceptance Scenarios**:

1. **Given** a current incident, **When** the operator opens Preview, **Then** the preview shows
   the read-only evidence summary, provenance, availability, target shift, and intended target
   without invoking AI or creating a record.
2. **Given** a preview exists, **When** the selected shift, evidence, investigation name, or
   notebook URL changes, **Then** the preview is invalidated and must be reviewed again.
3. **Given** a valid preview, **When** the operator explicitly confirms creation, **Then** AI
   generation begins from the exact previewed evidence snapshot, subject to availability
   revalidation.
4. **Given** the operator cancels or does not confirm, **Then** no AI request, external action,
   or investigation persistence occurs.

---

### User Story 4 - Preserve investigation operations and operator-facing behavior (Priority: P2)

Existing investigation inspection, lifecycle transitions, reviewed findings, Datadog links,
incident attachment behavior, selected-shift synchronization, and local persistence continue to
work with investigations generated by the new provider-independent workflow.

**Why this priority**: The new generation path must not regress the operational records and review
workflows operators already use.

**Independent Test**: Generate an investigation through the new workflow, then exercise inspection,
lifecycle changes, reviewed-finding publication, Datadog link rendering, incident attachment, and
selected-shift navigation. Verify existing behavior and validation rules remain intact.

**Acceptance Scenarios**:

1. **Given** a generated investigation, **When** an operator inspects it, **Then** existing
   investigation detail, lifecycle, review, provenance, and Datadog link behavior remain available.
2. **Given** an existing investigation record, **When** the new workflow is used, **Then** existing
   records are not overwritten or corrupted and collision protection still applies.
3. **Given** the Investigations UI, **When** it describes investigation generation, **Then** it
   describes read-only Datadog REST evidence and the configured AI provider rather than requiring
   noc-inv, Copilot, or Datadog MCP.
4. **Given** the selected shift changes, **When** the operator creates an investigation, **Then**
   the selected-shift synchronization and create target remain correct.
5. **Given** the existing handover workflow, **When** this feature is delivered, **Then**
   noc-handover generation behavior is unchanged.

---

### Edge Cases

- Copilot CLI is not installed, is unavailable, or has exhausted its allowance while DeepSeek
  Flash is correctly configured.
- The configured AI provider is unavailable, times out, returns an error, or has incomplete
  required configuration.
- AI output is empty, malformed, missing a required section, oversized, or contains unsupported
  or fabricated evidence identifiers.
- AI output claims that partial or unavailable evidence is complete or current.
- Feature 015 evidence is invalid, over-bound, unavailable, or missing a referenced notebook or
  monitor.
- A referenced notebook has no supported cells or a required incident evidence item is absent.
- The operator changes the selected shift, investigation name, notebook URL, or evidence after
  previewing but before confirming creation.
- The operator cancels preview or creation.
- An investigation name collides with an existing record.
- The AI provider or evidence contains credential-like values or unrelated environment content
  that must not reach a prompt or persisted record.
- The configured provider fails and no automatic fallback is permitted.
- An existing investigation is already selected while a new investigation is created.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When an operator creates an investigation from a current Datadog incident, the
  system MUST obtain all Datadog evidence exclusively through Feature 015's validated read-only
  evidence service; it MUST NOT retrieve incident, notebook, or monitor evidence through any
  other source.
- **FR-002**: The evidence package MUST include validated incident detail, referenced notebooks,
  referenced monitors, stable evidence identifiers and source links, provenance, availability,
  relationship metadata, and explicit partial or unavailable evidence states.
- **FR-003**: The system MUST pass only a bounded, minimized, validated evidence package to the
  configured AI provider. The package MUST exclude raw provider payloads, credentials,
  Authorization headers, unrelated environment values, and evidence fields not needed for
  investigation generation or citation.
- **FR-004**: The system MUST validate the minimized evidence package before any AI request,
  including incident identity, evidence references, schema, size bounds, and internal consistency.
  Invalid or unavailable required incident detail MUST fail closed; missing or unavailable
  referenced notebooks and monitors are handled as partial evidence.
- **FR-005**: The system MUST use the configured AI provider established by Feature 014 and MUST
  support DeepSeek Flash through the existing DeepSeek provider configuration.
- **FR-006**: The investigation-generation workflow MUST NOT require noc-inv, GitHub Copilot CLI,
  or Datadog MCP. Confirmed generation MUST work when Copilot is completely unavailable or its
  allowance is exhausted.
- **FR-007**: The system MUST NOT automatically fall back between DeepSeek, Copilot, or any other
  provider. A failure of the configured provider MUST fail closed with an operator-visible,
  sanitized error.
- **FR-008**: Preview MUST remain non-generative and read-only. Preview MUST NOT call the AI
  provider, create or persist an investigation, or mutate any external system.
- **FR-009**: AI generation MAY occur only after the operator explicitly confirms creation
  immediately before generation. The system MUST NOT infer confirmation from preview, selection,
  or AI-generated content.
- **FR-010**: AI output MUST remain advisory. It MUST NOT directly or indirectly modify Datadog,
  Jira, tickets, monitors, notebooks, incidents, shift records, or any other external system, and
  Feature 015 MUST remain structurally read-only toward Datadog.
- **FR-011**: Generated investigations MUST use the existing local investigation persistence,
  collision protection, provenance, lifecycle states, reviewed-finding flow, and validation rules.
  The workflow MUST NOT bypass or weaken those rules.
- **FR-012**: The system MUST reject malformed, incomplete, or partially valid AI output. It MUST
  NOT silently accept, repair, or persist invalid output as a valid investigation.
- **FR-013**: Generated findings and conclusions MUST cite supplied evidence inline using stable
  identifiers in the form `incident:<id>`, `notebook:<id>`, or `monitor:<id>`, validated against
  the minimized package. Unsupported, unknown, fabricated, or non-canonical references MUST fail
  closed.
- **FR-014**: AI output MUST include all sections and fields required by the existing investigation
  validation contract. Missing or empty required sections MUST fail closed.
- **FR-015**: Partial or unavailable Datadog evidence MUST be explicitly identified through
  system-authored availability metadata and an operator-visible disclosure generated outside
  AI-authored content and persisted with the investigation record. AI output that characterizes
  partial or unavailable evidence as complete or current, or contradicts the system-authored
  disclosure, MUST be rejected.
- **FR-016**: Provider timeout, unavailability, authentication or configuration failure, or
  incomplete required configuration MUST fail closed without creating or replacing an
  investigation and without provider fallback.
- **FR-017**: A preview MUST be invalidated when the selected shift, incident, evidence, target
  investigation name, or notebook URL changes. Confirmed generation MUST use the exact bounded
  evidence snapshot reviewed in Preview; the system MUST revalidate the snapshot's availability
  before AI generation and MUST fail closed if the snapshot is no longer valid or has changed.
  The operator MUST review the updated preview before creation.
- **FR-018**: The system MUST preserve selected-shift synchronization. Datadog incident awareness
  MAY remain globally current, but investigation creation MUST target the selected shift.
- **FR-019**: Existing investigation inspection, lifecycle transitions, reviewed findings, Datadog
  links, incident attachment behavior, and selected-shift navigation MUST remain compatible.
- **FR-020**: Investigations UI wording MUST describe read-only Datadog REST evidence and the
  configured AI provider. It MUST NOT state or imply that noc-inv, GitHub Copilot CLI, or Datadog
  MCP are required for investigation generation.
- **FR-021**: The system MUST NOT expose or persist credentials, API keys, access tokens,
  Authorization headers, or other secrets in prompts returned to clients, logs, reports, generated
  Markdown, API responses, frontend output, exceptions, or persisted operational data.
- **FR-022**: Evidence minimization MUST exclude DeepSeek API keys, Datadog access tokens, raw
  provider credentials, Authorization headers, and unrelated process environment values. If
  credential-like content is detected in evidence or provider input, the system MUST redact it or
  fail closed.
- **FR-023**: This feature MUST NOT change noc-handover generation behavior.
- **FR-024**: The workflow MUST issue zero Datadog mutation requests. Any attempted or detected
  mutation MUST fail closed.
- **FR-025**: The feature MUST include regression coverage for evidence minimization, successful
  DeepSeek generation, evidence-reference validation, partial evidence handling, malformed AI
  output, provider timeout and unavailability, credential non-disclosure, no automatic fallback,
  zero noc-inv/Copilot/MCP dependency, non-generative preview, explicit operator confirmation,
  local investigation persistence, provenance, lifecycle compatibility, and zero Datadog mutation
  requests.
- **FR-026**: Evidence packages and AI requests and responses MUST be bounded in size. Over-bound
  evidence or output MUST fail closed rather than being silently truncated.
- **FR-027**: Operator-visible failures MUST be actionable and sanitized. They MUST NOT expose
  secrets, raw provider payloads, Authorization headers, or unrelated environment values.
- **FR-028**: AI-generated content MUST NOT become authoritative operational state. Generated
  investigations remain unreviewed until the existing human review process explicitly accepts them.
- **FR-029**: Backend response changes and frontend consumers MUST remain contract-consistent. Any
  changed request or response shape MUST update all in-repository consumers in the same change.
- **FR-030**: Generated investigations MUST persist a provenance map from every cited stable
  evidence identifier to its Datadog source link and availability state so reviewers can trace
  each citation to the Feature 015 evidence package.
- **FR-031**: Validated incident detail is the minimum required evidence for advisory generation.
  When incident detail is valid, missing or unavailable referenced notebooks and monitors MUST be
  explicitly labeled partial and MUST NOT block generation solely because they are unavailable.
  Invalid or unavailable required incident detail MUST fail closed.
- **FR-032**: Existing investigation name normalization, collision protection, and overwrite
  protections MUST apply to synthesized investigations; no existing record may be silently
  overwritten.
- **FR-033**: This feature MUST NOT weaken Feature 015's credential handling, GET-only behavior,
  timeout, response-size, schema-validation, or fail-closed protections.
- **FR-034**: The workflow MUST NOT require new Datadog credentials, write-scoped permissions, or
  direct Datadog access beyond the existing Feature 015 evidence service.
- **FR-035**: The workflow MUST preserve the full Datadog incident title as display metadata and
  derive a deterministic, filesystem-safe local investigation identifier when a local name is
  omitted. A supplied local name MUST retain the existing strict validation contract.

### Security and Privacy Constraints

- Credentials in scope include DeepSeek API keys (`DEEPSEEK_API_KEY`,
  `NOC_WEB_DEEPSEEK_API_KEY`), Datadog access tokens (`DD_ACCESS_TOKEN`,
  `NOC_WEB_DATADOG_ACCESS_TOKEN`), Authorization headers, any raw provider credentials, and
  unrelated process environment values.
- The AI provider request MUST contain only the bounded, minimized evidence package and the
  instructions required to produce the advisory investigation. It MUST NOT contain an environment
  dump, credential values, Authorization headers, or unrelated operational data.
- Credentials MUST NOT appear in client-returned prompts, logs, reports, generated Markdown, API
  responses, frontend output, exceptions, or persisted operational data.
- Error responses and logs MUST be sanitized before they are exposed to operators or written to
  operational records.

### Key Entities *(include if feature involves data)*

- **Investigation Generation Request**: The operator's request to create an investigation for a
  current Datadog incident, including the selected shift, full Datadog display title, optional
  local investigation identifier, notebook URL, evidence reference, and confirmation state.
- **Evidence Package**: The bounded, minimized, validated set of Feature 015 evidence used for
  generation, including incident detail, notebooks, monitors, evidence identifiers and source
  links, provenance, relationships, availability, and partial or unavailable states.
- **Evidence Reference**: A stable identifier (`incident:<id>`, `notebook:<id>`, or
  `monitor:<id>`), Datadog source link, and availability state for an item included in the
  evidence package. Generated findings and conclusions must cite these identifiers.
- **Evidence Provenance Map**: A persisted mapping from each cited stable evidence identifier to
  its Datadog source link and availability state, retained with the investigation record.
- **Evidence Availability Disclosure**: System-authored metadata and operator-visible text that
  identifies partial or unavailable evidence independently of AI-authored content. AI output that
  contradicts this disclosure is rejected.
- **Investigation Preview**: A non-generative, read-only summary of the target, selected shift,
  evidence provenance, availability, and intended generation inputs, backed by the exact bounded
  evidence snapshot that confirmed generation must use.
- **Operator Confirmation**: The explicit action that authorizes AI generation immediately before
  creation; it is distinct from preview and cannot be inferred.
- **AI Generation Result**: The advisory output or failure returned by the configured provider,
  including its validation status, provider identity, and any timeout, unavailability, or
  malformed-output condition.
- **Generated Investigation Draft**: The validated output proposed for persistence, including
  findings, conclusions, evidence citations, and required sections.
- **Persisted Investigation Record**: The existing local investigation record with provenance,
  lifecycle state, review state, collision protection, and Datadog link/attachment behavior.
- **Provider Failure**: A timeout, unavailable provider, authentication/configuration failure, or
  incomplete configuration that must terminate generation without fallback.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of confirmed investigation generations use only Feature 015 evidence, with zero
  noc-inv, Copilot, Datadog MCP, or direct Datadog evidence-retrieval calls.
- **SC-002**: With Copilot unavailable or exhausted and DeepSeek Flash configured, 100% of valid
  confirmed generation attempts complete within the configured provider timeout.
- **SC-003**: Preview invokes the AI provider in 0 cases and creates 0 investigation records before
  explicit operator confirmation.
- **SC-004**: 100% of generated findings and conclusions cite at least one supplied stable
  evidence identifier, and 0 unsupported, fabricated, or non-canonical references are accepted.
- **SC-005**: 100% of partial or unavailable evidence is explicitly labeled through
  system-authored disclosure, and 0 generated investigations present it as complete or current.
- **SC-006**: 100% of malformed, missing-section, or over-bound AI outputs are rejected with no
  investigation persisted.
- **SC-007**: 100% of provider timeout, unavailability, and incomplete-configuration cases fail
  closed with 0 investigations created and 0 automatic provider fallbacks.
- **SC-008**: Credential scans across prompts, logs, reports, generated Markdown, API responses,
  frontend output, exceptions, and persisted data report 0 exposed credentials.
- **SC-009**: The workflow issues 0 Datadog mutation requests.
- **SC-010**: Existing investigation inspection, lifecycle, reviewed-finding, Datadog link,
  incident attachment, and selected-shift regression suites pass unchanged.
- **SC-011**: 100% of generated investigations use existing local persistence, provenance,
  collision protection, and validation rules; 0 existing records are overwritten.
- **SC-012**: UI review finds 0 statements that noc-inv, Copilot, or Datadog MCP are required for
  investigation generation, and the new architecture is described consistently.
- **SC-013**: The noc-handover regression suite passes unchanged.
- **SC-014**: 100% of operator-visible generation failures are actionable and contain 0 secrets or
  raw provider payloads.
- **SC-015**: 0 automatic fallback events occur in provider-failure tests.
- **SC-016**: 100% of confirmed generations use the exact evidence snapshot reviewed in Preview;
  0 generations use silently refreshed or unverified evidence.

## Assumptions

- Feature 015 provides a validated, read-only evidence bundle containing incident detail,
  referenced notebooks, referenced monitors, provenance, availability, relationships, and
  partial/unavailable states.
- Feature 014 provides the configured AI provider abstraction and existing DeepSeek provider
  configuration, including DeepSeek Flash support and explicit provider selection.
- Existing local investigation persistence, validation, normalization, collision protection,
  lifecycle, review, and provenance rules remain authoritative and are not replaced by this
  feature.
- Preview is a read-only, non-generative view and is separate from the explicit confirmation
  action that authorizes AI generation. The bounded previewed evidence package is retained as the
  exact input to confirmed generation; evidence changes require a new preview.
- Datadog incident awareness remains globally current; the selected shift governs investigation
  creation and local record association.
- Validated incident detail is the minimum evidence required for advisory generation. Missing or
  unavailable referenced notebooks and monitors are labeled partial rather than automatically
  blocking generation; invalid or unavailable incident detail fails closed.
- Required AI output sections follow the existing investigation validation contract; this feature
  does not introduce a new investigation file format or lifecycle model.
- Credentials remain in the existing environment configuration. This feature does not add new
  external integrations, credential stores, or provider fallbacks.
- The exact credential names in scope are `DEEPSEEK_API_KEY`, `NOC_WEB_DEEPSEEK_API_KEY`,
  `DD_ACCESS_TOKEN`, and `NOC_WEB_DATADOG_ACCESS_TOKEN`, plus any Authorization headers or raw
  provider credentials supplied by the existing provider configuration.
- noc-handover generation is out of scope and must remain behaviorally unchanged.
