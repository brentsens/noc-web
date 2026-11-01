---
description: "Implementation tasks for WSL runtime and Windows launch"
---

# Tasks: WSL Runtime and Windows Launch

**Input**: Design documents from `specs/011-wsl-runtime-launch/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/`, and `quickstart.md`

**Tests**: The specification explicitly requires regression coverage (FR-029
and FR-030); focused tests are included before each story's implementation.

**Organization**: Tasks are grouped by user story so each operator workflow
can be implemented and verified as an independent increment.

**Format**: `- [ ] Tnnn [P?] [USn?] Description with file path`

## Phase 1: Setup

**Purpose**: Make application runtime installation reproducible without
changing the test-only dependency set.

- [X] T001 Add pinned direct application dependencies for FastAPI, Pydantic, and Uvicorn in `requirements.txt`; keep test-only dependencies in `requirements-test.txt`.

---

## Phase 2: Foundational

**Purpose**: Build validated configuration, service-launch, and dependency
capability primitives required by all user stories.

- [X] T002 [P] Add runtime-configuration validation and atomic-preservation tests in `tests/test_runtime_config.py`, including malformed, unsafe, unknown-version, and valid-upgrade configurations.
- [X] T003 Implement the versioned runtime configuration reader, validator, and atomic writer in `backend/config.py`. Apply the exact `data-model.md` constraints: `schemaVersion`: “Supported positive schema version; unknown versions fail before changing runtime artifacts.”; `repositoryRoot`: “Existing expected NOC Web checkout; no root path, traversal component, or unsafe symlink target.”; `virtualEnvironment`: “Existing/creatable NOC Web virtual environment associated with this checkout.”; `wslDistribution`: “Exact current/configured distribution name; derived during setup or explicitly selected, never inferred from the mutable default at launch.”; `linuxUser`: “Current non-root WSL user; validated against the current account.”; `linuxUid`: “Current user's UID, used only to address the user runtime manager when necessary. Must not be zero.”; `port`: “`1..65535`; default `8000`.”; `applicationUrl`: “HTTP URL whose hostname is `127.0.0.1` or `localhost`, whose port matches `port`, and which contains no credentials or non-localhost target. Default `http://127.0.0.1:8000`.”; `healthTimeoutSeconds`: “Positive bounded timeout; default `60`, with a documented upper bound.”; `shortcutDirectory`: “Optional; defaults to the current user's Desktop. Resolve known folders at setup time, not through a hard-coded profile path.”; `feature005Settings`: “Allowlisted existing `NOC_WEB_*` paths/limits only; each setting is validated through the existing Feature 005 configuration rules.” Do not copy ambient environment wholesale or store secrets.
- [X] T004 Add service-context regression coverage in `tests/test_runtime_service.py` that executes the generated unit's exact `ExecStart` in a subprocess using the declared `WorkingDirectory` and environment, with inherited `VIRTUAL_ENV` and `PYTHONPATH` removed, and verifies startup passes the `backend` import boundary; retain required `systemd-analyze --user verify` coverage and fail if the tool is missing or rejects the unit.
- [X] T005 Update `systemd/noc-web.service.in`, `scripts/run_service.py`, and add `scripts/__init__.py` so the unit invokes the validated virtual-environment interpreter as `-m scripts.run_service --config <runtime-config>` from the validated repository root, without relying on shell activation or inherited `PYTHONPATH`; preserve directive-specific escaping, localhost binding, safe environment, and bounded restart behavior.
- [X] T006 [P] Add safe dependency-probe contract tests in `tests/test_dependency_readiness.py` for absent, usable, unverified-authentication, transient-failure, timeout, and sensitive-output cases.
- [X] T007 Implement shared external-capability probes and redacted readiness results in `backend/services/dependency_readiness.py`. Apply the exact `data-model.md` result constraints: `id` is a stable string; `category` is `core`, `service`, `external`, `storage`, or an existing readiness category; `capability` is the operator-facing string; `status` is `ready`, `setup_required`, or `unavailable`; `required` is boolean; `impact` and `correctiveAction` are safe strings; `checkedAt` is a UTC timestamp; `sourceId` is optional. Bound every probe, discard raw stdout/stderr, and never return credentials, authentication material, sensitive paths, or operational content.

