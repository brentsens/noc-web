# Feature Specification: Operator Workflow

**Feature Branch**: `004-operator-workflow`
**Created**: 2026-10-29
**Status**: Draft
**Input**: User description: "Improve the noc-web daily NOC operator workflow so Start Shift, Dashboard, Tickets, Investigations, Status, and End Shift form one consistent operational flow. Remove redundant information and actions, improve navigation and state visibility, expose clear stale/error states, and ensure every state-changing operation remains confirmation-gated. Preserve the existing Jira cache architecture, Local NOC Tracking model, handover integration, read-only defaults, and existing API contracts unless a contract change is explicitly justified. The result should reduce operator clicks and ambiguity without adding hidden automation or duplicating Jira data."

## Clarifications

### Session 2026-10-29

- Decisions: Keep the selected shift in the URL (default to today when absent); obtain Datadog evidence only through existing noc-inv and Copilot MCP, read it without mutation, and treat AI output as operator-reviewed advice. noc-web owns the lifecycle and reviewed context—not source evidence—and may publish only concise reviewed findings and state to notes, Dashboard, Status, End Shift, and handover; it must not duplicate raw evidence or expand noc-inv into Jira-ticket investigations.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Follow Daily NOC Work (Priority: P1)

An operator can move from Start Shift through Dashboard, Tickets, Investigations, Status, and End
Shift with consistent navigation, shift context, and a clear indication of the current workflow
state.

**Why this priority**: A coherent daily flow reduces missed work and time spent interpreting
unrelated or contradictory screens.

**Independent Test**: An operator starts or selects a shift, visits every in-scope view, and can
identify the selected shift, available next action, and current operational state without
re-entering context.

**Acceptance Scenarios**:
1. **Given** a selected shift, **When** an operator moves among in-scope views, **Then** each view
shows the same shift context and provides a clear path to the appropriate next workflow step.
2. **Given** an operator is on any in-scope view, **When** no action is required, **Then** redundant
actions and duplicated information do not distract from the operational summary.

---

### User Story 2 - Understand Operational State (Priority: P2)

An operator can distinguish current, stale, unavailable, error, and read-only information before
relying on it or taking a deliberate action.

**Why this priority**: Ambiguous stale or failed data can lead to incorrect operational decisions.

**Independent Test**: With current, stale, unavailable, and failed data conditions, each affected
view clearly communicates the condition while retaining unrelated available information.

**Acceptance Scenarios**:
1. **Given** stale or unavailable Jira cache information, **When** an operator views Dashboard,
Tickets, or Status, **Then** the condition and its operational meaning are explicit.
2. **Given** an operational request fails, **When** an operator remains on the view, **Then** the
failure is actionable and existing valid state remains visible.
3. **Given** Datadog evidence is retrieved through the existing noc-inv and Copilot MCP path,
**When** an operator reviews it, **Then** the workflow identifies it as read-only source evidence
and AI advice as non-authoritative until the operator reviews it.

---

### User Story 3 - Execute Deliberate Changes (Priority: P3)

An operator can make state-changing decisions only through an immediate confirmation, with a clear
distinction between local NOC changes and separately intentional Jira actions.

**Why this priority**: Confirmation gates prevent unintended operational effects while preserving
read-only inspection.

**Independent Test**: For every state-changing control in the in-scope workflow, cancelling its
confirmation changes nothing; confirming it performs only the stated operation and does not
silently modify Jira.

**Acceptance Scenarios**:
1. **Given** a state-changing control, **When** an operator cancels confirmation, **Then** no
local or Jira state changes.
2. **Given** a read-only inspection flow, **When** an operator navigates or refreshes a view,
**Then** no Jira or local mutation is initiated.

### Edge Cases

- The selected shift is absent or invalid; views show an actionable state without losing safe
  navigation.
- A shift changes while the operator is on an in-scope view; the interface makes the active
  context unambiguous before a state-changing action.
- Local tracking data, Jira cache data, or an investigation is unavailable; the view distinguishes
  the failed source and does not present it as current.
- Datadog evidence retrieval through noc-inv or Copilot MCP fails or returns no result; the view
  identifies the source condition, retains other available information, and neither retries through
  a direct Datadog integration nor writes to the source.
- AI advice is unavailable, unreviewed, or rejected; it is not shown as operational state and no
  finding is propagated to notes, Dashboard, Status, End Shift, or handover.
