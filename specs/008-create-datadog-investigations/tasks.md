# Tasks: Confirmation-Gated Datadog Investigation Creation

**Input**: Design documents from `specs/008-create-datadog-investigations/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, and `quickstart.md`

**Tests**: Tests are included because the feature specification explicitly requires regression coverage for preview, confirmation, validation, failures, review, propagation, and frontend modules.

**Organization**: Tasks are grouped by the three P1 user stories. Complete shared test/configuration foundations first, then deliver preview/confirmed creation, generated-record validation/review, and reviewed-only propagation.

## Phase 1: Setup

**Purpose**: Provide isolated test infrastructure for the command and filesystem workflows.

- [X] T001 Add temporary NOC-root/configuration and fake `noc-inv` executable fixtures in `tests/conftest.py`; tests must not use real NOC data, network services, or credentials.

---

## Phase 2: Foundational

**Purpose**: Establish shared generation state and readiness required by every creation story.

- [X] T002 [P] Define shared request/result types in `backend/services/investigation_generation.py`, with `generationStatus` values `completed`, `failed`, `timed_out`, or `unavailable`, `validationStatus` values `ready_for_review` or `needs_review`, and initial `reviewState` `unreviewed`; keep the frontend/API contract independent of subprocess details.
- [X] T003 [P] Add a bounded `NOC_WEB_INVESTIGATION_TIMEOUT_SECONDS` setting (default 300, maximum 900) in `backend/config.py`, and extend readiness to report `noc-inv`, GitHub Copilot CLI, and writable investigation-storage availability in `backend/services/readiness.py`, with isolated regression coverage in `tests/test_readiness.py`.

**Checkpoint**: Shared contracts and readiness are available; user-story implementation can proceed.

---

## Phase 3: User Story 1 - Preview and confirm an investigation (Priority: P1) 🎯 MVP

**Goal**: Provide a read-only preview and a separate, explicitly confirmed, shift-scoped generation action.

**Independent Test**: Preview valid inputs and verify the selected shift, normalized investigation name, exact Notebook URL, logical target, generation/review warnings, and no-source-modification notice without starting a process or creating files. Then confirm separately and verify only the displayed shift/name are targeted.

### Tests for User Story 1

- [X] T004 [P] [US1] Add preview tests proving no command or filesystem mutation, selected-shift validation, and exact preview fields in `tests/test_investigation_creation.py`.
- [X] T005 [P] [US1] Add generation-adapter tests for explicit confirmation, duplicate conflict, argument-array invocation, disabled shell interpretation, bounded timeout, missing `noc-inv`, Copilot/MCP/authentication unavailability, non-zero exit, missing output, permission failure, and sanitized errors in `tests/test_investigation_generation.py`.

### Implementation for User Story 1

- [X] T006 [US1] Implement request validation in `backend/services/investigation_generation.py`: Investigation Name is required and trimmed; normalization lowercases, collapses whitespace/repeated hyphens, accepts only ASCII letters/digits/hyphens, starts with a letter/digit, and is at most 80 characters; reject separators, traversal, controls, empty normalized names, and other unsafe values.
- [X] T007 [US1] Implement FINAL Notebook URL validation in `backend/services/investigation_generation.py`: accept only HTTPS `https://app.datadoghq.com/notebook/<numeric-id>/<slug>` with one non-empty slug segment; reject credentials, other hosts/schemes, extra path segments, query strings, and fragments; preserve the exact validated URL.
- [X] T008 [US1] Implement the bounded `noc-inv` adapter in `backend/services/investigation_generation.py` using the fixed argument sequence from `contracts/noc-inv-invocation.md`, `shell=False`, configured executable/timeout, server-generated staging path, sanitized outcomes, cleanup, and no interactive fallback.
- [X] T009 [US1] Add stateless preview and explicitly confirmed create request models/routes in `backend/api/investigations.py`; use the shift-scoped route, return 409 for normalized-name conflicts, revalidate at creation, and never invoke generation unless `confirmed` is literal `true`.
- [X] T010 [P] [US1] Add preview/create API client methods in `frontend/js/api.js` and the selected-shift create form, preview panel, Cancel, and **Create Investigation** action in `frontend/investigations.html`; preserve validated shift context and show the exact values requiring confirmation.
- [X] T011 [P] [US1] Add frontend module/import and create-form regression checks in `tests/test_frontend_modules.py`, including that external Notebook URLs are not fetched or given noc-web context.
- [X] T012 [US1] Run focused US1 tests from `tests/test_investigation_creation.py`, `tests/test_investigation_generation.py`, `tests/test_readiness.py`, and `tests/test_frontend_modules.py`; resolve failures before proceeding.