**Checkpoint**: Runtime configuration, service runner, and capability probe
contracts are available; user-story work can proceed against these shared
interfaces.

---

## Phase 3: User Story 1 - Launch NOC Web from Windows (Priority: P1)

**Goal**: Install and execute a hidden Windows launcher that starts or reuses
the configured user service, waits for local health, and opens the default
browser only after success.

**Independent Test**: With a stubbed systemd/WSL boundary, verify the exact
shortcut name and configured distribution, running-service reuse, stopped
service startup, bounded health polling, browser ordering, clear failure
handling, localhost-only targeting, no duplicate shortcut, no credentials,
and no visible or persistent terminal. Where Windows Script Host is available,
execute the generated VBS through both `cscript.exe` and the shortcut's hidden
`wscript.exe` target, verify the known-good WSL command succeeds with quoted
arguments, and distinguish an unexpected `Run` result such as `-1` from
verified WSL/distribution failure. Repeat the artifact/hidden-window
acceptance on a supported Windows/WSL test workstation.

### Tests for User Story 1

- [X] T008 [P] [US1] Add mocked launcher tests in `tests/test_windows_launcher.py` for shortcut target/config, already-running and stopped service behavior, bounded health success/timeout, browser open ordering, WSL/service errors, localhost-only URL, credential-free arguments, and no duplicate instance.
- [X] T009 [P] [US1] Add opt-in Windows/WSL acceptance checks in `tests/windows/test_launcher_acceptance.ps1` for actual per-user `.lnk` creation, configured distro targeting, default-browser launch after health, rerun deduplication, and absence of a persistent terminal.

### Implementation for User Story 1

- [X] T010 [P] [US1] Implement idempotent per-user shortcut creation/update in `scripts/windows/install-shortcut.ps1`; enforce `name`: “Exactly `SESAMI NOC Operations`”; `shortcutPath`: “One stable per-user shortcut path; Desktop by default or configured per-user location”; `target`: “Windows Script Host (`wscript.exe`) running the installed hidden launcher”; `distribution`: exact configured WSL distribution; `linuxUser`: exact validated unprivileged operator; `applicationUrl`: validated localhost-only URL; and `healthTimeoutSeconds`: bounded deadline with default 60. Update the same `.lnk` and never embed credentials or create a suffixed duplicate.
- [X] T011 [P] [US1] Implement the hidden WSL launch sequence in `scripts/windows/launch-hidden.vbs`: target the exact configured distribution and Linux user, idempotently start `noc-web.service`, poll the validated localhost health URL with a 60-second default bound, open the default browser only after health succeeds, and show safe failure categories without raw subprocess output or a persistent terminal. Keep `lastResult` transient and limited to “Success, WSL unavailable, service unavailable, health timeout, or browser launch failure; never includes subprocess output.”
- [X] T034 [P] [US1] Extend generated-launcher regression coverage in `tests/test_windows_launcher.py` for Windows-command-line quoting of the distribution name, Linux user, Python path, launcher path, runtime-config path, localhost URL, and timeout; require the template to resolve the Windows `wsl.exe` executable and map an unexpected `WScript.Shell.Run` result, including `-1`, to `WINDOWS_LAUNCH_EXECUTION_FAILED` without raw command output.
- [X] T035 [P] [US1] Extend Windows Script Host acceptance coverage in `tests/windows/test_launcher_acceptance.ps1` to execute the installed generated VBS through `cscript.exe` and the shortcut's `wscript.exe` target when available; verify the known-good configured WSL command succeeds, argument boundaries survive quoting edge cases, no persistent console remains, and unexpected execution failure is not reported as WSL/distribution unavailable.
- [X] T036 [US1] Update `scripts/windows/launch-hidden.vbs.in` and `scripts/windows/launcher.py` so the hidden launcher resolves the Windows `wsl.exe` executable, applies the existing Windows command-line quoting routine to every configured argument, preserves hidden synchronous `WScript.Shell.Run` execution, and reports invocation errors or unrecognized results including `-1` as `WINDOWS_LAUNCH_EXECUTION_FAILED`; reserve WSL/distribution-unavailable messaging for verified launcher results.

