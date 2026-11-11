---

description: "Task list for provider-independent AI investigation generation"
---

# Tasks: Provider-Independent AI Investigation Generation

**Input**: Design documents from `/specs/016-ai-investigation-generation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — the feature specification explicitly requires regression coverage for evidence minimization, generation, citations, partial evidence, failures, credentials, fallback, preview, confirmation, persistence, provenance, lifecycle, and zero Datadog mutations.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- Web application: `backend/`, `frontend/`, `tests/`, `docs/`
- Feature design artifacts: `specs/016-ai-investigation-generation/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare deterministic Feature 016 test fixtures and injection points.

- [X] T001 Create `tests/support/investigation_ai.py` with builders for complete, partial, unavailable, malformed, and over-bound Feature 015 evidence bundles; fake AI provider success/failure results; and an injectable clock for preview-store tests.
- [X] T002 Add Feature 016 fixture wiring in `tests/conftest.py` to inject fake evidence loaders, fake AI providers, preview-store resets, and temporary NOC roots into investigation API tests.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared evidence, preview, provider, provenance, and API foundations required by all user stories.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Foundational Tests

- [X] T003 [P] Add failing tests in `tests/test_investigation_ai_evidence.py` for evidence minimization, stable IDs (`incident:<id>`, `notebook:<id>`, `monitor:<id>`), availability, package `≤256 KiB`, `≤10` notebooks, `≤10` monitors, notebook Markdown `≤16 KiB` each and `≤64 KiB` total, canonical digest, and credential exclusion.
- [X] T004 [P] Add failing tests in `tests/test_investigation_preview_store.py` for a maximum of `32` active snapshots, `10`-minute TTL, atomic single-use consumption, expiry/eviction, no disk persistence, and injected clock behavior.
- [X] T005 [P] Add failing tests in `tests/test_investigation_output_validation.py` for the exact five required keys (`summary`, `confirmedFindings`, `currentStatus`, `nextActions`, `handoverSummary`), non-empty lists, `≤8` items per section, `≤2 KiB` per item, `≤64 KiB` total, and inline stable-ID citation requirements.
- [X] T006 [P] Add failing tests in `tests/test_deepseek_provider.py` and `tests/test_ai_provider.py` for the investigation prompt profile, bounded response handling, explicit configured-provider selection, and no automatic fallback.

### Foundational Implementation

- [X] T007 Create `backend/services/investigation_evidence.py` to build the bounded evidence package from `backend.services.datadog_evidence.get_incident_evidence` only, enforce the package bounds and stable IDs, compute a canonical digest, and fail closed on credential-like evidence.
- [X] T008 [P] Create `backend/services/investigation_preview_store.py` with a thread-safe, in-memory, `32`-entry, `10`-minute, single-use snapshot store; no disk, log, or database persistence.
- [X] T009 Create `backend/services/investigation_ai.py` with the provider-neutral investigation system prompt that forbids tools/external actions and credential solicitation, a bounded envelope builder, five-section JSON schema, citation extraction, and availability-claim rejection rules; every generated item must cite at least one supplied stable evidence ID.
- [X] T010 Extend `backend/services/deepseek_provider.py`, `backend/services/copilot_cli.py`, and `backend/services/ai_provider.py` with an optional investigation prompt profile while preserving Assistant defaults, DeepSeek Flash support through the existing DeepSeek configuration, existing timeouts, bounded responses, explicit provider selection, and no fallback.
- [X] T011 [P] Extend `backend/services/investigations.py` provenance detection and projection to recognize system-authored `ai-evidence` metadata/files while preserving legacy `noc-inv` and `copilot-mcp` records.
- [X] T012 Add the preview orchestration foundation in `backend/services/investigation_generation.py`: require a valid current ACTIVE/STABLE incident ID, enforce collision protection, build the evidence package, check static provider readiness, store the exact snapshot, and return a bounded preview summary without calling the AI provider or writing a record.
- [X] T013 Add preview request/response models and sanitized preview error mapping in `backend/api/investigations.py`, including `incidentId`, `previewId`, evidence summary, provider identity/model, and controlled failure codes.

**Checkpoint**: Evidence, preview, provider, provenance, and API foundations are ready; user stories can begin.

---

## Phase 3: User Story 1 - Generate an investigation from validated incident evidence (Priority: P1) 🎯 MVP

**Goal**: An operator confirms creation and NOC Web generates a locally persisted investigation from Feature 015 evidence using the configured AI provider, without noc-inv, Copilot CLI, or Datadog MCP.

