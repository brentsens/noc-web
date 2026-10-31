# Feature Specification: Live Datadog Incident Awareness

**Feature Branch**: `009-live-datadog-incident-awareness`

**Created**: 2026-10-30

**Status**: Draft

**Input**: User description: "Add Live Datadog Incident Awareness to noc-web."

## Clarifications

### Session 2026-10-30

- Q: Should the no-overlap guarantee cover multiple noc-web worker processes sharing the incident cache, or only one process? → A: Multiple worker processes may share the incident cache; refresh operations must be coalesced across processes.
- Q: What maximum number of current incidents should one successful snapshot support before a refresh fails and preserves the previous snapshot? → A: 100 current incidents per snapshot.
- Datadog incident state is distinct from cache freshness. `ACTIVE` and `STABLE` are both current incidents and remain visible; `RESOLVED` is removed only after a successful refresh confirms it. Preserve and display the exact state value returned by Datadog, including on a stale last-known snapshot.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See current Datadog incidents (Priority: P1)

An operator can see a concise view of current Datadog incidents (`ACTIVE` and
`STABLE`) on the Dashboard and Investigations pages, clearly separate from
locally managed NOC investigations. The same incident snapshot and cache
freshness are shown in both places, while each incident retains its exact
Datadog state.

**Why this priority**: Operators need immediate situational awareness without
mistaking Datadog incidents for reviewed local investigations or waiting for
page-specific retrieval.

**Independent Test**: Provide a successful snapshot containing multiple current
incidents and verify that both pages show the same incidents, available
operational fields, counts, severity totals, and refresh age. Verify that a
successful empty snapshot is presented as zero current incidents.

**Acceptance Scenarios**:

1. **Given** Datadog has `ACTIVE` or `STABLE` incidents, **When** an incident
   refresh succeeds, **Then** each valid incident appears in both pages with
   available fields, its exact Datadog state, and a Datadog link.
2. **Given** one or more `ACTIVE` or `STABLE` incidents exist, **When** an operator opens
   Dashboard or Investigations, **Then** the page reads the shared snapshot
   without waiting for an external retrieval.
3. **Given** Datadog changes an incident between `ACTIVE` and `STABLE`,
   **When** a refresh succeeds, **Then** it remains visible with the exact new
   Datadog state. If Datadog reports `RESOLVED`, it disappears only after a
   successful refresh, while local investigation history remains unchanged.
4. **Given** a successful refresh returns no current incidents, **When** the
   snapshot is displayed, **Then** the UI reports zero current incidents
   rather than unavailable data.

---

### User Story 2 - Understand freshness and recover from retrieval failures (Priority: P1)

An operator can distinguish current, stale, unavailable, and refreshing
incident data, see the last successful refresh time, and explicitly request a
refresh. A failed refresh never erases a previously successful snapshot or
blocks other NOC workflows.

**Why this priority**: Stale or missing external data must not look like a
healthy empty incident list, and retrieval outages must not affect core shift
work.

**Independent Test**: Seed a successful snapshot, simulate retrieval failure,
and verify that its incident list and successful timestamp remain while
freshness becomes stale. With no prior snapshot, verify that failure is
unavailable, not zero. Exercise automatic, manual, and simultaneous refresh
requests.

**Acceptance Scenarios**:

1. **Given** a successful snapshot exists, **When** a later retrieval fails,
   **Then** the last snapshot and success time remain visible with stale status.
2. **Given** no successful snapshot exists, **When** retrieval fails, **Then**
   incident data is unavailable and is not represented as an empty successful
   result.
3. **Given** an automatic refresh is due or an operator selects “Refresh
   Incidents”, **When** retrieval is in progress, **Then** the cache shows
   `REFRESHING` independently of the incident's Datadog state, and overlapping
   retrieval is prevented or safely coalesced.
4. **Given** incidents are stale or unavailable, **When** an operator uses
   Dashboard, Investigations, shift lifecycle, Jira/Tickets, or handover,
   **Then** those workflows remain available and their state is not changed by
   incident retrieval.

---

### User Story 3 - Start an investigation only by operator choice (Priority: P1)

An operator may choose “Create Investigation” for a current incident and
continue through the existing investigation preview and explicit confirmation
workflow. Incident awareness itself never creates, reviews, closes, or deletes
local investigations and never turns every current incident into official
handover work.

**Why this priority**: Incident awareness is useful only if it preserves the
existing human-review, confirmation, and handover authority boundaries.

**Independent Test**: Verify that displaying and refreshing incidents causes
no local investigation or handover changes. Select Create Investigation and
verify that only safe incident-derived values may be prefilled, remain
operator-editable, and cannot bypass Preview or final confirmation.

