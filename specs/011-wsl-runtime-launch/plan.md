# Implementation Plan: WSL Runtime and Windows Launch

**Branch**: `011-wsl-runtime-launch` | **Date**: 2026-11-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/011-wsl-runtime-launch/spec.md`

## Summary

Provide an idempotent installer for a user-owned WSL systemd service, extend
the existing workstation readiness flow to report core and optional
capabilities independently, and install a per-user Windows shortcut that
starts the service through a hidden launcher and opens the default browser only
after bounded localhost health succeeds. Keep runtime configuration
credential-free and separate from operator-owned NOC records and tool
authentication. Launch the service entry point as a Python module from the
validated repository working directory, with no dependency on shell
activation or inherited `PYTHONPATH`. Generate the unit using
directive-specific systemd syntax and require native user-unit verification
and service-context execution in automated regression tests. Execute the
shortcut installer under Windows PowerShell 5.1, trust a reparse point only
for the exact Desktop path returned by the Windows known-folder API, retain
strict LocalAppData and custom-destination checks, and report shortcut
installation failure with a safe category as well as the generic failure code.
The hidden VBScript resolves and invokes the Windows WSL executable explicitly,
quotes every configured argument for Windows command-line parsing, and reports
an unexpected Windows Script Host launch result separately from verified WSL
unavailability. The service PATH adds only the trusted
`/home/linuxbrew/.linuxbrew/Homebrew/bin` location for supported Linuxbrew
dependencies; it does not inherit interactive-shell or Windows PATH entries.
Missing external tools disable only their dependent workflows.

## Technical Context

**Language/Version**: Python 3.10+ application runtime; Bash setup entry point;
Windows Script Host and Windows PowerShell 5.1 for shortcut integration. The
current local validation environment uses Python 3.15.

**Primary Dependencies**: FastAPI, Pydantic, Uvicorn; pinned application
dependencies will be separated from test-only dependencies. No new Python
runtime dependency is required for the installer or launcher.
`systemd-analyze` is a required host-side test utility, not an application
runtime dependency.

**Storage**: Existing file-backed NOC data remains in place. Add a validated,
credential-free per-user runtime configuration under
`${XDG_CONFIG_HOME:-$HOME/.config}/noc-web/`, a generated systemd user unit,
and per-user Windows launcher files/shortcut. Installation must not manage
operational records or external-tool authentication.

**Testing**: Focused pytest coverage for setup, service generation, readiness,
dependency gates, and failure preservation; automated service-generation tests
must run `systemd-analyze --user verify` and fail if the validator is missing
or rejects the unit. Service-context regression must execute the generated
unit's `ExecStart` in a subprocess using the declared working directory and
environment, with inherited `VIRTUAL_ENV` and `PYTHONPATH` removed, and verify
startup passes the `backend` import boundary. Windows regression coverage must
execute the shortcut installer with Windows PowerShell 5.1, exercise an
OS-reported Desktop redirected through a reparse point, reject arbitrary
configured reparse-point destinations, retain strict LocalAppData checks, and
assert safe categorized install failures. Also run frontend ES-module
validation; Linux unit tests with mocked Windows/systemd boundaries; a
separate supported Windows/WSL acceptance run; and, where Windows Script Host
is available, execute the generated VBScript through both its console and
hidden hosts to verify the actual command and result categorization. Then run
the full pytest suite and `git diff --check`.
Service-environment regression coverage must also verify a supported
Linuxbrew-installed dependency is discoverable through the explicit allowlist
while Windows and unallowlisted interactive-shell paths remain absent.

**Target Platform**: WSL2 Linux distributions with systemd enabled, launched
from Windows 10/11 for the ordinary operator flow. The application listener
and health URL remain localhost-only.

**Project Type**: File-backed Python/FastAPI web application with static HTML,
CSS, and JavaScript frontend and local OS integration.

**Performance Goals**: Launcher health wait is bounded to 60 seconds by
default; command probes and setup health checks are individually bounded.
Normal launch reuses the service and opens the browser only after health
succeeds.

**Scale/Scope**: One configured Windows user and one selected WSL distribution
per installation; no multi-user or fleet-management behavior is introduced.

**Constraints**: Service runs as the current unprivileged user, binds only to
127.0.0.1, and has bounded restart behavior. No credentials in configuration,
shortcut, responses, or logs. External tools remain separately managed.
Repeated install/update must preserve valid configuration and all operational
data. No system-wide root-owned application service or implicit provider
fallback. The systemd unit invokes `scripts.run_service` through the selected
virtual-environment interpreter with `-m` and uses the validated repository
root as `WorkingDirectory`; service startup must not rely on shell activation
or inherited `PYTHONPATH`. Only the exact Desktop path returned by
`Environment.GetFolderPath("DesktopDirectory")` may be a reparse point;
arbitrary configured shortcut destinations and LocalAppData install paths
retain conservative checks. Shortcut installation failures expose an
allowlisted safe reason category alongside `SHORTCUT_INSTALL_FAILED`, never
raw exception text. The generated VBScript calls the resolved Windows
`wsl.exe` executable with Windows-quoted, validated arguments; a `Run` result
such as `-1` is `WINDOWS_LAUNCH_EXECUTION_FAILED`, not WSL/distribution
unavailability. The service PATH includes only
`/home/linuxbrew/.linuxbrew/Homebrew/bin` in addition to its existing fixed
Linux paths; it does not derive or inherit an operator shell PATH.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate |
|---|---|
| I. Preserve Operational Data Integrity | Pass: validate configured paths and identifiers before use; atomically replace only NOC Web-owned config/unit/launcher artifacts; never remove NOC operational records. |
| II. Fail Safely and Explain Failures | Pass: bounded subprocess and health checks, explicit dependency status, redacted failure codes, and no success-shaped fallback. |
| III. Maintain API and UI Contract Consistency | Pass: extend the existing readiness response and update its frontend consumer and error behavior in the same change. |
| IV. Test Operational Workflows | Pass: isolate data in temporary directories, mock external processes in unit tests, execute the generated service entry point as a subprocess with `VIRTUAL_ENV` and `PYTHONPATH` removed, verify generated service syntax with the required native systemd validator, and run workstation acceptance without accessing live operational data. |
| V. Prefer Simple, Observable Changes | Pass: reuse Feature 005 readiness/configuration and existing service/API boundaries; add only installer, runtime, and Windows-launch integration needed by the feature. |
| VI. Require Deliberate Operational Execution | Pass: readiness and launch are read-only; they do not invoke external mutations or bypass existing action confirmations. |

No pre-design gate failures or constitution exceptions.

## Project Structure

### Documentation (this feature)

```text
specs/011-wsl-runtime-launch/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── installer-and-service.md
│   ├── readiness.md
│   └── windows-launcher.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── api/readiness.py
├── config.py
└── services/
    ├── readiness.py
    └── dependency_readiness.py