**Independent Test**: Using fake Feature 015 evidence and a fake DeepSeek Flash provider, preview and confirm an investigation; verify the record is persisted and ready for review while Copilot/noc-inv/MCP are absent and no Datadog mutation occurs.

### Tests for User Story 1

- [X] T014 [P] [US1] Add preview/create contract tests in `tests/test_investigation_creation.py` for `incidentId`, `previewId`, `confirmed: true`, selected shift, request/preview mismatch, and the API response fields.
- [X] T015 [P] [US1] Add successful generation tests in `tests/test_investigation_generation.py` using fake Feature 015 evidence and a fake configured DeepSeek Flash provider; assert `201`, `generationStatus: completed`, `validationStatus: ready_for_review`, and the created projection.
- [X] T016 [P] [US1] Add regression tests in `tests/test_datadog_readonly.py` asserting zero `noc-inv`, Copilot CLI, Datadog MCP, and Datadog mutation calls during a confirmed generation.
- [X] T017 [US1] Add selected-shift, collision-protection, and provenance-file tests in `tests/test_investigation_generation.py` and `tests/test_investigation_creation.py`; verify the target path uses the selected shift and an existing record is never overwritten.

### Implementation for User Story 1

- [X] T018 [US1] Add `incidentId`/`previewId`/confirmation handling and create orchestration in `backend/services/investigation_generation.py`: consume the active snapshot, verify request and provider identity, re-fetch Feature 015 evidence and compare the digest, call the configured provider once without fallback, validate output, and fail closed on any mismatch.
- [X] T019 [US1] Implement server-authored Markdown rendering and staged publication in `backend/services/investigation_generation.py` for `investigation.md`, `generation-status.json`, `evidence-provenance.json`, and `reviewed-context.json`, preserving atomic replace and collision protection.
- [X] T020 [US1] Implement create request handling and sanitized success/error mapping in `backend/api/investigations.py`, using the configured provider from application state and returning the existing investigation projection.
- [X] T021 [P] [US1] Update `frontend/js/api.js` `previewInvestigation` and `createInvestigation` signatures for `incidentId`, `previewId`, evidence summary, and provider metadata.
- [X] T022 [P] [US1] Update `frontend/js/active-incidents.js` to store a bounded session handoff containing `incidentId`, `title`, and optional `url` when the operator selects Create Investigation.
- [X] T023 [US1] Update `frontend/investigations.html` create-panel flow to read the incident handoff, require an incident ID, show the evidence/provider summary, and call preview/create with the new fields.
- [X] T024 [US1] Add success-path regression assertions in `tests/test_investigation_generation.py` for `ai-evidence` provenance, `ready_for_review` lifecycle, `reviewed-context.json`, and the absence of credential sentinels in persisted files.

**Checkpoint**: User Story 1 works independently with fake evidence/provider and no legacy tools.

---

## Phase 4: User Story 2 - Keep generated output evidence-grounded and fail closed (Priority: P1)

**Goal**: Reject unsupported references, malformed or incomplete output, provider failures, and credential leakage; keep partial evidence explicitly partial.

**Independent Test**: Use fake provider responses with unsupported citations, missing sections, malformed/over-bound output, timeout/unavailability, and sentinel credentials; verify every invalid case fails closed with no persisted investigation, while a valid partial-evidence response is accepted only with system-authored availability disclosure.

### Tests for User Story 2

- [X] T025 [P] [US2] Add unsupported, fabricated, non-canonical, and cross-package citation tests in `tests/test_investigation_ai_evidence.py`.
- [X] T026 [P] [US2] Add partial/unavailable evidence tests in `tests/test_investigation_output_validation.py` for system-authored disclosure, contradiction rejection, and acceptance only when incident detail is valid.
- [X] T027 [US2] Add missing-section, malformed, non-object, placeholder-only, and over-bound output tests in `tests/test_investigation_output_validation.py`.
- [X] T028 [P] [US2] Add provider timeout, unavailability, invalid-response, incomplete-configuration, and no-fallback tests in `tests/test_investigation_generation.py` and `tests/test_ai_provider.py`.
- [X] T029 [P] [US2] Add credential sentinel tests in `tests/test_datadog_secrets.py` across API responses, logs, generated Markdown, JSON files, exceptions, and frontend output.

### Implementation for User Story 2

