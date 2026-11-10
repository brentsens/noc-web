---

description: "Task list for Provider-Independent AI Support"
---

# Tasks: Provider-Independent AI Support

**Input**: Design documents from `/specs/014-ai-provider-architecture/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: REQUIRED. FR-022 and SC-001 through SC-008 mandate acceptance coverage for both providers, credential non-disclosure, fail-closed behavior, diagnostics, and scope isolation. Test tasks are included in each user-story phase.

**Organization**: Tasks are grouped by user story so each story can be implemented and verified independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1-US5)
- Every task includes an exact repository-relative file path

## Path Conventions

Web application layout: `backend/`, `frontend/`, `tests/`, `scripts/`, `systemd/` at repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish provider-neutral constants, exception aliases, and managed-service configuration plumbing.

- [X] T001 Create `backend/services/ai_provider.py` with canonical provider identifier constants (`deepseek-api`, `github-copilot-cli`), a supported-provider set, display-label mapping (`DeepSeek API`, `GitHub Copilot CLI`), and defaults (`deepseek-flash`, `https://api.deepseek.com`, timeout 55).
- [X] T002 [P] Add provider-neutral exception aliases (`ProviderUnavailable`, `ProviderTimeout`, `ProviderInvalid`) and provider-neutral docstrings while preserving the existing `CopilotProvider*` classes in `backend/services/copilot_mcp.py`.
- [X] T003 [P] Extend `build_service_environment()` in `scripts/run_service.py` to copy only `NOC_WEB_AI_PROVIDER`, `NOC_WEB_DEEPSEEK_API_KEY`, `NOC_WEB_DEEPSEEK_MODEL`, `NOC_WEB_DEEPSEEK_BASE_URL`, and `NOC_WEB_AI_TIMEOUT_SECONDS` from `inherited`, leaving `COPILOT_TOKEN` and all other inherited variables uncopied.
- [X] T004 Add an optional `EnvironmentFile=-@AI_PROVIDER_ENV_FILE@` line to `systemd/noc-web.service.in` and substitute `<config-dir>/ai-provider.env` in `render_systemd_unit()` in `scripts/run_service.py` (depends on T003).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Provider-neutral configuration, static readiness, runtime resolution, and Assistant/API identifier plumbing that every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Implement environment parsing and validation in `backend/services/ai_provider.py`: unset/empty `NOC_WEB_AI_PROVIDER` means not configured; only exact provider values are accepted; `NOC_WEB_DEEPSEEK_MODEL` defaults to `deepseek-flash` and must be non-empty, at most 128 characters, and free of control characters; `NOC_WEB_DEEPSEEK_BASE_URL` defaults to `https://api.deepseek.com` and must be HTTPS with a non-empty host and no userinfo, query, fragment, or parent traversal; `NOC_WEB_AI_TIMEOUT_SECONDS` defaults to 55 and must be an integer 1-60; every error names only the affected setting.
- [X] T006 Implement `provider_readiness()` in `backend/services/ai_provider.py` returning `configuredProvider`, `readiness` (`ready`/`notReady`/`notConfigured`), `label`, `model`, `impact`, and `correctiveAction`; readiness is static, makes no provider request, and asserts neither credential acceptance nor reachability.
- [X] T007 Implement the `ProviderRuntime` dataclass and `resolve_provider_runtime()` in `backend/services/ai_provider.py` returning the identifier, the selected provider callable or `None`, and readiness; any credential is captured only inside the callable closure and never stored in a serializable field.
- [X] T008 [P] Wire startup runtime resolution in `backend/app.py`: replace the hard-coded `answer_with_copilot_cli` default with the resolved runtime, set both `app.state.assistant_provider` and `app.state.assistant_provider_identifier`, and change `configure_assistant_provider(provider, identifier)` so an omitted identifier means not configured rather than Copilot.
- [X] T009 [P] Refactor `backend/services/assistant.py` to take an explicit provider identifier: remove the module-level `ASSISTANT_PROVIDER` default, add `provider_identifier` to `_response()` and `answer()`, stamp the provider on refusal, limited, unavailable, and success responses, make `validate_assistant_response(response, shift_date, expected_provider=None)` accept only the two canonical identifiers, and keep `ask_copilot` resolving the environment-selected provider instead of defaulting to Copilot.
- [X] T010 Update `backend/api/assistant.py` to read both provider state fields, return controlled 503 `assistant-provider-not-configured` when the identifier is `None`, return controlled 503 `assistant-provider-not-ready` when a provider is selected but its callable is missing or invalid, pass the identifier into `answer()`, validate against the expected provider, and never fabricate a response contract object (depends on T008, T009).
- [X] T011 [P] Update the `fake_assistant_provider` fixture in `tests/conftest.py` to accept an explicit identifier and set/reset both `app.state.assistant_provider` and `app.state.assistant_provider_identifier`, treating a missing identifier as not configured.
- [X] T012 [P] Add `tests/test_ai_provider.py` covering environment parsing and validation, static readiness for `deepseek-api`, `github-copilot-cli`, and not configured, unknown/invalid provider values, timeout/base-URL/model bounds, and the absence of any credential field in readiness or runtime output.

