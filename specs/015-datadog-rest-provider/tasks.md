# Tasks: Direct Read-Only Datadog Evidence Provider

**Input**: Design documents from `/specs/015-datadog-rest-provider/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Required. The specification explicitly requires regression coverage for zero Copilot/MCP invocation, read-only requests, credential non-disclosure, stale-cache preservation, malformed/oversized responses, bounded timeouts, static readiness, and incident API/frontend compatibility.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: `US1`–`US5` for user-story tasks only
- Every task includes exact repository-relative file paths

## Path Conventions

- Backend: `backend/services/`, `backend/api/`, `backend/app.py`
- Tests: `tests/`
- Runtime/config: `scripts/`, `systemd/`, `docs/`, `README.md`
- Feature docs: `specs/015-datadog-rest-provider/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the baseline and keep the existing incident contract observable before changes.

- [X] T001 Capture the pre-change baseline by running `python -m pytest tests/test_datadog_incidents.py tests/test_datadog_incidents_api.py tests/test_datadog_incidents_frontend.py tests/test_dependency_readiness.py tests/test_readiness_api.py tests/test_status.py -q` and record the result in the task execution notes; do not edit files outside `specs/015-datadog-rest-provider/` yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared validation, provider configuration, allowlisted client, and test transport used by every user story.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Implement shared bounded validation helpers in `backend/services/datadog_validation.py`: text limits (`id` ≤128, `title` ≤200, `severity` ≤32, `summary` ≤500, URL ≤2048), timezone-aware RFC 3339 parsing, Datadog URL validation, numeric identifier validation, and bounded list/mapping helpers.
- [X] T003 [P] Implement `DatadogConfiguration` and `datadog_provider_readiness()` in `backend/services/datadog_provider.py` using `NOC_WEB_DATADOG_ACCESS_TOKEN`, `NOC_WEB_DATADOG_BASE_URL` (default `https://api.datadoghq.com`), and `NOC_WEB_DATADOG_TIMEOUT_SECONDS` (integer 1–120, default 90); expose only `credentialPresent`, never the token.
- [X] T004 Implement the allowlisted `DatadogClient` and standard-library HTTPS transport in `backend/services/datadog_provider.py`: only `search_incidents` (`GET /api/v2/incidents/search`), `get_incident` (`GET /api/v2/incidents/{id}`), `get_notebook` (`GET /api/v1/notebooks/{id}`), and `get_monitor` (`GET /api/v1/monitor/{id}`); reject every other operation, refuse redirects, require HTTPS, and send the token only in `Authorization: Bearer`.
- [X] T005 Add shared test fixtures in `tests/conftest.py` for a fake Datadog transport, recorded requests, injected environment values, and a monotonic deadline helper; fixtures must never use the network or a real token.
- [X] T006 Add foundational provider tests in `tests/test_datadog_provider.py` for configuration validation, static readiness with zero transport calls, allowlist rejection, bearer-header construction, redirect refusal, status handling, malformed JSON, and the 1,000,000-byte response bound.

**Checkpoint**: Shared provider infrastructure is ready. US1, US2, US3, US4, and US5 can begin.

---

## Phase 3: User Story 1 - Retrieve live incidents without Copilot or MCP (Priority: P1) 🎯 MVP

**Goal**: Current `ACTIVE`/`STABLE` incidents refresh through the direct Datadog API while Copilot CLI and Datadog MCP are absent, with the existing snapshot and frontend contract preserved.

**Independent Test**: Remove Copilot and all MCP configuration, inject a fake Datadog incident-search response, refresh the cache, and verify the same incident projection, count, freshness, and Datadog links appear with zero Copilot subprocess and zero MCP calls.

### Tests for User Story 1

> Write these tests first and confirm they fail against the current Copilot/MCP implementation.

- [X] T007 [P] [US1] Add direct incident-retrieval tests in `tests/test_datadog_incidents.py` covering `state:(active OR stable)` search mapping, exact state preservation, duplicate-ID rejection, more-than-100 rejection, pagination bounds, URL construction, and zero Copilot/MCP invocation.
- [X] T008 [P] [US1] Add API contract regression tests in `tests/test_datadog_incidents_api.py` proving `GET /api/datadog/incidents` and `POST /api/datadog/incidents/refresh` keep the existing fields, `current`/`stale`/`unavailable`/`refreshing` values, null count semantics, and controlled error values.
- [X] T009 [P] [US1] Replace the obsolete `test_backend_retrieval_does_not_add_direct_datadog_api_or_sdk` assertion in `tests/test_datadog_incidents_frontend.py` with direct-provider, zero-Copilot, and zero-MCP assertions while retaining every incident renderer/contract assertion.