---

## Phase 4: User Story 2 - Install and Maintain a User-Owned Runtime (Priority: P1)

**Goal**: Provide repeatable setup/update that owns only NOC Web runtime files,
starts the user service, installs the Windows shortcut, and preserves operator
configuration, data, and authentication.

**Independent Test**: Run setup twice against an isolated supported checkout,
then repeat with existing valid configuration and representative operational
records. Verify user ownership, localhost service health, exact shortcut
installation, unchanged configuration/data, and no external-tool installation
or authentication. Execute the shortcut installer under Windows PowerShell
5.1 and verify the OS-reported redirected Desktop reparse-point exception,
strict custom-destination and LocalAppData checks, and safe failure reasons.
Verify generated unit syntax with
`systemd-analyze --user verify`; fail rather than skip if the validator is
unavailable or rejects it.

### Tests for User Story 2

- [X] T012 [US2] Add installer integration tests in `tests/test_runtime_installer.py` for expected-source validation, non-root execution, pinned venv installation, idempotent reruns, preserved valid configuration, unchanged NOC records/handovers/reports/investigation state/incident cache, service/health setup, shortcut-install failure reporting, and no external dependency installation or authentication.

### Implementation for User Story 2

- [X] T013 [US2] Implement setup preflight, source/Python/path validation, safe runtime-directory creation, configuration reuse, and venv installation in `scripts/install.sh` and `scripts/install_runtime.py`; fail before replacing artifacts when source or preserved configuration is invalid.
- [X] T014 [US2] Implement user-manager provisioning in `scripts/install_runtime.py`: install/update the unit from `systemd/noc-web.service.in`, verify or enable user lingering where supported, reload/enable/start `noc-web.service`, and perform a bounded check of `GET <applicationUrl>/api/health`; fail clearly rather than installing a root-owned service.
- [X] T015 [US2] Integrate the Windows shortcut installer and shared capability report into `scripts/install_runtime.py`; pass only validated non-secret workstation fields, update the existing shortcut in place, treat shortcut creation/update failure as setup failure, and report external setup guidance without installing/authenticating Atlas, Copilot, Datadog MCP, Microsoft 365 CLI, or noc-tools.
- [X] T016 [P] [US2] Document setup prerequisites, source validation, runtime configuration preservation, upgrade behavior, external dependency ownership, and shortcut installation in `docs/workstation-runtime.md`.
- [X] T030 [P] [US2] Add Windows PowerShell 5.1 integration coverage in `tests/windows/test_launcher_acceptance.ps1` that invokes the installer through `powershell.exe -NoProfile -File` with an OS-reported redirected Desktop reparse point, rejects an arbitrary configured reparse-point destination, retains conservative LocalAppData checks, detects an empty Desktop path, and confirms helper functions are available before use.
- [X] T031 [P] [US2] Extend `tests/test_runtime_installer.py` to verify shortcut-install failure preserves the generic `SHORTCUT_INSTALL_FAILED` code and an allowlisted safe reason through the installer boundary without exposing raw exception or subprocess output.
- [X] T032 [US2] Update `scripts/windows/install-shortcut.ps1` so all helper functions are defined before invocation, only the exact path returned by `Environment.GetFolderPath("DesktopDirectory")` may be a reparse point, an empty Desktop path fails safely, and arbitrary configured destinations and LocalAppData retain strict reparse-point rejection.
- [X] T033 [US2] Update `scripts/windows/install-shortcut.ps1` and `scripts/install_runtime.py` to pass an allowlisted shortcut failure category alongside `SHORTCUT_INSTALL_FAILED` while suppressing raw exception and subprocess output.