**Checkpoint**: Foundation ready — provider-neutral runtime and Assistant attribution are in place.

---

## Phase 3: User Story 1 - Use the Assistant with the configured provider (Priority: P1) 🎯 MVP

**Goal**: The Assistant and all four AI Actions preserve their existing contract, evidence model, advisory semantics, and report behavior whether `deepseek-api` (DeepSeek Flash) or `github-copilot-cli` serves inference.

**Independent Test**: Configure each provider in turn, run representative Assistant questions and all four AI Actions, and verify identical response structure, evidence labels, advisory categories, validation outcomes, and report persistence, with the response attributing the provider that actually served it.

### Tests for User Story 1

- [X] T013 [P] [US1] Add contract tests in `tests/test_assistant.py` for both providers verifying the unchanged top-level keys, status/providerStatus relationships, evidence/advisory validation, and correct provider attribution on complete, limited, unavailable, and not-invoked responses.
- [X] T014 [P] [US1] Add API integration tests in `tests/test_assistant_api.py` running representative questions and all four AI Actions with `deepseek-api` and `github-copilot-cli`, verifying response structure, report persistence, and that a provider change is reflected by the next request.
- [X] T015 [P] [US1] Add DeepSeek success-path tests in `tests/test_deepseek_provider.py` verifying the request body (`model: deepseek-flash`, `response_format: {"type": "json_object"}`, `thinking: {"type": "disabled"}`, `stream: false`, `temperature: 0.2`, `max_tokens: 4096`, literal `JSON` in the system prompt), credential placement only in the `Authorization` header, and that only the parsed content object is returned.
- [X] T016 [P] [US1] Update `tests/test_ai_reports.py` to assert the report Provider line is `DeepSeek API` for `deepseek-api` and `GitHub Copilot CLI` for `github-copilot-cli`.

### Implementation for User Story 1

- [X] T017 [US1] Implement the DeepSeek Flash adapter in `backend/services/deepseek_provider.py`: build the system prompt from the existing analysis rules including the literal word `JSON`, POST to `{base_url}/chat/completions` with `urllib.request` and the bounded timeout, enforce HTTPS, validated URL, refused redirects, 1 MiB response cap, strict UTF-8, dict-only non-empty content, and rejection of `finish_reason: "length"`, returning only the parsed provider object.
- [X] T018 [US1] Add `build_deepseek_provider(config)` in `backend/services/ai_provider.py` returning a callable closure built from the validated configuration without exposing the key (depends on T017).
- [X] T019 [US1] Wire the DeepSeek callable into `resolve_provider_runtime()` for `deepseek-api` in `backend/services/ai_provider.py` while keeping `github-copilot-cli` on the existing adapter (depends on T018).
- [X] T020 [US1] Update `_render_action_report()` in `backend/services/ai_reports.py` to render `- Provider: <display label>` from the validated canonical identifier instead of hard-coded `GitHub Copilot CLI`, leaving validation, normalization, filenames, paths, and persistence unchanged (depends on T001).
- [X] T021 [P] [US1] Update `frontend/js/api.js` to extend `ASSISTANT_PROVIDERS` with both canonical identifiers and add a shared display-label helper while leaving response validation otherwise unchanged.
- [X] T022 [US1] Update `frontend/assistant.html` and `frontend/ai-actions.html` to render the provider label dynamically from the validated response and derive the pre-submission disclosure from the configured provider (depends on T021).