**Checkpoint**: Preview is read-only and creation is possible only through the explicit confirmation action. Do not expose generated content as validated or reviewed yet.

---

## Phase 4: User Story 2 - Validate and review a generated investigation (Priority: P1)

**Goal**: Validate generated output, display its status/provenance/content, select it after refresh, and preserve explicit Review/Reject behavior.

**Independent Test**: A valid mocked generation appears as READY FOR REVIEW and remains unreviewed. Safe malformed output remains inspectable as GENERATED RECORD NEEDS REVIEW, cannot be marked reviewed, and is excluded from propagation. A refresh failure is distinct from generation status.

### Tests for User Story 2

- [X] T013 [P] [US2] Add generated-record tests for required metadata, selected shift/name, exact URL, provenance, required headings, placeholder-only sections, missing output, malformed output, and safe retention in `tests/test_investigation_output_validation.py`.
- [X] T014 [P] [US2] Add review/reject regression tests proving generated records start unreviewed, malformed records cannot be reviewed, and explicit Reject remains available in `tests/test_investigations.py`.

### Implementation for User Story 2

- [X] T015 [US2] Implement generated-output validation and safe staging/publication in `backend/services/investigation_generation.py`: `shiftDate` must equal the requested shift, `name` must equal the normalized request identifier, `notebookUrl` must preserve the exact validated URL, and provenance must identify `noc-inv` or Copilot MCP; require non-placeholder Summary, Confirmed Findings, Current Status, Handover Summary, and Next Actions when required; preserve safe malformed output as needs-review, clean temporary files, and prevent overwrite.
- [X] T016 [US2] Extend the shift-scoped investigation projection in `backend/services/investigations.py` to expose generation/validation state, provenance, exact Notebook URL, advisory content, review state, and unavailable sections without raw diagnostics.
- [X] T017 [US2] Guard Review in `backend/services/investigations.py` and `backend/api/investigations.py` so only eligible validated findings can be explicitly reviewed; preserve confirmed Reject behavior and the existing reviewed-context format.
- [X] T018 [US2] Update `frontend/investigations.html` to refresh and select the created record, display generation/validation/provenance/URL/advisory/review states, and distinguish list-refresh failure from creation failure.

**Checkpoint**: Generated records are inspectable, validation is visible, and successful generation never implies operator review.

---

## Phase 5: User Story 3 - Propagate only reviewed findings (Priority: P1)

**Goal**: Keep pending, rejected, malformed, and raw evidence out of downstream operational context and handover; show required review in End Shift readiness.

**Independent Test**: Across valid reviewed, unreviewed, rejected, malformed, and historical-shift cases, only concise validated reviewed findings and approved handover summaries appear in permitted operational views. Pending review is visible in End Shift readiness and raw evidence never enters handover or Assistant reviewed-finding context.

### Tests for User Story 3

- [X] T019 [P] [US3] Add reviewed-only propagation tests for Dashboard, Status, and Shift Notes projections in `tests/test_dashboard.py`, `tests/test_status.py`, and `tests/test_shift_notes.py`.
- [X] T020 [P] [US3] Add reviewed/unreviewed/rejected/malformed and raw-evidence exclusion tests for handover and Assistant context in `tests/test_handover.py` and `tests/test_assistant.py`.
- [X] T021 [P] [US3] Add End Shift readiness and historical-shift isolation tests for pending review and malformed generated records in `tests/test_end_shift.py` and `tests/test_investigations.py`.