### Implementation for User Story 1

- [X] T010 [US1] Implement `retrieve_active_incidents()` in `backend/services/datadog_incidents.py` using the allowlisted client, `query=state:(active OR stable)`, `page[size]=100`, a 90-second overall deadline, and local validation before returning the existing `{"incidents": [...]}` envelope.
- [X] T011 [US1] Implement incident-search normalization in `backend/services/datadog_incidents.py`: map `id`, `title`, exact `state`, optional `severity`, `created`→`createdAt`, `modified`→`updatedAt`, `customer_impact_scope`→`summary`, and a canonical `/incidents/{id}` app URL; reject states outside `ACTIVE`/`STABLE`, duplicate IDs, more than 100 records, malformed timestamps, or invalid Datadog URLs.
- [X] T012 [US1] Remove the Copilot prompt, CLI event parser, `subprocess`/`shutil` retrieval path, MCP constants, and `COPILOT_*` imports from `backend/services/datadog_incidents.py` while preserving all cache, lock, freshness, and snapshot functions unchanged.

**Checkpoint**: US1 works independently with Copilot absent and no MCP configuration.

---

## Phase 4: User Story 2 - Retrieve incident, notebook, and monitor evidence (Priority: P1)

**Goal**: Retrieve normalized incident details, referenced investigation notebooks, and referenced monitor definitions on demand with intact relationships and source identifiers.

**Independent Test**: Provide a fixture incident referencing one notebook and one monitor; call the internal evidence service and verify Markdown cells, time ranges, query definitions, monitor fields, relationships, source URLs, and unavailable-reference behavior, with no evidence cache write.

### Tests for User Story 2

- [X] T013 [US2] Add incident-detail and reference-discovery tests in `tests/test_datadog_evidence.py` for exact state, optional fields, source URL, structured attachment/field references, deduplication, the 10-references-per-kind bound, and unavailable-reference reporting.
- [X] T014 [US2] Add notebook-normalization tests in `tests/test_datadog_evidence.py` for Markdown cells, provider order, time ranges, up to 20 query/metric definitions per cell, the 200-cell bound, and unsupported cell types omitted into `omittedCellTypes` without raw content.
- [X] T015 [US2] Add monitor-normalization tests in `tests/test_datadog_evidence.py` for identity, name, type, query, thresholds (≤20 entries), tags (≤100), exact current state, message, assets, constructed URL, and malformed-field rejection.
- [X] T016 [US2] Add bundle-assembly tests in `tests/test_datadog_evidence.py` for `complete` versus `partial` status, relationships, reference-level timeout/not-found/forbidden/invalid errors, and absence of any evidence cache file.

### Implementation for User Story 2

- [X] T017 [US2] Implement incident-detail normalization and structured-only reference extraction in `backend/services/datadog_evidence.py`: link attachments, exact notebook/monitor URLs or `kind:id` field values, monitor notebook assets, no free-text scanning, no resource listing, and deduplication.
- [X] T018 [US2] Implement notebook normalization in `backend/services/datadog_evidence.py`: supported types `markdown`, `timeseries`, `toplist`, `heatmap`, `distribution`, `log_stream`; preserve Markdown and query definitions; omit unsupported types; reject invalid structure, no supported cells, more than 200 cells, or an ID mismatch.
- [X] T019 [US2] Implement monitor normalization in `backend/services/datadog_evidence.py`: require matching `id`, non-empty `name`/`type`, string `query`; expose `options.thresholds`, `tags`, `overall_state`/`state`, `message`, `assets`, timestamps, and a constructed `/monitors/{id}` URL.
- [X] T020 [US2] Implement `get_incident_evidence()`, `get_notebook_evidence()`, and `get_monitor_evidence()` in `backend/services/datadog_evidence.py`, including the `partial` bundle status and controlled reference-level failures; do not persist evidence.

**Checkpoint**: US2 works independently and leaves the incident cache untouched.

---

## Phase 5: User Story 3 - Fail closed and preserve the last trusted cache (Priority: P1)

**Goal**: Every provider failure preserves the last successful snapshot as stale, or reports unavailable when no snapshot exists, with bounded timeouts and no partial success.

