# Tasks: Trusted Release Pipeline

**Input**: Design documents from `specs/013-trusted-release-pipeline/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/release-contract.md`, and `quickstart.md`

**Tests**: The specification explicitly requires workflow and archive
regression coverage, full application validation, and first-release
verification.

**Organization**: Tasks are grouped by independently verifiable release
journey. No release publication may start before the foundational policy and
archive validation work is complete.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish release scripts and their test fixture boundaries.

- [X] T001 Create release workflow and helper-script directories in `.github/workflows/` and `scripts/release/`.
- [X] T002 [P] Create isolated release-policy and archive fixture tests in `tests/test_release_pipeline.py`.
- [X] T003 [P] Add generated release archive, checksum, and verification-workspace exclusions to `.gitignore`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define a fail-closed archive policy that every release workflow
uses before any artifact can be published.

**⚠️ CRITICAL**: All user stories depend on this phase.

- [ ] T004 Add regression cases for `vX.Y.Z` tag validation, exact
  `noc-web-vX.Y.Z.tar.gz` and `noc-web-vX.Y.Z.sha256` naming, unsafe archive
  entries, required runtime/bootstrap content, and excluded local content in
  `tests/test_release_pipeline.py`.
- [ ] T005 Implement valid-tag, exact-tag-target, and stable-artifact-name validation in `scripts/release/verify-release.sh`.
- [ ] T006 Implement an allowlisted archive builder in `scripts/release/build-archive.sh` that excludes `.git`, `.venv`, caches, local runtime configuration, credentials, tokens, logs, operator data, and temporary files.
- [ ] T007 Implement archive entry and required Feature 011/Feature 012 handoff-content validation in `scripts/release/verify-release.sh`, rejecting traversal paths and missing files before checksum or publication.
- [ ] T008 Implement checksum creation and verification in `scripts/release/verify-release.sh`, requiring the checksum record to name the exact archive and contain its 64-character SHA-256 digest.

**Checkpoint**: A candidate archive can be built and verified locally from a
valid tag, with unsafe or incomplete content rejected before publication.

---

## Phase 3: User Story 1 - Publish a Verified Versioned Release (Priority: P1) 🎯 MVP

**Goal**: A release manager can publish one validated archive and checksum
pair only from an explicit valid version tag.

**Independent Test**: Exercise the release workflow against valid and invalid
tag fixtures; valid tags produce exactly the documented assets after complete
tests pass, while failed validation produces no release.

### Tests for User Story 1

- [ ] T009 [P] [US1] Add workflow-policy tests for tag-only triggering,
  invalid-tag rejection, exact tag/commit association, least-privilege
  permissions, and validation-before-publication ordering in
  `tests/test_release_pipeline.py`.
- [ ] T010 [US1] Add release publication failure-path fixtures ensuring
  test, archive, checksum, and upload failures cannot report success in
  `tests/test_release_pipeline.py`.
- [ ] T011 [US1] Add clean-runner regression coverage in
  `tests/test_release_pipeline.py` proving `.github/workflows/release.yml`
  installs pytest from the approved pinned test-dependency source before
  invoking `python -m pytest -q`.

### Implementation for User Story 1

- [ ] T012 [US1] Create the tag-triggered release workflow in `.github/workflows/release.yml`, accepting only `v*` tags and rejecting non-`vX.Y.Z` references before release assembly.
- [ ] T013 [US1] Install the existing pinned application/runtime dependencies and pytest from an approved pinned test-dependency source in `.github/workflows/release.yml`, without assuming a developer `.venv`.
- [ ] T014 [US1] Run the complete repository pytest suite and `git diff --check` from `.github/workflows/release.yml` before any release asset or release record is created.
- [ ] T015 [US1] Invoke `scripts/release/build-archive.sh` and `scripts/release/verify-release.sh` from `.github/workflows/release.yml` to produce the exact archive/checksum pair only after validation passes.
- [ ] T016 [US1] Configure the final publication step in `.github/workflows/release.yml` to create one GitHub Release from the exact version tag and upload only the validated archive and checksum assets.