- [X] T030 [US2] Implement citation validation, required-section validation, availability-claim rejection, and output bounds in `backend/services/investigation_ai.py`; reject unsupported/fabricated IDs and any item without a supplied stable ID.
- [X] T031 [US2] Implement system-authored `Evidence Status` metadata, the `## Evidence Availability` section, and `evidence-provenance.json` generation in `backend/services/investigation_generation.py`; never let AI output author availability state.
- [X] T032 [US2] Implement provider failure mapping and no-fallback behavior in `backend/services/investigation_generation.py` and `backend/services/ai_provider.py`; map not-configured/not-ready to `503`, timeout to `504`, unavailable to `503`, and invalid response to `502` with sanitized messages.
- [X] T033 [P] [US2] Harden evidence secret exclusion/redaction for nested or unusual credential-like fields in `backend/services/investigation_evidence.py`; ensure no Authorization header, environment value, or credential value enters the package, and fail closed with `evidence-credential-detected` when detection is ambiguous.
- [X] T034 [US2] Add sanitized partial/error display and invalid-preview handling in `frontend/investigations.html` and `backend/api/investigations.py`; never expose raw provider payloads or credentials.
- [X] T035 [US2] Add regression assertions in `tests/test_investigation_generation.py` that every failure removes staging output and leaves no investigation directory, Markdown, or provenance files.

**Checkpoint**: User Story 2 fails closed for invalid output, partial-evidence contradictions, provider failures, and credentials.

---

## Phase 5: User Story 3 - Preview and explicitly confirm before generation (Priority: P1)

**Goal**: Preview remains non-generative and read-only; changes invalidate preview; AI runs only after explicit confirmation with an active preview.

**Independent Test**: Open preview with fake evidence and a provider spy; verify zero AI calls and zero records, invalidate the preview by changing shift/name/notebook/evidence/provider, and verify generation starts only after an explicit confirmation with a matching active `previewId`.

### Tests for User Story 3

- [X] T036 [US3] Add preview non-generative/no-provider-call/no-record tests in `tests/test_investigation_generation.py`.
- [X] T037 [P] [US3] Add preview invalidation tests for shift, name, notebook URL, evidence digest, provider identity/model, expiry, and single-use consumption in `tests/test_investigation_preview_store.py`.
- [X] T038 [P] [US3] Add explicit-confirmation, missing/expired/used/mismatched `previewId`, and no-record-before-confirmation tests in `tests/test_investigation_creation.py`.
- [X] T039 [P] [US3] Add frontend regression tests in `tests/test_frontend_modules.py` for incident handoff, preview display, confirmation dialog, selected-shift invalidation, and the non-generative preview message.

### Implementation for User Story 3

- [X] T040 [US3] Finalize preview summary, exact snapshot retention, expiry, invalidation, and single-use consumption in `backend/services/investigation_generation.py` and `backend/services/investigation_preview_store.py`; the preview must expose only bounded evidence metadata and no raw evidence.
- [X] T041 [US3] Update `frontend/investigations.html` preview panel, confirmation dialog, stale/expired messages, and reset/invalidation on selected-shift, name, notebook, evidence, and provider changes.
- [X] T042 [US3] Update `frontend/js/api.js` response handling for `previewId`, expiry, evidence status, provider identity/model, and sanitized preview/create failures.
- [X] T043 [US3] Add stale/expired/used/mismatch error mapping in `backend/api/investigations.py` and ensure the confirmation path is the only route that invokes AI generation.

**Checkpoint**: User Story 3 previews are non-generative and cannot be bypassed.

---

## Phase 6: User Story 4 - Preserve investigation operations and operator-facing behavior (Priority: P2)

**Goal**: Keep existing inspection, lifecycle, reviewed findings, Datadog links, incident attachment, selected-shift synchronization, and local persistence compatible while updating UI/docs wording.

**Independent Test**: Exercise legacy `noc-inv`/`copilot-mcp` records and new `ai-evidence` records through inspection, review, lifecycle transitions, rejection, Datadog attachment, and selected-shift navigation; verify existing behavior and noc-handover remain unchanged.

### Tests for User Story 4

- [X] T044 [P] [US4] Add legacy provenance regression tests in `tests/test_investigation_projection.py`, `tests/test_investigation_lifecycle.py`, `tests/test_assistant.py`, and `tests/test_assistant_api.py` for inspection, review, routing, and reports.
- [X] T045 [US4] Add `ai-evidence` lifecycle/review/rejection/Datadog-attachment/cross-shift tests in `tests/test_investigation_lifecycle.py` and `tests/test_investigation_attachments.py`.
- [X] T046 [US4] Add UI wording, provenance label, selected-shift synchronization, and incident-handoff tests in `tests/test_frontend_modules.py`.

### Implementation for User Story 4

