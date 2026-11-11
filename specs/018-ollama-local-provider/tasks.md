---

description: "Task list for adding the Ollama local AI provider"
---

# Tasks: Ollama Local AI Provider

**Input**: Design documents from `/specs/018-ollama-local-provider/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — the feature specification explicitly requires regression coverage for endpoint
validation, configurable model/qwen3:8b, provider failures, metadata exclusion, credentials, no
automatic fallback, explicit retry, provenance, Assistant/investigation/handover compatibility, and
provider isolation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- Web application: `backend/`, `frontend/`, `tests/`, `docs/`
- Feature design artifacts: `specs/018-ollama-local-provider/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare deterministic Ollama, provider-selection, and retry fixtures.

- [X] T001 Create `tests/support/ollama_provider.py` with fake Ollama transports, valid/invalid generation and model-list responses, thinking/metadata fixtures, qwen3:8b configuration builders, and retry snapshot fixtures.
- [X] T002 Add Feature 018 fixture wiring in `tests/conftest.py` for fake Ollama transports, provider environment isolation, and retry-store reset.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Provider configuration, Ollama transport, retry store, and runtime selection foundations.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Foundational Tests

- [X] T003 [P] Add failing tests in `tests/test_ai_provider.py` for `ollama` provider configuration, required `NOC_WEB_OLLAMA_BASE_URL`, default/configured `NOC_WEB_OLLAMA_MODEL` (`qwen3:8b` recommended), bounded connect/read deadlines (5s/120s defaults, max 10s/300s), endpoint validation, and static primary/local readiness with no network call.
- [X] T004 [P] Add failing tests in `tests/test_ollama_provider.py` for bounded non-streaming generation, accepting only a non-empty string `response`, parsing that field to the workflow object, and rejecting missing/non-string/empty/malformed/unsupported/oversized output.
- [X] T005 [P] Add failing tests in `tests/test_ollama_provider_security.py` for thinking/context/duration/model metadata exclusion, redirect/host rejection, no Authorization/DeepSeek/Datadog/M365/environment secrets, no invented auth secret, and no external mutation path.
- [X] T006 [P] Add failing tests in `tests/test_local_retry.py` for a 10-minute TTL, maximum 32 in-memory snapshots, opaque single-use tokens, exact evidence/envelope retention, no disk persistence, and expired/used/unavailable failure behavior.

### Foundational Implementation

- [X] T007 Extend `backend/services/ai_provider.py` with `ollama` provider configuration/readiness/validation, `NOC_WEB_OLLAMA_BASE_URL`, `NOC_WEB_OLLAMA_MODEL` (`qwen3:8b` recommended), `NOC_WEB_OLLAMA_TIMEOUT_SECONDS`, `NOC_WEB_OLLAMA_CONNECT_TIMEOUT_SECONDS`, and `NOC_WEB_AI_PROVIDER=ollama` explicit selection while preserving DeepSeek default behavior.
- [X] T008 [P] Create `backend/services/ollama_provider.py` generation adapter for the configured Ollama origin: non-streaming request, only `response` consumed, all thinking/context/duration/model/loading metadata ignored, no Authorization header, redirects rejected, bounded response (1 MiB) and output size.
- [X] T009 [P] Create `backend/services/local_retry.py` with an in-memory 10-minute/32-entry single-use retry store, opaque tokens, exact evidence/envelope snapshots, workflow/shift/request identity, and no disk/log persistence.
- [X] T010 Extend `backend/services/ai_provider.py` runtime resolution for explicit Ollama selection and explicit local retry while never falling back from DeepSeek or another provider.
- [X] T011 Add primary/local static readiness projection fields (`primaryProvider`, `localProvider`, endpoint configured/unconfigured, model, static readiness) in `backend/services/ai_provider.py` without network or inference.
- [X] T012 Add shared provider-selection and retry metadata response helpers in `backend/services/local_retry.py` and `backend/api/assistant.py` without changing existing success response shapes.