**Checkpoint**: A valid tag has a deterministic release pair; invalid or failed
candidates publish nothing.

---

## Phase 4: User Story 2 - Verify Release Provenance (Priority: P1)

**Goal**: Feature 012 can verify that the downloaded archive came from the
approved release workflow and exact tagged source without a private key.

**Independent Test**: Verify a valid release fixture against the documented
identity and reject altered archive, checksum, provenance, repository, tag, or
workflow identity fixtures before extraction.

### Tests for User Story 2

- [ ] T017 [P] [US2] Add release contract tests for checksum-to-archive binding
  and provenance identity pinning in `tests/test_release_pipeline.py`.
- [ ] T018 [US2] Add altered archive, checksum, provenance, repository,
  workflow-identity, and tag-target rejection fixtures in
  `tests/test_release_pipeline.py`.

### Implementation for User Story 2

- [ ] T019 [US2] Configure keyless artifact attestation for the final archive
  in `.github/workflows/release.yml` with only the permissions required for
  release publication and provenance.
- [ ] T020 [US2] Add the Feature 012 consumer verification identity, archive,
  checksum, repository, and tag requirements to
  `specs/013-trusted-release-pipeline/contracts/release-contract.md`.
- [ ] T021 [US2] Implement provenance verification guidance that pins the
  approved release workflow identity and exact tagged source in
  `scripts/release/verify-first-release.sh`.

**Checkpoint**: An archive’s checksum and provenance must both verify before a
consumer trusts it.

---

## Phase 5: User Story 3 - Receive a Safe Bootstrap Archive (Priority: P1)

**Goal**: The release archive contains only portable NOC Web source needed by
Feature 011 and Feature 012, never local or credential-bearing state.

**Independent Test**: Seed each excluded content class in a fixture checkout,
build an archive, and verify every excluded path is absent while all required
bootstrap/runtime files are present.

### Tests for User Story 3

- [ ] T022 [P] [US3] Add archive exclusion fixture cases for repository
  metadata, virtual environments, caches, runtime configuration, credentials,
  tokens, logs, operator data, and temporary files in
  `tests/test_release_pipeline.py`.
- [ ] T023 [US3] Add required Feature 011 installer and Feature 012
  bootstrap-consumer content fixture cases in `tests/test_release_pipeline.py`.

### Implementation for User Story 3

- [ ] T024 [US3] Harden the allowlist and exclusion validation in
  `scripts/release/build-archive.sh` so release assembly never reads files
  outside the tagged checkout or includes secret-like/operator-owned content.
- [ ] T025 [US3] Extend `scripts/release/verify-release.sh` to fail closed on
  empty, malformed, unsafe, or incomplete archives and prevent downstream
  checksum, attestation, and publication steps.

**Checkpoint**: Release artifacts are portable and contain no local workstation
state or secret material.

---

## Phase 6: User Story 4 - Validate the First Production Release (Priority: P2)

**Goal**: A release manager can independently approve the first real release
before Feature 012 consumes the new contract.

**Independent Test**: Run the first-release verifier against a valid release
fixture and against each contract mismatch; only the valid fixture produces an
approved record.

### Tests for User Story 4

- [ ] T026 [P] [US4] Add first-release verifier approval and actionable
  failure fixtures for archive name, checksum, provenance, tag target,
  safe-content, and consumer-verification checks in
  `tests/test_release_pipeline.py`.

### Implementation for User Story 4

- [ ] T027 [US4] Implement the independent first-release verification and
  approval-record flow in `scripts/release/verify-first-release.sh`.
- [ ] T028 [US4] Add first-real-release approval instructions and the
  Feature 012 unblock gate to
  `specs/013-trusted-release-pipeline/quickstart.md`.

**Checkpoint**: Feature 012 remains blocked until the first real release
passes every independent contract check.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Complete documentation and end-to-end validation.

