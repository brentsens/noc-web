# Tasks: Fresh Workstation Bootstrap Installer

**Input**: Design documents from `specs/012-fresh-workstation-bootstrap/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/bootstrap-installer.md`, `contracts/release-manifest.md`, and
`quickstart.md`

**Tests**: The specification explicitly requires automated regression coverage
and clean Windows/WSL acceptance coverage. Add focused tests before each
implemented workflow.

**Organization**: Tasks are grouped by user story so each journey can be
implemented and validated independently after the foundational release-policy
work is complete.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the bootstrap package layout and approved branding
conversion inputs without changing Feature 011-owned runtime files.

- [ ] T001 Create the bootstrap package and WSL script directories in `packaging/windows/`, `scripts/windows/`, and `scripts/bootstrap/`.
- [ ] T002 [P] Create the schema-versioned package policy in `packaging/windows/bootstrap-manifest.json` with the exact approved repository, Ubuntu distribution, release asset names, verification-key identifier, and branding asset.
- [ ] T003 [P] Add a reproducible multi-resolution icon generation script in `packaging/windows/generate-icon.ps1` that reads only `assets/windows/sesami-noc-operations.png` and writes `packaging/windows/sesami-noc-operations.ico`.
- [ ] T004 [P] Add package and bootstrap ignore rules in `.gitignore` for generated setup executables, downloaded release archives, verifier work directories, and local bootstrap records.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement the non-secret validation, state, and safe result
contracts required before any Windows bootstrap journey runs.

**⚠️ CRITICAL**: No user-story implementation can start until this phase
validates untrusted manifests, paths, archives, and state without logging
credentials or raw subprocess output.

- [ ] T005 Add focused bootstrap record, safe-path, archive-entry, checksum, and signature-verifier tests in `tests/test_bootstrap_release.py`.
- [ ] T006 Implement schema-version validation and typed bootstrap-manifest loading in `scripts/bootstrap/release_manifest.py`, rejecting unknown versions, unapproved repositories, missing hashes, unsafe paths, and incompatible tool entries.
- [ ] T007 Implement credential-free bootstrap installation and source-verification record serialization in `scripts/bootstrap/acquire_release.py`, enforcing the data-model constraints: `installRoot` is “one validated per-user WSL application location; never an unsafe root, traversal path, or untrusted symlink,” and failed transitions preserve the prior verified installation.
- [ ] T008 Implement safe bootstrap result categories and non-secret diagnostic formatting in `scripts/windows/bootstrap-install.ps1` for the categories in `contracts/bootstrap-installer.md`.
- [ ] T009 Add controlled subprocess helpers and bounded deadlines in `scripts/windows/bootstrap-install.ps1` and `scripts/bootstrap/acquire_release.py` that never inherit the full Windows or interactive WSL PATH and never return raw command output.
- [ ] T010 Add release-policy and safe-record validation coverage in `tests/test_bootstrap_release.py` for every rejection path implemented by `scripts/bootstrap/release_manifest.py` and `scripts/bootstrap/acquire_release.py`.

**Checkpoint**: A malformed policy, unsafe path, or incomplete record fails
closed with a categorized non-secret result before a user story can execute.

---

## Phase 3: User Story 1 - Bootstrap NOC Operations (Priority: P1) 🎯 MVP

**Goal**: A fresh supported Windows/WSL workstation can verify and stage NOC
Web, delegate runtime setup to Feature 011, and launch the single branded
shortcut without manual checkout or virtual-environment activation.

**Independent Test**: In an isolated supported Windows/WSL fixture with no
checkout, Feature 011 artifacts, or shortcut, the package verifies a release,
stages it at the deterministic location, completes Feature 011 handoff, and
creates exactly one shortcut; a second shortcut launch reuses the service.

### Tests for User Story 1

- [ ] T011 [P] [US1] Add archive acquisition, signed checksum verification, required Feature 011 artifact, unsafe archive-entry, and atomic-staging regression cases in `tests/test_bootstrap_release.py`.
- [ ] T012 [P] [US1] Add Feature 011 handoff, pinned virtual-environment creation, health success, and safe handoff-failure regression cases in `tests/test_bootstrap_handoff.py`.
- [ ] T013 [P] [US1] Add Windows PowerShell package tests for first shortcut launch, hidden launch behavior, exactly one shortcut, and managed-service reuse in `tests/windows/test_bootstrap_acceptance.ps1`.

### Implementation for User Story 1

