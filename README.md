# SESAMI NOC Operations

SESAMI NOC Operations is a Windows-accessible NOC operations application backed
by a managed WSL runtime. Operators use a branded Windows shortcut and browser
UI while noc-web runs locally in WSL.

Two installation frontends share the same trusted-release and Feature 011
runtime engine:

1. **WSL-native bootstrap** (`scripts/install-sesami.sh`) — supported baseline
   and unsigned-install fallback when a Windows EXE is blocked.
2. **`SESAMI-NOC-Operations-Setup.exe`** — existing Windows wizard frontend.
   May require Authenticode signing or application-control approval on systems
   enforcing Smart App Control.

Automated tests and packaging regressions are validated. **Genuine
clean-workstation acceptance for both frontends remains pending.**

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
Windows Desktop
  |
SESAMI NOC Operations shortcut
  |
Microsoft wsl.exe
  |
SESAMI Linux launcher (~/.local/bin/sesami-noc-launch)
  |
noc-web.service
  |
/api/health
  |
default Windows browser
  |
http://127.0.0.1:8000
```

The Windows EXE path may still install Feature 011's hidden `wscript` launcher
for compatibility. The WSL-native path creates a Desktop shortcut that targets
Microsoft's installed `wsl.exe` only — no custom unsigned Windows executable is
required for daily launch.

NOC Web listens only on `127.0.0.1:8000`. Normal operators do not need to keep
a WSL terminal open after installation.

## Architecture

**Windows**

- Optional `SESAMI-NOC-Operations-Setup.exe` wizard frontend
- Branded SESAMI NOC Operations Desktop shortcut
- Microsoft `wsl.exe` (WSL-native daily launch path)
- Default browser

**WSL**

- `scripts/install-sesami.sh` bootstrap frontend
- noc-web (`v1.0.4`)
- Python `.venv`
- `noc-web.service` systemd user service
- `~/.local/bin/sesami-noc-launch`
- Optional noc-tools (`v1.0.1`)
- Operational CLI integrations (Atlas/Copilot/M365 remain optional); Datadog uses a direct read-only API provider

Feature 011 owns the managed runtime, health checks, service, `runtime.json`,
and controlled environment. Feature 012 owns fresh installation frontends,
trusted acquisition, provisioning, repair/rerun behavior, Windows packaging,
and the Feature 011 handoff.

## Fresh Installation

### 1. WSL-native bootstrap (supported baseline / unsigned fallback)

Do **not** use `curl | bash`. Download the pinned release assets explicitly,
verify integrity, then run the installer from the verified tree:

```bash
# From Windows, open your WSL2 distribution terminal as a non-root operator.
gh release download v1.0.4 -R brentsens/noc-web \
  -p noc-web-v1.0.4.tar.gz -p noc-web-v1.0.4.sha256

# Optional helper shipped in a trusted checkout or prior verified tree:
# ./scripts/bootstrap/verify_bootstrap_bundle.sh \
#   --archive noc-web-v1.0.4.tar.gz \
#   --checksum noc-web-v1.0.4.sha256

# Or verify manually (pinned digest from packaging/windows/bootstrap-manifest.json):
sha256sum -c noc-web-v1.0.4.sha256
gh attestation verify noc-web-v1.0.4.tar.gz \
  --repo brentsens/noc-web \
  --signer-workflow brentsens/noc-web/.github/workflows/release.yml \
  --source-ref refs/tags/v1.0.4

tar -xzf noc-web-v1.0.4.tar.gz
cd noc-web-*   # extracted verified package root

./scripts/install-sesami.sh \
  --confirm-prerequisites \
  --github-cli-approved \
  --confirm-replacement \
  --confirm-noc-tools
```

That path reuses Feature 012 trusted acquisition and Feature 011 runtime
ownership, installs `~/.local/bin/sesami-noc-launch`, and creates the Desktop
shortcut targeting Windows-owned `wsl.exe`.

### 2. Windows EXE wizard

```text
SESAMI-NOC-Operations-Setup.exe
  |
Windows / WSL preflight
  |
verified trusted releases
  |
noc-web v1.0.4 + noc-tools v1.0.1
  |
Feature 011 managed runtime
  |