**Checkpoint**: Provider config, Ollama transport, retry store, and explicit selection foundations are ready.

---

## Phase 3: User Story 1 - Explicitly retry a failed primary request with local AI (Priority: P1) 🎯 MVP

**Goal**: After a primary failure, expose an explicit Retry with Local AI action for all four workflows, using the exact failed-request evidence and existing validators.

**Independent Test**: Simulate a primary failure in Assistant, AI Actions, investigation generation, and handover generation; verify no Ollama call without confirmation, a confirmed retry uses the same 10-minute snapshot, tokens are single-use, and retry output passes the existing validator or fails closed without replacing prior records.

### Tests for User Story 1

- [X] T013 [P] [US1] Add retry snapshot integration tests in `tests/test_local_retry.py` for exact evidence reuse, TTL, single-use consumption, expired/used/unavailable tokens, and no disk persistence.
- [X] T014 [P] [US1] Add Assistant/AI Actions retry tests in `tests/test_assistant.py` and `tests/test_assistant_api.py` covering primary failure, no automatic Ollama call, explicit confirmation, same envelope reuse, and local validator rejection.
- [X] T015 [P] [US1] Add investigation retry tests in `tests/test_investigation_generation.py` covering primary failure, exact previewed evidence package reuse, explicit confirmation, and existing Feature 016 validation/persistence.
- [X] T016 [P] [US1] Add handover retry tests in `tests/test_handover.py` covering primary failure, exact evidence/advisory envelope reuse, explicit confirmation, existing Feature 017 validation, and archive/rollback behavior.
- [X] T017 [US1] Add no-automatic-fallback/retry confirmation regression tests in `tests/test_ai_provider.py` and `tests/test_local_retry.py`; failed primary requests must never invoke Ollama without an explicit confirmed retry.

### Implementation for User Story 1

- [X] T018 [US1] Add failed-request retry snapshot capture and additive `localRetry` availability metadata in `backend/services/assistant.py` and `backend/api/assistant.py`; never expose evidence contents or secrets.
- [X] T019 [US1] Add Assistant/AI Actions explicit local retry endpoint and confirmation handling in `backend/api/assistant.py`, reusing the stored envelope and existing response validators/report persistence.
- [X] T020 [US1] Add investigation retry snapshot capture/retry endpoint in `backend/services/investigation_generation.py` and `backend/api/investigations.py`, reusing the exact preview evidence and Feature 016 validators/lifecycle/persistence.
- [X] T021 [US1] Add handover retry snapshot capture/retry endpoint in `backend/services/handover.py` and `backend/api/handover.py`, reusing the exact evidence/envelope and Feature 017 validators/provenance/archive/rollback.
- [X] T022 [P] [US1] Update `frontend/js/api.js` with explicit retry-token client functions for Assistant, AI Actions, investigations, and handover while preserving existing success clients.
- [X] T023 [US1] Add explicit Retry with Local AI confirmation UI and retry availability display in `frontend/assistant.html`.
- [X] T024 [US1] Add explicit Retry with Local AI confirmation UI and retry availability display in `frontend/investigations.html`.
- [X] T025 [US1] Add explicit Retry with Local AI confirmation UI and retry availability display in `frontend/end-shift.html`.
- [X] T026 [US1] Add frontend regressions in `tests/test_frontend_modules.py` and `tests/test_end_shift.py` proving no automatic retry and explicit confirmation for all retry UI paths.

**Checkpoint**: All four workflows fail closed on primary failure and retry locally only after explicit confirmation with exact evidence.

---

## Phase 4: User Story 2 - Configure and validate the local provider safely (Priority: P1)

**Goal**: Configure the Ollama endpoint/model safely, explicitly probe availability, and fail closed on endpoint, network, model, response, and secret violations.

**Independent Test**: With fake Ollama hosts, verify configurable endpoint/model and qwen3:8b; reject invalid/credentialed/query/fragment/path/redirect/unexpected-host endpoints; verify unreachable/refused/timeout/missing-model/malformed/missing/non-string/oversized cases fail closed; verify explicit probe checks endpoint/model without inference and static readiness makes no request.

