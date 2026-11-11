---

description: "Task list for provider-independent AI handover generation"
---

# Tasks: Provider-Independent AI Handover Generation

**Input**: Design documents from `/specs/017-ai-handover-generation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included — the feature specification explicitly requires regression coverage for every
open ticket, evidence minimization, DeepSeek generation, exact citations, stale/partial
qualification, malformed output, invalid citations, provider failures, no fallback, credential
non-disclosure, zero legacy-tool dependency, confirmation, preview, regeneration, persistence,
readiness, and delivery compatibility.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- Web application: `backend/`, `frontend/`, `tests/`, `docs/`
- Feature design artifacts: `specs/017-ai-handover-generation/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare deterministic handover evidence and provider fixtures.

- [X] T001 Create `tests/support/handover_ai.py` with builders for shift notes, local/remote tickets, stale/partial ticket caches, investigations, Datadog snapshot context, status/dashboard/readiness, fake AI providers, and evidence digests.
- [X] T002 Add Feature 017 fixture wiring in `tests/conftest.py` for temporary handover workspaces, evidence loaders, fake providers, and reset isolation.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared evidence, AI, deterministic assembly, provenance, preview, and API foundations.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Foundational Tests

- [X] T003 [P] Add failing tests in `tests/test_handover_evidence.py` for stable handover IDs (`shift-note:<date>:<hash>`, `ticket:<key>`, `investigation:<name>`, `incident:<uuid>`, `status:<date>`, `dashboard:<date>`, `readiness:<date>`), evidence availability, reviewed/unreviewed flags, package `≤1 MiB`, `≤500` tickets, `≤2,000` shift-note entries, `≤200` investigations, `≤100` incident context items, and canonical digest.
- [X] T004 [P] Add failing tests in `tests/test_handover_ai.py` for the four-key advisory schema (`advisorySummary`, `operationalRisks`, `recommendedFocus`, `watchItems`), 1–8 items per array, `≤2 KiB` per item, `≤64 KiB` total, and exact available-ID citation requirements.
- [X] T005 [P] Add failing tests in `tests/test_handover_preview.py` for deterministic preview, zero AI invocation, zero file/archive/delivery changes, evidence digest, and section compatibility.
- [X] T006 [P] Add failing provider-profile tests in `tests/test_ai_provider.py` and `tests/test_deepseek_provider.py` for the handover prompt profile, DeepSeek Flash support, bounded responses, and no fallback.

### Foundational Implementation

- [X] T007 [P] Create `backend/services/handover_evidence.py` to build the bounded handover evidence package from validated services and available read-only Datadog context, enforce package bounds, stable IDs, canonical digest, review flags, and secret exclusion.
- [X] T008 [P] Create `backend/services/handover_ai.py` with the provider-neutral handover prompt, advisory envelope, exact allowed/unavailable ID contract, forbidden citation forms, and fail-closed advisory validator.
- [X] T009 Create the deterministic assembly foundation in `backend/services/handover.py`: existing intro/closing shape, mandatory section renderer, availability/readiness disclosure, and preservation of existing section parsing.
- [X] T010 [P] Create `backend/services/handover_provenance.py` for `formatVersion: "2"`, evidence digest, provider/model, references, availability, advisory status, and sanitized sidecar serialization.
- [X] T011 [P] Add generation-preview request/response models and a read-only preview endpoint skeleton in `backend/api/handover.py`.
- [X] T012 Add preview digest/evidence-summary helpers and sanitized handover error mapping in `backend/api/handover.py` and `backend/services/handover.py`.

**Checkpoint**: Evidence, AI, deterministic assembly, provenance, preview, and API foundations are ready.

---

## Phase 3: User Story 1 - Generate a complete handover from validated shift evidence (Priority: P1) 🎯 MVP

**Goal**: Generate the mandatory handover deterministically with every validated open ticket, without noc-handover or Copilot.

**Independent Test**: With local-only, remote-only, stale, partial, duplicate, and zero-ticket fixtures, generate a handover without noc-handover/Copilot; verify every merged ticket appears in the mandatory section and the handover persists in the existing format.

### Tests for User Story 1