---

## Phase 5: User Story 3 - Check Workstation and Dependency Readiness (Priority: P1)

**Goal**: Extend Feature 005 readiness so operators can distinguish core
runtime health from individual external capability readiness and recheck safely.

**Independent Test**: Independently vary Atlas, GitHub Copilot CLI, Datadog
MCP, Microsoft 365 CLI, noc-tools, runtime, workspace write access, and service
state. Verify one redacted status per capability, core health remains distinct,
and Recheck reflects changes without restarting or mutating operational state.

### Tests for User Story 3

- [X] T017 [US3] Extend readiness API and frontend regression tests in `tests/test_readiness.py`, `tests/test_readiness_api.py`, and `tests/test_frontend_modules.py` for core/runtime/service checks, individual external statuses, preserved 400/422 behavior, sensitive-output redaction, keyboard-accessible Recheck, and visible request failures.

### Implementation for User Story 3

- [X] T018 [US3] Extend readiness assessment and API response in `backend/services/readiness.py` and `backend/api/readiness.py` to report the Python/application runtime, validated configuration, writable NOC workspace, user-service state, and separate Atlas/Copilot/Datadog MCP/Microsoft 365/noc-tools statuses; keep optional dependency failures out of core startup status and preserve existing response fields.
- [X] T019 [US3] Extend the existing readiness client and page in `frontend/js/api.js` and `frontend/readiness.html` with an accessible `Recheck` action, timestamp refresh, clear core-versus-optional status labels, safe corrective guidance, and explicit error rendering without raw subprocess output.

---

## Phase 6: User Story 4 - Continue Work When an External Capability Is Missing (Priority: P1)

**Goal**: Fail only the workflows that depend on an unavailable integration,
without substituting providers or blocking unrelated native NOC Web work.

**Independent Test**: Remove or invalidate one dependency at a time and verify
its dependent operation reports an explicit safe unavailable result while
unrelated workflows continue. Confirm Datadog cache behavior remains governed
by Feature 009 and no provider fallback occurs.

### Tests for User Story 4

- [X] T020 [US4] Add isolated dependency-degradation tests in `tests/test_dependency_gates.py` for missing Atlas, Copilot/MCP, Datadog MCP, Microsoft 365 CLI, and noc-tools; assert safe API errors, unrelated workflow availability, no substitute provider calls, retained valid incident-cache behavior, and no sensitive output leakage.

### Implementation for User Story 4

- [X] T021 [P] [US4] Gate Atlas-dependent Jira and noc-tools ticket workflows in `backend/services/jira_discovery.py`, `backend/services/jira_create.py`, `backend/services/ticket_sync.py`, `backend/api/jira_discovery.py`, `backend/api/jira_create.py`, and `backend/api/ticket_sync.py`; return explicit safe dependency errors and leave native/local workflows unaffected.
- [X] T022 [P] [US4] Gate Copilot and Datadog-MCP workflows in `backend/services/copilot_cli.py`, `backend/services/assistant.py`, `backend/services/datadog_incidents.py`, `backend/services/investigation_generation.py`, `backend/api/assistant.py`, `backend/api/ai_reports.py`, `backend/api/datadog_incidents.py`, and `backend/api/investigations.py`; do not substitute direct Datadog API access and preserve Feature 009 cache rules.
- [X] T023 [P] [US4] Gate Microsoft 365 email preview/send in `backend/services/handover_delivery.py` and `backend/api/handover_delivery.py`; report unavailable safely while retaining permitted local handover generation and preview.

---

## Phase 7: User Story 5 - Recover and Troubleshoot the Managed Service (Priority: P2)