### Tests for User Story 2

- [X] T027 [P] [US2] Add endpoint/model/timeout/configuration tests in `tests/test_ai_provider.py`, including `qwen3:8b`, explicit Ollama default selection, and no hard-coded host default.
- [X] T028 [P] [US2] Add Ollama generation tests in `tests/test_ollama_provider.py` for response-only parsing, thinking/context/duration/model metadata exclusion, missing/non-string/empty/malformed/unsupported/oversized response, redirects, and bounded deadlines.
- [X] T029 [P] [US2] Add endpoint/security tests in `tests/test_ollama_provider_security.py` for embedded credentials, query, fragment, non-root path, redirects, unexpected hosts, missing endpoint/model, and no Authorization/process secrets.
- [X] T030 [US2] Add explicit probe tests in `tests/test_ollama_provider.py` and `tests/test_readiness.py` for endpoint reachability, configured model presence, no inference/model loading, unavailable reasons, and no static-page probe.

### Implementation for User Story 2

- [X] T031 [US2] Implement explicit `probe_ollama` in `backend/services/ollama_provider.py` using a bounded model-list request that checks endpoint reachability and configured model presence without inference.
- [X] T032 [US2] Add the explicit probe endpoint in `backend/api/providers.py` with sanitized availability/reason/model/endpoint-configured fields and no inference.
- [X] T033 [US2] Finish Ollama endpoint/model/timeout validation and sanitized failure mapping in `backend/services/ai_provider.py` and `backend/services/ollama_provider.py`.
- [X] T034 [US2] Add provider status/probe UI in `frontend/status.html` and shared `frontend/js/provider-status.js`, with explicit probe action and no automatic probe.
- [X] T035 [US2] Add provider configuration/readiness/probe regressions in `tests/test_readiness_api.py` and `tests/test_frontend_modules.py`.

**Checkpoint**: Ollama configuration/probe is safe, bounded, and fails closed without affecting core readiness when DeepSeek is usable.

---

## Phase 5: User Story 3 - Preserve every existing validator and safety boundary (Priority: P1)

**Goal**: Local inference passes the same Assistant/AI Actions/investigation/handover validators and provenance rules as DeepSeek.

**Independent Test**: Run identical valid/invalid fixtures through DeepSeek and Ollama; verify local output receives the same schema, citation, stale/partial, credential, size, lifecycle, reviewed-boundary, count, and provenance outcomes.

### Tests for User Story 3

- [X] T036 [P] [US3] Add Assistant/AI Actions local-provider compatibility tests in `tests/test_assistant.py` and `tests/test_assistant_api.py` for valid output, stale evidence, invalid schema, credential content, and size bounds.
- [X] T037 [P] [US3] Add investigation local-provider compatibility tests in `tests/test_investigation_generation.py` and `tests/test_investigation_ai_evidence.py` for exact citations, unavailable/non-authoritative/stale/partial evidence, lifecycle, review boundaries, and provenance.
- [X] T038 [P] [US3] Add handover local-provider compatibility tests in `tests/test_handover.py` and `tests/test_handover_ai.py` for bracketed citations, stale/partial qualification, count-claim rejection, all-ticket deterministic inclusion, advisory-only output, and provenance.
- [X] T039 [US3] Add local-provider provenance tests in `tests/test_ai_provider.py`, `tests/test_investigation_generation.py`, and `tests/test_handover.py` asserting `ollama` and configured model, never DeepSeek/Copilot/reviewed/deterministic labels.

### Implementation for User Story 3