**Acceptance Scenarios**:

1. **Given** a current incident is displayed, **When** the operator does not
   choose Create Investigation, **Then** no local investigation is created.
2. **Given** the operator chooses Create Investigation, **When** the existing
   workflow opens, **Then** any prefilled title or approved incident reference
   is reviewable and Preview and confirmation remain mandatory.
3. **Given** an incident is resolved in Datadog, **When** a successful refresh
   updates the current incident list, **Then** no local investigation review state or
   history is automatically altered.
4. **Given** a current incident has not been made handover-relevant through an
   operator-controlled workflow, **When** handover is generated, **Then** the
   incident is not automatically included.

## Edge Cases

- The Copilot CLI is missing, unauthenticated, times out, or cannot reach the
  configured Datadog retrieval service.
- The provider returns malformed JSON, an unexpected schema, duplicate
  incident IDs, or malformed individual incident entries.
- A provider result exceeds the maximum of 100 current incidents; the entire
  refresh fails rather than storing a partial snapshot.
- A failure happens before the first successful snapshot or after a prior
  successful snapshot.
- Cache storage cannot be read or written, or refresh requests overlap across
  application worker processes sharing the cache.
- Datadog returns a successful empty current-incident result.
- An incident lacks optional severity, timestamps, impact summary, or URL.
- Incident descriptions contain unsafe or sensitive content that must not be
  rendered as executable input or persisted as raw evidence.
- The same incident changes between `ACTIVE`, `STABLE`, and `RESOLVED` while
  an operator is viewing the page or opening the investigation workflow.
- Incident awareness is unavailable while unrelated Dashboard,
  Investigations, shift, Jira/Tickets, Assistant, or handover operations are
  in use.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The product MUST show a concise “Datadog Incidents” view on
  Dashboard and Investigations, visually distinct from local NOC
  investigations.
- **FR-002**: Both views MUST consume the same incident snapshot and freshness
  metadata; loading either view MUST NOT independently block on external
  incident retrieval.
- **FR-003**: The incident view MUST show only available operational fields:
  incident ID, title, the exact Datadog state/status returned, severity,
  start/create time, update time, concise impact summary, and Datadog URL. It
  MUST NOT infer or rewrite the Datadog state or invent unavailable values.
- **FR-004**: A successful refresh MUST replace the current incident snapshot,
  including replacing it with an empty list when there are no current
  incidents. Both `ACTIVE` and `STABLE` MUST remain in the current view.
  `RESOLVED` MUST be removed only after a successful refresh confirms that
  state; a failed refresh MUST retain the last successful incident and state.
- **FR-005**: The system MUST distinguish CURRENT, STALE, UNAVAILABLE, and
  REFRESHING cache states from each incident's Datadog state, and show the
  last successful refresh timestamp whenever one exists.
- **FR-006**: The system MUST support a default target refresh interval of 60
  seconds and an explicit “Refresh Incidents” action, without refreshing
  independently from each page component.
- **FR-007**: Concurrent refresh requests across all application worker
  processes sharing the incident cache MUST be prevented or safely coalesced
  so that only one retrieval operation is active at a time.
- **FR-008**: Normal page loads MUST read the short-lived shared cache and MUST
  NOT wait for external retrieval to complete.
- **FR-009**: Retrieval failures, including missing CLI, unavailable
  authentication or retrieval service, timeout, invalid provider output,
  malformed entries, storage errors, and concurrency conflicts, MUST be
  reported as controlled freshness/error states.
- **FR-010**: On failed refresh, the system MUST preserve the last successfully
  retrieved incident list and successful timestamp, mark the data STALE, and
  MUST NOT present an empty list as a successful result. With no successful
  snapshot it MUST report UNAVAILABLE.
- **FR-011**: The retrieval path MUST use the approved authenticated
  workstation Copilot CLI and configured read-only Datadog MCP capability.
  The system MUST NOT add a direct Datadog API, SDK, browser integration,
  credential store, or second retrieval mechanism.
- **FR-012**: Retrieval MUST be read-only and bounded. Copilot CLI execution
  MUST use subprocess argument arrays, `shell=False`, a bounded timeout, and
  only the Datadog MCP tools required for read-only incident retrieval. It
  MUST NOT enable automatic approvals or unrestricted tool access. Incident
  text and operator input MUST NOT become executable shell arguments.
- **FR-013**: Browser responses and logs MUST NOT expose credentials, tokens,
  raw prompts, provider responses, sensitive stderr, or unnecessary raw
  Datadog evidence.
