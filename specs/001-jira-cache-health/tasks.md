---

description: "Task list for Jira Cache Health Visibility"
---

# Tasks: Jira Cache Health Visibility

**Input**: Design documents from `/specs/001-jira-cache-health/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/status-api.md`, and `quickstart.md`

**Tests**: pytest coverage is required by the specification and constitution.

**Organization**: Tasks are grouped by user story so each operator-facing behavior can be
implemented and validated independently after the shared cache-health foundation is available.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it changes a different file and has no incomplete dependency.
- **[Story]**: Maps a task to a user story from `spec.md`.

## Phase 1: Setup

**Purpose**: Establish a regression baseline before changing cache-health behavior.

- [ ] T001 Run the existing pytest baseline from `tests/` and record any pre-existing failures before modifying `backend/services/jira_cache.py`.

---

## Phase 2: Foundational Cache-Health Contract

**Purpose**: Build the read-only health projection required by every user story.

- [ ] T002 [P] Add failing cache-health tests for valid timestamps, the `<30 minutes` current rule, the `>=30 minutes` stale boundary, invalid timestamps, unavailable cache data, and no-write behavior in `tests/test_jira_cache.py`.
- [ ] T003 [P] Add failing Status aggregation contract tests for the additive `jiraCache` object and its `available`, `refreshedAt`, and `freshness` fields in `tests/test_status.py`.
- [ ] T004 Implement the read-only Jira Cache Health projection in `backend/services/jira_cache.py`, enforcing: "`true` only when the existing cache reader returns structurally valid cache data", "`current`" below 30 minutes, "`stale`" at 30 minutes or longer, and "`unavailable`" for unreadable cache or invalid/missing timestamp.
- [ ] T005 Aggregate the Jira Cache Health projection as the additive `jiraCache` object in `backend/services/status.py` without changing existing Status response fields or calling a Jira refresh path.

**Checkpoint**: The Status service exposes a fully tested, read-only cache-health contract.

---

## Phase 3: User Story 1 - View Jira Cache Health (Priority: P1) 🎯 MVP

**Goal**: Let an operator see availability, last successful refresh, and current or stale state on
the existing Status page.

**Independent Test**: With a valid current and a valid stale cache, an operator can load the Status
page and identify all cache-health values from the single existing Status request.

- [ ] T006 [US1] Render the `jiraCache` availability, refresh time, and `current` or `stale` freshness as an additional existing-style metric in `frontend/status.html`, using the existing Status request and preserving all existing page behavior.

**Checkpoint**: Current and stale cache health are visible in one read-only Status page view.

---

## Phase 4: User Story 2 - Understand an Unavailable Cache (Priority: P2)

**Goal**: Clearly distinguish unavailable cache health from healthy cache data while retaining the
rest of the Status page.

**Independent Test**: With missing, malformed, or invalid-timestamp cache data, an operator sees a
clear unavailable state and the existing Status content remains visible.

- [ ] T007 [US2] Extend unavailable-cache aggregation coverage in `tests/test_status.py` to assert `available: false`, `refreshedAt: null`, and `freshness: "unavailable"` without a healthy indication.
- [ ] T008 [US2] Render an explicit unavailable cache-health state in `frontend/status.html` without replacing or redesigning unrelated Status page content.

**Checkpoint**: An unreadable cache is never presented as healthy.

---

## Phase 5: User Story 3 - Reliably Inspect Without Side Effects (Priority: P3)

**Goal**: Prove that cache-health inspection is informational and cannot refresh Jira or mutate
operational data.

**Independent Test**: Exercising cache-health computation and Status aggregation leaves the cache
file and tickets unchanged and does not invoke a Jira refresh.

- [ ] T009 [US3] Add no-side-effect coverage in `tests/test_jira_cache.py` and `tests/test_status.py` proving health inspection neither writes the cache nor calls the Jira ticket-queue refresh operation.
- [ ] T010 [US3] Verify `backend/services/status.py` obtains `jiraCache` only through the read-only cache-health projection and never invokes ticket-refresh or ticket-mutation operations.

**Checkpoint**: Cache health is demonstrably read-only and stale status remains informational.

---

## Phase 6: Polish & Cross-Cutting Validation

**Purpose**: Validate the complete contract, operator display, and regression safety.

- [ ] T011 Run focused cache-health and Status aggregation validation in `tests/test_jira_cache.py` and `tests/test_status.py`.
- [ ] T012 Run the full regression suite in `tests/` and execute the operator scenarios in `specs/001-jira-cache-health/quickstart.md`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** has no dependencies.
- **Phase 2** depends on the baseline from Phase 1 and blocks all user stories.
- **US1** depends on Phase 2.
- **US2** depends on Phase 2 and the Status-page metric introduced by US1.
- **US3** depends on Phase 2; it can validate the backend contract independently of the UI.
- **Phase 6** depends on all desired user stories.

### User Story Dependencies

```text
Phase 1 → Phase 2 → US1 → US2 → Phase 6
                    └────→ US3 ───┘
```

## Parallel Opportunities

- **Phase 2**: T002 and T003 can run in parallel because they add tests in separate files.
- **US1**: No safe parallel task; the page render must consume the completed Status contract.
- **US2**: T007 precedes T008 so the unavailable UI state is driven by the verified contract.
- **US3**: T009 and T010 are sequential because T010 verifies the implementation protected by T009.

### Parallel Example: Foundational Contract

```text
Task: "Add cache-health tests in tests/test_jira_cache.py"
Task: "Add Status aggregation contract tests in tests/test_status.py"
```

## Implementation Strategy

### MVP First

1. Complete T001-T005 to establish and expose the additive read-only health contract.
2. Complete T006 to show current and stale health on the Status page.
3. Validate the US1 independent test before adding unavailable-state UI handling.

### Incremental Delivery

1. Deliver US1 for current and stale cache visibility.
2. Deliver US2 for explicit unavailable-state communication.
3. Deliver US3 verification that the complete feature has no side effects.
4. Complete focused and full regression validation.