- [X] T040 [US3] Wire explicit local provider selection through Assistant/AI Actions in `backend/services/assistant.py` and `backend/api/assistant.py` without bypassing existing schema/evidence/credential/size validators.
- [X] T041 [US3] Wire explicit local provider selection through investigation preview/create in `backend/services/investigation_generation.py` and `backend/api/investigations.py`, preserving exact citation, stale/partial, lifecycle, review, and persistence rules.
- [X] T042 [US3] Wire explicit local provider selection through handover preview/generation in `backend/services/handover.py` and `backend/api/handover.py`, preserving bracketed citations, count-claim rejection, all-ticket inclusion, deterministic presentation, provenance, and delivery behavior.
- [X] T043 [US3] Record local provider provenance (`ollama` + configured model) in Assistant/AI Actions responses, investigation generation status/provenance, and handover provenance sidecars in `backend/services/assistant.py`, `backend/services/investigation_generation.py`, and `backend/services/handover.py`.
- [X] T044 [US3] Add local-provider validator/secret/metadata regression assertions in `tests/test_ollama_provider_security.py` and `tests/test_datadog_secrets.py`; no local output may weaken or bypass existing validators.

**Checkpoint**: Local inference has no weaker validation, authority, or provenance than the primary provider.

---

## Phase 6: User Story 4 - Distinguish primary and local provider readiness and availability (Priority: P2)

**Goal**: Operators can distinguish primary DeepSeek, optional local Ollama, endpoint/model configuration, explicit probe availability, and retry availability.

**Independent Test**: Render health/status/UI with Ollama unconfigured, configured/sleeping, probed unavailable, and probed available; verify distinct states, no static probing, DeepSeek default retention, and retry availability only after failure.

### Tests for User Story 4

- [X] T045 [P] [US4] Add static primary/local readiness tests in `tests/test_readiness.py` and `tests/test_readiness_api.py` proving no Ollama network call, local unavailability does not fail core readiness, and primary/local fields are distinct.
- [X] T046 [P] [US4] Add status/health/UI tests in `tests/test_status.py` and `tests/test_frontend_modules.py` for primary/local labels, configured/unconfigured endpoint, model, explicit probe result, and retry availability.
- [X] T047 [US4] Add DeepSeek-default/no-automatic-migration and explicit-Ollama-default tests in `tests/test_ai_provider.py`, `tests/test_readiness.py`, and `tests/test_status.py`.
- [X] T048 [US4] Add probe/no-inference and retry-availability tests in `tests/test_readiness_api.py` and `tests/test_frontend_modules.py`.

### Implementation for User Story 4

- [X] T049 [US4] Add primary/local provider fields to `backend/app.py`, `backend/services/health.py`, `backend/services/status.py`, and `backend/services/dependency_readiness.py` without removing existing fields or making static network calls.
- [X] T050 [US4] Update `frontend/status.html` and `frontend/js/provider-status.js` to display primary/local provider state, endpoint/model, explicit probe result, and retry availability.
- [X] T051 [US4] Add explicit per-request provider selection controls where supported and retry availability messaging to `frontend/assistant.html`, `frontend/investigations.html`, and `frontend/end-shift.html` while preserving existing confirmation/generation/delivery UX.
- [X] T052 [US4] Update `README.md` and `docs/workstation-runtime.md` with Ollama configuration, `qwen3:8b`, explicit probe/retry, no-auth/no-secrets, endpoint validation, and DeepSeek default behavior.
- [X] T053 [US4] Add readiness/status/UI regression assertions in `tests/test_readiness.py`, `tests/test_readiness_api.py`, `tests/test_status.py`, and `tests/test_frontend_modules.py`.

**Checkpoint**: Operators can distinguish primary and optional local provider state without static inference or core readiness regressions.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Reconcile contracts, security-test all boundaries, and run complete verification.

