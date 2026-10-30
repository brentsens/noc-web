---
description: "Task list for feature 006 bounded NOC AI Assistant"
---

# Tasks: Bounded NOC AI Assistant

**Input**: Design documents from `specs/006-ai-assistant/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/assistant-api.md`, and `quickstart.md`

**Tests**: Required by FR-016 and the feature acceptance scenarios. Write focused tests before
their implementation tasks and verify the tests fail first.

**Organization**: Tasks are grouped by user story. Complete the shared foundation before story
work; then deliver the stories in dependency order because they share the assistant service and UI.

## Phase 1: Setup

**Purpose**: Establish deterministic, isolated assistant test support and runnable validation
guidance.

- [X] T001 [P] Add a deterministic fake provider callable and temporary NOC-root request fixtures in `tests/conftest.py`
- [X] T002 [P] Align focused test commands and expected checks with the feature contract in `specs/006-ai-assistant/quickstart.md`

---

## Phase 2: Foundational

**Purpose**: Establish the request, provider, and API boundaries required by all user stories.

- [X] T003 [P] Define transient request, source, answer, limitation, and route schemas in `backend/services/assistant.py`, including `shiftDate` as ISO `YYYY-MM-DD`, `question` as required non-empty bounded operator text, source `availability` values `available`, `unavailable`, `stale`, `malformed`, or `conflicting`, `jira-cache` freshness values `current`, `stale`, `unavailable`, or `malformed`, and response `status` values `complete`, `limited`, or `unavailable`
- [X] T004 [P] Define the provider-neutral callable adapter contract, runtime injection, configured timeout, and content-free provider errors in `backend/services/copilot_mcp.py` and `backend/app.py`
- [X] T005 Validate the ISO `YYYY-MM-DD` path shift, matching body `shiftDate`, bounded question, and required `providerDisclosureAcknowledged` in `backend/api/assistant.py` without logging request values
- [X] T006 Register the additive assistant router, expose startup provider injection, and keep request-scoped data transient in `backend/app.py`, `backend/api/assistant.py`, and `backend/services/assistant.py`

**Checkpoint**: Assistant requests have a bounded schema and a single controlled provider/API boundary.

---

## Phase 3: User Story 1 - Understand the current operational situation (Priority: P1) — MVP

**Goal**: Answer a selected-shift question from the minimum relevant NOC Web projections and
clearly separate facts, operator-reviewed findings, and AI-authored advice.

**Independent Test**: Populate one isolated shift with cached Jira tickets, Local NOC Tracking,
Shift Notes, Dashboard/Status/readiness, handover, and reviewed investigation context. Ask a
situation question and verify the response uses only that shift, does not refresh Jira, identifies
source availability, and keeps source-grounded facts and operator-reviewed findings separate from
AI observations and recommendations.

### Tests for User Story 1

- [X] T007 [P] [US1] Test selected-shift context isolation, inclusion of all available context sources, `jira-cache` freshness values `current`, `stale`, `unavailable`, or `malformed`, and no Jira refresh in `tests/test_assistant.py`
- [X] T008 [P] [US1] Test the question endpoint request and response contract, including mismatched shifts, disclosure acknowledgement, evidence IDs, and limitations in `tests/test_assistant_api.py`
- [X] T009 [P] [US1] Test assistant page imports and named ES-module exports used from `frontend/assistant.html` in `tests/test_frontend_modules.py`

### Implementation for User Story 1