**Checkpoint**: User Story 1 is independently functional — both providers produce the same contract and attributed reports.

---

## Phase 4: User Story 2 - Keep provider credentials secret (Priority: P1)

**Goal**: No provider credential value appears in API responses, frontend content, logs, reports, or persisted application data.

**Independent Test**: Configure a recognizable sentinel credential, exercise successful and failing Assistant/AI Action requests, then search API responses, frontend output, logs, reports, and persisted files for the sentinel value.

### Tests for User Story 2

- [X] T023 [P] [US2] Add sentinel-key non-disclosure tests in `tests/test_deepseek_provider.py` for success, authentication failure, timeout, malformed output, and upstream error text containing the sentinel; assert raised messages and `caplog` records contain no key value or reversible representation.
- [X] T024 [P] [US2] Add credential non-disclosure scan tests in `tests/test_assistant_api.py` and `tests/test_ai_reports.py` that run successful and failing Assistant/AI Action requests with a sentinel key and assert responses and persisted `ai-*.md` reports contain no key, token, prompt, or raw provider output.
- [X] T025 [P] [US2] Add a Copilot credential/argument regression test in `tests/test_copilot_cli.py` verifying prompts and records travel via stdin/content only, never CLI arguments, and no credential material appears in adapter output.

### Implementation for User Story 2

- [X] T026 [US2] Harden secret handling in `backend/services/deepseek_provider.py`: keep the key only in the `Authorization` header and closure, use fixed public failure messages, never log headers, body, URL query, or upstream error text, and ensure configuration errors name only the affected setting (depends on T017).
- [X] T027 [US2] Ensure `provider_readiness()`, `ProviderRuntime`, and configuration-error objects in `backend/services/ai_provider.py` contain no credential field or reversible secret and that redacted errors name only the setting (depends on T007).
- [X] T028 [US2] Enforce canonical provider attribution in `backend/services/ai_reports.py` by deriving the report label only from the validated response provider and rejecting non-canonical or missing provider values before persistence (depends on T020).

**Checkpoint**: User Story 2 is independently verifiable — no sentinel credential appears in any output surface.

---

## Phase 5: User Story 3 - Fail closed without automatic fallback (Priority: P1)

**Goal**: Every provider failure produces a clear controlled limitation, no success-shaped answer, no saved report, and never a request to another provider.

**Independent Test**: Make the configured provider fail in each defined way while another supported provider is available; verify no request reaches the other provider, no report is created, and the operator sees the existing controlled status.

### Tests for User Story 3

- [X] T029 [P] [US3] Add DeepSeek failure-classification tests in `tests/test_deepseek_provider.py`: 3xx/400/401/402/403/422/429/5xx and DNS/TLS/network failures map to unavailable; socket/read timeout maps to timeout; blank, truncated, non-dict, invalid UTF-8, and over-1-MiB payloads map to invalid; assert no retry occurs.
- [X] T030 [P] [US3] Add no-fallback and configuration-state tests in `tests/test_assistant_api.py`: DeepSeek selected with a missing/invalid key while Copilot is available returns 503 `assistant-provider-not-ready` with no Copilot call and no report; an unset provider returns 503 `assistant-provider-not-configured`; Copilot selected but absent or malformed yields a controlled failure and no report.
- [X] T031 [P] [US3] Add Assistant failure-contract tests in `tests/test_assistant.py` asserting provider exceptions map to `unavailable`/`timeout`/`invalid` with correct `providerInvoked`, no success-shaped answer, and preservation of the context-insufficiency `limited`/`not-invoked` distinction.
- [X] T032 [P] [US3] Add a scope-isolation regression test in `tests/test_safety.py` confirming non-Assistant endpoints and workflows remain available when the provider is not configured or failing.

