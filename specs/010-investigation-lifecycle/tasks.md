---
description: "Implementation tasks for the operator-controlled investigation lifecycle"
---

# Tasks: Operator-Controlled Investigation Lifecycle

**Input**: Design documents from
`/specs/010-investigation-lifecycle/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/investigations-api.md`, and `quickstart.md`

**Tests**: Regression tests are included because the feature specification
explicitly requires coverage for lifecycle transitions, migration, cross-shift
visibility, attachment, handover, and failure behavior. Write tests before the
corresponding implementation and verify they fail for the intended reason.

**Organization**: Tasks are grouped by the four P1 user stories. Shared local
record migration/defaults are foundational; subsequent stories build on that
projection.

## Phase 1: Setup

**Purpose**: Prepare reusable isolated fixtures for file-backed tests. The
existing FastAPI, Pydantic, pytest, and ES-module tooling is sufficient; no
dependency or project initialization changes are needed.

- [X] T001 Add reusable temporary NOC-root and investigation-context builders in `tests/conftest.py`; keep all generated paths under pytest temporary directories.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish conservative lifecycle defaults and legacy migration
before any user story consumes lifecycle state.

- [X] T002 [P] Add legacy migration tests in `tests/test_investigations.py`: only explicitly `reviewed` records may migrate from reviewed-context `state`; exact normalized full matches of `cured`, `done`, `resolved`, `complete`, `completed`, `closed`, `fixed`, `recovered`, `cleared`, `remediated`, `fully cured`, `fully resolved`, `self-recovered`, and exact `done (cured)` map to `cured`; exact full matches of `active`, `open`, `ongoing`, `in progress`, `investigating`, `monitoring`, `escalated`, `unresolved`, `follow-up required`, and `follow up required` map to `escalated_to_incident`; unknown, conflicting, malformed, or unreviewed records map to `ready_for_review`; Markdown `Status` alone never sets lifecycle; preserve legacy `state` and prior records on write failure.
- [X] T003 [P] Add creation-default tests in `tests/test_investigation_generation.py`: every new investigation has `lifecycleStatus` `ready_for_review`, while `generationStatus`, `validationStatus`, and `reviewState` remain separate fields.
- [X] T004 Implement exact, conservative lifecycle migration and lifecycle projection defaults in `backend/services/investigations.py`; support only `ready_for_review`, `escalated_to_incident`, and `cured`, preserve legacy `state`, and use the existing atomic temporary-file-and-replace write pattern.
- [X] T005 Initialize newly generated investigations as `lifecycleStatus: ready_for_review` in `backend/services/investigation_generation.py` without rewriting generation or validation metadata.

**Checkpoint**: Existing and newly generated investigations expose a safe,
single lifecycle projection without yet changing operator transitions.

---

## Phase 3: User Story 1 - Review and Manage Investigation Lifecycle (Priority: P1)

**Goal**: Give operators one confirmed, forward-only lifecycle that remains
separate from generation, validation, and review metadata.

**Independent Test**: Generate an investigation, verify Ready for Review and
separate metadata, then confirm valid transitions. Verify selection alone
causes no write, required findings are enforced, and list/detail badges follow
`lifecycleStatus`.

### Tests for User Story 1

- [X] T006 [P] [US1] Add lifecycle service and API regression tests in `tests/test_investigation_lifecycle.py` for required findings, explicit confirmation, validation/lifecycle separation, atomic-write failure, the forward-only graph (Ready → Escalated/Cured; Escalated → Cured; Cured terminal), and zero mutation of Datadog, Jira, Shift Notes, Local NOC Tracking, or email.
- [X] T007 [P] [US1] Add frontend regression coverage in `tests/test_frontend_modules.py` proving lifecycle dropdown selection alone makes no API call, confirmation submits the choice, and list/detail badges use `lifecycleStatus` rather than `validationStatus`.

### Implementation for User Story 1