- [X] T010 [P] [US1] Collect only selected-shift Jira-cache, Local NOC Tracking, investigation, Shift Notes, Dashboard/Status/readiness, and handover projections in `backend/services/assistant_context.py`
- [X] T011 [US1] Project source-grounded facts and unchanged operator-reviewed investigation findings from existing NOC Web sources in `backend/services/assistant_context.py`; never generate or relabel reviewed findings with Copilot
- [X] T012 [P] [US1] Validate provider output to allow only advisory `aiObservations` and `recommendations` with available evidence IDs in `backend/services/assistant.py`
- [X] T013 [US1] Compose facts, projected reviewed findings, provider advice, source statuses, and limitations into the response in `backend/services/assistant.py`
- [X] T014 [US1] Connect the validated question route to the selected-shift context collector and response mediator in `backend/api/assistant.py`
- [X] T015 [P] [US1] Add the assistant request helper and response-shape validation to `frontend/js/api.js`
- [X] T016 [US1] Add the selected-shift assistant page with distinct Facts, Operator-reviewed findings, AI observations, Recommendations, Evidence, and Limitations sections in `frontend/assistant.html`
- [X] T017 [P] [US1] Preserve the selected `?shift=` value in assistant entry and related workflow links in `frontend/js/workflow-context.js`
- [X] T018 [US1] Add scoped assistant response and source-status styles in `frontend/css/components.css`

**Checkpoint**: User Story 1 provides independently verifiable selected-shift operational context with clear evidence categories.

---

## Phase 4: User Story 2 - Review AI advice safely (Priority: P1)

**Goal**: Ensure action requests are refused and recommendations only navigate to existing
confirmation-gated workflows.

**Independent Test**: Request a ticket/local-tracking/investigation/shift/handover write, close,
refresh, synchronization, command, Datadog query, or other external action. Verify no provider or
action endpoint is called, the response states nothing changed, and any route preserves the
selected shift and the destination's independent confirmation step.

### Tests for User Story 2

- [X] T019 [P] [US2] Test prompt-boundary and prohibited-action refusals return no provider call or operational write in `tests/test_assistant.py`
- [X] T020 [P] [US2] Test recommendation routes preserve `shift`, cannot prefill consent, and retain destination confirmation behavior in `tests/test_assistant_api.py`

### Implementation for User Story 2

- [X] T021 [US2] Refuse out-of-scope requests and all requested writes, edits, closes, refreshes, syncs, commands, Datadog, and external actions before provider invocation in `backend/services/assistant.py`
- [X] T022 [US2] Validate recommendation links against existing shift-preserving routes and prohibit action payloads or confirmation prefill in `backend/services/assistant.py`
- [X] T023 [US2] Render refusal and navigation-only recommendation states without triggering actions in `frontend/assistant.html`

**Checkpoint**: User Story 2 leaves every operational decision and confirmation to the existing operator workflow.

---

## Phase 5: User Story 3 - Preserve a trustworthy bounded view (Priority: P2)

**Goal**: Isolate source/provider failures, disclose provider handling, avoid retaining interaction
data, and keep normal NOC Web workflows available.

**Independent Test**: Make an individual source unavailable and simulate provider timeout, transport
failure, and malformed output. Verify the affected source and limitation are explicit, no
success-shaped answer or raw error is returned, the disclosure appears before submit, no prompt or
response is persisted/logged, and Dashboard, Tickets, Investigations, Status, and shift/handover
flows remain usable.

### Tests for User Story 3

- [X] T024 [P] [US3] Test Copilot timeout, transport failure, malformed output, and success/failure no-retention behavior in `tests/test_assistant.py`
- [X] T025 [P] [US3] Test unavailable-source reporting, provider failure, disclosure acknowledgement, and continued normal API workflows in `tests/test_assistant_api.py`
- [X] T026 [P] [US3] Test no direct Datadog integration in `backend/services/assistant.py`, `backend/services/assistant_context.py`, `backend/services/copilot_mcp.py`, and `tests/test_safety.py`

### Implementation for User Story 3

- [X] T027 [P] [US3] Return controlled provider timeout, transport, and schema-failure limitations without exception or response payload leakage in `backend/services/copilot_mcp.py` and `backend/services/assistant.py`
- [X] T028 [P] [US3] Preserve independent `available`, `unavailable`, `stale`, `malformed`, and `conflicting` source states in `backend/services/assistant_context.py`
- [X] T029 [US3] Ensure successful and failed requests do not log or persist prompts, context, evidence, provider output, or derived responses in `backend/services/assistant.py`, `backend/api/assistant.py`, and `backend/services/copilot_mcp.py`
- [X] T030 [US3] Show the qualified provider-retention disclosure before submission and clear prompt/result DOM state on navigation or refresh in `frontend/assistant.html`