### Implementation for User Story 3

- [X] T033 [US3] Implement failure classification in `backend/services/deepseek_provider.py`, raising the shared `ProviderUnavailable`/`ProviderTimeout`/`ProviderInvalid` exceptions with correct `provider_invoked`, no retries, and no fallback (depends on T017).
- [X] T034 [US3] Enforce fail-closed API behavior in `backend/api/assistant.py`: return the two controlled 503 codes, never build a synthetic response contract, never persist a report, and never invoke a non-selected provider (depends on T010).
- [X] T035 [US3] Ensure `backend/services/assistant.py` maps provider exceptions to the existing statuses, stamps the active identifier on failures, never defaults to Copilot, and contains no automatic provider-switch path (depends on T009).

**Checkpoint**: User Story 3 is independently verifiable — all failure modes fail closed with zero cross-provider requests.

---

## Phase 6: User Story 4 - Diagnose provider readiness without secrets (Priority: P2)

**Goal**: Existing readiness and health surfaces accurately report the configured provider and static ready/not-ready/not-configured state with safe guidance and no secrets.

**Independent Test**: Inspect readiness and health with each provider configured and not configured, with credentials present and absent, and verify accurate provider identity and states that agree with each other without secret material.

### Tests for User Story 4

- [X] T036 [P] [US4] Update `tests/test_readiness_api.py` for the `external.aiProvider` contract: provider identity, model, `providerReadiness`, `required: false`, status mapping for ready/notReady/notConfigured, and no secret fields.
- [X] T037 [P] [US4] Update `tests/test_dependency_readiness.py` for `external.aiProvider` and confirm `external.copilot` remains a distinct Copilot-specific integration capability.
- [X] T038 [P] [US4] Update the root `/api/health` test in `tests/test_assistant_api.py` to assert the additive `aiProvider` object shape and non-secret ready/notReady/notConfigured values.
- [X] T039 [P] [US4] Update `tests/test_frontend_modules.py` for the AI Provider health panel and frontend helpers that accept both provider identifiers.

### Implementation for User Story 4

- [X] T040 [US4] Add the non-secret `aiProvider` object to the root `/api/health` handler in `backend/app.py` using `provider_readiness()`.
- [X] T041 [US4] Add the `AI Provider` section to `get_health()` in `backend/services/health.py` with state mapping ready→pass, notConfigured→warning, notReady→warning that never uses fail, and remove `copilot` from the unconditional required `TOOLS`.
- [X] T042 [US4] Add `external.aiProvider` to `assess_external_capabilities()` in `backend/services/dependency_readiness.py` with `required: false`, provider identity, model, readiness, impact, and safe corrective guidance, keeping `external.copilot` separate.
- [X] T043 [US4] Add the AI Provider diagnostic panel to `frontend/health.html` showing provider identity, readiness state, and corrective guidance without credentials (depends on T041).
- [X] T044 [P] [US4] Add health and readiness helper functions for the `aiProvider` and `external.aiProvider` shapes in `frontend/js/api.js` (depends on T021).

**Checkpoint**: User Story 4 is independently verifiable — readiness is authoritative, health agrees, and neither exposes secrets or probes the provider.

---

## Phase 7: User Story 5 - Preserve Copilot CLI as an optional provider (Priority: P3)

**Goal**: Copilot remains usable when explicitly selected, and a DeepSeek-selected deployment does not require Copilot installation or authentication.

**Independent Test**: Run Assistant and AI Action coverage with Copilot selected and available, Copilot selected and absent, and DeepSeek selected while Copilot is absent.

