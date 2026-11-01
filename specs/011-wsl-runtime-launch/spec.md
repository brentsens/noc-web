# Feature Specification: WSL Runtime and Windows Launch

**Feature Branch**: `011-wsl-runtime-launch`

**Created**: 2026-10-31

**Status**: Draft

**Input**: User description: "Add production-style local runtime and launch support for noc-web so the NOC engineer can use the web application from Windows without keeping a WSL terminal open."

## Clarifications

### Session 2026-10-31

- Q: Must successful setup install a usable Windows shortcut rather than only document manual creation? → A: Yes; setup creates or safely updates one per-user shortcut named SESAMI NOC Operations, targets the current workstation configuration, and reports launcher setup failure clearly if it cannot create it.

### Session 2026-11-01

- Q: How must Feature 011 validate generated systemd user units? → A: Use systemd directive-specific path escaping, require automated tests to run `systemd-analyze --user verify` and fail if it is unavailable or rejects the unit, and retain T029 as real workstation acceptance.
- Q: How must the managed service launch `run_service.py` and how must regression coverage verify its import environment? → A: Launch it with the validated virtual-environment interpreter and resolve `backend` imports from the validated repository root without relying on an activated shell or manually supplied `PYTHONPATH`; test the generated unit's `ExecStart` in a subprocess using its declared working directory and environment, with inherited `VIRTUAL_ENV` and `PYTHONPATH` removed, rather than only importing the module. T029 remains open until the actual installer, managed service, health endpoint, and Windows shortcut all succeed on the workstation.
- Q: When the Windows Desktop is a reparse point, which destination should the installer trust? → A: Trust only the path returned by `Environment.GetFolderPath("DesktopDirectory")` for the Desktop shortcut, including its reparse point; do not extend that trust to arbitrary configured destinations, and keep LocalAppData installation checks strict.
- Q: How should the launcher report an unexpected `WScript.Shell.Run` result such as `-1`? → A: Report a separate `WINDOWS_LAUNCH_EXECUTION_FAILED` category; reserve WSL/distribution-unavailable reporting for verified WSL failures.
- Q: Which Linuxbrew binary locations should the managed service trust? → A: Include only `/home/linuxbrew/.linuxbrew/Homebrew/bin`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Launch NOC Web from Windows (Priority: P1)

An operator starts a normal NOC work session from a Windows shortcut named
**SESAMI NOC Operations**. WSL starts when needed, the managed NOC Web service
becomes healthy, and the default browser opens the configured local application
without leaving a terminal window open.

**Why this priority**: The ordinary operator workflow must not depend on keeping
a WSL terminal open or knowing how to start a development server.

**Independent Test**: Exercise the launcher with WSL stopped, the service
already running, and each startup failure. Verify that the browser opens only
after a successful local health check and that no duplicate service or visible
terminal is left behind.

**Acceptance Scenarios**:

1. **Given** setup has installed the SESAMI NOC Operations shortcut and WSL is
   stopped, **When** the operator launches it, **Then** WSL wakes, the
   configured service starts, a successful bounded health check completes, and
   the browser opens the configured localhost URL.
2. **Given** the service is already running and healthy, **When** the operator
   launches the shortcut, **Then** the existing service is reused and no
   duplicate web server is started.
3. **Given** WSL, the configured distribution, service startup, or application
   health is unavailable, **When** the operator launches the shortcut,
   **Then** the launcher reports a clear failure and does not open the browser
   as though startup succeeded.
4. **Given** the launcher finishes successfully or unsuccessfully, **When**
   the operator returns to Windows, **Then** no visible terminal window remains
   running.

---

### User Story 2 - Install and Maintain a User-Owned Runtime (Priority: P1)

An operator installs or updates NOC Web from its expected source using a
repeatable setup workflow. The application runs as the operator's unprivileged
WSL user and keeps its service, runtime, configuration, and operational data
separate from independently maintained external tools.