- [X] T013 [US1] Add ticket-completeness tests in `tests/test_handover_evidence.py` and `tests/test_handover.py` for local/remote union, local-only, remote-only, duplicates, stale/partial entries, zero tickets, unestablishable ticket set, and over-bound ticket sets.
- [X] T014 [US1] Add deterministic mandatory-section tests in `tests/test_handover.py` for Summary, Open Salesforce Tickets semantics, Open Jira Tickets, Investigation Updates, Next Shift Actions, availability/readiness disclosure, and no AI-authored mandatory content.
- [X] T015 [US1] Add regression tests in `tests/test_handover.py` proving generation works with noc-handover and Copilot absent, uses selected-shift paths, preserves collision behavior, and makes zero Datadog mutation requests.
- [X] T016 [US1] Add end-to-end all-ticket generation tests in `tests/test_handover.py` for persisted Markdown, sidecar absence/presence, and existing response shape.

### Implementation for User Story 1

- [X] T017 [US1] Implement the complete open-ticket union/completeness logic in `backend/services/handover_evidence.py`: deduplicate by ticket key, include local-only and remote-only tickets, retain stale/partial entries with qualification, fail closed when no validated source establishes the set, and fail closed over bound.
- [X] T018 [US1] Implement deterministic mandatory handover assembly in `backend/services/handover.py`, including every merged ticket, reviewed findings, deterministic next actions, Salesforce section semantics, availability/readiness disclosure, and existing closing shape.
- [X] T019 [US1] Implement atomic Markdown/sidecar persistence and existing conflict behavior in `backend/services/handover.py`, preserving selected-shift paths and existing response fields.
- [X] T020 [US1] Implement generation request handling and sanitized errors in `backend/api/handover.py` for ticket/evidence/readiness failures and existing-handover conflicts.
- [X] T021 [US1] Update `frontend/js/api.js` with handover generation-preview and generation client functions while preserving delivery preview/send functions.
- [X] T022 [US1] Update `frontend/end-shift.html` generation wording and empty-state controls to describe validated evidence and the configured AI provider, not noc-handover or Copilot.
- [X] T023 [US1] Add success-path persistence and format regression assertions in `tests/test_handover.py` for all tickets, deterministic sections, and selected-shift behavior.

**Checkpoint**: User Story 1 works independently with every open ticket and no legacy generation tools.

---

## Phase 4: User Story 2 - Keep advisory AI synthesis evidence-grounded and fail closed (Priority: P1)

**Goal**: Validate internal advisory AI synthesis with exact citations, stale/partial honesty, and fail-closed provider behavior without emitting AI-specific sections into the final handover.

**Independent Test**: Use valid and invalid provider outputs with exact IDs, aliases, URLs, unavailable IDs, malformed sections, stale/partial contradictions, timeouts, unavailability, and credential sentinels; verify only valid advisory content is persisted and every invalid case fails closed.

### Tests for User Story 2

- [X] T024 [US2] Add valid DeepSeek advisory-generation tests in `tests/test_handover_ai.py` and `tests/test_handover.py` covering exact ticket, investigation, incident, shift-note, status, dashboard, and readiness citations.
- [X] T025 [US2] Add exact-ID envelope/citation tests in `tests/test_handover_ai.py` for colon-separated ticket keys, investigation names, UUID incidents, date IDs, and byte-for-byte copying.
- [X] T026 [US2] Add unsupported/invented/unavailable/shortened/aliased/URL/non-canonical citation tests in `tests/test_handover_ai.py` and ensure no repair/remapping occurs.
- [X] T027 [US2] Add missing-section, malformed, placeholder-only, and over-bound advisory output tests in `tests/test_handover_ai.py`.
- [X] T028 [US2] Add provider timeout, unavailability, invalid-response, incomplete-configuration, and no-fallback tests in `tests/test_handover.py` and `tests/test_ai_provider.py`.
- [X] T029 [US2] Add stale/partial contradiction and credential-sentinel tests in `tests/test_handover_ai.py` and `tests/test_datadog_secrets.py` across responses, logs, Markdown, sidecars, exceptions, and frontend output.

### Implementation for User Story 2

- [X] T030 [P] [US2] Implement the advisory schema, exact citation validation, available-reference enforcement, stale/partial contradiction rejection, output bounds, and credential checks in `backend/services/handover_ai.py`.
- [X] T031 [US2] Implement always-invoke configured-provider behavior and fail-closed/no-fallback handling in `backend/services/handover.py`, preserving existing handovers on failure.
- [X] T032 [US2] Implement internal advisory validation and system-authored availability disclosure in `backend/services/handover.py`; keep AI text and `[evidence:...]` markers out of the final handover and never let AI alter mandatory sections.
- [X] T033 [P] [US2] Implement sanitized provider/advisory error mapping in `backend/api/handover.py` for citation, malformed output, timeout, unavailability, and configuration failures.
- [X] T034 [P] [US2] Harden evidence secret exclusion/redaction in `backend/services/handover_evidence.py` and ensure no credentials, Authorization headers, or unrelated environment values enter the prompt or sidecar.
- [X] T035 [US2] Add regression assertions in `tests/test_handover.py` that failed advisory generation creates no Markdown or sidecar and preserves an existing handover.

