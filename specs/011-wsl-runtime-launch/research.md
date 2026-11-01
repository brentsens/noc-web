# Research: WSL Runtime and Windows Launch

## Decision 1: Use a user systemd unit and explicitly provision user-manager persistence

**Decision**: Install `noc-web.service` under the current user's systemd unit
directory, start it through `systemctl --user`, and configure bounded
`Restart=on-failure` behavior. Verify WSL systemd support and user-manager
availability. Enable or verify lingering so the user manager can run without an
interactive login; if the required system permission is unavailable, fail the
service setup step with an actionable instruction rather than installing a
root-owned service.

**Rationale**: A user unit runs with the operator's UID and can use the
operator's HOME and tool configuration. `loginctl enable-linger` is the
documented systemd mechanism for keeping a user manager available outside an
interactive login. Microsoft documents that WSL systemd support requires
systemd to be enabled in the distribution configuration and a sufficiently
recent WSL version.

**Alternatives considered**: A system-wide root-owned unit conflicts with the
operator-owned runtime boundary. A shell-started background process lacks
systemd status, restart limits, and journal integration.

**Sources**:
- [Microsoft: Use systemd to manage Linux services with WSL](https://learn.microsoft.com/en-us/windows/wsl/systemd)
- [systemd `user@.service`](https://www.freedesktop.org/software/systemd/man/latest/user@.service.html)
- [systemd `loginctl`](https://www.freedesktop.org/software/systemd/man/latest/loginctl.html)

## Decision 2: Install a per-user Windows Shell Link and launch it through a hidden script

**Decision**: Create or replace exactly one `SESAMI NOC Operations.lnk` in the
configured per-user shortcut folder (Desktop by default). Use Windows Shell
Link creation through `WScript.Shell.CreateShortcut`/PowerShell COM. Point the
link to a small Windows Script Host launcher that invokes the configured
`wsl.exe -d <distribution> -u <user>` target without a visible console, starts
the user service idempotently, performs bounded localhost health polling, then
opens the default URL handler only after the health endpoint succeeds.
Failures display a concise Windows error dialog; they never open a misleading
browser session. Reinstallation updates the same link in place.

**Rationale**: Shell Links are the Windows-native per-user shortcut format and
the documented Shell mechanism supports creating and saving them. A hidden
Windows Script Host process avoids leaving a console window; `.lnk` show-state
settings alone only minimize a console and are insufficient. Runtime values
are stored separately in a generated, credential-free launcher config; neither
shortcut arguments nor that config contain authentication material.

**Alternatives considered**: Manual shortcut instructions fail the mandatory
setup requirement. A `.cmd` target or direct visible `wsl.exe` launch leaves a
console. A machine-wide shortcut requires broader permissions and is not
needed for a single operator workstation.

**Sources**:
- [Microsoft: Shell Links](https://learn.microsoft.com/en-us/windows/win32/shell/links)
- [Microsoft: Known Folder IDs](https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid)
- [Microsoft: `IShellLinkW::SetShowCmd`](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-ishelllinkw-setshowcmd)
- [Microsoft: WSL basic commands](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)

## Decision 3: Keep launch operations inside the configured distribution and avoid shell-derived assumptions

**Decision**: Target the configured distribution and current Linux operator
explicitly for every WSL invocation; derive these values during setup rather
than hard-coding them. Pass only validated, non-secret runtime fields through
the generated launcher configuration or explicit process arguments. Do not
assume arbitrary Windows environment variables cross the WSL boundary. Keep
the repository and virtual environment on the Linux filesystem when available.

**Rationale**: Explicit `wsl.exe -d` and `-u` targeting avoids dependence on a
mutable default distribution or login user. WSL does not generally forward
Windows environment variables into Linux processes; its documented
`WSLENV` mechanism is selective and unnecessary when the installer writes a
validated launcher configuration. Microsoft recommends keeping Linux
workloads in the Linux filesystem for performance.

**Alternatives considered**: Using the current default distribution or relying
on inherited Windows environment can silently target the wrong installation
or omit configuration. Rewriting the distro's default user is broader than
per-invocation user targeting.

**Sources**:
- [Microsoft: WSL basic commands](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)
- [Microsoft: Share environment variables between Windows and WSL](https://devblogs.microsoft.com/commandline/share-environment-vars-between-wsl-and-windows/)
- [Microsoft: Work across file systems](https://learn.microsoft.com/en-us/windows/wsl/filesystems)

## Decision 4: Bound startup readiness and open only the localhost application URL

**Decision**: After idempotently requesting `systemctl --user start
noc-web.service`, poll the existing `GET /api/health` endpoint at the
validated configured localhost URL until healthy or the configured timeout
expires (60 seconds by default). Use a per-request timeout and an overall
deadline. Open the Windows default URL handler only after a healthy response.
Do not invoke `wsl --shutdown` as recovery.

**Rationale**: A bounded health poll handles cold WSL startup and service
startup without indefinite waits. The current health endpoint is a lightweight
application liveness check that does not access operational records or
external integrations. Microsoft notes that systemd services do not
indefinitely keep a WSL VM alive, so the launcher must wake the configured
distro and ensure the service on every use; this does not justify resetting
other running distributions.

**Alternatives considered**: A fixed sleep is not evidence that the app is
healthy. Opening the browser before health success creates a false successful
launch. `wsl --shutdown` affects all distributions and is unsafe as a normal
launcher step.

**Sources**:
- [Microsoft: Use systemd to manage Linux services with WSL](https://learn.microsoft.com/en-us/windows/wsl/systemd)
- [Microsoft: WSL basic commands](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)

## Decision 5: Extend Feature 005 readiness and keep optional dependencies non-blocking

**Decision**: Extend `/api/readiness/{shift_date}` and its existing
`frontend/readiness.html` consumer. Keep core runtime readiness separate from
external capability statuses, add a read-only Recheck control, and report
Atlas, GitHub Copilot CLI, Datadog MCP, Microsoft 365 CLI, and noc-tools
independently. Use only bounded, non-mutating checks and discard subprocess
stdout/stderr. A dependency is `READY` only when safe checks verify usability;
missing/unconfigured or unverifiable authentication/configuration is
`SETUP REQUIRED`, and transient probe failures are `UNAVAILABLE`. Do not
inspect or return credentials and do not call substitute providers.

**Rationale**: Feature 005 already supplies a redacted readiness endpoint,
configuration validation, safe command probes, and a static readiness page.
Reusing it avoids a competing health system. The existing required-command
aggregate must be split so optional tool absence does not make the application
unavailable. The app should still return explicit, bounded errors from only
the actions that depend on the missing integration.

**Alternatives considered**: A second setup/health application duplicates
configuration and confuses the operator. Treating every integration as a core
startup dependency contradicts graceful degradation. Inferring authentication
from the existence or contents of credential files is unsafe and unreliable.

**Sources**:
- Existing [Feature 005 readiness API](../../backend/api/readiness.py),
  [configuration](../../backend/config.py),
  [readiness probes](../../backend/services/readiness.py), and
  [operator guidance](../../docs/workstation-readiness.md)
- [Feature 005 readiness page](../../frontend/readiness.html)

## Decision 6: Separate pinned application requirements and preserve operator-owned state

**Decision**: Add a pinned runtime dependency manifest separate from the
test-only requirements. Setup validates the expected checkout and configuration
before changing owned files; it creates/updates the virtual environment,
runtime config, user unit, and shortcut idempotently. Write config and unit
updates atomically, retaining a validated prior copy when replacing owned
runtime configuration. Never recursively clean data directories or manage
external tools, credentials, or authentication.

**Rationale**: The repository currently has only a test requirements file;
the application imports FastAPI/Pydantic and is launched by Uvicorn. Separating
the app runtime requirements makes installation reproducible without taking
ownership of the operator's independent integrations. Atomic replacement and
strict ownership boundaries protect data through interrupted updates.

**Alternatives considered**: Installing from an unconstrained environment or
using a single test dependency file is not reproducible. Broad cleanup or
replacement of the user's config/data directory risks handovers, reports,
investigation lifecycle state, incident cache, and authentication.

**Sources**:
- Existing `backend/app.py`, `backend/config.py`, and `requirements-test.txt`
- [NOC Web Constitution](../../.specify/memory/constitution.md)

## Decision 7: Validate generated systemd units with the systemd parser

**Decision**: Render each substituted value according to the syntax of its
systemd directive rather than applying a generic shell-quoting function.
Automated service-generation tests must run
`systemd-analyze --user verify <generated-unit>` and fail if `systemd-analyze`
is unavailable or reports invalid unit configuration. This check is separate
from T029, which remains the real Windows/WSL workstation acceptance test.

**Rationale**: Systemd unit files have their own syntax and quoting rules, and
not every directive interprets quoted values as shell arguments. The official
`systemd-analyze verify` command loads unit files and reports detected errors,
so it catches parser-level failures that string assertions alone can miss.

**Alternatives considered**: Applying shell quoting uniformly can produce
directive-invalid values. Structural assertions alone do not prove that the
systemd parser accepts the generated unit. Skipping verification when the
validator is missing would let the regression pass without exercising the
failure boundary.

**Sources**:
- [systemd.syntax: general syntax and quoting rules](https://www.freedesktop.org/software/systemd/man/latest/systemd.syntax.html)
- [systemd-analyze: verify command](https://www.freedesktop.org/software/systemd/man/latest/systemd-analyze.html)

## Decision 8: Launch the service entry point as a repository-root Python module

**Decision**: Set the generated unit's `WorkingDirectory` to the validated
repository root and invoke the selected virtual-environment interpreter as
`python -m scripts.run_service --config <runtime-config>`. Add
`scripts/__init__.py` so the repository's `scripts` package is explicit and
cannot be resolved as a namespace package merged with an unrelated installed
`scripts` directory. Automated regression coverage executes the generated
unit's exact `ExecStart` in a subprocess using the unit's working directory
and declared environment, with inherited `VIRTUAL_ENV` and `PYTHONPATH`
removed; it verifies startup passes the `backend` import boundary.

**Rationale**: Python's documented `-m` behavior adds the current working
directory to the front of `sys.path` and resolves the module through the
standard import system. With systemd's validated repository-root working
directory, both `scripts.run_service` and `backend` resolve from this checkout
without shell activation or an inherited `PYTHONPATH`. The repository already
uses the same pattern for its child application process
(`python -m uvicorn backend.app:app`). A subprocess test of the generated
`ExecStart` preserves the actual interpreter, arguments, working directory,
and environment boundary that an in-process import test would bypass.

**Alternatives considered**: Invoking the absolute `scripts/run_service.py`
path places the script directory, rather than the repository root, at
`sys.path[0]` and reproduces the observed `ModuleNotFoundError`. Injecting
repository paths into Python from business logic duplicates path discovery;
relying on a manually or ambiently supplied `PYTHONPATH` violates the
workstation requirement and varies with the invoking shell. Running through
`-m` depends on `WorkingDirectory`, so the test must verify that the generated
unit sets the configured repository root and must retain the required
`systemd-analyze --user verify` check.

**Sources**:
- [Python command-line `-m` option](https://docs.python.org/3/using/cmdline.html#cmdoption-m)
- [Python import system: namespace packages](https://docs.python.org/3/reference/import.html#namespace-packages)
- Existing `scripts/run_service.py` Uvicorn command and
  `systemd/noc-web.service.in` working-directory contract

## Decision 9: Resolve and validate the Windows shortcut destination narrowly

**Decision**: Execute the shortcut installer under Windows PowerShell 5.1 and
define all helpers before their first invocation. Resolve the physical Desktop
using `[Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)`;
an empty result is a categorized installation failure. Permit a reparse point
only when using that OS-reported Desktop path, including a OneDrive Known
Folder Move redirect. Reject reparse points for arbitrary configured shortcut
destinations and retain strict LocalAppData checks. Report
`SHORTCUT_INSTALL_FAILED` together with a small allowlisted failure category,
never raw exception text or subprocess output.

**Rationale**: Microsoft documents that script functions must be defined
before calls in script files, and distinguishes the physical
`DesktopDirectory` from the virtual `Desktop`. The known-folder API resolves
the current OS-configured location, including OneDrive's supported Desktop
redirection. `GetFolderPath` can return an empty string when the location is
unavailable, so this must fail explicitly instead of allowing an empty path
into filesystem operations. PowerShell 5.1 does not expose
`FileSystemInfo.LinkTarget`; reparse-point checks use the `ReparsePoint`
attribute flag. The asymmetry between trusting the exact OS-known Desktop and
rejecting other configured reparse paths is a Feature 011 security decision
based on the documented known-folder provenance and reparse-point behavior;
Microsoft does not prescribe that exact policy as a named rule. Fixed safe
categories make failures actionable without exposing exception details.

**Alternatives considered**: Rejecting every reparse point breaks an
OS-configured OneDrive Desktop. Trusting all user-configured reparse paths
extends the exception beyond the known-folder source and can redirect writes.
Reading shell-folder registry keys directly duplicates the supported
`Environment.GetFolderPath` API. Echoing PowerShell exception messages can
expose local paths or other sensitive details.

**Sources**:
- [PowerShell 5.1 `about_Functions`](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_functions?view=powershell-5.1)
- [PowerShell 5.1 `about_Scripts`](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_scripts?view=powershell-5.1)
- [.NET Framework `Environment.SpecialFolder`](https://learn.microsoft.com/en-us/dotnet/api/system.environment.specialfolder?view=netframework-4.8)
- [.NET Framework `Environment.GetFolderPath`](https://learn.microsoft.com/en-us/dotnet/api/system.environment.getfolderpath?view=netframework-4.8)
- [Microsoft: Redirect and move Windows known folders to OneDrive](https://learn.microsoft.com/en-us/sharepoint/redirect-known-folders)
- [Microsoft: Reparse points](https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points)
- [.NET `FileSystemInfo.LinkTarget` availability](https://learn.microsoft.com/en-us/dotnet/api/system.io.filesysteminfo.linktarget?view=net-10.0)
- [PowerShell 5.1 `about_Try_Catch_Finally`](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_try_catch_finally?view=powershell-5.1)
- [`System.Management.Automation.ErrorCategory`](https://learn.microsoft.com/en-us/dotnet/api/system.management.automation.errorcategory?view=powershellsdk-7.4.0)

## Decision 10: Execute the generated WSL command through Windows Script Host explicitly

**Decision**: The hidden VBScript resolves the Windows WSL executable from the
Windows system directory and passes its complete command line to
`WScript.Shell.Run` with hidden window style and synchronous execution. It
uses one Windows-command-line quoting routine for every configured argument:
distribution, Linux user, Python path, launcher path, runtime-config path,
application URL, and timeout. A nonzero child exit code is mapped only from
the documented Python launcher exit codes; a `Run` invocation error or an
unexpected result such as `-1` is reported as
`WINDOWS_LAUNCH_EXECUTION_FAILED`. WSL or distribution-unavailable messaging
is reserved for a verified corresponding launcher result.

**Rationale**: The real workstation command succeeds when launched directly
from Windows PowerShell, while the same generated command returns `-1` from
both `wscript.exe` and `cscript.exe`. The defect therefore lies at the Windows
Script Host command-execution boundary, not in WSL, systemd, or the Python
launcher. Resolving the executable avoids reliance on host search-path
differences, consistent quoting preserves argument boundaries, and a distinct
safe error category prevents a Windows execution failure from being
misdiagnosed as a WSL outage. Automated Windows coverage must execute the
generated VBS with Windows Script Host when that host is available.

**Alternatives considered**: Treating every unrecognized result as WSL
unavailability produces a false diagnosis. Validating VBS text only does not
exercise Windows Script Host parsing or execution. Using a visible command
shell wrapper violates the no-persistent-console requirement.

**Sources**:
- Observed Feature 011 T029 workstation result: direct PowerShell execution
  succeeds; generated VBS returns `-1` through both `wscript.exe` and
  `cscript.exe`.
- [Microsoft: WScript.Shell Run method](https://learn.microsoft.com/en-us/previous-versions/windows/internet-explorer/ie-developer/windows-scripting/ateyt0fk(v=vs.84))
- [Microsoft: WSL basic commands](https://learn.microsoft.com/en-us/windows/wsl/basic-commands)

## Decision 11: Allowlist the Linuxbrew binary directory in the service PATH

**Decision**: Add only
`/home/linuxbrew/.linuxbrew/Homebrew/bin` to the explicit PATH generated for
the managed service. Do not derive a Homebrew prefix at service startup or
inherit the operator's interactive-shell or Windows PATH.

**Rationale**: Atlas is installed at this known Linuxbrew location and is
available to the operator's shell but absent from the managed service's fixed
PATH. Adding the one required trusted directory makes Atlas and supported
Linuxbrew dependencies discoverable while retaining deterministic systemd
execution and preventing Windows or arbitrary shell locations from affecting
the runtime.

**Alternatives considered**: Inheriting the full login-shell PATH makes
service behavior nondeterministic and can import Windows paths or shell
initialization. Including Linuxbrew `sbin` exceeds the currently demonstrated
need. Dynamically running `brew --prefix` during service startup adds a new
dependency on ambient command discovery.

**Sources**:
- Feature 011 workstation observation: `atlas` resolves to
  `/home/linuxbrew/.linuxbrew/Homebrew/bin/atlas` in the operator shell but is
  absent from the generated service PATH.

## Platform caveat

WSL can stop its lightweight VM independently of systemd service state. The
supported behavior is therefore: while the distro is running, the user unit
manages and restarts NOC Web; when Windows launches the shortcut later, it
wakes the configured distro, starts or reuses the service, and verifies health
again. The launcher must not promise that WSL remains resident indefinitely.
Actual hidden-window and Shell Link behavior requires an acceptance test on a
supported Windows/WSL workstation because Linux CI cannot exercise Windows
Shell COM.