- [X] T047 [US4] Extend provenance allowlists for `ai-evidence` alongside legacy `noc-inv`/`copilot-mcp` in `backend/services/investigations.py`, `backend/services/assistant.py`, `backend/services/assistant_context.py`, `backend/services/ai_reports.py`, and `frontend/js/api.js`, using provider-neutral error and UI labels.
- [X] T048 [US4] Extend the `evidence` projection and Investigations display in `backend/services/investigations.py` and `frontend/investigations.html` with `ai-evidence` status, reference count, and provenance label; keep legacy projections unchanged.
- [X] T049 [US4] Update investigation readiness/status/health wording in `backend/services/readiness.py`, `backend/services/dependency_readiness.py`, `backend/services/health.py`, and `backend/services/status.py`; use `external.datadog` + `external.aiProvider`, mark legacy `noc-inv`/`copilot` checks optional for this workflow, and update assertions in `tests/test_readiness.py`, `tests/test_dependency_readiness.py`, `tests/test_readiness_api.py`, and `tests/test_status.py`.
- [X] T050 [P] [US4] Update operator documentation in `README.md` and `docs/workstation-runtime.md` to describe read-only Datadog REST evidence and the configured AI provider, with no noc-inv/Copilot/MCP requirement for investigation generation.
- [X] T051 [US4] Add regression assertions in `tests/test_investigation_attachments.py` and `tests/test_handover.py` that Datadog incident attachment remains local/read-only and noc-handover behavior is unchanged.
- [X] T052 [US4] Add regression assertions in `tests/test_investigation_generation.py` and `tests/test_frontend_modules.py` that investigation creation still targets the selected shift and selected-shift navigation remains synchronized.

**Checkpoint**: User Story 4 preserves existing operational behavior and updates operator-facing wording.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Remove dead legacy invocation paths, validate contracts, and run the complete verification suite.

- [X] T053 [P] Remove dead `noc-inv`/Copilot/MCP invocation, subprocess, and tool-availability code from `backend/services/investigation_generation.py` while preserving legacy record reading and Feature 015/014 integration.
- [X] T054 [P] Tighten or adjust `tests/test_investigation_ai_evidence.py` and `tests/test_investigation_preview_store.py` for any discovered bound/TTL/digest edge cases.
- [X] T055 Run focused Feature 016 tests: `.venv/bin/python -m pytest tests/test_investigation_ai_evidence.py tests/test_investigation_preview_store.py tests/test_investigation_generation.py tests/test_investigation_output_validation.py tests/test_investigation_lifecycle.py tests/test_investigation_projection.py tests/test_investigations.py tests/test_investigation_creation.py tests/test_investigation_attachments.py tests/test_deepseek_provider.py tests/test_ai_provider.py tests/test_assistant.py tests/test_assistant_api.py tests/test_frontend_modules.py tests/test_datadog_readonly.py tests/test_datadog_secrets.py tests/test_datadog_evidence.py tests/test_readiness.py tests/test_dependency_readiness.py tests/test_readiness_api.py tests/test_status.py tests/test_handover.py -q`
- [X] T056 Run the full suite from `/home/bsmith/code/noc-web`: `.venv/bin/python -m pytest -q`.
- [X] T057 Execute the `specs/016-ai-investigation-generation/quickstart.md` validation scenarios and update any drifted contract/data-model/quickstart text.
- [X] T058 Run a credential-sentinel and zero-Datadog-mutation audit across `backend/services/investigation_generation.py`, `backend/services/investigation_ai.py`, `frontend/investigations.html`, preview/create responses, logs, generated Markdown, JSON files, and exceptions.
- [X] T059 Verify `backend/services/datadog_evidence.py` and noc-handover generation are unchanged in behavior and add/confirm focused regression evidence in `tests/test_datadog_evidence.py` and `tests/test_handover.py`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational; provides the generation path used by later stories.
- **User Story 2 (Phase 4)**: Depends on Foundational and the US1 generation path; validates fail-closed behavior.
- **User Story 3 (Phase 5)**: Depends on Foundational and US1 preview/create; shares `investigations.html` and `api.js` with US1, so complete US1 UI tasks first.
- **User Story 4 (Phase 6)**: Depends on US1 for `ai-evidence` records; can begin after US1.
- **Polish (Phase 7)**: Depends on all desired user stories.

### User Story Dependencies

- **US1 (P1)**: Independent after Foundational; MVP generation path.
- **US2 (P1)**: Independently testable with fake provider responses; integrate after US1 generation exists.
- **US3 (P1)**: Independently testable preview/invalidation/confirmation behavior; sequence UI work after US1 because both edit the same files.
- **US4 (P2)**: Independently testable compatibility behavior; sequence after US1 for new-record fixtures.

### Within Each User Story

- Tests MUST be written and fail before implementation.
- Entity/package/store foundations before service orchestration.
- Service orchestration before API endpoints.
- API before frontend integration.
- Core implementation before cross-story integration.