- [X] T054 [P] Reconcile `specs/018-ollama-local-provider/contracts/`, `data-model.md`, and `quickstart.md` with implementation-discovered details.
- [X] T055 [P] Add/strengthen `tests/test_ollama_provider.py` and `tests/test_ollama_provider_security.py` for remaining endpoint/model/timeout/metadata/oversize edges.
- [X] T056 Run focused Feature 018 tests: `.venv/bin/python -m pytest tests/test_ollama_provider.py tests/test_local_retry.py tests/test_ai_provider.py tests/test_assistant.py tests/test_assistant_api.py tests/test_investigation_generation.py tests/test_handover.py tests/test_handover_ai.py tests/test_ollama_provider_security.py tests/test_readiness.py tests/test_dependency_readiness.py tests/test_readiness_api.py tests/test_status.py tests/test_frontend_modules.py tests/test_datadog_readonly.py tests/test_datadog_secrets.py -q`.
- [X] T057 Run the full suite from `/home/bsmith/code/noc-web`: `.venv/bin/python -m pytest -q`.
- [X] T058 Execute `specs/018-ollama-local-provider/quickstart.md` validation scenarios and record expected outcomes.
- [X] T059 [P] Audit credential non-disclosure, Ollama metadata exclusion, redirect/host rejection, no automatic fallback/retry, and zero external mutation across `backend/services/ollama_provider.py`, `backend/services/ai_provider.py`, `backend/services/local_retry.py`, Assistant, investigation, handover, responses, logs, and persisted files.
- [X] T060 [P] Verify existing DeepSeek/Copilot behavior, Feature 016 investigation behavior, Feature 017 handover behavior, Microsoft 365 delivery, and Datadog read-only behavior remain unchanged; add/confirm focused regression evidence.

**Checkpoint**: Ollama is additive, isolated, fail-closed, and fully verified.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **US1 (Phase 3)**: Depends on Foundational.
- **US2 (Phase 4)**: Depends on Foundational; provides probe/configuration implementation used by US4.
- **US3 (Phase 5)**: Depends on Foundational and US1 provider/retry paths.
- **US4 (Phase 6)**: Depends on Foundational, US1, and US2 readiness/probe fields.
- **Polish (Phase 7)**: Depends on all desired user stories.

### User Story Dependencies

- **US1 (P1)**: Independent after Foundational; MVP explicit local retry.
- **US2 (P1)**: Independent after Foundational; configuration/probe safety.
- **US3 (P1)**: Independently testable with local fixtures; integrate after US1 local paths.
- **US4 (P2)**: Independently testable readiness/UI; integrate after US1/US2.

### Within Each User Story

- Tests MUST be written and fail before implementation.
- Provider configuration/transport before workflow retry/selection.
- Service orchestration before API endpoints.
- API before frontend integration.
- Core implementation before cross-story compatibility.

### Parallel Opportunities

- T003–T006 foundational tests can run in parallel.
- T007, T008, T009 are different files and can run in parallel once interfaces are known.
- T013–T016 retry tests are different files and can run in parallel.
- T018–T021 implementation touches different workflow files; sequence shared API/UI files.
- T022–T025 frontend files can be split where different.
- T027–T029 configuration/adapter/security tests can run in parallel.
- T036–T039 validator compatibility tests can run in parallel where different files.
- T045–T048 readiness/UI tests can run in parallel where different files.
- T054, T055, T059, T060 can run in parallel after dependencies; T056/T057 are ordered commands.

---

## Parallel Example: User Story 1

```bash
# Retry tests touch different workflow files and can run together:
Task: "Retry snapshot tests in tests/test_local_retry.py"
Task: "Assistant/AI Actions retry tests in tests/test_assistant.py and tests/test_assistant_api.py"
Task: "Investigation retry tests in tests/test_investigation_generation.py"
Task: "Handover retry tests in tests/test_handover.py"
```

## Parallel Example: User Story 2

```bash
# Configuration, adapter, and security tests can run together:
Task: "Provider configuration tests in tests/test_ai_provider.py"
Task: "Ollama adapter tests in tests/test_ollama_provider.py"
Task: "Endpoint/secret/metadata tests in tests/test_ollama_provider_security.py"
```

## Parallel Example: Foundational

