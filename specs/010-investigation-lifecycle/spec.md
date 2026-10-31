# Feature Specification: Operator-Controlled Investigation Lifecycle

**Feature Branch**: `010-investigation-lifecycle`

**Created**: 2026-10-31

**Status**: Draft

**Input**: User description: "Add an operator-controlled lifecycle and Datadog incident attachment workflow for noc-web investigations."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review and manage investigation lifecycle (Priority: P1)

An operator reviews a generated investigation, records a concise finding, and
explicitly assigns its current operational lifecycle. Generation and validation
results remain available as separate metadata and cannot override the lifecycle.

**Why this priority**: Operators need one trustworthy state across investigation
views so generated readiness is not confused with an operator's decision.

**Independent Test**: Generate an investigation, inspect its initial lifecycle,
then select and confirm each lifecycle state. Verify list and detail views
consistently show the operator-controlled state and that an unconfirmed
selection changes nothing.

**Acceptance Scenarios**:

1. **Given** noc-inv generation completes, **When** the investigation is created,
   **Then** its lifecycle is `ready_for_review`, independently of its generation,
   validation, and review metadata.
2. **Given** an operator changes the lifecycle selection, **When** they have not
   confirmed the change, **Then** no lifecycle or reviewed finding is saved.
3. **Given** an operator confirms `escalated_to_incident` or `cured`, **When** no
   concise operator-reviewed finding is supplied, **Then** the change is rejected
   and the prior lifecycle remains.
4. **Given** the lifecycle changes, **When** an operator views the investigation
   list, detail, Dashboard, Status, End Shift, or handover readiness, **Then** each
   uses `lifecycleStatus`, not the original `validationStatus`, as its current
   lifecycle.
5. **Given** an investigation is escalated, **When** an operator attempts to
   return it to Ready for Review, **Then** the transition is rejected. A Cured
   investigation cannot transition to another lifecycle state.

---

### User Story 2 - Carry investigations across shifts (Priority: P1)

An operator sees active investigations created on earlier shifts, understands
their origin and current lifecycle, and can find cured investigations in history
without reintroducing them as active work.

**Why this priority**: Investigation work often spans shifts; limiting visibility
to the creation shift risks losing unresolved operational context.

**Independent Test**: Create ready, escalated, and cured investigations on one
shift, then inspect active and historical views for that and later shifts. Verify
the selected shift remains clear and each record is classified correctly.

**Acceptance Scenarios**:

1. **Given** an investigation is `ready_for_review` or
   `escalated_to_incident`, **When** a later shift is selected, **Then** it remains
   visible as carried from its creation shift, with its source and lifecycle.
2. **Given** an operator marks an investigation `cured`, **When** its cure shift
   is viewed, **Then** it may appear as a concise cured-this-shift outcome.
3. **Given** a cured investigation is viewed on a later shift, **When** the
   default active list is shown, **Then** it is absent from that list but remains
   accessible through investigation history.
4. **Given** cross-shift views are generated, **When** an investigation is
   carried forward, **Then** its original evidence is not copied into each shift.

---

### User Story 3 - Attach a current Datadog incident (Priority: P1)

An operator may attach one current Datadog incident to an investigation when
escalating it, while keeping Datadog state authoritative and local lifecycle
changes under operator control.

**Why this priority**: A bounded incident reference connects related operational
work without merging external evidence into the local investigation record.

**Independent Test**: Provide current ACTIVE and STABLE incidents in the shared
incident snapshot. Attach each through explicit selection and confirmation,
then verify the stored reference, exact link, cache freshness, and behavior after
the incident is no longer current.

**Acceptance Scenarios**:

1. **Given** an investigation is being escalated and the shared incident snapshot
   is current, **When** an operator selects an ACTIVE or STABLE incident and
   confirms attachment, **Then** exactly that incident is attached.
2. **Given** the shared snapshot is stale, refreshing, or unavailable, **When**
   an operator tries to attach a new incident, **Then** attachment is unavailable
   and the cache freshness is visible.
3. **Given** an incident is resolved after attachment, **When** a successful
   current snapshot no longer lists it, **Then** the investigation remains
   `escalated_to_incident` and the UI presents the resolution warning and requires
   operator review.
4. **Given** an incident reference is attached, **When** the operator opens its
   link, **Then** the exact Datadog URL opens in a new tab with appropriate
   protection against access from the new page.

---

### User Story 4 - Apply lifecycle rules to End Shift and handover (Priority: P1)

An operator can complete End Shift and prepare handover based on lifecycle and
reviewed findings, without exposing raw generated or Datadog evidence as
authoritative work.

**Why this priority**: Lifecycle has operational value only if shift readiness
and handover consistently respect operator review.

**Independent Test**: Prepare shifts containing each lifecycle state and verify
End Shift blockers, handover eligibility, concise context, and cured outcomes.

**Acceptance Scenarios**:

