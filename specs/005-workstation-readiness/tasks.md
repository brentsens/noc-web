---

description: "Implementation tasks for workstation operational readiness"
---

# Tasks: Workstation Operational Readiness

**Input**: Design documents from `/specs/005-workstation-readiness/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/readiness-api.md`, and `quickstart.md`

**Tests**: Automated tests are required by FR-016 and Constitution Principle IV. Write each listed test before its corresponding implementation and verify it fails first.

**Organization**: Tasks are grouped by user story so each can be implemented and validated independently.

## Path Conventions

- Backend: `backend/`
- Static frontend: `frontend/`
- Tests: `tests/`
- Documentation: `docs/`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish isolated readiness-test fixtures and the additive feature file boundaries.

- [X] T001 [P] Create isolated readiness fixture helpers for temporary NOC roots, cache records, environment control, mocked subprocess/liveness probes, and non-sensitive test data in `tests/conftest.py`
- [X] T002 [P] Create the focused readiness service test module with shared result assertions in `tests/test_readiness.py`
- [X] T003 [P] Create the readiness API contract/redaction test module and static-client test scaffolding in `tests/test_readiness_api.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the reusable safe configuration and result boundaries that every readiness assessment needs.

**⚠️ CRITICAL**: Complete this phase before beginning user-story implementation.

- [X] T004 Define immutable configuration-profile, cache-source-policy, readiness-check, and assessment result types with only the contract fields and no serializable path/value/exception/output fields in `backend/config.py` and `backend/services/readiness.py`
- [X] T005 Implement the single allowlisted environment resolver for exactly `NOC_WEB_NOC_ROOT`, `NOC_WEB_NOC_BIN`, `NOC_WEB_READINESS_PROBE_DIR`, `NOC_WEB_JIRA_CACHE_MAX_AGE_SECONDS`, and `NOC_WEB_COMMAND_TIMEOUT_SECONDS` in `backend/config.py`
- [X] T006 Implement controlled non-sensitive status, impact, corrective-action, and error serialization helpers that never retain or log raw environment values, paths, credentials, command output, record content, or exceptions in `backend/services/readiness.py`
- [X] T007 Register the additive readiness router without changing existing health, status, cache, ticket, or confirmed-action route behavior in `backend/app.py` and `backend/api/readiness.py`

**Checkpoint**: Shared profile/result boundaries are available; no existing operational action is changed.

---

## Phase 3: User Story 1 - Verify a workstation before a shift (Priority: P1) 🎯 MVP

**Goal**: Return one bounded, read-only assessment with independently identifiable configuration, NOC data, cache, command, write-capability, and liveness results.

**Independent Test**: With a valid default profile, compatible NOC/cache records, usable command catalog, and safe writable probe directory, `GET /api/readiness/{shift_date}` returns HTTP 200 with `overallStatus: ready`, all required checks, and a separately rendered liveness array within 60 seconds.

### Tests for User Story 1

- [X] T008 [P] [US1] Add service tests proving an absent `NOC_WEB_*` override preserves `Path.home() / "noc"`, `Path.home() / ".local" / "bin"`, the current command catalog, and default behavior in `tests/test_readiness.py`
- [X] T009 [P] [US1] Add NOC-data and compatibility tests for accessible compatible records, missing/unreadable/malformed records, and explicit non-mutating rejection of incompatible records in `tests/test_readiness.py`
- [X] T010 [P] [US1] Add per-source cache tests for `jiraOpenTickets` retaining `.jira-open-tickets.json` format; missing, unreadable, malformed, naive, incompatible, and no-valid-max-age failures; and the exact boundary `age < limit` ready versus `age >= limit` not ready in `tests/test_readiness.py`
- [X] T011 [P] [US1] Add command tests for locate, executable permission, successful non-destructive invocation, failure, and configured timeout with discarded output in `tests/test_readiness.py`
- [X] T012 [P] [US1] Add write-probe tests proving exclusive random create, tiny sentinel flush/sync, `finally` cleanup, no overwrite/delete of an existing file, and not-ready results for missing, permission, capacity, I/O, or cleanup failures in `tests/test_readiness.py`
- [X] T013 [P] [US1] Add API contract tests for valid/invalid shift dates, the HTTP-200 failed-assessment shape, distinct required checks, `readOnly: true`, and unchanged existing health/status/action responses in `tests/test_readiness_api.py`
- [X] T014 [US1] Implement shift-date validation and one-time configuration resolution before any data, cache, command, write, or liveness probe in `backend/api/readiness.py`
- [X] T015 [US1] Implement read-only, non-converting NOC-record validation using the established local record boundary in `backend/services/readiness.py`
- [X] T016 [US1] Generalize the existing Jira cache reader into source-keyed policies while retaining the `.jira-open-tickets.json` record format and evaluate each configured source independently against its own configured maximum age in `backend/services/jira_cache.py` and `backend/services/readiness.py`
- [X] T017 [US1] Implement the fixed catalogued non-destructive command probes with `subprocess.run(shell=False, timeout=profile.commandTimeoutSeconds)` and controlled result messages in `backend/services/readiness.py`
- [X] T018 [US1] Implement the approved-probe-directory write capability check using `O_CREAT | O_EXCL`, random filename, tiny sentinel write, flush/sync, and deletion of only the created file in `finally` in `backend/services/readiness.py`
- [X] T019 [US1] Aggregate `ready` only when configuration and every required NOC-data/cache/command/write check is ready; produce a new ephemeral assessment with separate diagnostic liveness list and no persistent diagnostic record in `backend/services/readiness.py`
- [X] T020 [US1] Implement `GET /api/readiness/{shift_date}` response serialization for the published 200 assessment contract without request query/body overrides or operational authorization in `backend/api/readiness.py`
- [X] T021 [US1] Add the read-only readiness request function and result parsing without a refresh or mutating action call in `frontend/js/api.js`
- [X] T022 [US1] Add the readiness page displaying the overall decision, configuration/NOC/cache/command/write results, per-source cache ages, and a separate liveness panel in `frontend/readiness.html`

**Checkpoint**: A valid default workstation can be assessed independently without changing operational data or authorizing an action.

---

## Phase 4: User Story 2 - Apply an explicit workstation override safely (Priority: P1)

**Goal**: Use only valid documented explicit overrides and reject every invalid explicit override before any operational probe, without fallback.

**Independent Test**: A valid override is selected without exposing its value; each blank, relative, malformed, unsafe, conflicting, inaccessible, unusable, or invalid numeric override returns redacted HTTP 422 with empty probe lists and no default/alternate access.

### Tests for User Story 2

- [X] T023 [P] [US2] Add resolver tests for each supported valid explicit path/numeric override, source `explicit`, normalization, positive bounded numeric validation, and no value/path serialization in `tests/test_readiness.py`
- [X] T024 [P] [US2] Add parameterized no-fallback tests for explicitly present blank, relative, malformed, unsafe, conflicting, inaccessible, and unusable path overrides and invalid/out-of-range cache-age or timeout overrides in `tests/test_readiness.py`
- [X] T025 [P] [US2] Add API tests proving every invalid explicit override returns the documented 422 redacted configuration result with `checks: []`, `liveness: []`, no command/data/cache/write/liveness invocation, and no default or alternate selection in `tests/test_readiness_api.py`
- [X] T026 [US2] Enforce explicit-path validation as absolute, normalized, approved, and non-conflicting; require the probe directory to be inside the resolved NOC root; preserve valid documented defaults only when the setting is absent in `backend/config.py`
- [X] T027 [US2] Enforce positive bounded integer validation for per-source cache maximum age and command timeout, including explicit blank-as-invalid presence semantics, in `backend/config.py`
- [X] T028 [US2] Return the published terminal 422 configuration failure with a logical setting identifier, generic corrective action, and no probe execution when an explicit override is invalid in `backend/api/readiness.py`
- [X] T029 [US2] Document the exact defaults, five supported overrides, absent-versus-blank behavior, validation rules, terminal no-fallback guarantee, and no credential/path disclosure in `docs/workstation-readiness.md`

**Checkpoint**: Explicit overrides safely select the intended profile or halt the assessment without touching a fallback profile.

---

## Phase 5: User Story 3 - Diagnose and recover a blocked capability (Priority: P2)

**Goal**: Clearly distinguish liveness from proven operational readiness and provide safe recovery guidance without revealing sensitive information.

**Independent Test**: A responding liveness probe combined with an unavailable command, inaccessible NOC data, stale cache, or non-writable destination reports the liveness state separately, keeps overall readiness not ready, provides corrective guidance, and exposes no secret or engineer-specific path.

### Tests for User Story 3

- [X] T030 [P] [US3] Add liveness tests for configured available/unavailable bounded read-only probes, unconfigured `notConfigured`, no implicit network call, and liveness never upgrading a failed required check in `tests/test_readiness.py`
- [X] T031 [P] [US3] Add recovery-guidance tests for each configuration, NOC-data, cache, command, and write-capability failure requiring a stable status, operational impact, and generic corrective action in `tests/test_readiness.py`
- [X] T032 [P] [US3] Add redaction tests seeding credentials, tokens, supplied paths, home/user paths, raw exception text, command stdout/stderr, and record content; assert their absence from JSON and logs in `tests/test_readiness.py` and `tests/test_readiness_api.py`
- [X] T033 [P] [US3] Add route/UI tests proving liveness can be available while write capability, command, cache, or NOC data is not ready and that the page does not present readiness as action confirmation in `tests/test_readiness_api.py`
- [X] T034 [US3] Implement separately configured, bounded, read-only liveness probes with `shell=False`, discarded output, and `available`/`unavailable`/`notConfigured` states only when explicitly documented in `backend/services/readiness.py`
- [X] T035 [US3] Make every failed or limited capability result include controlled status, operational impact, and non-sensitive corrective guidance while preserving liveness as diagnostic rather than gating evidence in `backend/services/readiness.py`
- [X] T036 [US3] Render limited/not-ready capability recovery guidance and the independent liveness diagnostic state without exposing raw diagnostics or offering an authorization control in `frontend/readiness.html`
- [X] T037 [US3] Document readiness-versus-liveness interpretation, blocked-capability recovery, cache-source age behavior, compatible/incompatible data handling, approved non-destructive write evidence, and post-readiness confirmation requirements in `docs/workstation-readiness.md`

**Checkpoint**: Operators can diagnose a blocked capability safely without confusing reachability with readiness.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate portability, safety, and the complete documented workflow.

- [X] T038 [P] Document Windows-native and WSL-specific absolute path/command expectations, no automatic cross-environment path translation, and portable exclusive-write-probe semantics in `docs/workstation-readiness.md`
- [X] T039 [P] Add focused regression tests that assert readiness performs no Jira refresh, ticket/workflow/cache mutation, data conversion, credential discovery, directory scan outside approved roots, or confirmation bypass in `tests/test_readiness.py` and `tests/test_readiness_api.py`
- [X] T040 Run and record the focused readiness validation scenarios and full pytest command specified by `specs/005-workstation-readiness/quickstart.md` in `specs/005-workstation-readiness/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies; T001–T003 can run in parallel.
- **Phase 2 (Foundational)**: T004 precedes T005–T006; T007 follows the common configuration/result boundary. It blocks all user stories.
- **US1 (Phase 3)**: Depends on Phase 2. Tests T008–T013 can begin in parallel; implementation follows from resolver/route boundaries through T014–T022.
- **US2 (Phase 4)**: Depends on Phase 2 and can proceed in parallel with US1 after T005–T007. T026–T028 rely on the resolver/route from Phase 2.
- **US3 (Phase 5)**: Depends on Phase 2 and can proceed in parallel with US1/US2 after the common result model exists. T034–T036 build on the assessment service/page introduced by US1.
- **Phase 6 (Polish)**: Depends on the desired stories; T038–T039 can run in parallel, and T040 follows their implementation.

