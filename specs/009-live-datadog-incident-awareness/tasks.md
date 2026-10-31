# Tasks: Live Datadog Incident Awareness

**Input**: Design documents from `specs/009-live-datadog-incident-awareness/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/incidents-api.md`

**Organization**: Tasks are grouped by user story so each increment remains independently testable.

## Phase 1: Setup

No dependency, database, or project initialization changes are required. Keep
the feature within the existing FastAPI, Copilot CLI, configured NOC storage,
and static ES-module application.

## Phase 2: Foundational

No separate shared infrastructure is required. Implement and test each
capability in its user-story phase; all stories use the shared incident service
introduced in User Story 1.

## Phase 3: User Story 1 - See current Datadog incidents (Priority: P1) 🎯 MVP

**Goal**: Retrieve, validate, cache, and display one shared current incident snapshot on Dashboard and Investigations.

**Independent Test**: Mock successful multiple-incident and empty responses; verify one validated snapshot and identical projections on both pages, while malformed output fails closed and cannot replace a prior snapshot.

### Tests for User Story 1

- [X] T001 [P] [US1] Add service tests in `tests/test_datadog_incidents.py` for successful multiple-incident and successful-empty responses, live-only states, resolved-incident disappearance after a later success, malformed output rejection, and prior-snapshot preservation.
- [X] T002 [P] [US1] Add API tests in `tests/test_datadog_incidents_api.py` proving Dashboard and Investigations consume the same cached snapshot, normal reads do not wait for provider execution, and both endpoints expose the same response contract.

### Implementation for User Story 1

- [X] T003 [US1] Implement `backend/services/datadog_incidents.py` with a fixed Copilot CLI prompt, `subprocess.run` argument array, explicit `shell=False`, bounded timeout, strict `--available-tools datadog(search_datadog_incidents)` filtering, strict JSON validation, and no raw provider logging or output.
- [X] T004 [US1] Implement the cache and projection in `backend/services/datadog_incidents.py`: `id` is required, non-empty, at most 128 characters and unique; `title` is required, non-empty and at most 200 characters; preserve exact Datadog `state`, retaining `ACTIVE` or `STABLE` and excluding `RESOLVED` only after a successful refresh; optional `severity` is non-empty and at most 32 characters; optional `createdAt` and `updatedAt` are valid RFC 3339 timestamps of at most 40 characters; optional `summary` is at most 500 characters; optional `url` is at most 2048 characters and HTTPS on `datadoghq.com` or `datadoghq.eu`; reject unknown keys and malformed entries.
- [X] T005 [US1] Add `backend/api/datadog_incidents.py` with the shared `GET /api/datadog/incidents` and explicit `POST /api/datadog/incidents/refresh` contract, then register the router in `backend/app.py`.
- [X] T006 [US1] Add `getDatadogIncidents` and `refreshDatadogIncidents` to `frontend/js/api.js` using the shared API response contract.
- [X] T007 [US1] Create the reusable Datadog Incidents card and renderer in `frontend/js/active-incidents.js`, using text-only DOM rendering and distinguishing current, stale, unavailable, and refreshing from local investigations.
- [X] T008 [P] [US1] Add the Datadog Incidents Dashboard card to `frontend/index.html` and render the shared cached incident projection.
- [X] T009 [P] [US1] Add a visually separate Datadog Incidents section to `frontend/investigations.html`, keeping local NOC Investigations distinct and rendering the same shared projection.

## Phase 4: User Story 2 - Understand freshness and recover from retrieval failures (Priority: P1)

**Goal**: Refresh in the background on a 60-second target, coalesce concurrent requests, and preserve the last successful snapshot on all failures.

**Independent Test**: Seed a valid cache, force provider, timeout, malformed-output, and storage failures, and verify incident data and last-success time remain while status is stale. Without a valid cache, verify unavailable rather than a successful zero.

### Tests for User Story 2