frontend/
├── readiness.html
└── js/api.js
scripts/
├── __init__.py
├── install.sh
├── run_service.py
└── windows/
    ├── install-shortcut.ps1
    ├── launch-hidden.vbs.in
    ├── launcher.py
    └── launch.py
systemd/
└── noc-web.service.in
requirements.txt
docs/
└── workstation-runtime.md
tests/
├── test_runtime_installer.py
├── test_runtime_service.py
├── test_dependency_readiness.py
└── test_windows_launcher.py
```

**Structure Decision**: Extend the existing Python/FastAPI backend, static
readiness page, and pytest suite. Keep the systemd template and installer
artifacts at repository level. Linux-side tests mock Windows COM, WSL, and
systemd boundaries; Windows PowerShell 5.1 integration coverage executes the
shortcut installer and exercises the Desktop trust policy; an opt-in
Windows/WSL acceptance test exercises actual shortcut creation and launch.

## Constitution Check (Post-Design)

| Principle | Result |
|---|---|
| I. Preserve Operational Data Integrity | Pass: runtime config and generated artifacts are NOC Web-owned; installation writes them atomically with backup/validation and never traverses into or removes operational-data locations. |
| II. Fail Safely and Explain Failures | Pass: core health is independent of optional dependencies; each dependency has a bounded, redacted status; the fixed Linuxbrew PATH allowlist makes supported dependencies discoverable without inheriting unsafe shell context; shortcut installation reports a safe failure category without raw exceptions. |
| III. Maintain API and UI Contract Consistency | Pass: the existing GET readiness endpoint remains the contract, with the frontend Recheck action consuming the same response shape. |
| IV. Test Operational Workflows | Pass: unit tests use temp roots and stub processes, execute the generated service entry point with `VIRTUAL_ENV` and `PYTHONPATH` removed, require `systemd-analyze --user verify` for generated units, execute the shortcut installer under Windows PowerShell 5.1 with Desktop reparse-point and unsafe-destination cases, execute generated VBS through Windows Script Host where available, and platform acceptance uses a designated test distro and isolated test configuration. |
| V. Prefer Simple, Observable Changes | Pass: no second health system or runtime package manager is added; service manager and journal remain the operational observability path. |
| VI. Require Deliberate Operational Execution | Pass: installation creates only local runtime artifacts; startup and probes do not mutate Jira, Datadog, email, or NOC operational records. |

Post-design gates pass. The Windows/WSL boundary and narrow OS-reported
Desktop reparse-point exception are required by the specified operator
workflow and are isolated behind installer/launcher contracts; arbitrary
shortcut destinations and LocalAppData remain strictly validated. No
constitution exception is required.