**Independent Test**: Seed a successful snapshot, then exercise auth failure, timeout, malformed response, oversized response, server error, and cache-write failure; verify the prior incidents and `lastSuccessfulAt` survive as stale, and a first failure is unavailable rather than zero.

### Tests for User Story 3

- [X] T021 [P] [US3] Extend `tests/test_datadog_incidents.py` with direct-provider failure cases: `provider-unavailable`, `timeout`, `invalid-response`, oversized response, empty-success replacement, and stale preservation with the exact prior states and timestamps.
- [X] T022 [P] [US3] Add a zero-Copilot/MCP stale-cache regression in `tests/test_dependency_gates.py` using a failing fake Datadog transport and asserting the previous cache is preserved.
- [X] T023 [US3] Add cache-write and refresh-coalescing regressions in `tests/test_datadog_incidents.py` proving a failed write or overlapping refresh cannot replace the last successful snapshot or create a success-shaped empty result.

### Implementation for User Story 3

- [X] T024 [US3] Map `DatadogProviderUnavailable`, `DatadogProviderTimeout`, and `DatadogResponseInvalid` to the existing `provider-unavailable`, `timeout`, and `invalid-response` codes in `backend/services/datadog_incidents.py`; preserve `fail-closed` behavior and `cache-unavailable` handling.
- [X] T025 [US3] Enforce the overall monotonic deadline and 1,000,000-byte response bound in `backend/services/datadog_provider.py`, including paginated incident search, so no retrieval remains active past the configured timeout.
- [X] T026 [US3] Update sanitized refresh logging in `backend/services/datadog_incidents.py` to identify `provider=datadog-api` and include only controlled code/rule/category values, never raw payloads, URLs with credentials, or token material.

**Checkpoint**: US3 works independently and preserves the Feature 009 cache contract under all tested failures.

---

## Phase 6: User Story 4 - Keep the access token secret and the integration read-only (Priority: P1)

**Goal**: The bearer token is never disclosed, and the client can issue only allowlisted retrieval operations.

**Independent Test**: Configure a sentinel token, run success and failure paths, and search all responses, logs, exceptions, cache files, and test artifacts; record every transport request and verify only retrieval operations occur.

### Tests for User Story 4

- [X] T027 [P] [US4] Add allowlist and mutation-rejection tests in `tests/test_datadog_provider.py` proving unknown logical operations, non-allowlisted paths, invalid IDs, and create/update/acknowledge/mute/resolve/delete attempts are rejected before transport.
- [X] T028 [P] [US4] Add credential non-disclosure tests in `tests/test_datadog_secrets.py` using a recognizable sentinel token across success, auth failure, timeout, malformed response, and cache-write failure; assert absence from API responses, logs, exception strings, `repr()`, cache files, and temporary test artifacts.
- [X] T029 [P] [US4] Add structural read-only regression tests in `tests/test_datadog_readonly.py` asserting `backend/services/datadog_incidents.py` has no Copilot subprocess/MCP retrieval path and the provider exposes only the four allowlisted retrieval operations.

### Implementation for User Story 4

- [X] T030 [US4] Harden `backend/services/datadog_provider.py` so the token is stored in a private redacted field, every exception and `repr()` is sanitized, the header is added only to the configured Datadog destination, and response/error bodies are never included in failures.
- [X] T031 [US4] Verify and clean `backend/services/datadog_incidents.py` and `backend/services/datadog_evidence.py` so neither module imports or invokes Copilot, MCP, shell commands, or any Datadog mutation operation.

**Checkpoint**: US4 works independently; token disclosure and mutation paths are structurally absent.

---

## Phase 7: User Story 5 - Diagnose provider readiness without network calls (Priority: P2)

**Goal**: Readiness, status, and health report accurate static Datadog provider state without Datadog, Copilot, or MCP calls.

**Independent Test**: View readiness, status, and health with valid configuration, no token, invalid base URL, and no configuration; verify zero Datadog/Copilot/MCP calls, accurate ready/not-ready/not-configured states, and no credential value.

### Tests for User Story 5

- [X] T032 [P] [US5] Extend `tests/test_datadog_provider.py` with static readiness cases for ready, not-ready, and not-configured, asserting zero transport calls and no token in output.
- [X] T033 [P] [US5] Add health and status diagnostic tests in `tests/test_status.py` and `tests/test_safety.py` for the additive `datadogProvider` object and absence of credential material.
- [X] T034 [P] [US5] Update `tests/test_dependency_readiness.py` and `tests/test_readiness_api.py` to expect `external.datadog`, removal of `external.datadogMcp`, optional capability status mapping, and zero `copilot mcp list` invocation.
- [X] T035 [P] [US5] Update `tests/test_runtime_service.py` and `tests/test_bootstrap_provisioning.py` for the Datadog environment allowlist, optional `datadog-provider.env`, and the `external.datadog` readiness identifier.