- [X] T010 [P] [US2] Extend `tests/test_datadog_incidents.py` to cover last-attempt and last-success timestamps, stale after failure or age, unavailable on first failure, storage errors, missing CLI, timeout, and malformed individual incident entries.
- [X] T011 [P] [US2] Extend `tests/test_datadog_incidents_api.py` and service tests to prove automatic and manual refresh are read-only, simultaneous refresh attempts coalesce, cache reads remain nonblocking, and an empty successful list differs from unavailable.

### Implementation for User Story 2

- [X] T012 [US2] Add shared freshness evaluation and single-flight background refresh scheduling to `backend/services/datadog_incidents.py`, using the 60-second target, recording last attempted/successful refresh times, and returning `refreshing` while one operation is active.
- [X] T013 [US2] Make cache writes in `backend/services/datadog_incidents.py` atomic and failure-safe: commit only complete validated successful snapshots; on failure persist only safe attempt/freshness metadata while preserving the previous incident list and last-success timestamp.
- [X] T014 [US2] Wire explicit refresh and cache-due automatic scheduling through the shared endpoints in `backend/api/datadog_incidents.py`; keep `GET /api/datadog/incidents` nonblocking and make concurrent refresh requests share one active operation.
- [X] T015 [US2] Add the “Refresh Incidents” control and refreshing/failure/last-success display to `frontend/js/active-incidents.js`; refresh only through the shared API service and never call Datadog from browser code.

## Phase 5: User Story 3 - Start an investigation only by operator choice (Priority: P1)

**Goal**: Allow an operator to open the existing investigation form from a current incident without automatic creation or bypassing existing gates.

**Independent Test**: Verify incident refresh changes only its own cache, leaves investigation review/history and handover inputs unchanged, and the optional incident title hint still requires Notebook URL, Preview, and explicit confirmation.

### Tests for User Story 3

- [X] T016 [P] [US3] Add regression coverage in `tests/test_datadog_incidents_api.py` proving automatic/manual retrieval never creates, reviews, rejects, closes, or deletes local investigations and never adds live incidents to handover inputs.
- [X] T017 [P] [US3] Add frontend regression coverage for incident navigation in `tests/test_datadog_incidents_frontend.py`, proving only a one-time session-local display-title hint is passed and no Notebook URL, Preview, or confirmation gate is bypassed.

### Implementation for User Story 3

- [X] T018 [US3] Add the explicit “Create Investigation” action in `frontend/js/active-incidents.js`, navigating with only the session-local display title and no automatic API mutation.
- [X] T019 [US3] Prefill only the existing investigation title input from the one-time session handoff in `frontend/investigations.html`; leave Notebook URL empty and preserve the existing Preview and confirmed creation actions.

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T020 [P] [US1] Add sanitized provider fixtures and regression cases for unknown response keys, duplicate incident IDs, unsafe Datadog URLs, invalid timestamps, overlong fields, exclusion of resolved incidents, and rejection of unrecognized state values in `tests/test_datadog_incidents.py`.
- [X] T021 [P] [US2] Verify frontend module syntax for all changed frontend files and run relevant pytest coverage for `tests/test_datadog_incidents.py` and `tests/test_datadog_incidents_api.py`.
- [X] T022 [US2] Run the complete pytest suite, frontend ES-module validation, and `git diff --check`; fix only regressions introduced by this feature.
- [X] T023 [US3] Review changed files for any direct Datadog HTTP/SDK/browser retrieval, broad Copilot tool exposure, raw prompt/provider persistence, Assistant integration, or automatic handover/investigation mutation and remove any violation.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependency changes or project initialization are needed.
- **Foundational (Phase 2)**: No separate foundational code; User Story 1 establishes the shared service used by later stories.
- **User Story 1 (Phase 3)**: Implements the MVP and must complete before US2/US3.
- **User Story 2 (Phase 4)**: Depends on the shared service and API contract from US1.
- **User Story 3 (Phase 5)**: Depends on the shared incident card and existing investigation form from US1; it does not change the investigation backend.
- **Polish (Phase 6)**: Depends on all three user stories.

### User Story Dependencies