**Goal**: Make service status, safe logs, restart/stop/start, manual
troubleshooting, and return to managed operation clear and non-competing.

**Independent Test**: Exercise stopped/failed service and port-conflict cases.
Verify documented status/log/recovery commands, safe journal content, explicit
manual-run conflict behavior, and restoration to the managed service.

### Tests for User Story 5

- [X] T024 [US5] Add recovery and log-safety tests in `tests/test_runtime_recovery.py` for service state/log access, restart data preservation, manual-versus-managed port conflicts, clear safe failure codes, and absence of configured sensitive fixtures from journal output.

### Implementation for User Story 5

- [X] T025 [US5] Configure safe service diagnostics and clear port-conflict handling in `scripts/run_service.py` and `backend/app.py`; permit only timestamp/operation/status/duration/HTTP status/safe error codes in runtime logs and exclude prompts, model output, Datadog evidence, Jira/ticket/Shift Note/handover contents, credentials, tokens, and raw sensitive subprocess output.
- [X] T026 [P] [US5] Document the exact status/restart/stop/start and journal commands plus safe manual-run/return-to-service recovery in `docs/workstation-runtime.md`; require stopping the user unit before manual execution and explain that a port already in use fails clearly rather than creating a competing listener.

---

## Phase 8: Polish and Cross-Cutting Validation

**Purpose**: Validate compatibility across Features 001-010 and the complete
installation-to-launch workflow.

- [X] T027 Re-run the full regression suite in `tests/` after the service entry-point fix, including required generated-unit verification and service-context execution; verify Features 001-010 remain behaviorally compatible.
- [X] T028 Re-run frontend ES-module validation in `tests/test_frontend_modules.py`, Python compilation for `backend/` and `scripts/`, and `git diff --check` after the service entry-point fix.
- [X] T029 Execute the end-to-end installation, upgrade, readiness, service recovery, and Windows shortcut scenarios in `specs/011-wsl-runtime-launch/quickstart.md` using an isolated supported WSL/Windows test configuration after T030-T036; keep this open until `./scripts/install.sh` succeeds, the managed service reaches healthy `/api/health`, the installed Windows shortcut opens the configured localhost URL, and a second shortcut launch reuses the same managed service without starting a duplicate.

---

## Phase 9: User Story 3 Follow-up - Discover Linuxbrew Dependencies (Priority: P1)

**Goal**: Make supported Linuxbrew-installed dependencies, including Atlas,
available to the deterministic managed-service environment without inheriting
interactive-shell or Windows paths.

**Independent Test**: Build the managed-service environment and verify its
PATH includes only the fixed Linuxbrew bin allowlist in addition to existing
trusted paths. Execute the Atlas readiness probe with an executable available
only through that managed PATH, and verify Windows and unallowlisted
interactive-shell locations are absent.

### Tests for User Story 3 Follow-up

- [X] T037 [P] [US3] Add managed-service PATH regression coverage in `tests/test_runtime_service.py` that requires `/home/linuxbrew/.linuxbrew/Homebrew/bin`, rejects inherited Windows and unallowlisted interactive-shell entries, and retains existing trusted paths.
- [X] T038 [P] [US3] Add Atlas discovery regression coverage in `tests/test_dependency_readiness.py` using a stub executable available only through the trusted Linuxbrew service PATH, while proving unallowlisted inherited paths are not consulted.

### Implementation for User Story 3 Follow-up

- [X] T039 [US3] Update the fixed managed-service environment builder in `scripts/run_service.py` so PATH includes `/home/linuxbrew/.linuxbrew/Homebrew/bin` without dynamically resolving Homebrew or inheriting shell/Windows PATH entries.

**Checkpoint**: The user service can discover Atlas installed in the supported
Linuxbrew bin directory while remaining isolated from ambient shell state.

---

## Phase 10: User Story 3 Follow-up - Verify Atlas Authentication (Priority: P1)