- [ ] T014 [US1] Implement download-to-temporary-location, public-key signature verification, SHA-256 verification, required-artifact inspection, and safe archive extraction in `scripts/bootstrap/acquire_release.py`.
- [ ] T015 [US1] Implement atomic verified-release staging and prior-release retention until handoff succeeds in `scripts/bootstrap/acquire_release.py`.
- [ ] T016 [US1] Implement deterministic WSL release-root handoff to the staged Feature 011 installer in `scripts/windows/bootstrap-install.ps1`, consuming only its safe installer and health result rather than creating a service, launcher, runtime configuration, or shortcut.
- [ ] T017 [US1] Add a Feature 011 handoff entry point in `scripts/bootstrap/acquire_release.py` that creates the release `.venv` from pinned project dependencies and verifies its runtime before returning control to `scripts/windows/bootstrap-install.ps1`.
- [ ] T018 [US1] Create the Inno Setup package definition in `packaging/windows/SESAMI-NOC-Operations-Setup.iss` that builds `SESAMI-NOC-Operations-Setup.exe`, bundles the bootstrap scripts, policy, verification key, verifier, and generated approved icon, and launches `scripts/windows/bootstrap-install.ps1`.
- [ ] T019 [US1] Add the bundled release-verification public key with its declared identifier to `packaging/windows/release-public-key.txt` and validate identifier matching from `scripts/bootstrap/release_manifest.py`.

**Checkpoint**: The primary clean-workstation core bootstrap works through
Feature 011 without duplicating any Feature 011 runtime ownership.

---

## Phase 4: User Story 2 - Understand Prerequisites and Readiness (Priority: P1)

**Goal**: The bootstrap distinguishes platform, source, permission, and
runtime failures while preserving independent Feature 011 readiness reporting
for optional integrations.

**Independent Test**: Simulate every core preflight state and verify the
bootstrap emits its precise safe category and guide-only next step; after core
success, optional capability statuses remain independent and sensitive output
is absent.

### Tests for User Story 2

- [ ] T020 [P] [US2] Add WSL-missing, distribution-missing, unsupported runtime/systemd, permission-blocked, confirmation-declined, and source-failure cases in `tests/test_bootstrap_handoff.py`.
- [ ] T021 [P] [US2] Add Windows PowerShell guide-only prerequisite and categorized-diagnostic acceptance cases in `tests/windows/test_bootstrap_acceptance.ps1`.
- [ ] T022 [P] [US2] Extend readiness regression coverage for post-bootstrap Atlas ready, setup-required, unavailable, and output-redaction cases in `tests/test_dependency_readiness.py`.

### Implementation for User Story 2

- [ ] T023 [US2] Implement bounded WSL, approved-distribution, systemd, Python runtime, permission, and confirmation preflight assessments in `scripts/windows/bootstrap-install.ps1`, returning the distinct contract categories without initiating WSL or Ubuntu installation.
- [ ] T024 [US2] Implement guide-only prerequisite remediation messages and machine-readable safe status output in `scripts/windows/bootstrap-status.ps1`.
- [ ] T025 [US2] Integrate the existing Feature 011 readiness assessment after successful handoff in `scripts/windows/bootstrap-status.ps1`, presenting each optional capability independently and never exposing raw probe output.
- [ ] T026 [US2] Preserve the Atlas trusted Linuxbrew location `/home/linuxbrew/.linuxbrew/Homebrew/bin` and its `atlas auth status --json` readiness contract in `backend/services/dependency_readiness.py` while making bootstrap status consume the existing safe readiness result.

**Checkpoint**: A failed prerequisite is never presented as a successful
installation, and an optional integration state never blocks core application
readiness.

---

## Phase 5: User Story 3 - Install Tools Without Migrating Identity (Priority: P1)

**Goal**: The operator can optionally install only approved, compatible tools
after confirmation, with authentication remaining separate and operator-owned.

**Independent Test**: For each manifest-listed tool, verify absent, installed
but unauthenticated, ready, unavailable, declined, and bad-source cases while
inspecting records and output for credential non-migration.

### Tests for User Story 3

- [ ] T027 [P] [US3] Add manifest entry validation and provisioning result tests for Atlas, Copilot, Microsoft 365 CLI, Datadog MCP, and noc-tools in `tests/test_bootstrap_provisioning.py`.
- [ ] T028 [US3] Add noc-tools regression cases for absent, compatible installed, incompatible installed, checksum-failed, partial-install, and successful-install states in `tests/test_bootstrap_provisioning.py`, verifying `tix`, `noc-start`, `noc-status`, `noc-inv`, and `noc-handover` after a successful install.
- [ ] T029 [US3] Add confirmation, checksum/source failure, missing-entry guidance, authentication-required, credential-redaction, and noc-tools no-developer-checkout tests in `tests/test_bootstrap_provisioning.py`.
- [ ] T030 [P] [US3] Add Windows PowerShell acceptance coverage for independently reported optional dependency states, no automatic sign-in, and clean noc-tools command verification in `tests/windows/test_bootstrap_acceptance.ps1`.

