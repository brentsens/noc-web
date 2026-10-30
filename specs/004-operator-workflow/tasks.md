---

description: "Task list for the Operator Workflow feature"
---

# Tasks: Operator Workflow

**Input**: Design documents from `specs/004-operator-workflow/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/operational-workflow.md`, and `quickstart.md`

**Tests**: Automated verification is mandatory for every user story because the success criteria
require 100% behavior coverage for the defined workflows. Write the focused tests first and observe
them fail before the corresponding implementation tasks.

**Organization**: Tasks are grouped by user story so each increment remains independently
implementable and testable.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish shared, non-persistent UI primitives and regression-test support for all six
workflow views.

- [X] T001 [P] Create the shared URL-context, workflow-link, and source-state module scaffold in frontend/js/workflow-context.js
- [X] T002 [P] Create shared workflow-bar, state-panel, advisory, reviewed, and confirmation-dialog styles in frontend/css/components.css
- [X] T003 Add safe request-error and immediate-confirmation helpers without implicit confirmation in frontend/js/api.js
- [X] T004 Add static frontend workflow regression helpers in tests/test_safety.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Make URL context, navigation, and read-only behavior safe before any workflow view
adopts them.

**⚠️ CRITICAL**: Complete this phase before beginning any user-story phase.

- [X] T005 Implement ISO shift validation, local-today normalization, query-preserving workflow links, active-step display, and no-fetch initialization in frontend/js/workflow-context.js
- [X] T006 Implement invalid-shift context errors that prevent date-scoped requests while retaining safe navigation in frontend/js/workflow-context.js
- [X] T007 Verify shared context initialization, source-state rendering, and inspection helpers issue no POST, PATCH, Jira refresh, local write, or evidence-source request in tests/test_safety.py

**Checkpoint**: The shared shell is URL-reproducible, read-only by default, and safe to adopt in
each user story.

---

## Phase 3: User Story 1 - Follow Daily NOC Work (Priority: P1) 🎯 MVP

**Goal**: Let an operator follow Start Shift → Dashboard → Tickets → Investigations → Status → End
Shift with one unambiguous URL-backed shift context and an appropriate next workflow step.

**Independent Test**: Open every in-scope page with `?shift=2026-10-29`, follow each workflow
link, and verify that the destination retains the shift and highlights its step. Repeat without
`shift` and with an invalid date, verifying normalization or an actionable no-request error.

### Tests for User Story 1

- [X] T008 [P] [US1] Add Start Shift URL-context, absent-date normalization, invalid-date no-request, and read-only preflight tests in tests/test_start_shift.py
- [X] T009 [P] [US1] Add Dashboard URL-context propagation, deep-link preservation, and read-only inspection tests in tests/test_dashboard.py
- [X] T010 [P] [US1] Add Tickets context propagation while preserving its unscoped ticket-read contract in tests/test_tickets.py
- [X] T011 [P] [US1] Add Investigations and Status selected-shift propagation plus invalid-date no-request tests in tests/test_investigations.py
- [X] T012 [P] [US1] Add End Shift URL-context propagation and read-only preflight tests in tests/test_end_shift.py
- [X] T013 [P] [US1] Add static checks for all six workflow-bar imports, ordered links, active steps, and preserved shift query strings in tests/test_safety.py

### Implementation for User Story 1

- [X] T014 [P] [US1] Initialize the shared Start Shift context, next-step suggestion, and consolidated navigation in frontend/start-shift.html
- [X] T015 [P] [US1] Initialize the shared Dashboard context, query-preserving deep links, next-step suggestion, and consolidated navigation in frontend/index.html
- [X] T016 [P] [US1] Initialize the shared Tickets context and consolidated navigation without changing GET /api/tickets in frontend/tickets.html
- [X] T017 [P] [US1] Initialize the shared Investigations context and pass only a validated shift to its loader in frontend/investigations.html
- [X] T018 [P] [US1] Initialize the shared Status context, next-step suggestion, and query-preserving navigation in frontend/status.html
- [X] T019 [P] [US1] Initialize the shared End Shift context, next-step suggestion, and consolidated navigation in frontend/end-shift.html
- [X] T020 [US1] Render active-step and already-loaded or preflight-only next-step suggestions without adding requests in frontend/js/workflow-context.js

**Checkpoint**: The complete daily navigation journey is independently usable with no hidden
browser-session context or inspection mutation.

---

## Phase 4: User Story 2 - Understand Operational State (Priority: P2)

**Goal**: Make current, stale, unavailable, error, and read-only source states explicit while
retaining independently available information, and distinguish evidence, advisory, and reviewed
context.

**Independent Test**: Exercise current, stale, unavailable, failed, evidence no-result, and
advisory-review conditions. Each affected panel must name its source and state while healthy local
or workflow content remains visible; raw evidence and unreviewed advice must be absent from every
operational summary.

### Tests for User Story 2