SESAMI NOC Operations shortcut
```

Run the EXE from Windows when application-control policy permits it. On
managed or Smart App Control systems, the unsigned EXE may be blocked until
Authenticode signing or an allowlisting exception is approved. Use the
WSL-native path above as the supported fallback.

Operators should not need to manually clone noc-web or noc-tools. Consequential
WSL and prerequisite changes remain operator-controlled. Homebrew remains
optional and is never installed automatically; `jq` remains optional and does
not block core noc-web installation.

## Trusted Distribution

| Component | Repository | Release |
|---|---|---|
| noc-web | `brentsens/noc-web` | `v1.0.4` |
| noc-tools | `brentsens/noc-tools` | `v1.0.1` |

Trusted acquisition verifies the pinned SHA-256 digest and GitHub SLSA
provenance, including repository identity, tag identity, and approved
signer-workflow identity. The legacy noc-tools compatibility result, when that
tool is installed for another workflow, is:

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

Readiness independently reports Atlas Jira, the configured AI provider, the
Datadog API provider, Microsoft 365, and legacy noc-tools. Datadog incident and
evidence retrieval uses a direct read-only API with a process-environment bearer
token. Datadog investigation generation uses Feature 015 read-only evidence and the
configured AI provider; it does not require noc-inv, GitHub Copilot CLI, or
Datadog MCP. Handover generation assembles all validated open tickets and factual
sections deterministically, then uses the configured AI provider for internal advisory
validation; the final handover remains deterministic and contains no AI-specific sections or
internal citation markers. It does not require noc-handover or Copilot CLI. Authentication
is operator-specific. Credentials, tokens, cookies,
sessions, and another operator's authentication are never bundled or copied by
the installer.

Assistant and AI Action inference additionally report the explicitly configured
provider (`deepseek-api`, `github-copilot-cli`, or `ollama`) and its static
readiness. The optional local Ollama provider requires only
`NOC_WEB_OLLAMA_BASE_URL` (no authentication secret), defaults to the `qwen3:8b`
model, and is available through explicit per-request selection or an explicitly
confirmed **Retry with Local AI** action after a primary failure. Static readiness
never contacts Ollama; the Status page provides an explicit probe that checks the
model list without inference. There is no automatic fallback or automatic retry. No
provider is selected by default, provider changes require a restart, and there is
no automatic fallback. Configure provider settings through the process
environment or the managed-service provider environment files
(`ai-provider.env`, `datadog-provider.env`, and the optional
`ollama-provider.env`) described in
[docs/workstation-runtime.md](docs/workstation-runtime.md). Credentials are never
returned by the API, written to logs, or persisted in reports.

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

The Inno Setup source and build scripts remain supported. Keep them for the
Windows wizard frontend even when the WSL-native path is preferred.

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
installer as digitally signed. Environments that enforce Smart App Control or
similar application control may require Authenticode signing or an explicit
allowlisting exception before the EXE can run.

## Development

WSL/Ubuntu is the development and runtime environment. From the repository:

```bash
source .venv/bin/activate
python -m pytest -q
```

## Validation

Current validated state:

- pytest: **569 passed**
- `git diff --check`: passed
- focused WSL-native / bootstrap / launcher regressions: passed
- Windows Pester 6.2.0 suite: available via
  `packaging/windows/run-pester-regression.ps1` (includes WSL-native shortcut
  contract checks; re-run on Windows after pulling these changes)
- Windows ICO generation / Inno Setup build: previously validated; EXE source
  retained
- **T050 clean-workstation acceptance (EXE and WSL-native): PENDING**

Do not claim fresh-machine acceptance for either frontend until that result is
recorded on a genuine clean supported Windows/WSL workstation.

## Troubleshooting

Run these commands in the WSL/Ubuntu runtime:

```bash
systemctl --user status noc-web --no-pager -l
journalctl --user -u noc-web -n 100 --no-pager
curl -sS http://127.0.0.1:8000/api/health
systemd-analyze --user verify ~/.config/systemd/user/noc-web.service
command -v atlas
# Optional only if another workflow still uses these legacy tools:
command -v copilot
command -v noc-inv
noc-inv --contract-version
```

WSL-native daily launch uses:

```text
Desktop\SESAMI NOC Operations.lnk
  -> %SystemRoot%\System32\wsl.exe
  -> --distribution <WSL_DISTRO_NAME> --exec ~/.local/bin/sesami-noc-launch
```

The EXE/Feature 011 path may still place a compatibility launcher under:

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