**Checkpoint**: User Story 2 fails closed for invalid citations, stale/partial contradictions, provider failures, malformed output, and credentials.

---

## Phase 5: User Story 3 - Preview, confirm, regenerate, and deliver without changing existing contracts (Priority: P1)

**Goal**: Provide deterministic read-only preview, explicit confirmation, safe regeneration, and unchanged delivery compatibility.

**Independent Test**: Preview without AI or state changes, verify digest/stale handling, confirm generation/regeneration, and exercise delivery preview/send; verify archive/restore, recipient validation, and Microsoft 365 compatibility remain unchanged.

### Tests for User Story 3

- [X] T036 [P] [US3] Add deterministic preview/no-AI/no-file/no-archive/no-delivery tests in `tests/test_handover_preview.py`.
- [X] T037 [US3] Add preview digest mismatch, selected-shift change, and evidence-change invalidation tests in `tests/test_handover_preview.py` and `tests/test_handover.py`.
- [X] T038 [US3] Add explicit confirmation, generate/regenerate, archive verification, and restore-on-failure tests in `tests/test_handover.py`.
- [X] T039 [P] [US3] Add delivery preview/send/recipient/confirmation/M365 compatibility tests in `tests/test_handover_delivery.py` and `tests/test_end_shift.py`.
- [X] T040 [US3] Add frontend preview/confirmation/regeneration and preview-invalidation tests in `tests/test_frontend_modules.py` and `tests/test_end_shift.py`.

### Implementation for User Story 3

- [X] T041 [US3] Implement the generation-preview endpoint and deterministic preview response in `backend/api/handover.py` and `backend/services/handover.py`, including evidence digest and no AI/state changes.
- [X] T042 [US3] Implement optional `previewDigest` support and `preview-stale` failure behavior in `backend/api/handover.py` and `backend/services/handover.py`.
- [X] T043 [US3] Implement regeneration archive/restore for Markdown and the provenance sidecar in `backend/services/handover.py`, preserving existing archive naming/verification behavior.
- [X] T044 [US3] Update `frontend/end-shift.html` preview, generate, regenerate, confirmation, and invalidation behavior; keep delivery preview/send separate and unchanged.
- [X] T045 [US3] Update `frontend/js/api.js` generation-preview/digest/generate/regenerate handling and preserve existing delivery client functions.
- [X] T046 [US3] Add delivery compatibility regression assertions in `tests/test_handover_delivery.py` proving the sidecar is not delivered and AI is never invoked by delivery.

**Checkpoint**: User Story 3 previews are deterministic, confirmations are explicit, regeneration is safe, and delivery remains compatible.

---

## Phase 6: User Story 4 - Preserve review boundaries and operational compatibility (Priority: P2)

**Goal**: Keep reviewed findings authoritative, make legacy tooling optional, and preserve End Shift/status/delivery compatibility.

**Independent Test**: Generate handovers with reviewed and unreviewed investigation evidence; verify reviewed content is authoritative, unreviewed/AI content is advisory only, and End Shift/health/readiness/status work with noc-handover and Copilot absent.

### Tests for User Story 4

- [X] T047 [P] [US4] Add reviewed/unreviewed boundary tests in `tests/test_handover_evidence.py` and `tests/test_handover.py`, including attempts to promote advisory content into mandatory reviewed sections.
- [X] T048 [US4] Add legacy handover record and optional-sidecar compatibility tests in `tests/test_handover.py`, covering read/preview/delivery of existing Markdown without provenance.
- [X] T049 [P] [US4] Add readiness/health/status/End Shift tests in `tests/test_readiness.py`, `tests/test_readiness_api.py`, `tests/test_dependency_readiness.py`, `tests/test_status.py`, and `tests/test_end_shift.py` proving noc-handover and Copilot are optional.
- [X] T050 [US4] Add UI wording and documentation regression tests in `tests/test_frontend_modules.py` and `tests/test_end_shift.py` for the new evidence/AI architecture.

### Implementation for User Story 4