- [X] T021 [P] [US2] Add current, stale, unavailable, request-error, retained-local-work, and no-refresh Dashboard state tests in tests/test_dashboard.py
- [X] T022 [P] [US2] Add Jira-cache versus local-tracking state separation and read-only inspection tests in tests/test_tickets.py
- [X] T023 [P] [US2] Add Status cache freshness, unavailable-source, retained-valid-content, and read-only tests in tests/test_status.py
- [X] T024 [P] [US2] Add stale and unavailable Jira-cache no-write regression cases in tests/test_jira_cache.py
- [X] T025 [P] [US2] Add noc-inv/Copilot-MCP-only provenance, read-only evidence failure/no-result, advisory-versus-reviewed, and no-direct-Datadog tests in tests/test_investigations.py
- [X] T026 [P] [US2] Add reviewed-only concise propagation and raw-evidence, advisory, and Jira-ticket-investigation exclusion tests in tests/test_shift_notes.py, tests/test_dashboard.py, tests/test_status.py, tests/test_end_shift.py, and tests/test_handover.py
- [X] T027 [P] [US2] Add static checks for source-specific state panels, no hidden evidence retry, and advisory versus reviewed labels in tests/test_safety.py

### Implementation for User Story 2

- [X] T028 [US2] Implement reusable current, stale, unavailable, error, and read-only source-state panels that retain independent content in frontend/js/workflow-context.js
- [X] T029 [US2] Restrict investigation response projection to noc-inv or Copilot MCP provenance/reference, availability, advisory review state, and concise reviewed context in backend/api/investigations.py
- [X] T030 [US2] Preserve read-only evidence provenance and sanitize investigation lifecycle context so it stores or returns no raw evidence, MCP output, credentials, direct Datadog result, or Jira-ticket investigation content in backend/services/investigations.py
- [X] T031 [US2] Project only concise operator-reviewed finding and state, never advisory or raw evidence, to notes, Dashboard, Status, End Shift, and handover in backend/services/shift_notes.py, backend/services/dashboard.py, backend/services/status.py, backend/services/end_shift.py, and backend/services/handover.py
- [X] T032 [P] [US2] Render Jira-cache and local-work states independently without a refresh in frontend/index.html
- [X] T033 [P] [US2] Render separately sourced Jira-cache, local-tracking, request-error, and read-only states in frontend/tickets.html
- [X] T034 [P] [US2] Render noc-inv/Copilot MCP provenance as read-only, evidence availability separately from workflow state, advisory analysis as non-authoritative, and reviewed findings only as operational context in frontend/investigations.html
- [X] T035 [P] [US2] Render independent Jira-cache, local-work, reviewed-finding, request-error, and read-only states in frontend/status.html
- [X] T036 [US2] Preserve valid Start Shift and End Shift preflight content while rendering actionable request errors and reviewed-only context in frontend/start-shift.html and frontend/end-shift.html

**Checkpoint**: Operators can identify every source condition and evidence boundary without masking
healthy information, triggering hidden work, or treating AI advice as authoritative.

---

## Phase 5: User Story 3 - Execute Deliberate Changes (Priority: P3)

**Goal**: Require a last-step explicit confirmation for every visible mutation, distinguish local
NOC actions from separately intentional Jira effects, and keep evidence-source access read-only.

**Independent Test**: Cancel every visible state-changing action and assert no request or artifact
change. Confirm each action and assert that it performs only the dialog's named local or Jira
effect. Verify Start Shift rejects missing or false confirmation before service execution, and
review/reject/publish actions never mutate evidence sources, Datadog, or Jira.

### Tests for User Story 3

- [X] T037 [P] [US3] Add missing, false, and true Start Shift confirmation request tests that assert no preflight execution or service mutation before confirmation in tests/test_start_shift.py
- [X] T038 [P] [US3] Add cancellation/no-request and confirmed local-tracking versus explicitly labeled Jira-action regression cases in tests/test_tickets.py
- [X] T039 [P] [US3] Add confirmed End Shift and handover execution-gate cancellation and success cases in tests/test_end_shift.py and tests/test_handover.py
- [X] T040 [P] [US3] Add review, reject, and publish cancellation/no-request cases that assert concise reviewed context only and no evidence-source, Datadog, or Jira mutation in tests/test_investigations.py
- [X] T041 [P] [US3] Add static checks for immediate confirmation dialogs, exact local/Jira scopes, reviewed-context destinations, and cancellation no-request behavior in tests/test_safety.py

### Implementation for User Story 3

- [X] T042 [US3] Require a boolean confirmed body and reject omitted or false values before Start Shift preflight or service execution in backend/api/start_shift.py
- [X] T043 [P] [US3] Send the confirmed Start Shift body only after an immediate confirmation dialog names its local workspace and Jira-refresh effect in frontend/start-shift.html
- [X] T044 [P] [US3] Route local tracking and separately labeled Jira ticket actions through the immediate shared confirmation dialog in frontend/tickets.html
- [X] T045 [P] [US3] Route investigation review, reject, and reviewed-finding publication through a local-context confirmation dialog without evidence-source, Datadog, or Jira mutation in frontend/investigations.html
- [X] T046 [P] [US3] Route visible End Shift generation, regeneration, and handover delivery actions through immediate confirmation dialogs in frontend/end-shift.html
- [X] T047 [US3] Refresh only relevant displayed data after a confirmed mutation and retain actionable action errors without automatic retry in frontend/js/api.js