**Why this priority**: A reliable one-click workflow depends on a correctly
installed, maintainable runtime that does not take ownership of credentials or
operational records.

**Independent Test**: Run setup twice against an isolated supported checkout,
then repeat it as an upgrade with existing configuration and sample operational
records. Verify the service is user-owned, the same configuration remains
effective, data remains intact, and external tools are neither installed nor
authenticated by setup.

**Acceptance Scenarios**:

1. **Given** an expected NOC Web source, a supported Python environment, and
   valid workstation configuration, **When** setup runs, **Then** it installs
   only NOC Web's pinned runtime requirements, configures the user service,
   installs the usable SESAMI NOC Operations shortcut for the current Windows
   user, and validates local health.
2. **Given** setup has already succeeded, **When** it runs again, **Then** it
   safely updates or preserves the same shortcut and service definition without
   creating duplicates or changing the operator's selected paths, credentials,
   or operational data.
3. **Given** a required external tool is missing, **When** setup runs,
   **Then** NOC Web can still start and the missing capability is reported
   separately with a reference to that tool's authoritative setup process.
4. **Given** setup is run from an unexpected source or invalid configuration,
   **When** validation fails, **Then** it reports the issue before replacing
   runtime configuration or starting an unusable service.

---

### User Story 3 - Check Workstation and Dependency Readiness (Priority: P1)

An operator can see whether NOC Web and its supporting workstation capabilities
are ready, distinguish core application health from optional dependency
readiness, and recheck after resolving a setup issue.

**Why this priority**: Operators need to know which workflows are available
without mistaking a missing integration for a failed application or exposing
authentication information.

**Independent Test**: Vary each dependency independently, inspect the existing
Health/Readiness experience, and use Recheck. Verify each capability changes
independently, core readiness remains available, and no credentials or raw
command output are exposed.

**Acceptance Scenarios**:

1. **Given** the core runtime is healthy and all configured dependencies are
   ready, **When** the operator opens workstation readiness, **Then** each core
   and external capability is reported separately.
2. **Given** one external dependency is missing or not authenticated, **When**
   readiness is checked, **Then** that capability reports setup required while
   unrelated capabilities and core NOC Web health retain their own statuses.
3. **Given** an operator installs or authenticates a dependency, **When** they
   select Recheck, **Then** the displayed readiness is refreshed without
   restarting the application or performing an external state change.
4. **Given** a readiness probe fails or its subprocess emits sensitive text,
   **When** the result is displayed or logged, **Then** only a safe status and
   corrective guidance are shown.

---

### User Story 4 - Continue Work When an External Capability Is Missing (Priority: P1)

An operator can continue using unrelated NOC Web workflows when an independently
maintained integration is unavailable. The application explains which
capability is blocked and does not silently substitute another provider.

**Why this priority**: A missing optional tool must not turn a local application
or unrelated NOC workflow into a system-wide outage.

**Independent Test**: Isolate each missing external dependency and verify that
the application starts, reports the affected capability, rejects or disables
only dependent actions, and leaves unrelated native workflows usable.

**Acceptance Scenarios**:

1. **Given** Atlas is unavailable, **When** an operator uses NOC Web, **Then**
   Jira refresh is reported unavailable while unrelated workflows continue.
2. **Given** GitHub Copilot CLI or its required MCP configuration is
   unavailable, **When** an operator uses NOC Web, **Then** AI, Copilot, and
   Copilot-backed Datadog workflows report unavailable while non-AI workflows
   continue.
3. **Given** Datadog MCP is unavailable, **When** an operator requests a live
   incident refresh or Datadog investigation generation, **Then** that action
   reports unavailable, the prior valid Feature 009 cache remains governed by
   its existing rules, and unrelated workflows continue.
4. **Given** Microsoft 365 CLI is unavailable, **When** an operator uses
   email preview or send, **Then** those actions report unavailable while
   permitted local handover generation and preview continue.