1. **Given** an investigation is `ready_for_review`, **When** End Shift or
   handover readiness is evaluated, **Then** it is identified as requiring review,
   blocks handover generation, and is excluded from handover content.
2. **Given** an investigation is `escalated_to_incident` with a reviewed finding,
   **When** handover is prepared, **Then** concise operator-reviewed active
   context may appear in Investigation Updates and Next Shift Actions, and
   generated suggestions do not override it.
3. **Given** an investigation is `cured`, **When** a later shift is prepared,
   **Then** it does not block End Shift or contribute future actions.
4. **Given** an investigation is cured in the selected shift, **When** handover
   is prepared, **Then** a concise reviewed cured outcome may be included without
   raw records or evidence.

## Edge Cases

- Existing investigation records have missing, malformed, conflicting, or
  ambiguous review and lifecycle information during migration.
- A lifecycle update or migration write fails after a valid prior record exists.
- A record contains an unsafe identifier or a source reference outside the
  allowed investigation location.
- An incident becomes resolved between display, selection, and confirmation.
- The shared incident snapshot is stale, refreshing, unavailable, empty, or
  does not contain the previously attached incident.
- The incident's title matches an investigation title, but the operator has not
  explicitly selected and confirmed the attachment.
- A cured investigation is revisited in its cure shift, on a later shift, or
  through history.
- Generated recommendations conflict with the operator-reviewed finding or
  suggest additional work after cure.
- An investigation has no reviewed finding when escalation or cure is requested.
- Multiple investigations are carried into one shift and some require review
  while others are eligible for handover.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every local investigation MUST have exactly one lifecycle status:
  `ready_for_review`, `escalated_to_incident`, or `cured`.
- **FR-002**: New investigations MUST begin with `lifecycleStatus` set to
  `ready_for_review`.
- **FR-003**: Generation and validation metadata MUST remain separate from the
  operator-controlled lifecycle. Changing lifecycle MUST NOT rewrite
  `generationStatus`, `validationStatus`, or generated content.
- **FR-004**: `reviewState` MUST remain distinct from `lifecycleStatus`. Current
  lifecycle labels MUST be derived from `lifecycleStatus`, never from the
  original validation state.
- **FR-005**: The review interface MUST provide an accessible lifecycle
  selection with the labels Ready for Review, Escalated to Incident, and Cured,
  plus a concise single-line operator-reviewed finding field.
- **FR-006**: Selecting a lifecycle value MUST NOT save it. A lifecycle change
  MUST require an explicit operator confirmation immediately before it is saved.
- **FR-007**: Transitioning to `escalated_to_incident` or `cured` MUST require a
  non-empty operator-reviewed finding. A confirmed transition to either state
  MUST record `reviewState` as reviewed. An unconfirmed or invalid change MUST
  preserve the previous lifecycle and finding.
- **FR-008**: Investigation list and detail views, Dashboard, Status, End Shift,
  and handover readiness MUST show a consistent current lifecycle based on the
  same investigation projection.
- **FR-009**: The selected shift MUST remain visible. Investigations MUST be
  classified as Created this shift, Carried from an earlier shift, Cured this
  shift, or Historical when applicable.
- **FR-010**: Ready-for-review and escalated investigations MUST remain visible
  across later shifts until cured, with their creation shift, last lifecycle
  change time, current lifecycle, reviewed finding, attachment reference, and
  source investigation reference.
- **FR-011**: Cured investigations MUST be omitted from the default active view
  on later shifts and MUST remain accessible through investigation history.
  Their original records and review history MUST be preserved.
- **FR-012**: While an investigation is `escalated_to_incident`, the shared
  Datadog incident snapshot MUST be the only source for new attachments. An
  attachment MUST be available only when the snapshot is current and the
  incident state is ACTIVE or STABLE. The selection view MUST show incident ID,
  title, available severity, exact Datadog state, URL, and cache freshness.
- **FR-013**: An incident attachment MUST require an explicit operator
  selection and confirmation. No attachment may be inferred from matching titles
  or generated content.
- **FR-014**: An investigation MUST have at most one attached Datadog incident.
  The attachment MUST retain only its incident ID, exact URL, title, last-known
  Datadog state, and attachment timestamp; raw incident evidence MUST NOT be
  copied into the investigation.
- **FR-015**: An attached incident link MUST display “View Datadog Incident”,
  open the exact stored URL in a new tab using `target="_blank"` and
  `rel="noopener noreferrer"`.
- **FR-016**: When a successful current incident snapshot no longer contains an
  attached incident, the UI MUST show “Datadog incident resolved”, “Local
  investigation still Escalated to Incident”, and “Operator review required”.
  This condition MUST NOT change local lifecycle automatically.
- **FR-017**: A `ready_for_review` investigation MUST remain visible, be
  identified as requiring operator review at End Shift, block handover
  generation, and be excluded from handover content. Generated content MUST
  remain advisory and MUST NOT be included as a reviewed finding.