### Implementation for User Story 3

- [ ] T031 [US3] Define the `nocTools` release-manifest entry in `packaging/windows/bootstrap-manifest.json` with an immutable approved artifact source, SHA-256 checksum, version, noc-web compatibility range, validated non-checkout installation target, `requiresConfirmation: true`, and its Feature 011 readiness identifier.
- [ ] T032 [US3] Implement bounded, checksum-verified, manifest-controlled optional artifact provisioning in `scripts/bootstrap/provision_dependencies.py`, accepting only the tool enum `atlas`, `copilot`, `m365`, `datadogMcp`, or `nocTools`.
- [ ] T033 [US3] Implement explicit confirmation gates, non-secret dependency provisioning records, and safe missing-manifest guidance in `scripts/bootstrap/provision_dependencies.py`, enforcing that `requiresConfirmation` “must be true for a workstation-changing install.”
- [ ] T034 [US3] Implement Atlas provisioning to the Feature 011 trusted Linuxbrew deployment model in `scripts/bootstrap/provision_dependencies.py` without importing a Linuxbrew, interactive-shell, or Windows PATH.
- [ ] T035 [US3] Implement noc-tools acquisition, checksum verification, extraction or installation, and command exposure in `scripts/bootstrap/provision_dependencies.py` when it is absent, using only the verified `nocTools` release-manifest artifact and never requiring or creating `~/code/noc-tools`.
- [ ] T036 [US3] Implement noc-tools post-install validation in `scripts/bootstrap/provision_dependencies.py` requiring usable `tix`, `noc-start`, `noc-status`, `noc-inv`, and `noc-handover`, including the existing `noc-inv` contract-version compatibility validation.
- [ ] T037 [US3] Implement noc-tools installation-state handling in `scripts/bootstrap/provision_dependencies.py` that preserves a compatible valid installation, upgrades an incompatible installation only from the approved verified release manifest after confirmation, and classifies checksum failures, partial installs, or missing required commands as provisioning failure or unavailable rather than `setup_required`.
- [ ] T038 [US3] Implement separate installed, setup-required, ready, and unavailable tool results in `scripts/windows/bootstrap-status.ps1`, ensuring `setup_required` is used for noc-tools only when no approved manifest artifact exists and failed approved provisioning or command validation is unavailable.
- [ ] T039 [US3] Enforce credential, session, token, cookie, secret, and authentication-file exclusion from package inputs, bootstrap records, logs, arguments, and provisioning output in `scripts/bootstrap/provision_dependencies.py`.

**Checkpoint**: Tool installation is auditable and optional; no tool action
implies or transfers identity.

---

## Phase 6: User Story 4 - Reinstall or Update Safely (Priority: P2)

**Goal**: Rerunning the package repairs or reuses the verified release by
default and updates application-owned content only after verified, explicit
operator approval.

**Independent Test**: Run the installer twice against the same fixture, then
offer a newer verified release and test both decline and approval while
comparing the application location, Feature 011 artifacts, NOC data, runtime
configuration, and authentication state.

### Tests for User Story 4

- [ ] T040 [P] [US4] Add same-release repair, interrupted-stage recovery, duplicate-prevention, newer-release decline, and approved-update tests in `tests/test_bootstrap_release.py`.
- [ ] T041 [P] [US4] Add Windows PowerShell rerun acceptance coverage for one repository location, service, launcher, virtual environment, runtime configuration, Desktop shortcut, and compatible noc-tools preservation in `tests/windows/test_bootstrap_acceptance.ps1`.

### Implementation for User Story 4

- [ ] T042 [US4] Implement installed-record resolution, same-release repair/reuse, and interrupted-staging recovery in `scripts/bootstrap/acquire_release.py`.
- [ ] T043 [US4] Implement newer verified release discovery, version display, explicit replacement confirmation, and prior-release preservation on decline or failed handoff in `scripts/windows/bootstrap-install.ps1`.
- [ ] T044 [US4] Enforce preservation of NOC data, valid Feature 011 runtime configuration, and operator authentication while replacing only verified application-owned content in `scripts/bootstrap/acquire_release.py`.
- [ ] T045 [US4] Reuse Feature 011 idempotent installer behavior from `scripts/install_runtime.py` through the bootstrap handoff and reject any bootstrap action that would create a duplicate service, launcher, runtime configuration, virtual environment, repository, or shortcut.