5. **Given** noc-tools is unavailable, **When** an operator uses a workflow
   that depends on a missing command, **Then** that workflow identifies the
   unavailable capability while unrelated native NOC Web workflows remain
   usable.

---

### User Story 5 - Recover and Troubleshoot the Managed Service (Priority: P2)

An operator can determine service state, inspect safe recent logs, restart or
stop the service, and temporarily run NOC Web manually for troubleshooting
without creating competing server instances.

**Why this priority**: Operators need a safe recovery path when the background
runtime fails, while ordinary use should remain terminal-free.

**Independent Test**: Simulate an unavailable service and a port conflict.
Verify that service status and recent logs are accessible, documented recovery
actions work, and manual operation is exclusive with the managed service.

**Acceptance Scenarios**:

1. **Given** the service is running or stopped, **When** an operator checks
   service status, **Then** the result identifies its state and provides access
   to useful recent logs.
2. **Given** troubleshooting requires a manual run, **When** the operator
   follows the recovery procedure, **Then** the managed instance is stopped
   before the manual instance starts and can be restored afterward.
3. **Given** a manual or managed instance already owns the configured port,
   **When** another instance is started, **Then** it fails clearly instead of
   silently competing for the same listener.

## Edge Cases

- WSL, the configured distribution, or the user systemd manager is unavailable;
  setup and launch fail clearly without falling back to a root-owned service.
- The service is already active, is starting, is unhealthy, or repeatedly
  crashes; the launcher does not start a duplicate and reports bounded startup
  failure.
- The configured port is occupied by a different process or another manual
  instance.
- The repository, virtual environment, or NOC workspace path is missing,
  unsafe, inaccessible, or no longer matches preserved workstation settings.
- The operator's HOME, PATH, or user-owned tool configuration is absent from
  the service environment.
- Atlas or another supported dependency is installed only in the trusted
  Linuxbrew binary directory; the service discovers it without inheriting an
  interactive-shell or Windows PATH entry.
- An external tool exists but its authentication or required MCP configuration
  is missing, expired, unreadable, or cannot be verified safely.
- A readiness or installer subprocess times out or emits credentials,
  customer data, or other sensitive output.
- An upgrade is interrupted while replacing a service definition or runtime
  configuration.
- An upgrade encounters existing handovers, AI reports, Feature 009 incident
  cache, Feature 010 lifecycle state, or other operational data.
- The default Windows browser cannot be opened, but the service is healthy.
- Windows Script Host cannot execute the generated launcher command or returns
  an unexpected result, including `-1`; this is reported as a safe Windows
  launcher-execution failure, not as WSL or distribution unavailability.
- The current user's Windows shortcut location is unavailable or cannot be
  written; setup reports launcher installation failure and does not report the
  launcher step as successful.
- The OS-reported Desktop directory may be a OneDrive-redirected reparse point;
  permit that exact known-folder destination, but do not trust arbitrary
  configured reparse-point destinations or relax LocalAppData validation.
- A configured launcher URL attempts to use a non-localhost host or an unsafe
  scheme.
- A setup workflow is invoked from an unexpected repository or release source.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: NOC Web MUST run as the current unprivileged WSL operator. Its
  preferred managed background service MUST be a systemd user service, MUST
  start without an interactive terminal, and MUST stop cleanly.
- **FR-002**: The service MUST use the validated NOC Web repository as its
  working directory, the application's virtual environment, the configured
  application port, and the required operator-owned HOME and user environment.
  The default port MUST be 8000.
- **FR-003**: The service MUST bind only to `127.0.0.1` by default, MUST NOT
  expose a listener to the LAN, and MUST use the configured local application
  URL.
- **FR-004**: The service MUST restart after unexpected failure under a
  bounded restart policy and MUST expose service status and useful logs through
  the user service manager and its journal.