**Goal**: Report a valid managed-service Atlas installation as ready from its
supported machine-readable authentication-status contract instead of a
synthetic Jira search.

**Independent Test**: Stub `atlas auth status` JSON responses and verify a
usable signed-in session with a usable Jira-capable `sesamiio` site is ready;
unauthenticated and unusable-site responses are not ready; malformed JSON,
timeouts, and a missing executable are safely classified with no response
content exposed. Confirm Linuxbrew executable discovery remains unchanged.

### Tests for User Story 3 Atlas Authentication Follow-up

- [X] T040 [US3] Extend `tests/test_dependency_readiness.py` with machine-readable `atlas auth status` probe cases for ready (`session_usable=true`, `signed_in=true`, usable `sesamiio` Jira site), unauthenticated, unusable-site, malformed JSON, timeout, and missing-Atlas outcomes; assert bounded execution and redaction of all raw JSON/stdout/stderr fixtures.

### Implementation for User Story 3 Atlas Authentication Follow-up

- [X] T041 [US3] Replace the synthetic Atlas Jira-search probe in `backend/services/dependency_readiness.py` with a bounded `atlas auth status` JSON probe that safely validates usable authenticated-session and Jira-capable site fields, maps invalid/unusable states to existing safe readiness statuses, and preserves the trusted Linuxbrew-only executable search path.

**Checkpoint**: Managed-service readiness reports a valid authenticated Atlas
session as `ready` without issuing synthetic Jira queries.

---

## Dependencies and Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 creates the reproducible runtime dependency manifest.
- **Foundational (Phase 2)**: T002-T007 depend on setup and block user-story integration because they establish validated configuration, service invocation, and safe capability contracts. T004/T005 are reopened for the real service import-path defect; complete the subprocess regression before the module-entry-point change.
- **User Stories (Phases 3-7)**: Begin after Phase 2. US1 can be tested against a stub service. US2 installs the real service and consumes the US1 shortcut installer. US3 extends readiness on the shared capability contract. US4 consumes the capability contract and may proceed after T007; US5 depends on the managed service and status behavior from US2/US3.
- **Polish (Phase 8)**: Depends on all five user stories, the T004/T005 service-entry-point fix, and the T034-T036 Windows Script Host launch fix; rerun T027/T028 before T029, which remains the real Windows/WSL workstation acceptance test.
- **US3 Linuxbrew follow-up (Phase 9)**: T037 and T038 define the fixed-path and Atlas-discovery boundary and can run in parallel. T039 implements the environment change after those expectations are established. Re-run the focused service and dependency tests, then the full regression suite.
- **US3 Atlas authentication follow-up (Phase 10)**: T040 defines all
  machine-readable authentication-status outcomes. T041 depends on T040 and
  retains the trusted Linuxbrew discovery boundary established by T037-T039.
- **US2 shortcut-safety follow-up**: T030 and T031 are independent regression tests and can run in parallel. T032 follows T030; T033 follows T031 and T032. T029 remains open and must be run only after T030-T033 and the existing T027/T028 checks succeed.

### User Story Dependencies

- **US1 (P1)**: Depends on Phase 2; no dependency on another story for mocked launcher tests.
- **US1 Windows Script Host follow-up**: T034 and T035 are independent regression tests and can run in parallel. T036 depends on their specified launcher contract. T029 remains open until the generated VBS succeeds through Windows Script Host and the installed shortcut completes both a cold launch and a service-reuse launch.
- **US2 (P1)**: Depends on Phase 2 and US1's shortcut creation/launch artifacts; installer integration is not complete until both are available.
- **US3 (P1)**: Depends on Phase 2; can proceed in parallel with US1 and US2 implementation.
- **US4 (P1)**: Depends on Phase 2 capability probes (T007); its integration groups can run in parallel after the shared contract is stable.
- **US5 (P2)**: Depends on US2's managed service and US3's reported service state; it adds recovery behavior/documentation without changing external workflows.