**Checkpoint**: User Story 3 makes source and provider boundaries visible without disrupting other NOC workflows.

---

## Phase 6: Polish and Cross-Cutting Validation

**Purpose**: Confirm contract consistency and preserve features 001–005.

- [X] T031 [P] Align examples and documented statuses with the final assistant API/UI contract in `specs/006-ai-assistant/contracts/assistant-api.md`
- [X] T032 [P] Add regression coverage for features 001–005 and normal workflow availability during assistant failures in `tests/test_dashboard.py`, `tests/test_status.py`, `tests/test_tickets.py`, `tests/test_investigations.py`, and `tests/test_safety.py`
- [X] T033 Run the focused and full pytest suites plus frontend module checks from `specs/006-ai-assistant/quickstart.md` and `tests/test_safety.py`
- [X] T034 Run `git diff --check` and verify the generated feature artifacts under `specs/006-ai-assistant/`

---

## Dependencies and Execution Order

### Phase Dependencies

- **Setup**: No dependencies; T001 and T002 may run in parallel.
- **Foundational**: Depends on Setup. T003 and T004 may run in parallel; request validation and
  router registration follow the shared schemas.
- **User Story 1**: Depends on the Foundation. It delivers the MVP context collection and response
  contract.
- **User Story 2**: Depends on User Story 1 because refusal and recommendation behavior use its
  response schema, service, and page.
- **User Story 3**: Depends on User Story 1 and User Story 2; failure states and disclosure modify
  the same service and page.
- **Polish**: Depends on all three user stories.

### User Story Dependencies

- **US1 (P1)**: Starts after the Foundational phase; no dependency on another story.
- **US2 (P1)**: Starts after US1; requires the established assistant response and route contract.
- **US3 (P2)**: Starts after US2 to avoid conflicting edits to the shared mediator and assistant
  page while adding failure and retention behavior.

### Parallel Opportunities

- Setup: T001 and T002.
- Foundation: T003 and T004.
- US1: T007, T008, and T009; after those pass, T010 and T012 can proceed in parallel.
- US2: T019 and T020.
- US3: T024, T025, and T026; T027 and T028 can proceed in parallel.
- Polish: T031 and T032.

## Parallel Example: User Story 1

```text
Task: T007 context and cache isolation tests in tests/test_assistant.py
Task: T008 API contract tests in tests/test_assistant_api.py
Task: T009 frontend module integrity tests in tests/test_frontend_modules.py
```

## Parallel Example: User Story 2

```text
Task: T019 prohibited-action policy tests in tests/test_assistant.py
Task: T020 recommendation route and confirmation tests in tests/test_assistant_api.py
```

## Parallel Example: User Story 3

```text
Task: T024 provider failure and retention tests in tests/test_assistant.py
Task: T025 source failure and workflow continuity tests in tests/test_assistant_api.py
Task: T026 Datadog boundary tests in tests/test_safety.py
```

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational tasks.
2. Complete User Story 1, including its tests, then verify its independent test scenario.
3. Stop for operator review of the source labels, Jira-cache freshness, and shift isolation before
   adding recommendation or failure behavior.

### Incremental Delivery

1. Deliver US1 as the read-only, evidence-labeled assistant MVP.
2. Add US2 refusals and navigation-only recommendations without changing existing confirmation
   gates.
3. Add US3 failure isolation, retention disclosure, and no-retention verification.
4. Run the cross-feature regression and full validation tasks.

## Post-completion runtime provider alignment