- **FR-005**: The service environment MUST retain access to operator-owned
  `~/noc`, `~/.local/bin`, GitHub Copilot CLI authentication, Copilot MCP
  configuration, Atlas configuration and authentication, Datadog MCP
  configuration, Microsoft 365 CLI authentication, and installed noc-tools.
  Service setup MUST NOT copy credentials, tokens, or authentication material
  into NOC Web configuration or the service definition.
- **FR-006**: NOC Web MUST detect and report core runtime readiness and each
  external capability independently: Atlas, GitHub Copilot CLI, Datadog MCP,
  Microsoft 365 CLI, and noc-tools. Authentication readiness MUST be reported
  without displaying credential values or authentication material. Each
  capability MUST report `READY` when verified usable, `SETUP REQUIRED` when
  absent, unconfigured, or unauthenticated, or `UNAVAILABLE` when a transient
  check cannot complete.
- **FR-007**: Missing or unauthenticated external dependencies MUST NOT
  prevent the core NOC Web service from starting. They MUST NOT silently
  trigger a different provider, command, or integration.
- **FR-008**: When Atlas is unavailable, Jira refresh MUST report unavailable
  without blocking unrelated workflows.
- **FR-009**: When GitHub Copilot CLI or its required MCP configuration is
  unavailable, dependent AI Actions, Assistant, Copilot-backed, and
  Copilot-backed Datadog workflows MUST report unavailable without blocking
  unrelated non-AI workflows.
- **FR-010**: When Datadog MCP is unavailable, live incident refresh and
  Datadog investigation generation through the existing Copilot CLI/MCP path
  MUST report unavailable; the prior valid incident cache MUST continue to
  follow Feature 009 behavior, and unrelated workflows MUST continue. NOC Web
  MUST NOT substitute direct Datadog API access.
- **FR-011**: When Microsoft 365 CLI is unavailable, email preview and send
  MUST report unavailable while permitted local handover generation and
  preview remain available.
- **FR-012**: When a required noc-tools command is unavailable or incompatible,
  dependent workflows MUST report that limitation while unrelated native NOC
  Web workflows remain available.
- **FR-013**: NOC Web MUST extend or reuse the existing Health/Readiness
  experience rather than add a competing health system. The workstation
  readiness view MUST report the application/runtime, Python environment,
  writable NOC workspace, background service, Atlas, GitHub Copilot CLI,
  Datadog MCP, Microsoft 365 CLI, and required noc-tools compatibility.
- **FR-014**: The readiness view MUST provide a Recheck action that refreshes
  capability results without requiring an application restart or performing an
  external state change.
- **FR-015**: Readiness MUST expose safe status, operational impact, and
  corrective guidance, but MUST NOT expose credentials, tokens, authentication
  material, sensitive subprocess output, or raw subprocess stdout/stderr.
- **FR-016**: A Windows launcher named **SESAMI NOC Operations** MUST start or
  wake the configured WSL distribution, ensure the managed service is running,
  wait for a bounded local health check, and open the default Windows browser
  to the configured localhost URL only after health succeeds. Its hidden
  VBScript launcher MUST reliably invoke the validated WSL launcher command
  under Windows Script Host 5.1, preserving safe argument boundaries for the
  distribution name, paths, runtime configuration, URL, and timeout.
- **FR-017**: The launcher MUST reuse an already-running healthy service and
  MUST NOT start a duplicate NOC Web server. Its health wait MUST be bounded,
  with a documented safe default of 60 seconds.
- **FR-018**: The launcher MUST fail clearly when WSL is unavailable, the
  configured distribution is missing, service startup fails, or the health
  check exceeds its bound. It MUST NOT open the browser as a successful launch
  in those cases and MUST NOT leave a visible terminal window running.
- **FR-019**: Launcher and service configuration MUST NOT hard-code an
  operator name, WSL distribution, repository path, virtual environment path,
  or non-default port. It MUST reuse Feature 005 workstation configuration
  where applicable and provide documented safe defaults. The installed
  shortcut MUST contain no credentials, tokens, or authentication material.
