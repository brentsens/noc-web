---

description: "Task list for Local NOC Tracking"
---

# Tasks: Local NOC Tracking

**Input**: Design documents from `/specs/002-local-noc-tracking/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/ticket-tracking.md`, and `quickstart.md`

**Tests**: pytest coverage is required by the specification and constitution.

**Organization**: Tasks are grouped by user story so each operator-facing workflow can be
implemented and tested independently after the common local-tracking projection is available.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it changes a different file and has no incomplete dependency.
- **[Story]**: Maps a task to a user story from `spec.md`.

## Phase 1: Setup

**Purpose**: Establish a regression baseline before changing ticket, sync, or handover behavior.

- [X] T001 Run the existing pytest baseline in `tests/test_ticket_sync.py` and `tests/test_handover.py`, recording any pre-existing failures before modifying `backend/services/tickets.py`.

---

## Phase 2: Foundational Local-Tracking Contract

**Purpose**: Add the additive, compatible local-tracking projection that all user stories consume.

- [X] T002 Add failing regression coverage for legacy tracked-ticket normalization, additive `trackingState`, and retained NOC context in `tests/test_tickets.py`.
- [X] T003 Add failing API contract coverage for an additive `trackingState` and optional `localTracking` in `tests/test_tickets.py`.
- [X] T004 Extend `backend/services/tickets.py` to read existing tracked-ticket records compatibly and project `trackingState` as `jira-only`, `active`, or `closed` plus optional local tracking context.
- [X] T005 Extend the ticket response contract in `backend/api/tickets.py` so existing ticket fields are unchanged and `trackingState` and `localTracking` are additive.

**Checkpoint**: Legacy tracked tickets remain accessible and every ticket has an unambiguous,
read-only tracking state.

---

## Phase 3: User Story 1 - Start Local Tracking (Priority: P1) 🎯 MVP

**Goal**: Allow an operator to explicitly start tracking a Jira-only ticket with local NOC context
without changing Jira.

**Independent Test**: A Jira-only ticket becomes locally active only after confirmation, shows its
saved Next Action and NOC Notes, rejects a duplicate active record, and makes no Jira mutation.

- [X] T006 [US1] Add failing create-tracking tests in `tests/test_tickets.py` for confirmed creation, missing/cancelled/stale/mismatched confirmation, duplicate active records, `jiraKey` validation, and no Jira create/update/transition/close calls.
- [X] T007 [US1] Implement local tracking creation in `backend/services/tickets.py`, enforcing the data-model rules "`jiraKey` is required, valid, and immutable", new state is `active`, and only local `nextAction`, `nocNotes`, `createdAt`, and `updatedAt` are persisted.
- [X] T008 [US1] Add an explicit confirmed create-tracking operation to `backend/api/tickets.py` that returns actionable validation and duplicate-record failures without changing Jira.
- [X] T009 [US1] Add Jira-only ticket tracking controls, a confirmation immediately before creation, and active local-context rendering in `frontend/tickets.html` without issuing a Jira mutation.

**Checkpoint**: A Jira-only ticket can be explicitly tracked as local NOC work while Jira remains
the source of truth.

---

## Phase 4: User Story 2 - Maintain NOC Context (Priority: P2)

**Goal**: Let operators deliberately update local NOC context and refresh Jira-owned display data
without mixing ownership or losing saved work.

**Independent Test**: A confirmed update changes only Next Action and NOC Notes; a confirmed sync
refreshes the Jira view, preserves local context, and leaves Jira unmodified, including on failure.

- [X] T010 [P] [US2] Add failing local-context update tests in `tests/test_tickets.py` for confirmed and cancelled updates, wrong-state rejection, and no Jira mutations.
- [X] T011 [P] [US2] Add failing explicit-sync tests in `tests/test_ticket_sync.py` for confirmation, retained `nextAction` and `nocNotes`, Jira unavailability, and no Jira write/transition operation.
- [X] T012 [US2] Implement confirmed local-context updates in `backend/services/tickets.py`, allowing changes only to NOC-owned `nextAction` and `nocNotes` while retaining the same `jiraKey` and `active` state.
- [X] T013 [US2] Implement explicit, read-only Jira-view synchronization in `backend/services/ticket_sync.py`; preserve local `nextAction`, `nocNotes`, and lifecycle state if the sync succeeds or fails.
- [X] T014 [US2] Add confirmed update and sync operations to `backend/api/tickets.py`, returning an actionable error for unavailable Jira data or invalid tracking state without overwriting local context.
- [X] T015 [US2] Add local-context edit/save and explicit sync controls with immediate confirmations, ownership labels, and failure messaging in `frontend/tickets.html`.