- **FR-018**: An `escalated_to_incident` investigation MUST require reviewed
  operator context, remain active across shifts, and be eligible for concise
  active-investigation handover context in Investigation Updates and Next Shift
  Actions after explicit review.
- **FR-019**: A `cured` investigation MUST be treated as locally resolved, MUST
  NOT block End Shift, and MUST NOT contribute generated recommendations or
  future actions. A concise reviewed outcome MAY appear in its cure shift.
- **FR-020**: Handover MUST NOT expose raw review records, raw generated
  content, raw Datadog evidence, or internal lifecycle storage as standalone
  sections. Operator-reviewed context MUST remain authoritative over generated
  suggestions.
- **FR-021**: Lifecycle changes MUST NOT modify Datadog, Jira, Local NOC
  Tracking, Shift Notes, email, or other external systems. Lifecycle MUST NOT
  change automatically due to AI output or Datadog state.
- **FR-022**: Existing investigations MUST migrate conservatively: unreviewed
  records to `ready_for_review`; reviewed records with an explicitly recognized
  cured/resolved state to `cured`; reviewed records with clear active
  escalation context to `escalated_to_incident`; all ambiguous records to
  `ready_for_review`.
- **FR-023**: Migration MUST NOT infer cure from ambiguous text or silently
  discard existing investigation records, generated content, or review history.
- **FR-024**: Lifecycle and cross-shift projection updates MUST preserve the
  complete prior record if an update fails. Cross-shift references MUST reject
  unsafe identifiers and path traversal.
- **FR-025**: Cross-shift visibility MUST use a concise projection or reference
  to the original investigation and MUST NOT duplicate raw investigation
  evidence into each shift.
- **FR-026**: The feature MUST preserve existing behavior and safety boundaries
  of Features 001-009.
- **FR-027**: Lifecycle transitions MUST be forward-only: `ready_for_review`
  MAY transition to `escalated_to_incident` or `cured`,
  `escalated_to_incident` MAY transition to `cured`, and `cured` MUST be
  terminal. Attempts at any other transition MUST preserve the prior lifecycle
  and reviewed finding.

### Key Entities *(include if feature involves data)*

- **Investigation Lifecycle**: The single current operator-controlled state,
  separate from generation, validation, and review metadata, with a last-change
  time and concise reviewed finding.
- **Cross-Shift Investigation Projection**: A bounded view of an investigation's
  source, creation shift, lifecycle, review context, attachment reference, and
  historical availability.
- **Datadog Incident Reference**: One explicitly attached incident's ID, exact
  URL, title, last-known state, and attachment time; it does not make the local
  lifecycle dependent on Datadog state.
- **Handover Investigation Context**: A concise, operator-reviewed active
  finding or cure-shift outcome, separate from raw evidence and generated
  recommendations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All new investigations display Ready for Review until an
  operator confirms a lifecycle change; generation and validation states remain
  separately available.
- **SC-002**: Every listed lifecycle view shows the same current lifecycle
  status, including after lifecycle changes and migration.
- **SC-003**: No lifecycle or attachment change is persisted from selection
  alone; all such changes require explicit confirmation.
- **SC-004**: Ready and escalated investigations remain visible across shifts;
  cured investigations are absent from later active lists and remain findable
  in history.
- **SC-005**: New attachments are limited to one current ACTIVE or STABLE
  incident, retain only the specified reference fields, and are never selected
  automatically.
- **SC-006**: In all tested resolved-incident cases, the local investigation
  remains escalated until an operator confirms Cured.
- **SC-007**: Handover excludes Ready for Review work and raw evidence, while
  reviewed escalations and eligible cure-shift outcomes appear only as concise
  operator-reviewed context.
- **SC-008**: Ambiguous legacy investigations migrate to Ready for Review, and
  migration or lifecycle write failures preserve existing records.
- **SC-009**: Lifecycle changes cause zero mutations to Datadog, Jira, Local
  NOC Tracking, Shift Notes, email, or local investigation evidence outside the
  intended lifecycle fields.
- **SC-010**: Existing operator workflows in Features 001-009 retain their
  prior user-visible behavior while the new lifecycle is consistently used for
  investigation and shift readiness.

## Assumptions

- A cured lifecycle is terminal in this workflow; renewed operational work
  starts as a new investigation rather than silently reopening a cured record.
- Only one Datadog incident may be attached at a time. Replacing or removing an
  attachment, if supported, requires a separate explicit confirmation.
- A new incident can be attached only from a CURRENT shared snapshot. When the
  snapshot is stale, refreshing, or unavailable, the last-known attachment
  remains visible with its freshness but cannot be used for a new attachment.
- A successful CURRENT snapshot that omits an attached incident is treated as
  resolved for the warning display only; it does not change local lifecycle.
- Existing lifecycle and reviewed finding data are local operator records; no
  external system is a lifecycle authority.
- Recognized legacy cured/resolved or active-escalation values must be
  explicitly defined from existing records during planning; uncertain records
  remain Ready for Review.