### Implementation for User Story 3

- [X] T022 [US3] Enforce the validated-and-explicitly-reviewed gate in `get_reviewed_findings()` in `backend/services/investigations.py`; preserve compatible existing reviewed records and exclude generated needs-review, unreviewed, rejected, raw, or malformed content.
- [X] T023 [US3] Ensure `backend/services/end_shift.py` visibly reports investigations requiring review as readiness work without adding their findings to handover content.

**Checkpoint**: Only concise, validated, explicitly reviewed findings can propagate; creation still does not create or deliver handover.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the complete operator workflow and regression boundaries.

- [ ] T024 [P] Perform the browser smoke scenarios in `specs/008-create-datadog-investigations/quickstart.md` against `frontend/investigations.html`, verifying preview/cancel side effects, confirmation, refresh/selection, responsive behavior, and no Notebook URL fetch. **Blocked in this environment: no browser binary or browser automation runtime is installed.**
- [X] T025 Run the focused/full pytest suite, frontend ES-module validation, and `git diff --check` documented in `specs/008-create-datadog-investigations/quickstart.md`; resolve regressions without altering unrelated Features 001–007 behavior.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No production-code dependency; establishes isolated test support.
- **Foundational (Phase 2)**: Depends on Setup; blocks user stories because they share generation states and readiness.
- **User Story 1 (Phase 3)**: Depends on Foundation; establishes preview and confirmed generation.
- **User Story 2 (Phase 4)**: Depends on US1; validates and presents records produced by the creation workflow.
- **User Story 3 (Phase 5)**: Depends on US2; enforces propagation and readiness behavior for generated records.
- **Polish (Phase 6)**: Depends on all three stories.

### User Story Dependencies

- **US1 (P1)**: Starts after Foundation; independently verifies preview/confirmation and command safety.
- **US2 (P1)**: Depends on US1's request, adapter, and record flow; independently verifies validation and review.
- **US3 (P1)**: Depends on US2's validation/review states; independently verifies downstream gates and historical-shift isolation.

### Parallel Opportunities

- T002 and T003 can proceed in parallel after T001 because they modify separate service/readiness files.
- T004 and T005 can be authored in parallel because they cover separate test modules.
- T010 and T011 can proceed in parallel after the API contract is stable because they modify separate frontend/test files.
- T013 and T014 can proceed in parallel because output-validation and review-gate tests are in separate files.
- T019, T020, and T021 can proceed in parallel because they cover separate downstream test modules.
- Avoid parallel edits to `backend/services/investigation_generation.py`, `backend/services/investigations.py`, or `frontend/investigations.html`; those tasks have ordered dependencies.

## Implementation Strategy

### MVP First

1. Complete Setup and Foundation.
2. Complete US1 and verify preview has no side effects and only an explicit confirmation invokes the mocked adapter.
3. Keep real generation unavailable until US2 validates/presents output and US3 verifies reviewed-only propagation.
4. Complete US2 and US3 before enabling the workflow for operator-created investigations.

### Incremental Delivery

1. Setup + Foundation: isolated tests and configured readiness.
2. US1: preview, explicit confirmation, safe command boundary, and selected-shift targeting.
3. US2: output validation, safe malformed retention, visible status, explicit Review/Reject.
4. US3: reviewed-only propagation and End Shift readiness.
5. Polish: browser smoke, full regression suite, module validation, and diff checks.

### Notes

- Every task uses the required `- [ ] T### [P?] [US#?] ... file path` format.
- `[P]` marks only work in separate files with no unfinished prerequisite.
- Tests must use temporary storage and mocked commands; never access real NOC data, credentials, or network services.
- `noc-inv` remains authoritative; if the configured executable lacks the documented non-interactive contract, fail closed rather than automating its interactive mode.