- **FR-020**: Configured repository, runtime, workspace, distribution, port,
  and localhost URL values MUST be validated before use. The localhost URL
  MUST reject non-localhost hosts and unsafe schemes. Valid selected
  configuration MUST persist across application upgrades.
- **FR-021**: Installation MUST validate the expected NOC Web source or
  release, Python requirements, and application configuration; create or
  update the NOC Web virtual environment; install pinned NOC Web dependencies;
  create required local runtime directories safely; install or update the
  user-service definition; reload the user service manager; start and enable
  the service where supported; and verify localhost health.
- **FR-022**: Installation MUST be repeatable and idempotent. It MUST report
  external dependency readiness and provide authoritative setup guidance, but
  MUST NOT automatically install or authenticate GitHub Copilot CLI, Atlas,
  Datadog MCP, Microsoft 365 CLI, or noc-tools. Setup MUST create or install a
  usable per-user Windows shortcut named exactly **SESAMI NOC Operations**,
  targeted to the configured workstation. Manual shortcut-creation instructions
  alone do not satisfy setup. If shortcut creation or update fails, setup MUST
  report that launcher-installation step as failed and MUST NOT report launcher
  setup as successful. Re-running setup MUST update or preserve the existing
  shortcut without creating duplicates.
- **FR-023**: Updates and uninstall MUST preserve `~/noc` operational records,
  handovers, AI reports, Feature 010 investigation history and lifecycle state,
  Feature 009 incident cache unless replacement is necessary, and operator
  authentication. Updates MUST preserve valid workstation configuration and
  MUST NOT silently overwrite it; runtime configuration MUST be validated or
  backed up before replacement. Uninstall MAY remove NOC Web-owned runtime
  files and its shortcut, but MUST NOT delete operator operational data or
  external authentication.
- **FR-024**: Operator documentation MUST provide the supported service
  management and log commands:
  `systemctl --user status noc-web`,
  `systemctl --user restart noc-web`,
  `systemctl --user stop noc-web`,
  `systemctl --user start noc-web`,
  `journalctl --user -u noc-web`, and
  `journalctl --user -u noc-web -f`.
- **FR-025**: Operator documentation MUST explain recovery by checking status,
  inspecting recent safe logs, restarting or stopping the service, running
  NOC Web manually for troubleshooting, and returning to the managed service.
  Manual and managed runs MUST NOT silently compete for the configured port.
- **FR-026**: Background logs MUST provide useful safe diagnostics, such as
  timestamp, operation, status, duration, HTTP status, and safe error codes.
  Logs MUST NOT contain prompts, raw model output, Datadog evidence, Jira
  ticket content, Shift Notes, handover content, credentials, tokens,
  authentication material, or raw sensitive subprocess output.
- **FR-027**: Runtime and launcher behavior MUST preserve existing read-only
  defaults, explicit confirmation gates, operator authority, and Jira and
  Datadog source-of-truth boundaries. Neither the service nor launcher may
  bypass an application confirmation workflow or cause a silent external
  mutation.
- **FR-028**: Existing Features 001-010 MUST retain their user-visible
  behavior. Frontend and API behavior MUST remain independent of whether an
  external command adapter is implemented using current noc-tools or future
  native Python services.
- **FR-029**: Automated regression coverage MUST verify localhost-only service
  binding, unprivileged execution, correct repository and virtual environment,
  idempotent setup, configuration and operational-data preservation, setup
  creation of the exact named shortcut for the configured WSL distribution,
  no duplicate shortcut on installer reruns, and no credentials in the
  shortcut. Coverage MUST also verify graceful startup with each external
  dependency missing, individual readiness and Recheck behavior, launcher
  duplicate-service prevention and bounded health wait, stopped-service
  startup, startup-failure handling, default-browser launch ordering,
  localhost-only URL, no persistent terminal, service-restart data
  preservation, sensitive-log redaction, shortcut-installer execution under
  Windows PowerShell 5.1, helper-function availability before invocation, the
  OS-reported Desktop when redirected through OneDrive and marked as a
  reparse point, rejection of arbitrary configured reparse-point destinations,
  conservative LocalAppData validation, useful safe shortcut-install failure
  reasons, generated-VBScript execution through Windows Script Host where it
  is available, safe argument handling for the generated WSL launcher command,
  safe categorization of unexpected `WScript.Shell.Run` results, and
  compatibility with Features 001-010.
