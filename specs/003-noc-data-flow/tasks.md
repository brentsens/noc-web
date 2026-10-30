---

description: "Task list for NOC Data Flow"
---

# Tasks: NOC Data Flow

**Input**: Design documents from `/specs/003-noc-data-flow/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/local-work-summary.md`, and `quickstart.md`

**Tests**: pytest coverage is required by the specification and constitution.

## Phase 1: Setup

**Purpose**: Establish a regression baseline before changing operational summaries.

- [X] T001 Run the existing pytest baseline in `tests/test_dashboard.py`, `tests/test_status.py`, `tests/test_shift_notes.py`, `tests/test_handover.py`, and `tests/test_end_shift.py`.

---

## Phase 2: Foundational Local-Work Projection

**Purpose**: Provide one validated active local-work source for every workflow.

- [X] T002 Add failing projection tests in `tests/test_tickets.py` for unique active `jiraKey` entries, local-only `trackingState`, `nextAction`, and `nocNotes`, closed-record exclusion, and malformed-local-data failure.
- [X] T003 Implement the canonical Operational Work Summary in `backend/services/tickets.py`, enforcing "`items` contains at most one entry per `jiraKey`", active-only state, and no Jira-managed fields.
- [X] T004 Add read-only no-Jira-write regression coverage for the shared projection in `tests/test_tickets.py`.

**Checkpoint**: A single safe local-work summary is available without copied Jira details.

---

## Phase 3: User Story 1 - See Consistent Local NOC Context (Priority: P1) 🎯 MVP

**Goal**: Show the same active local NOC context on Dashboard and Status.

**Independent Test**: Dashboard and Status expose the same active local-work entry or explicit
local-data failure, with no copied Jira fields.

- [X] T005 [P] [US1] Add Dashboard aggregation tests in `tests/test_dashboard.py` for additive `localWork`, empty active work, malformed local data, and no Jira writes.
- [X] T006 [P] [US1] Add Status aggregation tests in `tests/test_status.py` for the same `localWork` contract, closed-record exclusion, and no Jira writes.
- [X] T007 [US1] Aggregate the canonical local-work summary in `backend/services/dashboard.py` and expose its additive response in `backend/api/dashboard.py`.
- [X] T008 [US1] Aggregate the canonical local-work summary in `backend/services/status.py` and expose its additive response in `backend/api/status.py`.
- [X] T009 [US1] Render active local-work context, empty state, and actionable unavailable state in `frontend/index.html` without rendering Jira-managed ticket fields.
- [X] T010 [US1] Render the same local-work contract in `frontend/status.html` without changing existing Status behavior.

**Checkpoint**: Dashboard and Status show consistent local-only active work.

---

## Phase 4: User Story 2 - Carry Local Context into Shift Work (Priority: P2)

**Goal**: Include each active local work item once in shift notes and generated handovers.

**Independent Test**: Generated shift output has one local-only entry per active Jira reference,
excludes closed work, and preserves existing artifact data on failure.

- [X] T011 [P] [US2] Add shift-note tests in `tests/test_shift_notes.py` for active local context, closed exclusion, duplicate prevention, and local-data failure.
- [X] T012 [P] [US2] Add handover-generation tests in `tests/test_handover.py` for one `## Active Local NOC Work` entry per active `jiraKey`, no Jira fields, and no artifact overwrite on summary failure.
- [X] T013 [US2] Integrate the canonical local-work summary into `backend/services/shift_notes.py` while retaining existing shift-note content and read-only Jira behavior.
- [X] T014 [US2] Integrate one local-work snapshot into `backend/services/handover.py`, preserving existing handover content and excluding closed records.
- [X] T015 [US2] Update `backend/api/shift_notes.py` and `backend/api/handover.py` only as needed to expose actionable local-data failures without changing existing response fields.

**Checkpoint**: Shift artifacts retain existing content and add one local-only active-work section.

---

## Phase 5: User Story 3 - Complete End Shift with Accurate Local Work (Priority: P3)

**Goal**: Present outstanding active local work in End Shift without altering execution safeguards.

**Independent Test**: End Shift preflight distinguishes active, closed, and Jira-only tickets and
does not write Jira or bypass existing confirmation gates.

- [X] T016 [US3] Add End Shift tests in `tests/test_end_shift.py` for additive `localWork`, active-only filtering, malformed-local-data failure, and no Jira writes during preflight or execution.
- [X] T017 [US3] Aggregate the canonical local-work summary in `backend/services/end_shift.py` without changing existing End Shift execution or confirmation behavior.
- [X] T018 [US3] Expose the additive End Shift local-work contract in `backend/api/end_shift.py` with explicit local-data failures.
- [X] T019 [US3] Render outstanding local work, empty state, and local-data failure in `frontend/end-shift.html` without rendering Jira-managed fields.

**Checkpoint**: End Shift accurately shows active local work while retaining its safeguards.

---

## Phase 6: Polish & Cross-Cutting Validation

- [X] T020 Run focused local-work workflow validation in `tests/test_tickets.py`, `tests/test_dashboard.py`, `tests/test_status.py`, `tests/test_shift_notes.py`, `tests/test_handover.py`, and `tests/test_end_shift.py`.
- [X] T021 Run the full regression suite in `tests/` and execute `specs/003-noc-data-flow/quickstart.md`.
- [X] T022 Review `backend/services/tickets.py`, `backend/services/handover.py`, and `backend/services/end_shift.py` against `specs/003-noc-data-flow/contracts/local-work-summary.md` to verify unique local-only entries and no Jira write path.

---

## Dependencies & Execution Order

- Phase 1 precedes Phase 2.
- Phase 2 blocks every user story.
- US1 delivers the shared operator-facing response contract.
- US2 and US3 both depend on Phase 2 and can proceed after US1 when sequentially staffed.
- Phase 6 depends on all user stories.

```text
Phase 1 → Phase 2 → US1 → US2 → Phase 6
                         └→ US3 ───┘
```

## Parallel Opportunities

- T005 and T006 can run in parallel because they update different test files.
- T011 and T012 can run in parallel because they update different test files.
- All tasks editing `backend/services/tickets.py`, `backend/services/handover.py`, or an affected
  frontend page remain sequential with their corresponding contract work.

## Implementation Strategy

### MVP First

1. Complete T001-T004 to establish the single active local-work projection.
2. Complete T005-T010 to make Dashboard and Status consistent.
3. Validate User Story 1 independently before extending artifacts or End Shift.

### Incremental Delivery

1. Deliver Dashboard and Status local-work visibility.
2. Deliver local context in shift notes and handover artifacts.
3. Deliver End Shift local-work visibility and cross-workflow validation.