- [X] T008 [US1] Implement confirmed lifecycle transitions and atomic operator-context updates in `backend/services/investigations.py`; require a non-empty, concise, single-line finding for `escalated_to_incident` and `cured`, preserve the existing finding length limit, set `reviewState` to `reviewed`, and record `lastLifecycleChangedAt` as UTC plus `lastLifecycleChangedShiftDate` as `YYYY-MM-DD`.
- [X] T009 [US1] Update the review request model and route in `backend/api/investigations.py` to accept the lifecycle enum, finding, selected shift, and `confirmed: true`; reject every transition outside Ready → Escalated/Cured and Escalated → Cured without modifying the prior lifecycle or finding.
- [X] T010 [US1] Add the confirmed lifecycle request method to `frontend/js/api.js`; do not submit on dropdown change.
- [X] T011 [US1] Replace the free-form state control with an accessible lifecycle dropdown and single-line finding field in `frontend/investigations.html`; require immediate operator confirmation and render list/detail badges from `lifecycleStatus`.

**Checkpoint**: An operator can create, review, and explicitly advance an
investigation lifecycle without changing generated metadata or external state.

---

## Phase 4: User Story 2 - Carry Investigations Across Shifts (Priority: P1)

**Goal**: Show active investigations across selected shifts and retain cured
investigations in history without copying source evidence.

**Independent Test**: Create Ready and Escalated records on one shift, then
select later shifts and verify carried status and source identity. Cure a
record, verify it appears as Cured this shift, is absent from later active
views, and remains in history.

### Tests for User Story 2

- [X] T012 [P] [US2] Add cross-shift projection tests in `tests/test_investigation_projection.py` for `created_this_shift`, `carried`, `cured_this_shift`, and `historical`; verify Ready/Escalated persist across shifts, later active views exclude Cured, history retains it, unsafe source identifiers are rejected, and projections contain no copied raw evidence.

### Implementation for User Story 2

- [X] T013 [US2] Extend the shared projection in `backend/services/investigations.py` to enumerate validated source shifts and expose `selectedShiftDate`, `creationShiftDate`, safe `sourceReference`, `lifecycleStatus`, reviewed finding, last-change timestamp/shift, bounded incident reference, and visibility limited to `created_this_shift`, `carried`, `cured_this_shift`, or `historical`; do not copy raw investigation evidence.
- [X] T014 [US2] Extend the list route in `backend/api/investigations.py` with `view=active|history` (default `active`) and return the selected shift plus the cross-shift projection; keep detail and mutation identifiers bound to the creation shift and safe normalized name.
- [X] T015 [US2] Add active/history list calls and source-reference detail navigation to `frontend/js/api.js`; keep the selected shift in every request and response.
- [X] T016 [US2] Update `frontend/investigations.html` to distinguish Created this shift, Carried from an earlier shift, Cured this shift, and Historical, and provide active/history views while preserving the selected shift display.

**Checkpoint**: Active work carries across shifts, cured records remain
historically accessible, and source evidence stays only at its original path.

---

## Phase 5: User Story 3 - Attach a Current Datadog Incident (Priority: P1)

**Goal**: Let an operator explicitly attach one current ACTIVE or STABLE
Datadog incident using Feature 009's shared snapshot.

**Independent Test**: With a mocked CURRENT snapshot, attach a selected ACTIVE
or STABLE incident after confirmation. Verify exact reference fields and URL;
reject stale/unavailable/resolved choices; after successful refresh omission,
show the warning while lifecycle remains Escalated.

### Tests for User Story 3

- [X] T017 [P] [US3] Add attachment service/API tests in `tests/test_investigation_attachments.py` for current ACTIVE and STABLE acceptance; reject non-CURRENT cache, absent or RESOLVED incident, non-escalated investigation, missing confirmation, duplicate attachment, and title-based matching; verify persisted fields are exactly incident ID, URL, title, last-known state, and attachment timestamp, with cache freshness kept separate from Datadog state.
- [X] T018 [P] [US3] Add frontend attachment regressions in `tests/test_frontend_modules.py` for explicit incident selection/confirmation, cache freshness display, exact Datadog URL with `target="_blank"` and `rel="noopener noreferrer"`, and the resolved warning without local cure.