- **US1 (P1)**: Independent MVP after setup; produces the shared bounded read contract and both read-only views.
- **US2 (P1)**: Depends on US1's service and API to add automatic/manual refresh semantics and failure freshness.
- **US3 (P1)**: Depends on US1's incident card and existing investigation UI; does not depend on US2's freshness implementation.

### Parallel Opportunities

- T001 and T002 can be written in parallel because they target separate test files.
- T008 and T009 can be implemented in parallel after T007 because they target separate pages.
- T010 and T011 can be written in parallel because they target separate test files.
- T016 and T017 can be written in parallel because they target separate test files.
- T020 and T021 can be worked on in parallel after their corresponding stories are complete.

## Implementation Strategy

### MVP First

1. Complete US1 tests, provider/cache service, API, and the two shared-cache views.
2. Verify ACTIVE/STABLE, multiple, resolved-after-success, empty-success, malformed-output, and shell/tool-boundary cases.
3. Add US2 freshness and failure preservation before enabling automatic scheduling.
4. Add US3 title-only navigation while preserving existing investigation gates.
5. Run the full regression and frontend validation suite before feature completion.

### Notes

- All test tasks are required by the explicit user regression-test list; write them before their corresponding implementation.
- No Datadog call, network access, or real NOC filesystem access is permitted in automated tests.
- No commits, pushes, or external mutations are part of this feature.

## Phase 7: Convergence

- [X] T024 Implement cross-process single-flight refresh coordination for workers sharing the incident cache, with a regression test proving at most one retrieval runs at a time per FR-007 and SC-009 (partial).
- [X] T025 Add boundary regression tests proving 100 valid incidents succeed and 101 incidents fail without truncating or replacing the previous snapshot per SC-010 (partial).

## Phase 8: Convergence

- [X] T026 Make shared cache reads report REFRESHING while another worker holds the refresh lock, without blocking, and add cross-worker GET regression coverage per FR-005, US2/AC3, and SC-009 (partial).

## Phase 9: Convergence

- [X] T027 Preserve the last successful incident projection and timestamp when a shared-cache GET fails; report stale/request-failure state rather than unavailable when cached data exists, with UI regression coverage per FR-010 and US2/AC1 (partial).
- [X] T028 Render incident IDs in the shared incident cards using text-only DOM rendering and add Dashboard/Investigations regression coverage per FR-003 and US1/AC1 (partial).

## Phase 10: Datadog State Lifecycle

- [X] T029 [US1/US2/US3] Add service, API, and frontend regression coverage for ACTIVE/STABLE visibility and transitions, exact state display, successful RESOLVED removal, failed-refresh state preservation, independent cache freshness, and unchanged local investigation state per FR-003–FR-005, FR-015–FR-017, and SC-011.
- [X] T030 [US1/US2/US3] Accept current uppercase Datadog states without rewriting provider values, retain ACTIVE and STABLE across snapshots, remove RESOLVED only on successful refresh, render the exact incident state, and label the shared UI “Datadog Incidents” per FR-001, FR-003–FR-005, and FR-016 (partial).

## Phase 11: Convergence

- [X] T031 Update incident count and empty-state wording to describe current Datadog incidents, including both ACTIVE and STABLE, and add frontend regression coverage for mixed-state and successful-empty snapshots per FR-001, FR-004, and US1/AC4 (partial).
- [X] T032 Keep the explicit Refresh Incidents control functional after each render and add regression coverage for repeated manual refreshes without a page reload per FR-006 and US2/AC3 (partial).

## Phase 12: Provider Output Reliability

- [X] T033 [US1/US2] Use Copilot CLI JSONL transport, isolate the final assistant message for strict JSON parsing, grant execution permission only to the Datadog incident-search tool, and regress prose, Markdown fences, commentary, extra JSON, prior-snapshot preservation, and redacted diagnostics without changing the incident schema.

## Phase 13: Convergence

- [X] T034 Add an explicit typed incident-snapshot response schema and bind both API routes to it (CRITICAL) per Constitution III (contradicts)
- [X] T035 Require successful completion of the authorized Datadog incident-search tool before accepting CLI output, with regressions for missing or failed tool calls (HIGH) per FR-011 (partial)