### Implementation for User Story 5

- [X] T036 [P] [US5] Replace the `external.datadogMcp` probe in `backend/services/dependency_readiness.py` with the static `external.datadog` capability using `datadog_provider_readiness()`; remove the `copilot mcp list` subprocess path and keep `external.copilot` separate.
- [X] T037 [P] [US5] Add `datadogProvider` to `backend/app.py` (`/api/health`) and `backend/services/status.py` (`get_status` response) using the shared static readiness object.
- [X] T038 [P] [US5] Add the Datadog environment allowlist and optional `datadog-provider.env` `EnvironmentFile=-` to `scripts/run_service.py` and `systemd/noc-web.service.in`, with no token in the unit file.
- [X] T039 [P] [US5] Update `scripts/windows/bootstrap-status.ps1` and `scripts/bootstrap/release_manifest.py` so Datadog evidence readiness uses `external.datadog` and does not require Datadog MCP for Feature 015.
- [X] T040 [P] [US5] Document the new variables, readiness semantics, and optional environment file in `docs/workstation-runtime.md` and `README.md`.

**Checkpoint**: US5 works independently and diagnostics remain static.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, regression, security, and documentation validation.

- [X] T041 [P] Update `tests/test_frontend_modules.py` only where additive diagnostics fields or obsolete Datadog references require it; preserve all existing frontend module assertions.
- [X] T042 [P] Review `backend/services/datadog_incidents.py`, `backend/services/datadog_provider.py`, and `backend/services/datadog_evidence.py` for dead code, unused imports, and stale Copilot/MCP references; remove them without changing the public incident contract.
- [X] T043 Run the focused suites from `specs/015-datadog-rest-provider/quickstart.md` sections 2–5 and fix all failures.
- [X] T044 Run the full suite `python -m pytest -q` and fix all regressions.
- [X] T045 Run the quickstart static-readiness, evidence, and optional live-readiness checks in `specs/015-datadog-rest-provider/quickstart.md` and record outcomes.
- [X] T046 Perform a sentinel-token scan of test outputs, logs, temporary directories, and generated artifacts using a recognizable test value; confirm no token fragment appears.
- [X] T047 Review `specs/015-datadog-rest-provider/contracts/` and `specs/015-datadog-rest-provider/data-model.md` against the implementation and update any drift in `docs/workstation-runtime.md` and `README.md`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **User Stories (Phases 3–7)**: All depend on Foundational completion.
  - US1 and US2 can start in parallel.
  - US3 depends on US1 implementation.
  - US4 depends on Foundational and can start in parallel with US1/US2.
  - US5 depends on Foundational and can start in parallel with US1/US2/US4.
- **Polish (Phase 8)**: Depends on all desired user stories.

### User Story Dependencies

- **US1 (P1)**: Requires T002–T006. No dependency on other stories.
- **US2 (P1)**: Requires T002–T006. Independent of US1; uses the shared provider client.
- **US3 (P1)**: Requires T002–T006 and US1 T010–T012.
- **US4 (P1)**: Requires T002–T006. Independent of other stories.
- **US5 (P2)**: Requires T002–T006. Independent of other stories.

### Within Each User Story

- Tests first, then implementation.
- Shared normalizers/entities before bundle assembly.
- Provider/client tasks before incident or evidence integration.
- Complete and validate each story before moving to the next.

### Parallel Opportunities

- T002 and T003 can run in parallel.
- US1 test tasks T007–T009 can run in parallel.
- US2 test tasks T013–T016 are sequential because they edit the same test file.
- US3 test tasks T021–T022 can run in parallel; T023 follows.
- US4 test tasks T027–T029 can run in parallel.
- US5 test tasks T032–T035 can run in parallel.
- US5 implementation tasks T036–T040 can run in parallel after their tests.
- Polish documentation/review tasks T041–T042 can run in parallel.

---

## Parallel Example: User Story 1

```bash
# Launch the three US1 regression tasks together:
Task: "Add direct incident-retrieval tests in tests/test_datadog_incidents.py"
Task: "Add API contract regression tests in tests/test_datadog_incidents_api.py"
Task: "Replace the obsolete architecture assertion in tests/test_datadog_incidents_frontend.py"
```