### Implementation for User Story 3

- [X] T019 [US3] Implement attachment validation and persistence in `backend/services/investigations.py`; accept only a `current` shared Feature 009 snapshot, an `escalated_to_incident` investigation, and exact `ACTIVE` or `STABLE` state; allow at most one reference with exact ID, URL, title, state, and UTC attachment time, and never copy raw evidence.
- [X] T020 [US3] Add the confirmed attachment endpoint in `backend/api/investigations.py`; use the shared incident snapshot without initiating retrieval and return explicit errors without writes for stale, refreshing, unavailable, absent, invalid-state, or already-attached cases.
- [X] T021 [US3] Add the attachment request method to `frontend/js/api.js` using the investigation creation-shift source reference and explicit `confirmed: true`.
- [X] T022 [US3] Add the incident picker and attachment display to `frontend/investigations.html`; show ID, title, optional severity, exact state, URL, and cache freshness; show “Datadog incident resolved”, “Local investigation still Escalated to Incident”, and “Operator review required” when a successful CURRENT snapshot omits the attached ID, without changing local lifecycle.

**Checkpoint**: Only explicitly selected current incidents attach; Datadog
resolution remains advisory and cannot cure a local investigation.

---

## Phase 6: User Story 4 - Apply Lifecycle Rules to End Shift and Handover (Priority: P1)

**Goal**: Make Dashboard, Status, End Shift, and handover readiness consume the
same lifecycle projection and exclude raw/generated evidence from handover.

**Independent Test**: Verify Ready blocks handover and is excluded, reviewed
Escalated context is concise and eligible, and Cured does not block or create
future actions; a cure-shift outcome may appear without raw evidence.

### Tests for User Story 4

- [X] T023 [P] [US4] Add lifecycle-consistency tests in `tests/test_dashboard.py` and `tests/test_status.py`; verify both use the same `lifecycleStatus` projection and never display `validationStatus` as the current lifecycle.
- [X] T024 [P] [US4] Add End Shift and handover tests in `tests/test_end_shift.py` and `tests/test_handover.py`; verify Ready blocks and generated content is excluded, reviewed Escalated context is concise, Cured does not block or create future actions, cure-shift outcomes are optional, and raw review/generated/Datadog content is not emitted.

### Implementation for User Story 4

- [X] T025 [P] [US4] Update `backend/services/dashboard.py` and `backend/services/status.py` to consume the shared lifecycle projection and consistently expose lifecycle labels and Ready-for-Review requirements.
- [X] T026 [P] [US4] Update `backend/services/end_shift.py` and `backend/services/handover.py` to block on Ready, include only reviewed Escalated context, include Cured only as an optional cure-shift outcome, and exclude generated future actions and raw evidence for Cured investigations.
- [X] T027 [US4] Update `frontend/index.html`, `frontend/status.html`, and `frontend/end-shift.html` to display the same lifecycle and selected-shift visibility, identify Ready review blockers, and show only the allowed concise handover context.

**Checkpoint**: Lifecycle status and readiness are consistent across
investigations, Dashboard, Status, End Shift, and handover.

---

## Phase 7: Polish and Cross-Cutting Concerns

**Purpose**: Keep design documentation and repository-wide validation aligned
with the completed implementation.

- [X] T028 Update `specs/010-investigation-lifecycle/contracts/investigations-api.md` and `specs/010-investigation-lifecycle/quickstart.md` to match final route fields, errors, lifecycle behavior, and executable validation commands.
- [X] T029 Run the focused and full checks listed in `specs/010-investigation-lifecycle/quickstart.md`, including pytest, Python compilation, frontend ES-module validation, and `git diff --check`; resolve all failures before completion.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001; no dependencies.
- **Foundational (Phase 2)**: T002 and T003 depend on T001 and can run in
  parallel. T004 follows T002; T005 follows T003 and T004. This phase blocks
  all user stories.
- **User Stories (Phases 3-6)**: Each story starts after its listed
  dependencies. Regression tests precede the corresponding implementation.