- [X] T035 [P] Add mocked Copilot CLI adapter tests for bounded invocation, authentication and process failures, strict output, and temporary-context cleanup in `tests/test_copilot_cli.py`
- [X] T036 Implement the default tool-less Copilot CLI provider behind the existing callable boundary in `backend/services/copilot_cli.py`, `backend/services/copilot_mcp.py`, and `backend/app.py`
- [X] T037 Update feature 006 requirements, architecture, API contract, and validation guidance to document the default CLI provider in `spec.md`, `plan.md`, `research.md`, `contracts/assistant-api.md`, and `quickstart.md`
- [X] T038 Verify all four AI Actions reach the provider without bypassing assistant policy in `tests/test_assistant.py` and `tests/test_frontend_modules.py`
- [X] T039 Add regression coverage for provider invocation/status provenance and successful-but-empty AI results in `tests/test_assistant.py`, `tests/test_assistant_api.py`, `tests/test_copilot_cli.py`, and `tests/test_frontend_modules.py`
- [X] T040 Add bounded provider identity, invocation, and outcome metadata to assistant responses while preserving controlled failure behavior in `backend/services/assistant.py`, `backend/services/copilot_mcp.py`, and `backend/services/copilot_cli.py`
- [X] T041 Validate and render provider provenance and successful-but-empty results in both Assistant views, and document the response contract in `frontend/js/api.js`, `frontend/assistant.html`, `frontend/ai-actions.html`, and `specs/006-ai-assistant/contracts/assistant-api.md`
- [X] T042 Run focused Assistant tests, the full pytest suite, frontend ES-module validation, and `git diff --check`
- [X] T043 Add tests for semantically distinct AI Action prompts and evidence-grounded, non-empty validated responses in `tests/test_assistant.py` and `tests/test_copilot_cli.py`
- [X] T044 Strengthen the fixed Copilot prompt and four action questions to require useful action-scoped analysis while preserving the strict JSON contract in `backend/services/copilot_cli.py` and `frontend/ai-actions.html`
- [X] T045 Align provider schema documentation with strict recommendation route validation and normalize `frontend/js/api.js` to LF line endings in `specs/006-ai-assistant/contracts/assistant-api.md` and `frontend/js/api.js`
- [X] T046 Run focused and full pytest suites, frontend ES-module validation, plain `git diff --check`, and bounded live Summarize/Follow-ups smoke tests

## Post-completion AI Action report compatibility

- [X] T047 [P] Add backend tests for predefined action execution, validated advisory report persistence, action metadata, historical-shift isolation, non-overwriting names, failure paths, and read-only report viewing in `tests/test_ai_reports.py`
- [X] T048 [P] Add frontend API and AI Actions regression coverage for constrained action requests, visible save warnings, immediate report-list refresh, and report-viewer compatibility in `tests/test_frontend_modules.py`
- [X] T049 [P] Enforce that `investigations.html` recommendations cite available `noc-inv` or `copilot-mcp` investigation evidence; ordinary Jira/Salesforce correlation must not route to Investigations in `backend/services/assistant.py` and `backend/services/copilot_cli.py`
- [X] T050 Implement the fixed-action API and collision-safe `ai-*.md` writer/list/view integration in `backend/api/assistant.py` and `backend/services/ai_reports.py`
- [X] T051 Persist only validated normalized report sections, preserve successful analysis with a separate save warning, and refresh Recent AI Reports after a successful save in `frontend/ai-actions.html` and `frontend/js/api.js`
- [X] T052 Document the predefined-action report exception, advisory report schema, and Datadog-only Investigations route boundary in `specs/006-ai-assistant/spec.md`, `specs/006-ai-assistant/data-model.md`, `specs/006-ai-assistant/contracts/assistant-api.md`, `specs/006-ai-assistant/plan.md`, and `specs/006-ai-assistant/quickstart.md`
- [X] T053 Run focused AI Assistant/report tests, the full pytest suite, frontend ES-module validation, `git diff --check`, and a bounded live Summarize action with immediate report-list/viewer verification
