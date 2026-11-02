# SESAMI NOC Operations

SESAMI NOC Operations is a Windows-launched NOC Web workstation application.
It keeps operational workflows read-only by default and requires explicit
operator confirmation for state-changing actions. The FastAPI backend and
static web UI run in a managed Ubuntu WSL runtime; Windows provides the
operator-facing installer, icon, shortcut, and default browser.

## Architecture and normal launch

Feature 011 owns the managed runtime: the Python virtual environment,
`noc-web.service`, `runtime.json`, localhost health check, controlled PATH,
hidden launcher, and one Desktop shortcut. Feature 012 acquires a verified
release and hands it to Feature 011; it does not create a competing service,
runtime configuration, or shortcut.

Normal launch is:

```text
SESAMI NOC Operations shortcut
  -> hidden WSL launcher
  -> noc-web.service
  -> localhost health check
  -> default Windows browser
```

The shortcut is installed through the Windows known Desktop folder, including
OneDrive-redirected Desktops. Its hidden launcher is stored under the current
user's Local AppData and runs without a persistent console window.

## Install or repair on a Windows workstation

The built installer is:

```text
dist/windows/SESAMI-NOC-Operations-Setup.exe
```

Use a supported Windows workstation with the approved Ubuntu WSL distribution
and user systemd enabled. Run the installer, then explicitly approve or decline
the proposed NOC Web repair/install and the separate optional noc-tools install.
WSL and Ubuntu platform setup are guide-only; the installer does not enable
WSL, install Ubuntu, reboot Windows, or sign in to any service.

Rerunning the installer reuses or repairs the deterministic per-user WSL
installation. It preserves valid `runtime.json`, the managed virtual
environment where appropriate, operator-owned NOC data, investigations,
shift/handover records, and compatible noc-tools. It does not duplicate the
service, runtime configuration, hidden launcher, or shortcut.

The installer uses the approved SESAMI branding asset to create the
multi-resolution installer icon and branded shortcut. The installer is
currently **NotSigned** by Authenticode; do not treat it as Authenticode
code-signed.

## Trusted release inputs

The bootstrap policy pins immutable approved releases:

| Component | Approved release |
|---|---|
| noc-web | `v1.0.3` |
| noc-tools | `v1.0.1` |

Before content is executed, bootstrap verifies the pinned SHA-256 digest and
published checksum asset, then verifies GitHub SLSA provenance against the
pinned repository, tag, and fully qualified signer workflow. Do not substitute
mutable branches, package-manager artifacts, or unapproved download sources.

The approved noc-tools distribution supplies:

```text
tix
noc-start
noc-status
noc-inv
noc-handover
```

`noc-inv --contract-version` must return:

```text
noc-inv-contract=1
```

## Identity and readiness

Software installation is separate from operator authentication. The installer
never bundles, copies, reads, migrates, or logs credentials, tokens, cookies,
sessions, or another operator's authentication material.

Atlas, GitHub Copilot CLI, Microsoft 365 CLI, Datadog MCP, and noc-tools are
independently assessed after core NOC Web setup:

| Status | Meaning |
|---|---|
| `READY` | The bounded availability and applicable authentication/compatibility check succeeded. |
| `SETUP_REQUIRED` | The software, operator sign-in, site access, or configuration needs operator action. |
| `UNAVAILABLE` | A command, approved artifact, compatibility check, or bounded probe failed. |

Atlas remains an operator-managed trusted Linuxbrew integration. A missing
Atlas binary is guided setup, not an installer-provided binary; Atlas readiness
uses `atlas auth status --json`. Missing optional integrations do not block
core NOC Web availability.

## Operator troubleshooting

From Windows PowerShell, replace `Ubuntu` only when your approved distribution
uses another configured name:

```powershell
wsl.exe -d Ubuntu -- systemctl --user status noc-web --no-pager
wsl.exe -d Ubuntu -- systemctl --user is-active noc-web
wsl.exe -d Ubuntu -- curl -fsS http://127.0.0.1:8000/api/health
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\bootstrap-status.ps1 -Distribution Ubuntu
```

For shortcut or launcher issues, verify the `SESAMI NOC Operations.lnk` file
in the Windows Desktop known folder and the launcher at:

```text
%LOCALAPPDATA%\SESAMI\NOC Operations\launch-hidden.vbs
```

Relevant recovery state is per-user and must be inspected without copying
secrets:

```text
~/.local/share/sesami-noc-operations/noc-web/
~/.local/state/sesami-noc-operations/installation-state.json
~/.config/noc-web/runtime.json
```

If service or health recovery is needed, use the commands above before
reinstalling. Do not delete operational data or authentication material as a
first recovery step.

## Development and maintenance

Develop inside the repository's WSL checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --requirement requirements.txt
.venv/bin/python -m uvicorn backend.app:app --reload
```

Run automated checks:

```bash
.venv/bin/pytest -q
git diff --check
```

Run the non-destructive Windows package regression suite from Windows
PowerShell with Pester 6.2.0:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packaging\windows\run-pester-regression.ps1
```

The runner stages only allowlisted test and package-contract resources in a
native temporary Windows directory, so it works when the repository is hosted
through `\\wsl$\`.

To build the installer, install Inno Setup 6 on Windows (the build script
discovers a per-user installation at
`$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe`), then run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packaging\windows\generate-icon.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\packaging\windows\build-installer.ps1
```

The trusted-release pipeline updates the pinned repository, tag, archive,
SHA-256, and signer workflow together; it then independently verifies
provenance and builds the package. Never publish credentials or private
download URLs in release inputs.

## Validation status

- Python tests: **526 passed**
- `git diff --check`: passed
- Windows Pester 6.2.0: **9 passed, 0 failed, 0 skipped**
- Windows ICO generation: passed
- Inno Setup 6.7.3 compilation: passed; the installer was produced
- **T050 clean-workstation acceptance remains pending.** It must run on a
  genuinely clean supported Windows/WSL workstation with no prior NOC Web
  checkout, Feature 011 runtime, shortcut, NOC data, noc-tools, or third-party
  authentication.
