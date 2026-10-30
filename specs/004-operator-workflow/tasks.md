---

description: "Task list for the Operator Workflow feature"
---

# Tasks: Operator Workflow

**Input**: Design documents from `specs/004-operator-workflow/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/operational-workflow.md`, and `quickstart.md`

**Tests**: Automated verification is required by the success criteria. Add focused pytest cases
to the existing test modules named below before each story's implementation tasks.

**Organization**: Tasks are grouped by user story so each increment can be implemented and
verified independently.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the reusable frontend primitives and test convention for the six workflow
views without creating persistent workflow state.

- [X] T001 [P] Create the URL shift parser, normalizer, and workflow-link builder in frontend/js/workflow-context.js
- [X] T002 [P] Add shared workflow-bar, state-panel, dialog, and read-only presentation rules in frontend/css/components.css
- [X] T003 Add safe request-error and confirmation-dialog helpers to frontend/js/api.js
- [X] T004 Add static frontend regression helpers for workflow pages in tests/test_safety.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Make the shared shell safe for every view before implementing individual workflow
screens.

**⚠️ CRITICAL**: Complete this phase before beginning any user-story phase.

- [X] T005 Implement a no-fetch shared workflow-bar initializer with active-step and safe-next-step rendering in frontend/js/workflow-context.js
- [X] T006 Implement invalid-shift context errors that prevent date-scoped requests in frontend/js/workflow-context.js
- [X] T007 Verify shared workflow helpers never issue POST/PATCH requests during inspection in tests/test_safety.py

**Checkpoint**: URL context, navigation primitives, and read-only guarantees are ready for story
implementation.

---

## Phase 3: User Story 1 - Follow Daily NOC Work (Priority: P1) 🎯 MVP

**Goal**: Let an operator follow Start Shift → Dashboard → Tickets → Investigations → Status →
End Shift with the selected URL shift and an unambiguous active workflow step.

**Independent Test**: Open each page with `?shift=2026-10-29`, follow its workflow links, and
verify every destination retains that date, highlights its current step, and makes no inspection
mutation. Open each page without `shift` to verify normalization, then use an invalid shift to
verify no date API call occurs.

### Tests for User Story 1

- [X] T008 [P] [US1] Add Start Shift URL-context, absent-date normalization, invalid-date no-request, and read-only preflight tests in tests/test_start_shift.py
- [X] T009 [P] [US1] Add Dashboard URL-context propagation and no-mutation inspection tests in tests/test_dashboard.py
- [X] T010 [P] [US1] Add End Shift URL-context propagation and read-only preflight tests in tests/test_end_shift.py
- [X] T011 [P] [US1] Add static checks for all six workflow-bar imports, ordered links, and preserved shift query strings in tests/test_safety.py

### Implementation for User Story 1

- [X] T012 [US1] Initialize the Start Shift workflow context and replace duplicate shift navigation in frontend/start-shift.html
- [X] T013 [US1] Initialize the Dashboard workflow context, carry shift through dashboard deep links, and consolidate duplicate navigation in frontend/index.html
- [X] T014 [US1] Initialize the Tickets workflow context while retaining the unscoped ticket read contract in frontend/tickets.html
- [X] T015 [US1] Initialize the Investigations workflow context and pass only validated shifts to its existing loader in frontend/investigations.html
- [X] T016 [US1] Initialize the Status workflow context and preserve selected shifts in status navigation in frontend/status.html
- [X] T017 [US1] Initialize the End Shift workflow context and replace duplicate shift navigation in frontend/end-shift.html
- [X] T018 [US1] Render active-step and already-loaded/preflight-only next-step suggestions without adding fetches in frontend/js/workflow-context.js

**Checkpoint**: An operator can complete the navigation portion of the daily workflow with
URL-backed shift context and no hidden state changes.

---

## Phase 4: User Story 2 - Understand Operational State (Priority: P2)

**Goal**: Clearly distinguish current, stale, unavailable, error, and read-only source states
while keeping independently available operational information visible.

**Independent Test**: Exercise current, stale, unavailable, and failed cache/local/investigation
conditions; each affected panel names its source and state, while valid unrelated panels remain
visible and no automatic refresh occurs.

### Tests for User Story 2

- [X] T019 [P] [US2] Add current, stale, unavailable, and retained-local-work Dashboard state tests in tests/test_dashboard.py
- [X] T020 [P] [US2] Add Tickets cache/local-tracking state separation and read-only inspection tests in tests/test_tickets.py
- [X] T021 [P] [US2] Add Status cache freshness, unavailable-source, and retained-valid-content tests in tests/test_status.py
- [X] T022 [P] [US2] Add cache-health no-write regression cases for stale and unavailable caches in tests/test_jira_cache.py
- [X] T023 [P] [US2] Add investigation unavailable/error panel and no-hidden-retry static checks in tests/test_safety.py

### Implementation for User Story 2

- [X] T024 [US2] Add reusable current, stale, unavailable, error, and read-only state-panel rendering in frontend/js/workflow-context.js
- [X] T025 [US2] Render Jira-cache and local-work states independently without a refresh in frontend/index.html
- [X] T026 [US2] Render separate Jira-cache, local-tracking, request-error, and read-only states in frontend/tickets.html
- [X] T027 [US2] Render source-specific investigation unavailable and request-error states while retaining context in frontend/investigations.html
- [X] T028 [US2] Render independent Jira-cache, local-work, request-error, and read-only states in frontend/status.html
- [X] T029 [US2] Preserve valid preflight content while showing actionable request errors in frontend/start-shift.html
- [X] T030 [US2] Preserve valid preflight content while showing actionable request errors in frontend/end-shift.html

**Checkpoint**: Every in-scope view presents the condition and safe meaning of its sources without
masking independent valid information.