- **FR-014**: The persisted cache MUST contain only the bounded incident
  projection and required metadata: last attempted refresh, last successful
  refresh, and freshness state. It MUST NOT persist unnecessary prompts or
  raw source evidence.
- **FR-015**: Incident retrieval and refresh MUST NOT modify Datadog, Jira,
  local NOC tracking, shift notes, investigations, handover, or Microsoft 365.
- **FR-016**: “Create Investigation” MUST be an explicit operator action that
  routes through the existing preview and confirmation-gated
  noc-inv workflow. Any prefilled title or approved incident reference MUST
  be safe, reviewable, and MUST NOT skip either gate. Both `ACTIVE` and
  `STABLE` incidents remain eligible for this operator-controlled action.
- **FR-017**: Incident listing or resolution MUST NOT automatically create,
  review, reject, close, cure, or delete a local investigation.
- **FR-018**: Live incidents MUST remain situational awareness only and MUST
  NOT automatically enter handover. Only existing operator-controlled
  workflows may make an incident handover-relevant.
- **FR-019**: Raw incident material MUST NOT be added automatically to Feature
  006 Assistant context. If later exposed to Assistant, only the bounded
  cached projection may be used through the established source contract, and
  Assistant MUST NOT independently refresh Datadog.
- **FR-020**: Incident retrieval failures MUST NOT block Dashboard,
  Investigations, Start Shift, End Shift, Jira/Tickets, or handover.
- **FR-021**: The feature MUST preserve existing behavior and safety
  boundaries through Features 001 and the current release.
- **FR-022**: A successful snapshot MUST contain no more than 100 current
  incidents. If a provider result exceeds this limit, the entire refresh MUST
  fail and preserve the previous snapshot rather than truncate the incident
  list.

### Key Entities

- **Current Datadog Incident Projection**: A bounded, concise representation
  of one `ACTIVE` or `STABLE` Datadog incident, containing an identifier,
  exact state, and only the optional operational fields supplied by
  authoritative evidence.
- **Incident Snapshot**: The most recently successful set of up to 100 current
  incident projections with last-attempted and last-successful refresh times
  and a freshness state.
- **Incident Refresh**: A bounded, read-only attempt to retrieve and validate
  current incident projections; it either atomically replaces the successful
  snapshot or preserves it and reports failure.
- **Investigation Handoff**: An operator-initiated transition from an
  incident card into the existing preview and confirmation-gated local
  investigation creation workflow.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In all successful refresh tests, both pages show the same
  incident set and the same last-successful refresh time.
- **SC-002**: In all retrieval failure tests, a prior successful snapshot is
  preserved; without a prior snapshot, the UI shows unavailable rather than
  zero current incidents.
- **SC-003**: Within one configured refresh interval after a successful
  refresh, the shared snapshot is eligible for refresh without blocking page
  rendering.
- **SC-004**: In all tested resolved-incident cases, the incident leaves the
  current view after a later successful refresh while local investigation
  history and review state remain unchanged.
- **SC-005**: In all tests, incident retrieval is read-only and creates no
  investigation, handover entry, or external mutation.
- **SC-006**: In all tests, investigation creation from an incident requires
  the existing Preview and explicit confirmation steps.
- **SC-007**: Browser responses and persistent cache contain no credentials,
  prompts, raw provider output, or unnecessary raw Datadog evidence.
- **SC-008**: Existing pytest regressions and full frontend ES-module
  validation pass without regressions to Features 001 through the current
  release.
- **SC-009**: Concurrent refresh tests across multiple application worker
  processes sharing the cache verify that at most one retrieval operation is
  active at a time.
- **SC-010**: A refresh with 100 valid incidents succeeds; a result with more
  than 100 incidents fails without truncating or replacing the previous
  snapshot.
- **SC-011**: Tests verify that `ACTIVE`/`STABLE` transitions retain the
  incident and exact Datadog state, only a successful `RESOLVED` result
  removes it, failed refreshes preserve last-known states, and cache freshness
  remains a separate field.

## Assumptions

- Datadog incidents can be retrieved through the configured Datadog MCP
  integration using the authenticated Copilot CLI session, with sufficient
  tool restrictions to keep retrieval read-only.
- A 60-second refresh interval is a target, not a hard real-time guarantee;
  delayed or failed retrieval is reflected through freshness metadata.
- A successful empty incident result is authoritative and replaces the current
  list; failed or invalid output never does.
- The existing confirmation-gated Datadog investigation workflow remains
  authoritative and accepts only its current validated inputs.
- Current incident awareness is not a new source for Assistant context or
  formal handover; future inclusion requires an explicit approved contract.