### Parallel Opportunities

- T003, T004, T005, T006 can run in parallel.
- T007 and T008 can run in parallel; T011 can run alongside them once its interface is known.
- T014, T015, T016 can run in parallel; T017 shares `tests/test_investigation_creation.py` with T014, so run after T014.
- T025, T026, T028, T029 can run in parallel; T027 shares `tests/test_investigation_output_validation.py` with T026, so run after T026.
- T037, T038, T039 can run in parallel; T036 shares `tests/test_investigation_generation.py` with earlier generation tests, so run after those.
- T044 and T045 can run in parallel; T046 shares `tests/test_frontend_modules.py` with T039, so run after T039.
- T050, T053, T054, T057, T058, T059 can run in parallel after their dependencies; T055 and T056 are ordered commands.

---

## Parallel Example: User Story 1

```bash
# After Foundational is complete, run the independent US1 test files together:
Task: "Contract tests in tests/test_investigation_creation.py"
Task: "Successful generation tests in tests/test_investigation_generation.py"
Task: "Zero legacy-tool/mutation tests in tests/test_datadog_readonly.py"
```

## Parallel Example: User Story 2

```bash
# Run citation, partial-evidence, provider-failure, and credential tests together:
Task: "Citation tests in tests/test_investigation_ai_evidence.py"
Task: "Partial-evidence tests in tests/test_investigation_output_validation.py"
Task: "Provider failure tests in tests/test_investigation_generation.py and tests/test_ai_provider.py"
Task: "Credential sentinel tests in tests/test_datadog_secrets.py"
```

## Parallel Example: User Story 3

```bash
# Preview-store, creation, and frontend preview tests can run together:
Task: "Preview invalidation/TTL tests in tests/test_investigation_preview_store.py"
Task: "Explicit confirmation/expiry tests in tests/test_investigation_creation.py"
Task: "Frontend preview/confirmation tests in tests/test_frontend_modules.py"
```

## Parallel Example: User Story 4

```bash
# Legacy provenance tests and operator documentation updates can run together:
Task: "Legacy provenance tests in tests/test_investigation_projection.py and tests/test_investigation_lifecycle.py"
Task: "Operator documentation updates in README.md and docs/workstation-runtime.md"
```

## Parallel Example: Foundational

```bash
# Run independent foundational tests and modules concurrently:
Task: "Evidence package tests in tests/test_investigation_ai_evidence.py"
Task: "Preview store tests in tests/test_investigation_preview_store.py"
Task: "AI output tests in tests/test_investigation_output_validation.py"
Task: "Provider prompt tests in tests/test_deepseek_provider.py and tests/test_ai_provider.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: US1.
4. **STOP and VALIDATE**: Run T014–T017 and confirm a fake-evidence/fake-DeepSeek generation persists a reviewable record with no legacy tools or Datadog mutations.
5. Deploy/demo if ready.

### Incremental Delivery

1. Setup + Foundational → evidence/package/preview/provider foundations.
2. US1 → confirmed generation and local persistence.
3. US2 → evidence-grounded fail-closed validation and partial-evidence honesty.
4. US3 → preview/confirmation UX and invalidation hardening.
5. US4 → lifecycle/provenance/UI/docs compatibility.
6. Polish → remove dead legacy invocation paths and run full validation.

### Parallel Team Strategy

1. Team completes Setup + Foundational together.
2. After Foundational:
   - Developer A: US1 generation and persistence.
   - Developer B: US2 validation/failure tests and controls (after US1 service interface is stable).
   - Developer C: US3 preview/confirmation UX (sequence UI edits after US1 `investigations.html`/`api.js` changes).
   - Developer D: US4 compatibility and docs (after US1 creates `ai-evidence` fixtures).
3. Rejoin for Polish and full-suite validation.

---

## Notes

- [P] tasks touch different files and have no incomplete dependencies.
- [Story] labels map tasks to US1–US4 for traceability.
- Every user story has an independent test criterion and can be validated incrementally.
- Do not weaken Feature 015 read-only behavior, credential handling, timeouts, response bounds, or fail-closed protections.
- Do not change noc-handover generation.
- Do not add automatic fallback between DeepSeek and any other provider.
- Keep the selected-shift regression fix from `frontend/js/workflow-context.js` and `frontend/investigations.html` intact.

## Phase 8: Convergence

- [X] T060 Add a readiness regression in `tests/test_readiness.py` proving a missing or incompatible `noc-inv` command reports `required: false` and does not make the core workstation unready, matching the optional legacy-tool behavior already tested for Copilot per T049 / FR-006 (partial)