- [ ] T029 Add clean-checkout regression coverage in `tests/test_release_pipeline.py` that rejects missing `scripts/release/build-archive.sh`, `scripts/release/verify-release.sh`, or `scripts/release/verify-first-release.sh` before release validation.
- [ ] T030 Ensure `.github/workflows/release.yml`, `tests/test_release_pipeline.py`, and `scripts/release/build-archive.sh`, `scripts/release/verify-release.sh`, and `scripts/release/verify-first-release.sh` are tracked release implementation files and assert their tracked presence in `tests/test_release_pipeline.py`.
- [ ] T031 Add isolated virtual-environment fixtures for Feature 011 runtime installer error-order tests in `tests/test_runtime_installer.py`, preserving the configured virtual-environment interpreter contract without relying on repository `.venv`.
- [ ] T032 Update `.github/workflows/release.yml` to create the required project virtual environment deterministically with Python 3.10 and install the pinned `requirements.txt` runtime dependencies, including uvicorn, into that `.venv` before running clean-runner Feature 011 runtime tests; retain separate pinned release/test dependency installation and never commit or package `.venv`.
- [ ] T033 Add clean-runner regression coverage in `tests/test_runtime_installer.py` and `tests/test_runtime_service.py` proving shortcut-failure tests reach their intended shortcut failure and the configured `.venv/bin/python` can run the managed service with no `VIRTUAL_ENV` or `PYTHONPATH`, without falling back to the GitHub runner's global Python.
- [ ] T034 [P] Document release-manager tag creation, failure handling,
  artifact retrieval, and no-secret policy in `docs/release-pipeline.md`.
- [ ] T035 Run the focused release pipeline and runtime installer tests in
  `tests/test_release_pipeline.py` and `tests/test_runtime_installer.py`, then
  run the full repository pytest suite.
- [ ] T036 Run `git diff --check` and inspect the release workflow permissions,
  Python 3.10 virtual-environment setup, tracked release scripts, archive
  exclusions, and consumer contract in `.github/workflows/release.yml`.
- [ ] T037 Perform and record the first successful real release verification using
  `scripts/release/verify-first-release.sh` for a new immutable version after
  this fix, leaving failed `v1.0.0`, `v1.0.1`, and `v1.0.2` unchanged and
  unpublished, before enabling Feature 012 acquisition in
  `packaging/windows/bootstrap-manifest.json`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on setup and blocks every user story.
- **US1 (Phase 3)**: Depends on the foundational archive policy.
- **US2 (Phase 4)**: Depends on a final archive produced by US1.
- **US3 (Phase 5)**: Depends on the foundational archive policy and validates
  the archive assembled by US1.
- **US4 (Phase 6)**: Depends on US1–US3.
- **Polish (Phase 7)**: Depends on all user stories.

### User Story Dependencies

- **US1 (P1)**: MVP; publishes the validated stable release pair.
- **US2 (P1)**: Adds the provenance contract for the US1 archive.
- **US3 (P1)**: Verifies the safe contents of the US1 archive.
- **US4 (P2)**: Requires the complete release contract from US1–US3.

### Parallel Opportunities

- T002–T003 can run after T001.
- T009 and T017 are independent regression-policy work after their prior test
  tasks complete; T026 can proceed independently once a release fixture exists.
- US2 contract work and US3 archive-content work can proceed concurrently
  after a US1 archive fixture is available.

---

## Parallel Example: User Story 1

```text
Task: "Add tag and permission policy tests in tests/test_release_pipeline.py"
Task: "Add publication failure-path fixtures in tests/test_release_pipeline.py"
```

## Parallel Example: User Story 3

```text
Task: "Add excluded-content archive fixtures in tests/test_release_pipeline.py"
Task: "Add required-content archive fixtures in tests/test_release_pipeline.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete setup and foundational archive validation.
2. Implement the tag-gated workflow and fail-closed archive/checksum
   publication path.
3. Validate a disposable valid tag and invalid-tag fixture before proceeding.

### Incremental Delivery

1. Deliver US1 for stable, validated release assets.
2. Add US2 provenance identity verification.
3. Add US3 safe archive content enforcement.
4. Add US4 first-real-release approval before Feature 012 use.

## Notes

- `[P]` tasks are independent paths or test scopes; coordinate changes to the
  shared test file.
- The release workflow never contains a long-lived private signing key.
- No release task authorizes credentials, tokens, or operator data in artifacts.