### Tests for User Story 5

- [X] T045 [P] [US5] Add readiness tests in `tests/test_ai_provider.py` for Copilot executable-present/absent and for DeepSeek readiness while Copilot is absent, asserting DeepSeek selection does not require Copilot.
- [X] T046 [P] [US5] Add regression tests in `tests/test_copilot_cli.py` covering Copilot selected and available, Copilot selected and absent, and DeepSeek selected while Copilot is absent.

### Implementation for User Story 5

- [X] T047 [US5] Ensure Copilot readiness in `backend/services/ai_provider.py` is based only on `shutil.which("copilot")` presence and does not assert authentication or reachability (depends on T006).
- [X] T048 [US5] Verify Copilot is optional in `backend/services/health.py` and `backend/services/dependency_readiness.py` so a DeepSeek-selected deployment without Copilot is healthy, while `external.copilot` still reports Copilot integration state separately (depends on T041, T042).

**Checkpoint**: All five user stories are independently functional and Copilot is optional.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, cleanup, and full regression confirmation.

- [X] T049 [P] Document provider environment variables, the absence of a default provider, the restart requirement, and the mode-0600 operator-managed `ai-provider.env` in `README.md` and `docs/workstation-runtime.md`.
- [X] T050 [P] Add `ai-provider.env` to `.gitignore` so an operator-managed credential file cannot be committed.
- [X] T051 Execute `specs/014-ai-provider-architecture/quickstart.md` sections 1-8 (offline suite, DeepSeek/Copilot/not-configured/no-fallback/secret-scan/regression/failure paths) and record any deviations in the same file.
- [X] T052 Run the full pytest suite (`.venv/bin/python -m pytest -q`) and fix regressions, confirming no behavioral change to Datadog incident retrieval, noc-inv investigation generation, or noc-handover generation.
- [X] T053 [P] Run the sentinel credential scan from quickstart section 6 across `backend/` and `frontend/` (excluding documentation examples) and confirm zero matches outside isolated test fixtures.
- [X] T054 Remove dead implicit-Copilot defaults, duplicate provider constants, and any residual fallback code paths in `backend/services/assistant.py` and `backend/app.py`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational; establishes the DeepSeek adapter and report/frontend attribution.
- **User Story 2 (Phase 4)**: Depends on Foundational and US1 adapter (T017).
- **User Story 3 (Phase 5)**: Depends on Foundational and US1 adapter (T017); shares Assistant/API files with US1, so T033-T035 run after T010/T017.
- **User Story 4 (Phase 6)**: Depends on Foundational readiness (T006); T043 depends on T041 and T044 on T021.
- **User Story 5 (Phase 7)**: Depends on Foundational readiness (T006) and diagnostics tasks T041/T042.
- **Polish (Phase 8)**: Depends on all desired user stories.

### User Story Dependencies

- **US1 (P1)**: Foundational only.
- **US2 (P1)**: Needs the DeepSeek adapter from US1 for meaningful sentinel coverage.
- **US3 (P1)**: Needs the DeepSeek adapter from US1 for failure-path coverage.
- **US4 (P2)**: Needs foundational readiness; independent of US1-US3 implementation details.
- **US5 (P3)**: Needs foundational readiness and the health/readiness integration from US4.

### Within Each User Story

- Tests before implementation, and must fail before implementation.
- Provider adapter and configuration before Assistant wiring.
- Assistant wiring before API fail-closed behavior.
- Diagnostics service before frontend panel.
- Report rendering before persistence guard.

### Parallel Opportunities

