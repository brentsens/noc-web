# SESAMI NOC Operations

SESAMI NOC Operations is a Windows-accessible NOC operations application backed
by a managed WSL/Ubuntu runtime. Operators use a branded Windows shortcut and
browser UI while noc-web runs locally in WSL.

The application, Windows launcher, installer build, automated tests, and
Windows regression tests are validated. **T050 genuine clean-workstation
acceptance remains pending.**

## Screenshots

<!-- SCREENSHOT: Main NOC Status dashboard
Future file: docs/images/noc-status.png
-->
<!-- ![Main NOC Status dashboard](docs/images/noc-status.png) -->

<!-- SCREENSHOT: Health and readiness page
Future file: docs/images/noc-health.png
-->
<!-- ![Health and readiness page](docs/images/noc-health.png) -->

<!-- SCREENSHOT: Windows SESAMI NOC Operations shortcut and browser launch
Future file: docs/images/windows-launch.png
-->
<!-- ![Windows SESAMI NOC Operations shortcut and browser launch](docs/images/windows-launch.png) -->

## What It Does

SESAMI NOC Operations supports the operational workflow from shift startup to
handover:

- Shift startup, NOC status/dashboard, and health/readiness checks
- Ticket workflow and investigations
- AI-assisted operational work, with human review
- Shift notes and handover/end-shift workflow

## How It Works

```text
Windows
  |
SESAMI NOC Operations shortcut
  |
hidden Windows launcher
  |
WSL / Ubuntu
  |
noc-web.service
  |
localhost health check
  |
default Windows browser
  |
SESAMI NOC Operations
```

NOC Web listens only on `127.0.0.1:8000`. Normal operators do not need to keep
a WSL terminal open.

## Architecture

**Windows**

- `SESAMI-NOC-Operations-Setup.exe`
- Branded SESAMI NOC Operations shortcut
- Hidden Windows launcher
- Default browser

**WSL / Ubuntu**

- noc-web
- Python `.venv`
- `noc-web.service` systemd user service
- noc-tools
- Operational CLI integrations

Feature 011 owns the managed runtime, health checks, launcher, service,
`runtime.json`, shortcut, and controlled environment. Feature 012 owns fresh
installation, trusted acquisition, provisioning, repair/rerun behavior,
Windows packaging, and the Feature 011 handoff.

## Fresh Installation

```text
SESAMI-NOC-Operations-Setup.exe
  |
Windows / WSL preflight
  |
verified trusted releases
  |
noc-web v1.0.3 + noc-tools v1.0.1
  |
provisioning
  |
Feature 011 managed runtime
  |
SESAMI NOC Operations shortcut
  |
browser
```

Run the installer from Windows. Operators should not need to manually clone
noc-web or noc-tools. Consequential WSL and prerequisite changes remain
operator-controlled.

## Trusted Distribution

| Component | Repository | Release |
|---|---|---|
| noc-web | `brentsens/noc-web` | `v1.0.3` |
| noc-tools | `brentsens/noc-tools` | `v1.0.1` |

Trusted acquisition verifies the pinned SHA-256 digest and GitHub SLSA
provenance, including repository identity, tag identity, and approved
signer-workflow identity. The required noc-tools compatibility result is:

```text
noc-inv-contract=1
```

## noc-tools

The approved distribution provides:

```text
tix
noc-start
noc-status
noc-inv
noc-handover
```

Installation does not require a `~/code/noc-tools` checkout.

## Integrations and Readiness

| State | Meaning |
|---|---|
| `READY` | The bounded availability and applicable authentication or compatibility check succeeded. |
| `SETUP_REQUIRED` | The software, operator sign-in, site access, or configuration needs action. |
| `UNAVAILABLE` | A command, approved artifact, compatibility check, or bounded probe failed. |

Readiness independently reports Atlas Jira, GitHub Copilot CLI, Microsoft 365,
Datadog MCP, and noc-tools. Authentication is operator-specific. Credentials,
tokens, cookies, sessions, and another operator's authentication are never
bundled or copied by the installer.

## Safety Model

- Localhost-only binding
- Read-only defaults and explicit confirmation for consequential actions
- AI output is advisory and human-reviewed
- Fail-closed release verification
- No bundled credentials, tokens, or sessions
- Controlled systemd PATH
- Failed repair preserves the previous valid installation
- Pytest regression coverage isolates operational state
- Backend API and frontend UI contracts change together

## Repair and Reinstall

Installer reruns are idempotent. They preserve valid:

- `runtime.json`
- Operator configuration and operational records
- Investigations and shift/handover data
- Authentication and session material
- Compatible noc-tools

Reruns avoid duplicate services, launchers, shortcuts, virtual environments,
runtime configurations, and tools.

## Building the Windows Installer

Prerequisites:

- Windows PowerShell 5.1
- Inno Setup 6
- Approved SESAMI branding asset

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\packaging\windows\generate-icon.ps1

powershell.exe -ExecutionPolicy Bypass -File .\packaging\windows\build-installer.ps1
```

Output:

```text
dist\windows\SESAMI-NOC-Operations-Setup.exe
```

ICO generation was validated on Windows, and Inno Setup 6.7.3 compilation was
validated. The current EXE is **NotSigned** by Authenticode. Do not treat the
installer as digitally signed.

## Development

WSL/Ubuntu is the development and runtime environment. From the repository:

```bash
source .venv/bin/activate
python -m pytest -q
```

## Validation

Current validated state:

- pytest: **526 passed**
- `git diff --check`: passed
- Windows Pester 6.2.0: **9 passed, 0 failed, 0 skipped**
- Windows ICO generation: passed
- Inno Setup 6.7.3 build: passed
- Installer artifact generated successfully
- **T050 clean-workstation acceptance: PENDING**

T050 must execute on a genuinely clean supported Windows/WSL workstation. Do
not claim fresh-machine acceptance until that result is recorded.

## Troubleshooting

Run these commands in the WSL/Ubuntu runtime:

```bash
systemctl --user status noc-web --no-pager -l
journalctl --user -u noc-web -n 100 --no-pager
curl -sS http://127.0.0.1:8000/api/health
systemd-analyze --user verify ~/.config/systemd/user/noc-web.service
command -v atlas
command -v copilot
command -v noc-inv
noc-inv --contract-version
```

The hidden Windows launcher is stored under:

```text
%LOCALAPPDATA%\SESAMI\NOC Operations\launch-hidden.vbs
```

The shortcut uses the Windows Desktop known folder and supports a
OneDrive-redirected Desktop.

## Repository Layout

| Path | Purpose |
|---|---|
| `backend/` | FastAPI application, services, and operational logic |
| `frontend/` | Static browser UI |
| `scripts/` | Runtime, bootstrap, and Windows launcher scripts |
| `packaging/windows/` | Inno Setup package, manifest, icon, and build tooling |
| `assets/windows/` | Approved SESAMI branding asset |
| `tests/` | Python and Windows Pester regression coverage |
| `specs/` | Feature specifications, plans, contracts, and task records |

## Project Status

Feature 011: implemented and accepted.

Feature 012: implemented and converged.

T050: pending genuine clean-workstation acceptance.