**Checkpoint**: Operators can maintain NOC context and request a read-only Jira refresh without
silently changing Jira or losing local data.

---

## Phase 5: User Story 3 - Close Local Tracking and Preserve Handover (Priority: P3)

**Goal**: Allow operators to deliberately close or reactivate local tracking while retaining
historical context and existing handover behavior.

**Independent Test**: A confirmed closure makes only local tracking closed; a separately confirmed
reactivation restores it to active; legacy and new records remain usable by handover with Jira
unchanged.

- [X] T016 [P] [US3] Add failing lifecycle tests in `tests/test_tickets.py` for confirmed close/reactivate, cancelled confirmation, `closedAt`, duplicate-active prevention, and no Jira mutations.
- [X] T017 [P] [US3] Add handover compatibility tests in `tests/test_handover.py` for legacy and new active tracked tickets retaining their NOC context after the local-tracking projection changes.
- [X] T018 [US3] Implement confirmed close and reactivate transitions in `backend/services/tickets.py`, setting `closedAt` only on close and enforcing `active`/`closed` target-state validation without altering Jira.
- [X] T019 [US3] Add explicit confirmed close and reactivate operations to `backend/api/tickets.py` with clear wrong-state and confirmation failures.
- [X] T020 [US3] Preserve compatible active tracked-ticket consumption in `backend/services/handover.py` while excluding closed work from active handover output and retaining its historical context.
- [X] T021 [US3] Add active/closed state indicators plus separate confirmed close and reactivate controls in `frontend/tickets.html`, without presenting local closure as Jira closure.

**Checkpoint**: Local tracking has a deliberate lifecycle, and existing handover behavior remains
compatible.

---

## Phase 6: Polish & Cross-Cutting Validation

**Purpose**: Validate complete contract behavior, confirmation gates, data integrity, and operator
experience.

- [X] T022 Run focused tracking, sync, and handover validation in `tests/test_tickets.py`, `tests/test_ticket_sync.py`, and `tests/test_handover.py`.
- [X] T023 Run the full regression suite in `tests/` and execute the operator scenarios in `specs/002-local-noc-tracking/quickstart.md`.
- [X] T024 Review `frontend/tickets.html` and `backend/api/tickets.py` against `specs/002-local-noc-tracking/contracts/ticket-tracking.md` to verify every create, update, sync, close, and reactivate action has an immediate explicit confirmation and no Jira write path.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** has no dependencies.
- **Phase 2** depends on the baseline and blocks all user stories.
- **US1** depends on Phase 2.
- **US2** depends on the active tracking record delivered by US1.
- **US3** depends on the active tracking record delivered by US1; its handover compatibility work
  also depends on the finalized tracking projection.
- **Phase 6** depends on all user stories.

### User Story Dependencies

```text
Phase 1 → Phase 2 → US1 → US2 → Phase 6
                         └→ US3 ───┘
```

### Within Each User Story

- Write and observe the focused tests fail before the corresponding implementation.
- Complete service behavior before exposing the API operation.
- Complete API behavior before wiring the Tickets-page action.
- Preserve the local/Jira ownership boundary in every layer.

### Parallel Opportunities

- **US2**: T010 and T011 can run in parallel because they cover local updates and synchronization
  in different test files.
- **US3**: T016 and T017 can run in parallel because they cover lifecycle and handover
  compatibility in different test files.
- All subsequent tasks that edit `backend/services/tickets.py`, `backend/api/tickets.py`, or
  `frontend/tickets.html` are sequential to avoid file conflicts.

### Parallel Example: User Story 2

```text
Task: "Add local-context update tests in tests/test_tickets.py"
Task: "Add explicit-sync tests in tests/test_ticket_sync.py"
```

---

## Implementation Strategy

### MVP First

1. Complete T001-T005 to preserve and expose the compatible tracking projection.
2. Complete T006-T009 to deliver explicit local tracking for Jira-only tickets.
3. Validate US1 independently before expanding local maintenance or lifecycle behavior.

### Incremental Delivery

1. Deliver US1 to start local tracking with clear ownership and confirmation.
2. Deliver US2 to maintain NOC context and explicitly sync the Jira view.
3. Deliver US3 to close/reactivate local tracking and preserve handover compatibility.
4. Complete cross-cutting validation of every confirmation and no-Jira-write boundary.