**Checkpoint**: Every visible mutation is explicitly confirmed and accurately scoped; cancellation
is a no-request, no-change path, and evidence inspection remains read-only.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Document the additive contract and validate workflow, evidence, compatibility, and
regression behavior as a whole.

- [X] T048 [P] Document URL context, source states, noc-inv/Copilot-MCP evidence-only boundaries, advisory/reviewed distinction, reviewed-only propagation, and Start Shift confirmation in specs/004-operator-workflow/contracts/operational-workflow.md
- [X] T049 [P] Update focused automated and manual evidence-review validation instructions in specs/004-operator-workflow/quickstart.md
- [X] T050 Run the focused workflow, evidence, and propagation regression suite from specs/004-operator-workflow/quickstart.md
- [X] T051 Run the full pytest suite to verify existing Jira-cache, local-tracking, handover, and API-consumer compatibility in tests/

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 and T002 can start immediately in parallel; T003 and T004 follow the
  shared conventions.
- **Foundational (Phase 2)**: Depends on Phase 1 and blocks all user stories.
- **US1 (Phase 3)**: Depends on Phase 2. T008–T013 precede T014–T020.
- **US2 (Phase 4)**: Depends on Phase 2 and the stable shared shell from T020. T021–T027 precede
  T028–T036.
- **US3 (Phase 5)**: Depends on Phase 2 and the confirmation helper from T003. T037–T041 precede
  T042–T047.
- **Polish (Phase 6)**: Depends on completed selected user stories; T050 follows T048–T049 and
  T051 follows T050.

### User Story Dependencies

- **US1 (P1)**: Depends only on Foundational work and is the MVP.
- **US2 (P2)**: Depends on the shared shell delivered by US1; it preserves existing read contracts
  and adds only the documented, constrained investigation presentation.
- **US3 (P3)**: Depends on the shared confirmation helper; its Start Shift body is additive while
  ticket, Jira, handover, and evidence-source boundaries remain compatible.

### Within Each User Story

- Write and observe focused test failures before implementation.
- Complete shared modules before page integrations that consume them.
- Do not turn an unavailable source into a whole-page failure or trigger an automatic retry.
- Do not promote advisory AI output to operational state until explicit operator review.

---

## Parallel Opportunities

- T001 and T002 can run in parallel; T004 can proceed once the workflow paths are agreed.
- US1 tests T008–T013 can run in parallel. After T005, page integrations T014–T019 touch
  different files and can run in parallel.
- US2 tests T021–T027 can run in parallel. After T028–T031, the Dashboard, Tickets, Status, and
  Investigations presentation work in T032–T035 can run in parallel.
- US3 tests T037–T041 can run in parallel. After T003 and T042, T043–T046 touch separate pages
  and can run in parallel.
- T048 and T049 can run in parallel after feature behavior is complete.

## Parallel Example: User Story 2

```text
Task: "Add current, stale, unavailable, request-error, retained-local-work, and no-refresh Dashboard state tests in tests/test_dashboard.py"
Task: "Add Jira-cache versus local-tracking state separation and read-only inspection tests in tests/test_tickets.py"
Task: "Add noc-inv/Copilot-MCP-only provenance, read-only evidence failure/no-result, advisory-versus-reviewed, and no-direct-Datadog tests in tests/test_investigations.py"

Task: "Render Jira-cache and local-work states independently without a refresh in frontend/index.html"
Task: "Render separately sourced Jira-cache, local-tracking, request-error, and read-only states in frontend/tickets.html"
Task: "Render noc-inv/Copilot MCP provenance as read-only, evidence availability separately from workflow state, advisory analysis as non-authoritative, and reviewed findings only as operational context in frontend/investigations.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phases 1 and 2.
2. Complete and validate US1.
3. Demonstrate the six-page URL-backed journey and its no-mutation inspection behavior.
4. Stop before evidence-state or execution-gate expansion.

### Incremental Delivery

1. Deliver US1 for a coherent, reproducible daily workflow.
2. Add US2 for explicit source/evidence state and reviewed-only propagation.
3. Add US3 for deliberate, accurately scoped execution gates.
4. Complete Polish with focused and full regression verification.

### Parallel Team Strategy

1. Complete the context, styling, API-helper, and foundational safety work together.
2. Assign separate developers to the US1 page integrations, US2 state/evidence presentation, and
   US3 confirmation gates only after their shared prerequisites are complete.
3. Integrate and run T050–T051 after all selected story phases finish.

## Format Validation

All 51 tasks use the required `- [X] T### [P]? [US#]? Description with path` checklist format.
Setup, Foundational, and Polish tasks omit user-story labels; every user-story task has exactly one
user-story label; all new tasks are unchecked.