## Parallel Example: User Story 4

```bash
Task: "Add allowlist and mutation-rejection tests in tests/test_datadog_provider.py"
Task: "Add credential non-disclosure tests in tests/test_datadog_secrets.py"
Task: "Add structural read-only regression tests in tests/test_datadog_readonly.py"
```

## Parallel Example: User Story 5

```bash
Task: "Add static readiness cases in tests/test_datadog_provider.py"
Task: "Add health/status diagnostics tests in tests/test_status.py and tests/test_safety.py"
Task: "Update external readiness tests in tests/test_dependency_readiness.py and tests/test_readiness_api.py"
Task: "Update runtime/bootstrap tests in tests/test_runtime_service.py and tests/test_bootstrap_provisioning.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: US1.
4. Run the US1 quickstart scenarios and the existing incident API/frontend tests.
5. Stop and validate the MVP before adding evidence and diagnostics.

### Incremental Delivery

1. Foundation → US1: incidents work without Copilot/MCP.
2. US2: on-demand incident, notebook, and monitor evidence.
3. US3: failure and stale-cache hardening.
4. US4: secret and read-only regression hardening.
5. US5: static diagnostics and managed-service configuration.
6. Polish: full regression, security scan, docs consistency.

### Parallel Team Strategy

1. Complete Setup and Foundational together.
2. After Foundational:
   - Developer A: US1 incidents.
   - Developer B: US2 evidence.
   - Developer C: US4 secrets/read-only.
   - Developer D: US5 diagnostics.
3. US3 starts after US1 and focuses on failure/stale behavior.
4. Merge and run the full suite.

---

## Notes

- [P] tasks use different files and no incomplete dependency.
- [Story] labels map tasks to the five specification user stories.
- Tests must be written and observed failing before implementation.
- No task accesses real Datadog, real credentials, Copilot CLI, or Datadog MCP.
- No task adds an AI call, `noc-inv` generation change, or `noc-handover` change.

## Phase 9: Convergence

- [X] T048 Require the incident-detail envelope to identify itself as an incident (`data.type` must identify an incident) before normalization in `backend/services/datadog_evidence.py`, and add a wrong-type regression in `tests/test_datadog_evidence.py` asserting `invalid-response` per data-model: Incident Detail Evidence / FR-021 (partial)
- [X] T049 Require the notebook envelope to identify itself as a notebook (`data.type` == `notebooks`) before normalization in `backend/services/datadog_evidence.py`, and add a wrong-type regression in `tests/test_datadog_evidence.py` per research: Decision 9 / FR-021 (partial)
- [X] T050 Make notebook query/metric-definition overflow fail closed instead of silently truncating in `backend/services/datadog_evidence.py`; `_extract_queries` must raise an `invalid-response` failure when more than 20 distinct definitions are present, with a 21-definition regression in `tests/test_datadog_evidence.py` per FR-022 / data-model: Bounds Summary / T014 (contradicts)
- [X] T051 Bound and sanitize unsupported notebook cell-type names before adding them to `omittedCellTypes` in `backend/services/datadog_evidence.py` using shared bounded-text validation (for example, at most 64 characters and no control characters), and add oversized/control-character cell-type regressions in `tests/test_datadog_evidence.py` per FR-021 / FR-022 / data-model: Notebook Evidence (partial)
- [X] T052 Reject a non-mapping, non-null monitor `options` value instead of treating thresholds as absent in `backend/services/datadog_evidence.py`, and add malformed-`options` regression coverage in `tests/test_datadog_evidence.py` per FR-021 / data-model: Monitor Evidence (partial)
- [X] T053 Add the missing User Story 2 regression coverage in `tests/test_datadog_evidence.py`: incident-detail optional fields and source URLs, incident link-attachment reference discovery, notebook metadata (created/modified/status), monitor over-bounds (>20 thresholds, >100 tags, >20 assets), and reference-level timeout/forbidden/invalid-response bundle behavior per T013 / T014 / T015 / T016 / FR-027 / SC-012 (partial)
- [X] T054 Reconcile the Feature 015 specification artifacts with the implemented relative-path and notebook-to-monitor discovery behavior in `specs/015-datadog-rest-provider/spec.md`, `plan.md`, and `quickstart.md`: update FR-005/FR-006, US2 acceptance scenarios, Clarification Q18, plan Phase 0 wording, and quickstart section 4 expectations without changing runtime behavior per FR-005 / FR-006 / US2 / Clarification Q18 (contradicts)