- **Polish (Phase 7)**: T028 and T029 follow all desired stories; documentation
  alignment precedes final validation.

### User Story Dependencies

- **US1 (P1)**: Depends on Phase 2. Establishes confirmed lifecycle actions and
  the frontend lifecycle control.
- **US2 (P1)**: Depends on US1 because cross-shift projection requires the
  authoritative lifecycle and source identity.
- **US3 (P1)**: Depends on US1 because attachment is allowed only for an
  escalated investigation. It follows US2 in this task order because both
  extend the same investigation service, API, and UI files.
- **US4 (P1)**: Depends on US1 and US2; its shared projection must include
  current lifecycle and carried/cured-shift classifications.

### Within Each User Story

- Write and run the story's regression tests before implementation.
- Complete service behavior before routing it through the API.
- Update the frontend API client before wiring UI actions that use it.
- Keep each story independently testable at its checkpoint.

### Parallel Opportunities

- **Foundation**: T002 and T003 can run in parallel after T001.
- **US1**: T006 and T007 can run in parallel because they use separate test
  files; after tests, backend service, API, frontend client, and UI work follows
  the declared dependency chain.
- **US2**: T012 is isolated test work; its service, API, client, and UI tasks
  proceed in order.
- **US3**: T017 and T018 can run in parallel; the service/API/client/UI tasks
  then proceed in order.
- **US4**: T023 and T024 can run in parallel. T025 and T026 can also proceed in
  parallel after the tests because they touch separate backend service files;
  T027 follows both.

## Parallel Examples

### Foundation

```text
Task T002: Add conservative migration tests in tests/test_investigations.py
Task T003: Add new-investigation default tests in tests/test_investigation_generation.py
```

### User Story 1

```text
Task T006: Add lifecycle service/API regression tests in tests/test_investigation_lifecycle.py
Task T007: Add confirmation UI regression tests in tests/test_frontend_modules.py
```

### User Story 2

```text
Task T012: Add cross-shift projection tests in tests/test_investigation_projection.py
```

### User Story 3

```text
Task T017: Add incident attachment tests in tests/test_investigation_attachments.py
Task T018: Add frontend attachment regressions in tests/test_frontend_modules.py
```

### User Story 4

```text
Task T023: Add Dashboard/Status lifecycle tests in tests/test_dashboard.py and tests/test_status.py
Task T024: Add End Shift/handover lifecycle tests in tests/test_end_shift.py and tests/test_handover.py
Task T025: Update Dashboard/Status backend consumers
Task T026: Update End Shift/handover backend consumers
```

## Implementation Strategy

### MVP First (User Story 1)

1. Complete setup and foundational migration/default work.
2. Complete US1 regression tests and lifecycle controls.
3. Validate new investigations, confirmed transitions, invalid transitions,
   atomic failure, and consistent list/detail badges.
4. Stop at the US1 checkpoint for an independently testable operator lifecycle.

### Incremental Delivery

1. Deliver US1 lifecycle review and confirmation.
2. Add US2 cross-shift visibility and history.
3. Add US3 confirmed Datadog incident attachment.
4. Add US4 shared readiness and handover behavior.
5. Run the final quickstart and repository checks.

## Phase 8: Convergence

- [X] T030 CRITICAL Preserve lifecycle and operator-context fields when rejecting an advisory, prevent rejection from reopening escalated or cured investigations, and add API/UI regression coverage per Constitution I, FR-023, FR-027 (contradicts)
- [X] T031 Keep an existing Datadog incident reference and safe link visible when snapshot retrieval fails while reporting unavailable freshness, and add frontend regression coverage per US3/AC2 (partial)

## Phase 9: Convergence

- [X] T032 Show the stored Datadog incident link for cured investigations in history without enabling new attachment or presenting an inaccurate escalation warning, and add frontend regression coverage per FR-015, US3/AC4

## Phase 10: Convergence

- [X] T033 Reject lifecycle transitions whose selected shift predates the investigation's creation shift and add API regression coverage per FR-009, FR-010