- Existing handover and API consumers continue to receive their existing information.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The in-scope views MUST present a consistent selected-shift context and navigation
  through the daily NOC workflow. The selected shift MUST be represented in each view's URL and
  default to the current date only when absent.
- **FR-002**: The system MUST present clear current, stale, unavailable, error, and read-only
  states for information each view uses.
- **FR-003**: The system MUST remove or consolidate redundant in-scope information and actions
  without removing required operational information.
- **FR-004**: The system MUST preserve the existing Jira cache architecture, Local NOC Tracking
  model, handover integration, read-only defaults, and existing API contracts unless a documented,
  additive contract change is necessary.
- **FR-005**: The system MUST distinguish local NOC context from Jira-managed information and MUST
  NOT duplicate Jira-managed data in local operational summaries.
- **FR-006**: Every state-changing operation in the in-scope workflow MUST require an explicit
  confirmation immediately before execution.
- **FR-007**: Cancelling or omitting confirmation MUST leave all local and Jira state unchanged.
- **FR-008**: Read-only navigation, status inspection, and cache-health viewing MUST NOT trigger
  hidden automation, Jira refreshes, or state changes.
- **FR-009**: The system MUST retain unrelated available information when one operational source
  is stale, unavailable, or fails.
- **FR-010**: The system MUST preserve existing handover and API consumer compatibility.
- **FR-011**: The system MUST obtain Datadog evidence only through the existing noc-inv and
  Copilot MCP paths; it MUST NOT add a direct Datadog integration.
- **FR-012**: Retrieved evidence MUST be read-only. AI-generated analysis MUST be labeled advisory
  and remain distinct from operator-reviewed operational state.
- **FR-013**: noc-web MUST own the lifecycle and reviewed context for an investigation, but not
  the source evidence. It MUST NOT duplicate raw evidence or extend noc-inv into Jira-ticket
  investigations.
- **FR-014**: Only concise, operator-reviewed findings and state MAY flow to notes, Dashboard,
  Status, End Shift, and handover; raw source evidence MUST NOT flow to those destinations.

### Key Entities

- **Operational Workflow Context**: The selected shift, current workflow state, and available
  next operator action shared across in-scope views.
- **Operational Data State**: The current, stale, unavailable, error, or read-only condition
  communicated for an information source.
- **Confirmation Gate**: The explicit operator decision immediately before a state-changing action.
- **Evidence Source**: Read-only Datadog evidence supplied through existing noc-inv and Copilot
  MCP paths; noc-web references it without becoming its source of record.
- **Advisory Finding**: AI-generated analysis that becomes workflow context only after operator
  review; it is distinct from source evidence and operational state.
- **Reviewed Finding**: A concise operator-reviewed finding or state that may be shared with
  notes, Dashboard, Status, End Shift, and handover.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tested daily workflows, operators can move between all in-scope views
  while retaining an unambiguous selected-shift context.
- **SC-002**: In 100% of tested stale, unavailable, and failed-source scenarios, the affected view
  shows a clear state while unrelated available information remains visible.
- **SC-003**: In 100% of tested in-scope state-changing actions, cancellation produces no change
  and confirmation performs only the stated action.
- **SC-004**: In automated verification, 100% of read-only inspection flows complete without
  changing Jira or local operational data.
- **SC-005**: Representative operators complete the daily shift workflow with at least 20% fewer
  navigation steps than the prior workflow, without losing required information.
- **SC-006**: In 100% of tested evidence-review flows, evidence is obtained only through noc-inv
  or Copilot MCP, no source mutation occurs, and unreviewed AI advice is not presented as
  operational state.
- **SC-007**: In 100% of tested publishing flows, only concise operator-reviewed findings or
  state reach notes, Dashboard, Status, End Shift, or handover; raw evidence is absent.

## Assumptions

- Existing Start Shift and End Shift execution safeguards remain authoritative.
- The selected shift is retained through navigation and refresh using the URL, rather than hidden
  browser-session state.
- An additive display contract is preferred over a breaking API change.
- Jira updates remain separate, deliberate operator actions.
- noc-inv and Copilot MCP remain the existing evidence-access paths; neither is extended to
  investigate Jira tickets as part of this feature.
- The feature improves existing in-scope views and does not add a new operational workflow.