- **FR-030**: The release MUST pass the full pytest regression suite, frontend
  ES-module validation, and `git diff --check`.
- **FR-031**: The installer MUST generate a systemd user unit whose paths and
  values follow the syntax required by each systemd directive; generic
  shell-style quoting MUST NOT make configured absolute paths invalid.
  Automated regression tests MUST run `systemd-analyze --user verify` against
  the generated unit and MUST fail if the tool is unavailable or rejects the
  unit. This automated check MUST NOT replace T029's real workstation
  acceptance test.
- **FR-032**: The managed service MUST launch `scripts/run_service.py` with the
  validated virtual-environment interpreter and resolve `backend` imports
  from the validated repository root without relying on an activated shell or
  manually supplied `PYTHONPATH`. Automated regression coverage MUST execute
  the generated unit's `ExecStart` in a subprocess using its declared working
  directory and environment, with inherited `VIRTUAL_ENV` and `PYTHONPATH`
  removed; importing `run_service.py` as a Python module alone does not
  satisfy this requirement.
- **FR-033**: The Windows shortcut installer MUST be compatible with Windows
  PowerShell 5.1 and MUST define or load helper functions before their first
  invocation. Automated regression coverage MUST execute the installer under
  Windows PowerShell 5.1, not merely check that its syntax is compatible.
- **FR-034**: The installer MAY allow a reparse point for the exact Desktop
  directory returned by `Environment.GetFolderPath("DesktopDirectory")`,
  including a OneDrive-redirected Desktop. This exception MUST NOT implicitly
  trust an arbitrary configured shortcut destination; other reparse-point
  shortcut destinations MUST fail validation. LocalAppData installation
  paths MUST retain their existing conservative reparse-point checks.
- **FR-035**: When shortcut installation fails, setup MUST preserve and report
  a safe, useful reason in addition to the generic
  `SHORTCUT_INSTALL_FAILED` code. The reason MUST identify the failure
  category without exposing raw exception output, credentials, or sensitive
  content.
- **FR-036**: An unexpected `WScript.Shell.Run` result, including `-1`, MUST
  report `WINDOWS_LAUNCH_EXECUTION_FAILED` with safe corrective guidance. The
  launcher MUST report WSL or configured-distribution unavailability only
  when that condition is verified and MUST NOT expose raw command output,
  exception text, credentials, or sensitive content.
- **FR-037**: The managed service PATH MUST include
  `/home/linuxbrew/.linuxbrew/Homebrew/bin` so supported Linuxbrew-installed
  dependencies, including Atlas, are discoverable. It MUST remain an explicit
  deterministic allowlist and MUST NOT inherit the operator's full interactive
  PATH, Windows PATH entries, or arbitrary shell initialization.

### Key Entities

- **Workstation Runtime Configuration**: Validated local selections for the
  NOC Web source, runtime environment, WSL distribution, port, local URL, and
  workspace. It contains no credentials and remains stable across upgrades.
- **Managed NOC Web Service**: The operator-owned background application
  process, including its running state, restart behavior, local listener, and
  safe diagnostic log stream.
- **Capability Readiness Result**: A current, redacted status for core runtime
  or an external dependency, including whether it is available, the dependent
  NOC capability, and safe setup or recovery guidance.
- **Windows Launcher**: The operator's SESAMI NOC Operations shortcut and its
  configured WSL target, bounded startup check, local URL, and result.