- T002 and T003 run in parallel with T001.
- T008 and T009 are parallel across `backend/app.py` and `backend/services/assistant.py`; T011 and T012 are parallel across `tests/conftest.py` and `tests/test_ai_provider.py`.
- In US1, T013-T016 are parallel test files; T021 is parallel with backend work.
- In US2, T023-T025 are parallel test files.
- In US3, T029-T032 are parallel test files.
- In US4, T036-T039 are parallel test files; T044 is parallel with T043.
- In US5, T045 and T046 are parallel test files.
- Polish T049, T050, T053 are parallel.

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together:
Task: "Add Assistant contract tests in tests/test_assistant.py"
Task: "Add API integration tests in tests/test_assistant_api.py"
Task: "Add DeepSeek success-path tests in tests/test_deepseek_provider.py"
Task: "Update report provider-label tests in tests/test_ai_reports.py"

# Launch independent frontend and backend work together:
Task: "Update provider identifiers/helpers in frontend/js/api.js"
Task: "Implement the DeepSeek Flash adapter in backend/services/deepseek_provider.py"
```

---

## Parallel Example: User Story 4

```bash
# Launch diagnostic contract tests together:
Task: "Update readiness contract tests in tests/test_readiness_api.py"
Task: "Update dependency-readiness tests in tests/test_dependency_readiness.py"
Task: "Update frontend module tests in tests/test_frontend_modules.py"

# Launch independent surfaces together after services exist:
Task: "Add AI Provider panel in frontend/health.html"
Task: "Add health/readiness helpers in frontend/js/api.js"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Phase 1 (Setup).
2. Complete Phase 2 (Foundational) — blocks all stories.
3. Complete Phase 3 (US1) so both providers satisfy the preserved contract.
4. **STOP and VALIDATE**: run T013-T016 plus quickstart section 1.
5. Demo the DeepSeek-selected and Copilot-selected Assistant paths.

Note: US2 and US3 are also P1 safety requirements. US1 must not be deployed operationally without them; treat US1+US2+US3 as the minimum production-safe increment.

### Incremental Delivery

1. Setup + Foundational → provider-neutral runtime ready.
2. US1 → both providers preserve the contract and reports (MVP).
3. US2 → credential non-disclosure verified.
4. US3 → fail-closed/no-fallback verified.
5. US4 → provider diagnostics on readiness and health.
6. US5 → Copilot confirmed optional.
7. Polish → docs, quickstart validation, full regression, cleanup.

### Parallel Team Strategy

1. Team completes Setup + Foundational together.
2. After Foundational:
   - Developer A: US1 (adapter + Assistant + reports).
   - Developer B: US4 diagnostics (independent of adapter internals).
3. After US1:
   - Developer C: US2 credential hardening and scans.
   - Developer D: US3 failure classification and no-fallback.
4. US5 and Polish follow once US4/T041-T042 land.

---

## Notes

- `[P]` tasks touch different files and have no dependency on incomplete work.
- Tests are mandatory per FR-022; verify they fail before implementation.
- Every Assistant response, including refusal and failure responses, must stamp the active canonical provider identifier.
- Readiness is static: no provider request, no credential acceptance claim, no reachability claim.
- [P] tasks must not be assigned to the same file simultaneously; several test files are revisited in later story phases and must be sequenced across phases.

---

## Phase 9: Convergence

- [X] T055 Remove the adapter-level stale-claim pruning in `backend/services/deepseek_provider.py` (`_omit_unqualified_stale_claims` and its call) so the parsed provider object is returned unchanged and `validate_assistant_response` applies the same fail-closed stale-qualifier rule for both providers; update `tests/test_deepseek_provider.py` accordingly per FR-004/FR-011 (contradicts)
- [X] T056 Apply the validated `NOC_WEB_AI_TIMEOUT_SECONDS` value to the Copilot mediation path (thread the configured timeout into `CopilotMcpAdapter` from `backend/services/assistant.py` and `backend/services/copilot_mcp.py`) so the setting bounds both providers, with tests per plan: provider timeout contract (partial)
- [X] T057 Correct the GitHub Copilot CLI capability row in `docs/workstation-runtime.md` so Assistant and AI Action unavailability is scoped to `github-copilot-cli` selection, consistent with a `deepseek-api` deployment that does not require Copilot per FR-016 (partial)