- [X] T051 [US4] Enforce reviewed/unreviewed provenance boundaries in `backend/services/handover_evidence.py`, `backend/services/handover_ai.py`, and `backend/services/handover.py`; unreviewed content is advisory only.
- [X] T052 [US4] Update `backend/services/readiness.py`, `backend/services/health.py`, `backend/services/status.py`, `backend/services/dependency_readiness.py`, and `backend/services/end_shift.py` so noc-handover/Copilot are optional compatibility checks and handover readiness depends on validated evidence plus the configured provider.
- [X] T053 [US4] Update `frontend/end-shift.html`, `README.md`, and `docs/workstation-runtime.md` to describe validated evidence, the configured AI provider, optional legacy tooling, dedicated advisory content, and unchanged M365 delivery.
- [X] T054 [US4] Preserve legacy handover Markdown/archive/delivery compatibility in `backend/services/handover.py`; sidecar absence is tolerated and no existing response field is removed.
- [X] T055 [US4] Update End Shift preflight/readiness regression assertions in `tests/test_end_shift.py` for handover generation availability and optional legacy tools.

**Checkpoint**: User Story 4 preserves review boundaries, legacy records, readiness, UI wording, and delivery compatibility.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Remove dead legacy generation code, validate contracts, and run complete verification.

- [X] T056 [P] Remove dead noc-handover/Copilot/subprocess generation code from `backend/services/handover.py` while preserving legacy handover reading and delivery.
- [X] T057 [P] Tighten `tests/test_handover_evidence.py` and `tests/test_handover_ai.py` for ticket-source degradation, digest determinism, advisory bounds, and stale/partial edge cases.
- [X] T058 [P] Reconcile `specs/017-ai-handover-generation/contracts/`, `data-model.md`, and `quickstart.md` with implementation-discovered contract details.
- [X] T059 Run focused handover/readiness/frontend tests: `.venv/bin/python -m pytest tests/test_handover_evidence.py tests/test_handover_ai.py tests/test_handover_preview.py tests/test_handover.py tests/test_handover_delivery.py tests/test_ai_provider.py tests/test_deepseek_provider.py tests/test_end_shift.py tests/test_readiness.py tests/test_readiness_api.py tests/test_dependency_readiness.py tests/test_status.py tests/test_tickets.py tests/test_shift_notes.py tests/test_investigations.py tests/test_datadog_readonly.py tests/test_datadog_secrets.py tests/test_frontend_modules.py -q`.
- [X] T060 Run the full suite from `/home/bsmith/code/noc-web`: `.venv/bin/python -m pytest -q`.
- [X] T061 Execute `specs/017-ai-handover-generation/quickstart.md` validation scenarios and record expected outcomes.
- [X] T062 [P] Run a credential-sentinel and zero-Datadog-mutation audit across `backend/services/handover.py`, `backend/services/handover_evidence.py`, `backend/services/handover_ai.py`, `frontend/end-shift.html`, API responses, logs, Markdown, sidecars, archives, and exceptions.
- [X] T063 [P] Verify Feature 015 Datadog behavior, Feature 016 investigation behavior, and Microsoft 365 delivery behavior remain unchanged; add/confirm focused evidence in `tests/test_datadog_evidence.py`, `tests/test_investigation_generation.py`, and `tests/test_handover_delivery.py`.

**Checkpoint**: All tasks complete, focused and full suites pass, contracts and docs are consistent.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **US1 (Phase 3)**: Depends on Foundational; provides deterministic mandatory handover and ticket completeness.
- **US2 (Phase 4)**: Depends on Foundational and US1 generation path; adds advisory AI validation.
- **US3 (Phase 5)**: Depends on Foundational and US1/US2; shares End Shift/API files with US1/US2, so sequence UI edits.
- **US4 (Phase 6)**: Depends on US1/US2 for generated record fixtures; readiness/docs can follow.
- **Polish (Phase 7)**: Depends on all desired user stories.

### User Story Dependencies

- **US1 (P1)**: Independent after Foundational; MVP complete handover.
- **US2 (P1)**: Independently testable with fake provider outputs; integrate after US1 generation exists.
- **US3 (P1)**: Independently testable preview/confirmation/regeneration/delivery; sequence UI work after US1/US2.
- **US4 (P2)**: Independently testable review boundaries/readiness/docs; sequence after US1/US2 fixtures.

### Within Each User Story

- Tests MUST be written and fail before implementation.
- Evidence/package foundations before orchestration.
- Service orchestration before API endpoints.
- API before frontend integration.
- Core implementation before compatibility regressions.

### Parallel Opportunities