```bash
# These files are independent:
Task: "Provider configuration/readiness in backend/services/ai_provider.py"
Task: "Ollama transport in backend/services/ollama_provider.py"
Task: "Retry store in backend/services/local_retry.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: US1.
4. **STOP and VALIDATE**: Run T013–T017 and confirm all four workflows fail closed on primary failure and retry locally only after explicit confirmation with exact evidence.
5. Deploy/demo if ready.

### Incremental Delivery

1. Setup + Foundational → provider configuration, adapter, retry store.
2. US1 → explicit local retry across all four workflows.
3. US2 → endpoint/probe/security hardening.
4. US3 → validator/provenance compatibility.
5. US4 → readiness/status/UI visibility.
6. Polish → contracts, security audit, full validation.

### Parallel Team Strategy

1. Team completes Setup + Foundational together.
2. After Foundational:
   - Developer A: US1 retry workflows.
   - Developer B: US2 configuration/probe/security.
   - Developer C: US3 validator compatibility after US1 paths stabilize.
   - Developer D: US4 readiness/UI after US1/US2 fields stabilize.
3. Rejoin for Polish and full-suite validation.

---

## Notes

- [P] tasks touch different files and have no incomplete dependencies.
- [Story] labels map tasks to US1–US4.
- No automatic fallback or retry; explicit operator selection/confirmation is mandatory.
- No Ollama auth secret; no Authorization/DeepSeek/Datadog/M365/environment secrets to Ollama.
- Only Ollama's `response` field is usable; thinking/context/duration/model metadata is ignored.
- Reuse existing validators; local inference receives no additional authority.
- Preserve Feature 016/017 persistence/lifecycle/provenance and Microsoft 365 delivery.

---

## Phase 8: Convergence Follow-ups

**Purpose**: Close the gaps identified by the post-implementation convergence review so the
feature's remaining work is directly executable.

- [X] T061 [P] [US4] Add distinct static `primaryProvider` and `localProvider` state to the shift health and root health projections without network calls, keep Ollama warning-only, and add regressions in `backend/services/health.py`, `backend/api/health.py`, `backend/services/dependency_readiness.py`, `tests/test_readiness.py`, and `tests/test_readiness_api.py` (FR-022, T049; partial).
- [X] T062 [US4] Add explicit per-request provider selection controls where supported in `frontend/assistant.html`, `frontend/investigations.html`, and `frontend/end-shift.html`, passing the selected provider through `frontend/js/api.js` while preserving DeepSeek defaults and existing confirmation/retry behavior (FR-004, FR-022, T051; partial).
- [X] T063 [US1] Add AI Actions local-retry endpoint coverage and frontend retry-confirmation regressions in `tests/test_assistant_api.py`, `tests/test_frontend_modules.py`, and `tests/test_end_shift.py`, proving no automatic retry and explicit confirmation for every retry UI path (T014, T026; partial).
- [X] T064 [P] [US3] Add Ollama-local investigation and handover validator compatibility tests in `tests/test_investigation_generation.py` and `tests/test_handover.py` for invalid citations, stale/partial qualification, count claims, and fail-closed persistence using the local provider path (T037, T038; partial).
- [X] T065 [US4] Add readiness/status/UI regression assertions in `tests/test_readiness.py`, `tests/test_readiness_api.py`, `tests/test_status.py`, and `tests/test_frontend_modules.py` for distinct primary/local labels, endpoint/model state, no implicit probe or inference, explicit probe results, and retry availability (T035, T045-T048, T053; partial).
- [X] T066 [P] Document and justify the additive structured Assistant output schema, safe stage diagnostics, and managed-service `ollama-provider.env` propagation in the Feature 018 contracts/quickstart and runtime documentation, or remove them if they are outside the feature scope (unrequested; low).

---

## Phase 9: Convergence

- [X] T067 Render distinct primary and local provider state from `health.aiProvider` in `frontend/health.html`, including endpoint/model/static unavailable state without exposing secrets, and add a frontend regression in `tests/test_frontend_modules.py` per FR-022 (partial).