---

## Phase 5: User Story 3 - Execute Deliberate Changes (Priority: P3)

**Goal**: Require a last-step explicit confirmation for every visible mutation, distinguish local
from Jira effects, and leave all state unchanged on cancellation.

**Independent Test**: Cancel every visible state-changing control and assert no request/artifact
change; confirm each control and assert it sends only its documented effect. Verify Start Shift
rejects omitted and false confirmation before service execution.

### Tests for User Story 3

- [X] T031 [P] [US3] Add missing, false, and true Start Shift confirmation request tests that assert no service execution before confirmation in tests/test_start_shift.py
- [X] T032 [P] [US3] Add cancellation/no-request and confirmed local tracking action regression cases in tests/test_tickets.py
- [X] T033 [P] [US3] Add confirmed End Shift and handover execution-gate regression cases in tests/test_end_shift.py
- [X] T034 [P] [US3] Add static dialog labels, local-versus-Jira scope, and cancellation no-request checks in tests/test_safety.py

### Implementation for User Story 3

- [X] T035 [US3] Require a boolean confirmed request body and reject omitted or false values before Start Shift service execution in backend/api/start_shift.py
- [X] T036 [US3] Send the confirmed Start Shift body only from an immediate confirmation dialog in frontend/start-shift.html
- [X] T037 [US3] Route local tracking and separately labeled Jira ticket actions through the shared confirmation dialog in frontend/tickets.html
- [X] T038 [US3] Route visible investigation generation/regeneration actions through the shared confirmation dialog in frontend/investigations.html
- [X] T039 [US3] Route visible End Shift and handover delivery actions through the shared confirmation dialog in frontend/end-shift.html
- [X] T040 [US3] Ensure confirmed mutation helpers refresh only their relevant displayed data and retain action errors in frontend/js/api.js

**Checkpoint**: All visible workflow mutations are explicitly confirmed, cancellable without a
request, and accurately scoped as local or Jira effects.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate compatibility, documentation, and end-to-end behavior across the completed
workflow.

- [X] T041 [P] Document the implemented URL, read-only, state-presentation, and Start Shift confirmation behavior in specs/004-operator-workflow/contracts/operational-workflow.md
- [X] T042 [P] Update focused automated and manual validation instructions for the implemented workflow in specs/004-operator-workflow/quickstart.md
- [X] T043 Run the focused regression command and resolve workflow regressions recorded in specs/004-operator-workflow/quickstart.md
- [X] T044 Run the full pytest suite to verify existing API and handover consumer compatibility in pytest.ini

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; T001 and T002 may run in parallel, then T003 and T004.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **US1 (Phase 3)**: Depends on Foundational and is the MVP. T008–T011 precede T012–T018.
- **US2 (Phase 4)**: Depends on Foundational and can begin after US1 navigation primitives are
  stable; T019–T023 precede T024–T030.
- **US3 (Phase 5)**: Depends on Foundational and can begin after the shared confirmation helper;
  T031–T034 precede T035–T040.
- **Polish (Phase 6)**: Depends on the desired user-story phases and their focused tests.

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundational; no dependency on US2 or US3.
- **US2 (P2)**: Depends only on Foundational for implementation; it consumes existing read
  responses and must not change their contracts.
- **US3 (P3)**: Depends only on Foundational for implementation; its Start Shift body is the
  documented additive contract change, while existing tracking and handover contracts remain
  compatible.

### Within Each User Story

- Write and observe focused tests failing before implementation.
- Complete page/module tasks after their corresponding tests.
- Keep each view's source data independent and preserve read-only inspection.

---

## Parallel Opportunities

- T001 and T002 can run in parallel; T004 can proceed after the paths are agreed.
- US1 tests T008–T011 can run in parallel; page integrations T012–T017 can proceed in parallel
  once the shared initializer is available.
- US2 tests T019–T023 can run in parallel; T025–T030 touch separate pages after T024.
- US3 tests T031–T034 can run in parallel; T036–T039 touch separate pages after T035 and the
  shared dialog helper.
- T041 and T042 can run in parallel after feature behavior is complete.

## Parallel Example: User Story 2

```text
Task: "Add current, stale, unavailable, and retained-local-work Dashboard state tests in tests/test_dashboard.py"
Task: "Add Tickets cache/local-tracking state separation and read-only inspection tests in tests/test_tickets.py"
Task: "Add Status cache freshness, unavailable-source, and retained-valid-content tests in tests/test_status.py"

Task: "Render Jira-cache and local-work states independently without a refresh in frontend/index.html"
Task: "Render separate Jira-cache, local-tracking, request-error, and read-only states in frontend/tickets.html"
Task: "Render independent Jira-cache, local-work, request-error, and read-only states in frontend/status.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup and Foundational phases.
2. Complete US1 tests and implementations.
3. Validate the URL-backed journey across all six pages and its no-mutation behavior.
4. Demo the coherent navigation flow before expanding state presentation or execution controls.

### Incremental Delivery

1. Deliver US1 for a consistent, URL-reproducible daily workflow.
2. Add US2 to make all source health and failures explicit without hidden refreshes.
3. Add US3 to ensure every mutation has a last-step, accurately scoped confirmation.
4. Complete Polish with focused and full regression verification.

### Parallel Team Strategy

1. Complete the shared context, styling, API helpers, and foundational safety checks together.
2. Assign separate developers to the US1 page integrations, US2 state panels, and US3 execution
   gates only after their shared primitives are stable.
3. Integrate and run T043–T044 after all selected story phases are complete.

## Format Validation

All 44 implementation tasks use the required `- [ ] T### [P]? [US#]? Description with path`
checklist format. Setup, Foundational, and Polish tasks omit user-story labels; story-phase tasks
include exactly one US label.