- **Operational Data**: Operator-owned NOC records, handovers, AI reports,
  investigation lifecycle records, and incident cache that must remain intact
  during installation, upgrade, restart, or recovery.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In supported workstation tests, the Windows launch flow opens
  NOC Web only after local health succeeds and completes within the configured
  bound, whose default is 60 seconds.
- **SC-002**: In all service and launcher tests, the application listens only
  on localhost, runs as the unprivileged operator, and leaves no visible
  terminal after launch.
- **SC-003**: Across tests with each external dependency independently absent
  or unauthenticated, 100% of readiness results identify the affected
  capability and unrelated core workflows remain available.
- **SC-004**: Repeating installation and upgrade in tests changes no existing
  operational record, handover, AI report, lifecycle state, incident cache
  unless required, valid workstation setting, or authentication material.
- **SC-005**: In readiness and launcher tests, Recheck reflects repaired
  capabilities, every successful setup creates exactly one shortcut with the
  configured workstation target, installer reruns do not duplicate it,
  duplicate services are not launched, and startup failures never result in a
  false successful browser launch.
- **SC-006**: In tests containing configured sensitive fixtures, 0 credential,
  token, authentication, customer, ticket, handover, prompt, or raw provider
  output values appear in readiness responses or background logs.
- **SC-007**: Operators can follow documented steps to determine service
  status, inspect recent logs, stop or restart the service, use a temporary
  manual run, and return to managed operation without competing instances.
- **SC-008**: The full automated regression suite for Features 001-010 passes
  with the managed-runtime and launcher changes enabled.
- **SC-009**: Automated runtime tests pass native syntax verification for the
  generated user-service unit; missing verification support or invalid
  generated syntax causes test failure. T029 still verifies the installed
  service during real workstation acceptance and remains open until the
  actual `./scripts/install.sh` creates `SESAMI NOC Operations.lnk` and the
  shortcut successfully launches or reuses the managed WSL runtime on the
  workstation.
- **SC-010**: The automated service-context regression executes the generated
  unit's `ExecStart` with its declared working directory and environment,
  without inherited `VIRTUAL_ENV` or `PYTHONPATH`, and confirms startup
  proceeds past `backend` imports.
- **SC-011**: T029 remains open until the installed **SESAMI NOC Operations**
  shortcut successfully opens NOC Web from Windows and a second launch
  successfully reuses the existing managed service without starting a
  duplicate.
- **SC-012**: Service-environment regression coverage confirms a supported
  dependency installed in `/home/linuxbrew/.linuxbrew/Homebrew/bin` is
  discoverable while Windows PATH entries and unallowlisted interactive-shell
  paths remain absent.

## Assumptions

- The supported managed-service target is WSL with a functioning per-user
  systemd manager. If it is unavailable, setup reports the limitation and does
  not silently install a root-owned service or another unapproved manager.
- The safe application URL defaults to `http://127.0.0.1:8000`; the port and
  URL may be changed only through validated workstation configuration.
- The shortcut is installed for the current Windows user on that user's
  Desktop returned by the Windows known-folder API unless the workstation
  configuration specifies another supported per-user shortcut location. The
  OS-reported Desktop may be redirected, including through OneDrive.
- The Windows launcher waits up to 60 seconds by default for local health.
  A deployment may use a different documented bounded timeout.
- Readiness uses non-mutating capability checks supported by each dependency.
  If a dependency cannot safely confirm authentication or MCP configuration,
  its readiness is reported as unverified or setup required rather than
  inferred from credentials or raw command output.
- The existing Feature 005 workstation configuration remains authoritative for
  supported paths and overrides; this feature adds only the runtime settings
  needed for launch and service management.
- External tools and authentication remain operator-owned and are provisioned
  through their authoritative setup processes. Core NOC Web availability does
  not depend on their presence.
- Operational data remains in its existing configured locations. Installation
  and upgrades manage only NOC Web's application runtime and service files.
- Ordinary use is through the Windows launcher and browser. WSL terminals are
  reserved for development, maintenance, troubleshooting, Git operations, or
  manual noc-tools operations.