**Checkpoint**: A rerun is safe by default and an update requires a verified,
operator-approved replacement.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Complete package documentation, verification, and clean
workstation release acceptance.

- [ ] T046 [P] Document package build, release-signing inputs, public-key rotation, noc-tools artifact publication, and no-credential release requirements in `packaging/windows/README.md`.
- [ ] T047 [P] Update clean-workstation execution details and expected result categories in `specs/012-fresh-workstation-bootstrap/quickstart.md`, requiring an initially absent noc-tools installation to obtain the approved compatible release and expose `tix`, `noc-start`, `noc-status`, `noc-inv`, and `noc-handover`.
- [ ] T048 Run focused bootstrap, Feature 011 runtime, noc-tools provisioning, and readiness tests from `tests/test_bootstrap_release.py`, `tests/test_bootstrap_provisioning.py`, `tests/test_bootstrap_handoff.py`, `tests/test_dependency_readiness.py`, and `tests/test_runtime_installer.py`.
- [ ] T049 Run the complete pytest suite and `git diff --check` from the repository root after Feature 012 changes.
- [ ] T050 Execute and record the clean supported Windows/WSL acceptance flow in `tests/windows/test_bootstrap_acceptance.ps1` with no existing checkout, Feature 011 runtime, shortcut, NOC data, third-party authentication, or noc-tools; verify the approved compatible noc-tools installation and usable `tix`, `noc-start`, `noc-status`, `noc-inv`, and `noc-handover` afterward.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; establishes package paths and branding inputs.
- **Foundational (Phase 2)**: Depends on Phase 1; blocks every user story.
- **US1 (Phase 3)**: Depends on Phase 2; establishes the MVP core bootstrap.
- **US2 (Phase 4)**: Depends on Phase 2 and integrates after US1 handoff is available.
- **US3 (Phase 5)**: Depends on Phase 2 and Feature 011 readiness identifiers; it can proceed in parallel with late US1 work once its contract fixtures exist.
- **US4 (Phase 6)**: Depends on US1 staging and handoff behavior.
- **Polish (Phase 7)**: Depends on all selected user stories.

### User Story Dependencies

- **US1 (P1)**: MVP; no dependency on another user story.
- **US2 (P1)**: Uses the US1 handoff path only to validate post-bootstrap readiness; prerequisite classification is independently testable.
- **US3 (P1)**: Uses foundational manifest validation and existing Feature 011 readiness identifiers; tool installation does not depend on US2.
- **US4 (P2)**: Requires US1 verified staging and Feature 011 handoff behavior.

### Parallel Opportunities

- T002–T004 can run in parallel after T001.
- T005 can begin with T006–T009 once the directories exist; T010 follows their implementation.
- Per-story test tasks marked `[P]` can run in parallel.
- US2 preflight work and US3 provisioning work can proceed concurrently after Phase 2, provided neither changes shared `scripts/windows/bootstrap-status.ps1` without coordination.

---

## Parallel Example: User Story 1

```text
Task: "Add archive acquisition and staging regression cases in tests/test_bootstrap_release.py"
Task: "Add Feature 011 handoff regression cases in tests/test_bootstrap_handoff.py"
Task: "Add Windows package acceptance cases in tests/windows/test_bootstrap_acceptance.ps1"
```

## Parallel Example: User Story 3

```text
Task: "Add manifest entry provisioning tests in tests/test_bootstrap_provisioning.py"
Task: "Add credential-redaction provisioning tests in tests/test_bootstrap_provisioning.py"
Task: "Add Windows dependency-status acceptance coverage in tests/windows/test_bootstrap_acceptance.ps1"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phases 1 and 2.
2. Complete Phase 3, including the archive-verification, atomic-staging, and
   Feature 011-handoff tests.
3. Execute the clean Windows/WSL core bootstrap acceptance test.
4. Stop for review: a signed package must bootstrap core NOC Web without any
   optional tool or identity action.

### Incremental Delivery

1. Deliver US1 for verified core installation and Feature 011 reuse.
2. Add US2 for safe prerequisite and readiness diagnostics.
3. Add US3 for confirmed, credential-safe operational tool provisioning.
4. Add US4 for repair, update, and duplicate-prevention behavior.
5. Complete clean-workstation release acceptance only after all paths pass.

## Notes

- `[P]` tasks use separate files or independent test scopes and may run in
  parallel.
- User-story labels provide traceability to the Feature 012 specification.
- Feature 011 remains the sole owner of systemd service, `runtime.json`,
  hidden launcher, health verification, localhost binding, and Desktop
  shortcut behavior.