- T003, T004, T005, T006 can run in parallel.
- T007, T008, T010, T011 can run in parallel once interfaces are known.
- T013, T014, T015 can run in parallel; T016 follows generation integration.
- T024, T025, T026, T027, T028, T029 can run in parallel where different files.
- T036, T037, T038, T039, T040 can run in parallel where different files; T040/T049 share frontend/End Shift files with other phases, sequence accordingly.
- T047, T048, T049, T050 can run in parallel where different files.
- T056, T057, T058, T062, T063 can run in parallel after their dependencies; T059/T060 are ordered commands.

## Parallel Example: Foundational

```bash
# Foundational test and module files are independent:
Task: "Evidence package tests in tests/test_handover_evidence.py"
Task: "Advisory tests in tests/test_handover_ai.py"
Task: "Preview tests in tests/test_handover_preview.py"
Task: "Provider profile tests in tests/test_ai_provider.py and tests/test_deepseek_provider.py"
```

---

## Parallel Example: User Story 1

```bash
# US1 evidence, generation, API, and test edits share dependent contracts/files and are sequenced.
# No safe cross-file parallel slice exists within this story.
Task: "Complete US1 tasks sequentially: evidence union -> deterministic assembly -> persistence/API -> tests"
```

## Parallel Example: User Story 2

```bash
# These implementation modules touch different files and can proceed in parallel:
Task: "Advisory validator in backend/services/handover_ai.py"
Task: "API error mapping in backend/api/handover.py"
Task: "Evidence secret hardening in backend/services/handover_evidence.py"
# Generation invocation and advisory rendering share backend/services/handover.py; sequence them.
```

## Parallel Example: User Story 3

```bash
# These test files are independent and can run together:
Task: "Preview no-AI/no-state tests in tests/test_handover_preview.py"
Task: "Delivery compatibility tests in tests/test_handover_delivery.py and tests/test_end_shift.py"
# Regeneration tests and frontend confirmation edits share files with other US3 work; sequence them.
```

## Parallel Example: User Story 4

```bash
# These test groups touch different files and can run together:
Task: "Reviewed/unreviewed tests in tests/test_handover_evidence.py and tests/test_handover.py"
Task: "Optional legacy-tool readiness tests in tests/test_readiness.py, tests/test_readiness_api.py, tests/test_dependency_readiness.py, tests/test_status.py, and tests/test_end_shift.py"
# Legacy handover compatibility tests and UI wording edits share files with other US4 work; sequence them.
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: US1.
4. **STOP and VALIDATE**: Run T013–T016 and confirm every open ticket appears in a persisted handover with noc-handover/Copilot absent.
5. Deploy/demo if ready.

### Incremental Delivery

1. Setup + Foundational → evidence/AI/assembly/preview foundations.
2. US1 → complete deterministic handover and ticket completeness.
3. US2 → exact-cited advisory synthesis and fail-closed provider behavior.
4. US3 → preview/confirmation/regeneration/delivery compatibility.
5. US4 → review boundaries, readiness/docs, optional legacy tooling.
6. Polish → remove dead legacy generation and run full validation.

### Parallel Team Strategy

1. Team completes Setup + Foundational together.
2. After Foundational:
   - Developer A: US1 evidence/completeness and deterministic assembly.
   - Developer B: US2 AI advisory prompt/validator (after US1 package/assembly interfaces stabilize).
   - Developer C: US3 preview/regeneration/delivery (sequence shared End Shift/API edits after US1/US2).
   - Developer D: US4 review boundaries/readiness/docs (after US1/US2 fixtures).
3. Rejoin for Polish and full-suite validation.

---

## Notes

- [P] tasks touch different files and have no incomplete dependencies.
- [Story] labels map tasks to US1–US4 for traceability.
- Every user story has an independent test criterion.
- All open tickets must remain mandatory; never truncate, omit, or AI-summarize the ticket list.
- AI advisory analysis is validated internally; mandatory sections remain deterministic and AI text/citations are not emitted into the final handover.
- No provider fallback, no deterministic-only final path, no citation repair, no credential exposure.
- Preserve Feature 015 read-only behavior, Feature 016 investigation behavior, local persistence, archives,
  End Shift readiness, recipient handling, and Microsoft 365 delivery.

## Phase 8: Convergence

- [X] T064 Update the system-authored signature line in `backend/services/handover.py` to `[sesami.io](https://www.sesami.io/) | [LinkedIn](https://www.linkedin.com/company/sesami-cash-management-technologies-corporation)`, update the exact-signature regressions in `tests/test_handover.py`, and align `specs/017-ai-handover-generation/contracts/handover-record-format.md` and `specs/017-ai-handover-generation/contracts/handover-generation-api.md` with the signed-off linked-label signature with the linked line as the absolute final nonblank line per contract: handover-record-format signature block (partial)
