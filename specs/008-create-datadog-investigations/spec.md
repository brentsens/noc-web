# Feature Specification: Confirmation-Gated Datadog Investigation Creation

**Feature Branch**: `008-create-datadog-investigations`  
**Created**: 2026-10-30  
**Status**: Draft  
**Input**: User description: "Add confirmation-gated creation of Datadog investigations from FINAL Datadog Notebook URLs in noc-web, preserving noc-inv as the authoritative workflow and requiring validation and operator review before any findings can affect operations or handover."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Preview and confirm an investigation (Priority: P1)

An operator can start a separate create workflow from Investigations, enter a safe investigation
name and a FINAL Datadog Notebook URL, verify the selected shift and intended operation, and
explicitly confirm before any investigation is generated. Existing investigation inspection
remains read-only.

**Why this priority**: Operators need to preserve the established Datadog investigation workflow
without accidental execution, a shift mismatch, or an unintended write.

**Independent Test**: Preview valid inputs and verify that the selected shift, normalized
investigation name, exact Notebook URL, logical target location, generation and review warnings,
and no-source-modification notice are shown without invoking the generator or creating files.
Confirm separately and verify that only the selected shift is targeted.

**Acceptance Scenarios**:

1. **Given** a valid selected shift, **When** an operator chooses “Create from Datadog Notebook”,
   **Then** a professional form shows Investigation Name, FINAL Datadog Notebook URL, Selected
   Shift, Cancel, and Preview while the existing investigation list remains available.
2. **Given** valid name and URL values, **When** the operator previews, **Then** the preview shows
   the selected shift, normalized name, exact URL, logical destination, use of noc-inv with
   GitHub Copilot CLI and Datadog MCP, possible local record creation, required validation and
   review, and that Jira and Datadog will not be modified.
3. **Given** an operator previews the request, **When** they cancel or leave without confirming,
   **Then** noc-inv is not run and no investigation files are created.
4. **Given** a valid preview, **When** the operator explicitly chooses “Create Investigation” and
   confirms, **Then** creation targets only the displayed shift and name.

---

### User Story 2 - Validate and review a generated investigation (Priority: P1)

An operator can inspect the generated investigation, understand its provenance and validation
status, and explicitly review or reject its advisory findings. Successful generation alone does
not make findings authoritative.

**Why this priority**: Generated Datadog analysis must be checked for completeness and quality
before operators rely on it.

**Independent Test**: Complete a mocked successful generation and verify that a valid record is
shown as READY FOR REVIEW and remains unreviewed. Supply malformed or incomplete output and verify
that it remains available for controlled review, is marked GENERATED RECORD NEEDS REVIEW, and is
not treated as handover-ready.

**Acceptance Scenarios**:

1. **Given** noc-inv completes and produces a valid record, **When** the investigation list
   refreshes, **Then** the new record is selected and displays generation status, validation
   status, provenance, exact Notebook URL, advisory content, and unreviewed state.
2. **Given** generated output is incomplete, malformed, unsafe, or has invalid provenance,
   **When** validation completes, **Then** the record remains available when safe, is marked
   GENERATED RECORD NEEDS REVIEW, and is withheld from automatic handover propagation.
3. **Given** a generated record is unreviewed, **When** it is displayed, **Then** the existing
   explicit Review and Reject actions remain available and generation does not mark it reviewed.
4. **Given** list refresh fails after generation, **When** the result is shown, **Then** creation
   status and refresh status are distinguished and the operator is not misled about whether a
   local record was created.

---

### User Story 3 - Propagate only reviewed findings (Priority: P1)

An operator can rely on concise investigation findings in operational views and handover only
after explicitly reviewing them. Findings that are pending review, rejected, malformed, or
unavailable remain excluded.

**Why this priority**: A generated investigation is advisory evidence, not an authoritative
operational record; human review is the control that permits selected findings to affect handover.

**Independent Test**: For valid, unreviewed, reviewed, rejected, and malformed records, verify that
only concise validated reviewed findings and handover summaries appear in permitted operational
views, while raw evidence and unreviewed content never enter the final handover.

**Acceptance Scenarios**:

1. **Given** an investigation requires review, **When** an operator checks End Shift readiness,
   **Then** the pending review is visible and the finding is not silently included in handover.
2. **Given** an operator explicitly reviews a valid finding, **When** Dashboard, Status, Shift
   Notes context, End Shift readiness, handover, or Assistant reviewed-finding context is
   refreshed through its existing workflow, **Then** only the concise reviewed finding and
   approved handover summary may propagate.
3. **Given** an operator rejects a finding or its record is malformed, **When** operational
   context or handover is generated, **Then** the rejected or malformed content remains excluded.
4. **Given** an investigation was created for a historical shift, **When** it is reviewed or
   displayed, **Then** its data remains associated with that shift and does not affect another
   shift.

### Edge Cases

- The selected shift is absent, invalid, or changes while the form is open; preview and creation
  must not silently select another shift.