### User Story Dependencies

- **US1 (P1)**: Foundation only; the MVP.
- **US2 (P1)**: Foundation only for its validation work; integrates its terminal error route with US1’s endpoint.
- **US3 (P2)**: Foundation for its model/tests; its UI/service integration follows US1’s assessment endpoint.

### Parallel Opportunities

- T001–T003 are independent file setup tasks.
- T008–T013 are independent US1 test areas.
- T023–T025 are independent US2 test areas.
- T030–T033 are independent US3 test areas.
- T038–T039 can run in parallel after feature implementation.

## Parallel Examples

### User Story 1

```text
Task: "Add per-source cache boundary tests in tests/test_readiness.py"
Task: "Add command probe tests in tests/test_readiness.py"
Task: "Add readiness API contract tests in tests/test_readiness_api.py"
```

### User Story 2

```text
Task: "Add valid explicit override tests in tests/test_readiness.py"
Task: "Add invalid explicit no-fallback tests in tests/test_readiness.py"
Task: "Add HTTP 422 terminal-result tests in tests/test_readiness_api.py"
```

### User Story 3

```text
Task: "Add liveness separation tests in tests/test_readiness.py"
Task: "Add sensitive-data redaction tests in tests/test_readiness_api.py"
Task: "Add recovery-guidance tests in tests/test_readiness.py"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phases 1 and 2.
2. Complete US1 tests and implementation.
3. Run the independent US1 test criteria and focused tests.
4. Demonstrate the read-only ready/not-ready assessment before proceeding.

### Incremental Delivery

1. Add US1 for the complete default-profile assessment.
2. Add US2 to make all explicit override handling terminal and safe.
3. Add US3 for diagnostics, recovery, and redaction hardening.
4. Complete portability and full-suite validation.

### Task Format Validation

All 40 tasks use the required unchecked checklist form, sequential IDs, `[P]` only for parallel work, `[US#]` on every story task, and explicit file paths.
