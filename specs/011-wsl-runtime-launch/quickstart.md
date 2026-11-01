# Quickstart: WSL Runtime and Windows Launch

This guide is the end-to-end validation contract for the implementation.
Commands assume setup has been run from the validated NOC Web source directory
inside the configured WSL distribution. They do not require installing or
authenticating external tools.

## Prerequisites

- Supported WSL distribution with systemd enabled and an unprivileged operator
  account.
- `systemd-analyze` available for mandatory generated-unit verification.
- Python 3.10 or later and access to the configured Python package source.
- Windows interoperability available for per-user shortcut installation.
- Windows PowerShell 5.1 available to execute the shortcut installer.
- The configured NOC Web checkout and writable operator NOC workspace.
- Any required permission to enable systemd user lingering, if it is not
  already enabled.

## Install or update

```bash
./scripts/install.sh
```

Expected result: runtime configuration is validated/preserved, the
NOC-Web-owned virtual environment and user service are installed or updated,
localhost health succeeds, and exactly one **SESAMI NOC Operations** shortcut
exists for the current Windows user. Optional dependency statuses are
reported individually; missing external tools do not block service startup.

Validate the generated user unit with the systemd parser:

```bash
systemd-analyze --user verify \
  "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/noc-web.service"
```

The command must succeed. Automated regression tests require
`systemd-analyze`; they fail rather than skip if the validator is unavailable.
This generated-unit check does not replace T029's real workstation acceptance.
The service-context regression must also execute the generated unit's exact
`ExecStart` in a subprocess using the unit's working directory and environment
with inherited `VIRTUAL_ENV` and `PYTHONPATH` removed. It must confirm startup
passes the `backend` import boundary; importing the entry point within the test
process is not sufficient.

Run setup again and verify the same shortcut and service are updated in place.
Before and after the second run, compare representative hashes from the
configured NOC workspace (handovers, reports, investigation lifecycle data,
and incident cache); none may be removed or reset.

## Verify the managed service and readiness

```bash
systemctl --user status noc-web
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:8000/api/readiness/2099-12-31
```

The health endpoint must identify a healthy `noc-web` service. Readiness must
separately show core runtime/workspace/service evidence and the Atlas,
GitHub Copilot CLI, Datadog MCP, Microsoft 365 CLI, and noc-tools capability
statuses. Use the existing Workstation Readiness page's `Recheck` button after
changing a test capability; only its status and assessment time should change.

Use temporary test workspaces and stub executables to validate each dependency
missing or unavailable in isolation. Confirm core health remains available,
the affected action reports its dependency failure safely, and no unrelated
provider is substituted. Include sensitive fixture strings in stub command
output and confirm they do not appear in API responses or journal output.
Place a supported dependency fixture in
`/home/linuxbrew/.linuxbrew/Homebrew/bin` and confirm the managed service
discovers it. Confirm its generated PATH does not contain Windows PATH entries
or unallowlisted interactive-shell locations.

## Verify Windows shortcut behavior

On the supported Windows/WSL workstation:

```powershell
powershell.exe -NoProfile -File .\tests\windows\test_launcher_acceptance.ps1 `
  -Distribution "<configured WSL distribution>" `
  -LinuxUser "<configured Linux user>" `
  -RepositoryRoot "<configured Linux repository path>" `
  -RerunSetup -StopBeforeRun -Execute
```

Run this with Windows PowerShell 5.1. The acceptance harness must exercise
the actual installer process as well as the shortcut launch.

1. Confirm setup created exactly one current-user shortcut named
   `SESAMI NOC Operations`; inspect its resolved target and ensure it contains
   the configured WSL distribution and no credentials.
2. With the service stopped, launch the shortcut. Confirm the configured
   distribution wakes, the user service starts, health succeeds within the
   configured bound, the default browser opens the localhost URL, and no
   terminal remains.
3. Launch it again while healthy. Confirm the same service is reused and no
   second Uvicorn process is started.
4. With a test launcher configuration pointing to an unavailable distribution
   or blocked service, confirm a clear failure appears and no browser opens.
5. Re-run setup and confirm the same shortcut is updated/preserved in place
   without a suffixed duplicate.
6. Run the Windows launcher acceptance harness using Windows PowerShell 5.1.
   Its regression cases must cover an OS-reported Desktop redirected through
   OneDrive and marked as a reparse point, rejection of an arbitrary configured
   reparse-point destination, conservative LocalAppData validation, an
   unavailable/empty Desktop resolution, helper definitions before use, and
   categorized safe installation failures.
7. Where Windows Script Host is available, execute the installed generated
   VBScript through `cscript.exe` and the shortcut's hidden `wscript.exe`
   target. Verify that the known-good WSL launcher command succeeds with
   values containing safe quoting edge cases, no persistent console remains,
   and an injected/observed unexpected `Run` result such as `-1` is reported
   as `WINDOWS_LAUNCH_EXECUTION_FAILED`, never as WSL or distribution
   unavailability.

The launcher must use only a localhost URL. Do not use `wsl --shutdown` for
testing; it stops all running distributions.

## Verify recovery and exclusive manual operation

```bash
systemctl --user stop noc-web
systemctl --user status noc-web
journalctl --user -u noc-web
systemctl --user start noc-web
systemctl --user restart noc-web
```

Follow the runtime recovery instructions to run a temporary manual process
only after stopping the service. Confirm a second process cannot silently bind
the configured port. Stop the manual process before returning to
`systemctl --user start noc-web`.

## Regression validation

```bash
./.venv/bin/python -m pytest tests
./.venv/bin/python -m pytest tests/test_frontend_modules.py
git diff --check
```

Run the focused installer, service, readiness, and launcher pytest modules
first; run the full suite after those pass. Passing automated service-context
and parser checks does not complete T029. Keep T029 open until the actual
workstation installer, managed service, health endpoint, and Windows shortcut
all succeed. The Windows Shell Link and hidden-window scenarios also require
the workstation acceptance run because Linux pytest cannot exercise Windows
Shell COM. The shortcut installer test must execute the installer process
under Windows PowerShell 5.1; static compatibility checks are insufficient.
Likewise, generated-VBS text assertions do not satisfy the Windows Script Host
regression requirement.