- The name is blank, normalizes to an empty value, contains path separators, traversal sequences,
  control characters, or other unsafe characters.
- Another investigation already uses the same normalized name for the selected shift.
- The Notebook URL uses a non-HTTPS scheme, a non-Datadog host, or a path not on the approved
  Notebook URL allowlist.
- noc-inv is missing, not executable, interactive without a safe non-interactive contract, or exits
  unsuccessfully.
- GitHub Copilot CLI, Datadog MCP, or required authentication is unavailable.
- Generation exceeds its configured time limit.
- The expected generated file is missing, unreadable, malformed, has incomplete required sections,
  or contains unexpected provenance.
- The configured local storage path is unavailable or lacks permission.
- A list refresh fails after generation has created a local record.
- A failure occurs after temporary working files have been created.
- A generated investigation is pending review, rejected, or malformed when readiness or handover
  is evaluated.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Investigations MUST retain their existing read-only inspection behavior. Creation
  MUST be a separate, explicit operator workflow initiated by “Create from Datadog Notebook”.
- **FR-002**: The create form MUST display Investigation Name, FINAL Datadog Notebook URL,
  Selected Shift, Cancel, and Preview.
- **FR-003**: The selected shift MUST come from validated NOC Web shift context. The workflow MUST
  not silently switch shifts; an absent or invalid shift MUST block preview and creation.
- **FR-004**: Investigation Name MUST be required, trimmed, and normalized to a safe identifier.
  Normalization MUST lowercase the value, convert whitespace and repeated hyphens to a single
  hyphen, and accept only ASCII letters, digits, and hyphens with a leading letter or digit and a
  maximum of 80 characters. Path separators, traversal sequences, control characters, empty
  normalized names, and other unsafe values MUST be rejected.
- **FR-005**: The system MUST detect an existing investigation with the same normalized name in
  the selected shift and return a conflict without overwriting it. Regeneration is out of scope.
- **FR-006**: FINAL Datadog Notebook URL MUST be required, use HTTPS, and match only
  `https://app.datadoghq.com/notebook/<numeric-id>/<slug>` with a numeric Notebook ID and one
  non-empty slug path segment. Additional path segments, query strings, fragments, credentials,
  non-Datadog hosts, and other schemes MUST be rejected. The exact validated URL MUST be preserved
  in investigation metadata.
- **FR-007**: Preview MUST validate inputs and show the selected shift, normalized name, exact URL,
  logical target location, use of noc-inv and GitHub Copilot CLI with Datadog MCP for read-only
  evidence, possible local record creation, required validation and operator review, and the
  statement that Jira and Datadog will not be modified.
- **FR-008**: Preview and cancellation MUST NOT run noc-inv, create investigation records, or
  otherwise change operational state. The browser and NOC Web MUST NOT fetch the Notebook URL.
- **FR-009**: Only the explicitly confirmed final action, labeled “Create Investigation”, MAY
  start investigation creation.
- **FR-010**: noc-inv MUST remain the authoritative investigation-generation workflow. NOC Web
  MUST NOT reimplement its investigation or Datadog/Copilot evidence-retrieval behavior, add a
  second AI provider, or introduce a direct Datadog SDK, API client, or browser integration.
- **FR-011**: The generation workflow MUST use the operator’s configured GitHub Copilot CLI and
  Datadog MCP environment through noc-inv. Operator input MUST remain data and MUST NOT be
  interpreted as executable syntax, alter the intended operation, or introduce additional
  options or commands. Generation MUST use a bounded, non-interactive execution path.
- **FR-012**: Generation MUST have a bounded timeout, controlled exit-state handling, safe
  temporary-file cleanup on success and failure, and no unexpected overwrite. Raw command output,
  prompts, credentials, tokens, and filesystem details MUST NOT be exposed to the browser.
- **FR-013**: A created record MUST preserve the selected shift, normalized investigation name,
  exact FINAL Notebook URL, and evidence provenance identifying noc-inv or Copilot MCP.
- **FR-014**: Generated records MUST be validated for required metadata, selected shift,
  investigation name, exact Notebook URL, valid evidence provenance, required headings, and
  non-placeholder Summary, Confirmed Findings, Current Status, and Handover Summary content.
  Next Actions content MUST be validated when required by the existing investigation-output rules.
- **FR-015**: Valid generated output MUST be labeled READY FOR REVIEW. Incomplete, malformed, or
  unsafe output MUST be labeled GENERATED RECORD NEEDS REVIEW and, when safe, remain available for
  controlled operator inspection. Such output MUST NOT propagate automatically to handover.
- **FR-016**: After creation, the Investigations list MUST refresh and select the new investigation
  when refresh succeeds. The interface MUST distinguish generation status, validation status,
  provenance, Notebook URL, advisory content, review state, and unavailable sections or errors.
- **FR-017**: Generation MUST NOT mark findings reviewed. Existing explicit Review and Reject
  workflows MUST remain in effect.