### Parallel Opportunities

- After T001, T002 and T004 are independent test work; T006's capability tests are also isolated.
- Within US1, T008 and T009 are separate mocked/platform test files; T010 and T011 are separate Windows implementation files.
- Within the US1 Windows Script Host follow-up, T034 and T035 are separate Python and Windows acceptance test files; T036 follows their contract definition.
- US1 and US3 can proceed in parallel after Phase 2. US2 installer implementation can proceed once the US1 shortcut contract is stable.
- Within US4, T021, T022, and T023 touch separate integration groups and can proceed in parallel after T020 and the shared capability contract.
- In US5, safe runtime logging implementation and recovery documentation can proceed in parallel after T024.
- In the US3 Linuxbrew follow-up, T037 and T038 touch separate service and dependency test files and can proceed in parallel before T039.
- The US3 Atlas authentication follow-up is sequential because T040 and T041
  both change `tests/test_dependency_readiness.py` and
  `backend/services/dependency_readiness.py`'s shared probe contract.

## Parallel Examples

### User Story 1

```text
Parallel: T008 (mocked launcher tests) + T009 (Windows/WSL acceptance tests)
Parallel: T010 (shortcut creator) + T011 (hidden launcher)
Parallel: T034 (generated-launcher unit tests) + T035 (Windows Script Host acceptance tests)
```

### User Story 2

```text
After T012 defines installer expectations, implement T013/T014 sequentially
because both update installer orchestration; T016 documentation can proceed
in parallel once the config and install command are fixed.
Parallel: T030 (PowerShell 5.1/redirected Desktop coverage) + T031 (safe
failure propagation coverage); then T032 (shortcut validation) before T033
(failure-category propagation).
```

### User Story 3

```text
T017 defines API/UI expectations first; implement T018 (backend contract)
before T019 (frontend consumer) to keep the response shape synchronized.
```

### User Story 4

```text
Parallel after T020 and T007: T021 (Atlas/noc-tools),
T022 (Copilot/Datadog), and T023 (Microsoft 365).
```

### User Story 5

```text
After T024, T025 (safe logs/port conflict) and T026 (recovery guide)
can proceed in parallel.
```

### User Story 3 Linuxbrew Follow-up

```text
Parallel: T037 (managed-service PATH regression) + T038 (Atlas discovery regression)
Then: T039 (fixed Linuxbrew PATH implementation)
```

### User Story 3 Atlas Authentication Follow-up

```text
First: T040 (authentication-status JSON regression cases)
Then: T041 (safe Atlas authentication probe implementation)
```

## Implementation Strategy

### MVP

The smallest useful end-to-end MVP is US1 plus the service-installation slice
of US2: a validated user unit, idempotent startup, shortcut installation,
bounded localhost health check, and browser launch with no terminal left open.
US1 alone is mock-testable but cannot deliver the operator workflow without
US2's installed service and setup path.

### Incremental Delivery

1. Complete setup and foundation.
2. Deliver US1 launcher behavior and the US2 service/setup slice; validate one-click launch on the supported workstation.
3. Complete the US1 Windows Script Host follow-up T034-T036.
4. Add US3 readiness/recheck independently.
5. Add US4 graceful degradation per integration.
6. Add US5 recovery documentation and safe diagnostics.
7. Complete the US2 shortcut-safety follow-up tasks T030-T033, then run T029
   on the supported Windows/WSL workstation and the remaining quickstart
   scenarios.
8. Complete the US3 Linuxbrew follow-up T037-T039 and validate Atlas readiness
   through the managed service.
9. Complete the US3 Atlas authentication follow-up T040-T041 and validate
   the supported `atlas auth status` contract through the managed service.

## Format Validation

Every implementation/test task uses a checkbox, sequential `Tnnn` ID, `[P]`
only where files are independent, `[USn]` on user-story tasks, and an explicit
repository path. Tests are included because FR-029/FR-030 explicitly require
them.