- **FR-018**: Only concise, validated, explicitly operator-reviewed findings MAY propagate through
  existing workflows to Dashboard investigation state, Status, Shift Notes context, End Shift
  readiness, handover, and Feature 006 Assistant reviewed-finding context.
- **FR-019**: Final handover MUST exclude raw Notebook content, raw Datadog evidence, temporary
  Copilot context, raw provider output, unreviewed or rejected findings, malformed investigation
  content, provider diagnostics, credentials, and tokens. Investigations requiring review MUST be
  visible in End Shift readiness and MUST NOT silently enter handover.
- **FR-020**: Investigation creation MUST NOT modify Datadog, Jira, Local NOC Tracking, Shift
  Notes, or handover. Any later propagation MUST occur only through existing, separately confirmed
  and reviewed workflows.
- **FR-021**: Investigation generation and storage MUST use the approved configurable workstation
  locations and readiness capabilities established by Feature 005, without relying on
  engineer-specific locations. Readiness MUST report availability of noc-inv, GitHub Copilot CLI,
  and the required local storage capability.
- **FR-022**: The operator experience and its success, validation, and failure information MUST
  remain consistent if the underlying investigation-generation mechanism changes.
- **FR-023**: Missing commands, unavailable Copilot/MCP/authentication, invalid input, conflicts,
  timeout, non-zero exit, missing or malformed output, provenance mismatch, permission failure,
  and refresh failure MUST produce explicit controlled success, validation, timeout, unavailable,
  conflict, or failure states as appropriate. Failures MUST NOT corrupt existing records, affect
  unrelated NOC Web workflows, expose raw diagnostics, or claim a record was created when creation
  did not complete.
- **FR-024**: Historical-shift creation and review MUST remain isolated to the selected shift.
- **FR-025**: Investigations created through this workflow MUST be specific to Datadog monitor or
  incident evidence supplied through a qualifying FINAL Notebook URL. Ordinary Jira tickets,
  Salesforce cases, customer issues, and general operational questions MUST NOT create
  noc-inv investigations.
- **FR-026**: The feature MUST preserve all functionality and safety boundaries established by
  Features 001–007. Investigation creation MUST NOT generate or deliver a handover.

### Key Entities

- **Investigation Request**: The selected shift, entered and normalized investigation name, exact
  validated FINAL Notebook URL, and explicit confirmation state.
- **Generated Investigation**: A shift-scoped local record with validated metadata, evidence
  provenance, advisory generated content, generation state, validation state, and review state.
- **Reviewed Finding**: A concise finding and state explicitly reviewed or rejected by an
  operator, with its review status controlling whether it may propagate.
- **Generation Readiness**: Availability of the configured generation command, GitHub Copilot CLI,
  Datadog MCP/authentication, and approved local storage capability.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of preview-only and canceled flows, the investigation-generation workflow is
  not executed, and no investigation record or operational mutation is created.
- **SC-002**: In 100% of invalid-name, invalid-URL, invalid-shift, and duplicate-name cases,
  generation is blocked before an investigation record is created.
- **SC-003**: In 100% of successful creation flows, the operator confirms the displayed shift,
  normalized name, and exact Notebook URL before execution begins.
- **SC-004**: 100% of valid generated records display READY FOR REVIEW and remain unreviewed until
  an explicit operator review action.
- **SC-005**: 100% of malformed or incomplete generated records that can be retained safely remain
  inspectable as GENERATED RECORD NEEDS REVIEW and are excluded from automatic handover.
- **SC-006**: Across tested failure cases, no raw execution diagnostics, credentials, tokens, or
  filesystem details are exposed, and no pre-existing investigation is overwritten.
- **SC-007**: In all propagation tests, only concise, validated, explicitly reviewed findings are
  included in downstream operational views or final handover.
- **SC-008**: In all creation tests, Datadog, Jira, Local NOC Tracking, Shift Notes, and handover
  remain unchanged.
- **SC-009**: Operators can distinguish generation, validation, provenance, and review states
  without interpreting raw provider output.

## Assumptions

- Operators use the existing authenticated GitHub Copilot CLI session and configured Datadog MCP
  environment; this feature does not configure or store credentials.
- Feature 005’s approved configuration is authoritative for local storage and command locations.
- A preview displays the target as the logical selected-shift investigations location and
  normalized name; it does not expose an absolute workstation filesystem path.
- The normalized identifier is lowercase ASCII kebab-case as defined in FR-004; the existing
  investigation directory name and duplicate check use that same identifier.
- The only accepted Notebook URL form is the confirmed US1 Datadog host and path pattern in FR-006;
  other Datadog regional hosts are not accepted.
- A safe non-interactive noc-inv invocation contract will be used. If noc-inv is currently
  interactive, the implementation will add or use a bounded adapter without injecting input into
  an interactive terminal.
- A generated investigation is advisory and unreviewed by default. Existing operator Review and
  Reject workflows remain authoritative for propagation.
