# SESAMI NOC Operations

**SESAMI NOC Operations** is a locally hosted NOC operations platform that brings shift management, ticket tracking, investigations, operational health, AI-assisted analysis, and shift handover into one interface.

The application runs in WSL using a Python/FastAPI backend with a lightweight browser UI. It integrates with Atlas Jira, Datadog, Microsoft 365, DeepSeek, and optional local Ollama inference.

> **Design principle:** External systems provide data, inference, or transport. NOC Web owns workflow state, evidence validation, safety controls, human approval, and operational persistence.

<!-- SCREENSHOT: Main dashboard
Suggested path: docs/images/dashboard.png
![SESAMI NOC Operations dashboard](docs/images/dashboard.png)
-->

## What It Does

SESAMI NOC Operations supports the NOC workflow from shift startup through handover:

- Start and manage NOC shifts
- Track Jira tickets and next actions
- View operational status, health, and readiness
- Retrieve read-only Datadog incident evidence
- Create evidence-grounded investigations
- Run AI Assistant questions and operational AI Actions
- Review AI-generated work before treating it as operational fact
- Generate deterministic shift handovers
- Ensure all validated open tickets are included in the handover
- Preview and send approved handovers through Microsoft 365
- Use DeepSeek as the primary AI provider
- Optionally use Ollama with `qwen3:8b` as a local AI provider

Core operational workflows no longer depend on GitHub Copilot CLI, `noc-inv`, or `noc-handover`.

## Application Architecture

```text
Browser UI
    │
    ▼
Python / FastAPI
    │
    ├── API Routes
    ├── Workflow Services
    ├── Evidence Collection
    ├── Validation
    ├── Safety / Confirmation
    └── Local Persistence
              │
              ▼
        Provider Adapters
              │
       ┌──────┼────────┬─────────┬────────┐
       ▼      ▼        ▼         ▼        ▼
   DeepSeek Ollama  Datadog    Atlas    m365
     HTTP    HTTP   REST API   Jira CLI  CLI
```

The provider layer deliberately does not own operational policy:

- Datadog provides evidence.
- DeepSeek and Ollama provide advisory inference.
- Atlas provides Jira access.
- `m365` provides Microsoft 365 transport.
- Python determines whether data and AI output are acceptable.

## Safety Model

SESAMI NOC Operations follows a fail-closed design.

### AI is treated as untrusted input

AI output is not accepted simply because a model returned it.

```text
Evidence
    │
    ▼
AI Provider
    │
    ▼
Strict Output Schema
    │
    ▼
Evidence ID Validation
    │
    ▼
Freshness / Provenance Validation
    │
    ▼
Workflow Safety Rules
    │
    ├── Valid ──────► Continue
    └── Invalid ────► Fail Closed
```

Important controls include:

- Strict response schemas
- Exact evidence-ID validation
- Unsupported evidence references are rejected
- Stale evidence must be identified as stale
- Partial evidence cannot be represented as complete
- Provider output is bounded by size and structure
- AI output remains advisory until human review
- Read-only Datadog access
- Explicit confirmation for consequential actions
- No automatic AI-provider fallback
- No bundled credentials, tokens, or sessions
- Credentials are excluded from AI prompts and persisted operational output
- Frontend and backend API contracts are regression-tested together

Local Ollama inference passes through the same downstream safety controls as DeepSeek.

## Operator Workflow

### 1. Start Shift

The Start Shift workflow prepares the selected NOC shift and verifies the workstation environment.

```text
Select Shift
    │
    ▼
Preflight
    │
    ▼
Workspace
    │
    ├── Tickets
    ├── Notes
    ├── Investigations
    └── Operational Status
```

<!-- SCREENSHOT: Start Shift
Suggested path: docs/images/start-shift.png
![Start Shift workflow](docs/images/start-shift.png)
-->

### 2. Tickets

NOC Web combines operational ticket information with locally tracked next actions.

The application uses Atlas as its Jira integration while Python owns ticket normalization, workflow state, validation, and presentation.

```text
NOC Web
    │
    ▼
Atlas
    │
    ▼
Jira
```

<!-- SCREENSHOT: Tickets
Suggested path: docs/images/tickets.png
![Ticket workflow](docs/images/tickets.png)
-->

### 3. Assistant and AI Actions

The Assistant provides evidence-grounded operational analysis.

DeepSeek is the primary provider. Operators can explicitly choose local Ollama where supported.

```text
NOC Evidence
    │
    ▼
Selected AI Provider
    │
    ▼
Structured Output
    │
    ▼
NOC Web Validation
    │
    ▼
Advisory Response
```

The AI cannot directly modify tickets, investigations, Datadog objects, Microsoft 365 objects, or other operational state.

<!-- SCREENSHOT: Assistant provider selector and response
Suggested path: docs/images/assistant-providers.png
![Assistant provider selection](docs/images/assistant-providers.png)
-->

### 4. Investigations

Investigation generation uses validated read-only Datadog evidence.

```text
Datadog Incident
      │
      ▼
Incident Evidence
      │
      ├── Notebook
      └── Monitor Evidence
             │
             ▼
      Evidence Preview
             │
             ▼
     Operator Confirmation
             │
             ▼
       AI Generation
             │
             ▼
      Strict Validation
             │
             ▼
       Ready for Review
```

AI-generated investigation content does not automatically become reviewed operational fact.

Investigation persistence includes provenance and generation state separately from reviewed findings.

<!-- SCREENSHOT: Investigation evidence preview
Suggested path: docs/images/investigation-preview.png
![Investigation evidence preview](docs/images/investigation-preview.png)
-->

<!-- SCREENSHOT: Ready for Review
Suggested path: docs/images/investigation-review.png
![Investigation ready for review](docs/images/investigation-review.png)
-->

### 5. End Shift and Handover

Handover generation separates deterministic operational facts from AI assistance.

```text
Tickets
Investigations
Shift Notes
Datadog Context
Status / Readiness
       │
       ▼
Validated Evidence
       │
       ▼
Deterministic Handover
       │
       ▼
Bounded AI Assistance
       │
       ▼
Validation
       │
       ▼
Operator Review
       │
       ▼
Delivery Preview
       │
       ▼
Explicit Confirmation
       │
       ▼
Microsoft 365
```

All validated open tickets are included deterministically. The AI provider does **not** decide which open tickets appear in the handover.

The final handover remains operator-controlled and is delivered through Microsoft 365 only after confirmation.

<!-- SCREENSHOT: End Shift / handover
Suggested path: docs/images/end-shift.png
![End Shift handover](docs/images/end-shift.png)
-->

## Requirements

The supported workstation architecture is:

- Windows 11
- WSL2
- Supported Ubuntu distribution
- Python runtime used by NOC Web
- `systemd --user`
- GitHub CLI for trusted-release acquisition
- Atlas for Jira integration where Jira functionality is required
- Microsoft 365 CLI (`m365`) for handover email delivery

Provider-specific requirements depend on which integrations are enabled:

- DeepSeek API credentials
- Datadog read-only API credentials
- Optional network-accessible Ollama server
- Microsoft 365 operator authentication

Homebrew is optional.

`jq` is optional and does not block core NOC Web installation.

## Fresh Installation

SESAMI NOC Operations currently has two installation frontends.

### Option 1: WSL-native bootstrap

**Recommended baseline and fallback when the Windows installer is blocked by application-control policy.**

Do **not** use `curl | bash`.

Download the pinned release assets explicitly and verify them before installation.

```bash
gh release download v1.0.4 -R brentsens/noc-web \
  -p noc-web-v1.0.4.tar.gz \
  -p noc-web-v1.0.4.sha256
```

Verify the checksum:

```bash
sha256sum -c noc-web-v1.0.4.sha256
```

Verify release provenance:

```bash
gh attestation verify noc-web-v1.0.4.tar.gz \
  --repo brentsens/noc-web \
  --signer-workflow brentsens/noc-web/.github/workflows/release.yml \
  --source-ref refs/tags/v1.0.4
```

Extract the verified package:

```bash
tar -xzf noc-web-v1.0.4.tar.gz
cd noc-web-*
```

Run the installer:

```bash
./scripts/install-sesami.sh \
  --confirm-prerequisites \
  --github-cli-approved \
  --confirm-replacement \
  --confirm-noc-tools
```

The installer creates the managed WSL runtime and Windows Desktop launch path.

### Option 2: Windows Installer

The existing Windows frontend is:

```text
SESAMI-NOC-Operations-Setup.exe
```

Installation flow:

```text
Windows Installer
      │
      ▼
Windows / WSL Preflight
      │
      ▼
Trusted Release Verification
      │
      ▼
Managed WSL Runtime
      │
      ▼
SESAMI NOC Operations Shortcut
```

On systems enforcing Smart App Control or similar application-control policies, the unsigned installer may require Authenticode signing or an approved allowlisting exception.

Use the WSL-native installation path when the Windows executable is blocked.

> Genuine clean-workstation acceptance for both installation frontends should not be claimed until it has been recorded against a supported clean Windows/WSL workstation.

## Provider Configuration

Provider configuration is separated into managed environment files under:

```text
~/.config/noc-web/
```

The managed `systemd` service loads the applicable provider files.

### DeepSeek

DeepSeek is the normal primary AI provider.

Configuration is stored in:

```text
~/.config/noc-web/ai-provider.env
```

The actual API credential should never be committed to Git.

After changing provider configuration:

```bash
systemctl --user restart noc-web.service
```

### Datadog

Datadog incident and investigation evidence uses the direct read-only Datadog API provider.

Configuration is stored separately in:

```text
~/.config/noc-web/datadog-provider.env
```

The Datadog provider is intentionally read-only.

NOC Web does not grant AI providers permission to modify Datadog resources.

### Local Ollama

Ollama is an optional local inference provider.

Configuration:

```text
~/.config/noc-web/ollama-provider.env
```

Example:

```ini
NOC_WEB_OLLAMA_BASE_URL=http://OLLAMA_HOST:11434
NOC_WEB_OLLAMA_MODEL=qwen3:8b
```

Protect the configuration file:

```bash
chmod 600 ~/.config/noc-web/ollama-provider.env
```

Verify the Ollama host from WSL:

```bash
curl -sS http://OLLAMA_HOST:11434/api/tags
```

The currently validated local model is:

```text
qwen3:8b
```

The Ollama server may run on another workstation such as a GPU-equipped desktop.

The Ollama host can be offline or asleep without making core NOC Web unavailable.

### Microsoft 365

Microsoft 365 is used for approved handover delivery.

Check authentication using:

```bash
m365 auth status
```

A normal delivery flow is:

```text
Generate Handover
      │
      ▼
Review
      │
      ▼
Preview Delivery
      │
      ▼
Confirm Send
      │
      ▼
Microsoft 365
```

Delivery remains separate from AI generation.

### Atlas Jira

Atlas remains an external Jira integration.

Conceptually:

```text
NOC Web Python
      │
      ▼
Atlas CLI
      │
      ▼
Jira
```

Atlas being an external CLI does not make the NOC workflow Bash-driven. Python remains responsible for application logic, validation, workflow state, and safety.

## Local AI and Provider Selection

The default architecture is:

```text
DeepSeek API
   PRIMARY
      │
      │ failure
      ▼
  FAIL CLOSED
      │
      ▼
Operator decides whether
to Retry with Local AI
      │
      ▼
Explicit Confirmation
      │
      ▼
Ollama / qwen3:8b
```

There is **no automatic DeepSeek-to-Ollama fallback**.

Operators may also explicitly select Ollama on supported per-request workflows.

### Ollama response isolation

Ollama returns inference metadata in addition to model output.

NOC Web consumes only the model `response`.

Fields such as:

```text
thinking
context
total_duration
load_duration
eval_duration
```

are not treated as operational output.

They do not enter downstream AI validation or persisted NOC operational records.

## Workstation Runtime

Normal operators launch SESAMI NOC Operations from Windows.

```text
Windows Desktop
      │
      ▼
SESAMI NOC Operations Shortcut
      │
      ▼
Microsoft wsl.exe
      │
      ▼
~/.local/bin/sesami-noc-launch
      │
      ▼
noc-web.service
      │
      ▼
Python / FastAPI
      │
      ▼
127.0.0.1:8000
      │
      ▼
Default Windows Browser
```

NOC Web listens only on:

```text
127.0.0.1:8000
```

Normal operators do not need to keep an interactive WSL terminal open.

The WSL-native shortcut launches Microsoft's installed `wsl.exe`. The Windows installer may retain the Feature 011 hidden `wscript` launcher for compatibility.

## Trusted Distribution

Current trusted release components:

| Component | Repository | Release |
|---|---|---|
| noc-web | `brentsens/noc-web` | `v1.0.4` |
| noc-tools | `brentsens/noc-tools` | `v1.0.1` |

Trusted acquisition validates:

- Pinned SHA-256 digest
- GitHub artifact attestation
- Repository identity
- Release tag identity
- Approved release workflow identity

Installation does not require a permanent `~/code/noc-tools` checkout.

## Repair and Reinstall

Installer reruns are designed to be idempotent.

Valid existing state is preserved, including:

- `runtime.json`
- Operator configuration
- Operational records
- Investigations
- Shift and handover data
- Authentication/session material
- Compatible optional tooling

Reruns should avoid creating duplicate:

- Services
- Launchers
- Shortcuts
- Virtual environments
- Runtime configurations
- Tools

A failed repair must preserve the previous valid installation.

## Troubleshooting

Run these commands from the WSL/Ubuntu runtime.

### Service status

```bash
systemctl --user status noc-web.service --no-pager -l
```

### Recent logs

```bash
journalctl --user -u noc-web.service \
  --since "10 minutes ago" \
  --no-pager
```

### API health

```bash
curl -sS http://127.0.0.1:8000/api/health
```

### Validate systemd unit

```bash
systemd-analyze --user verify \
  ~/.config/systemd/user/noc-web.service
```

### Atlas

```bash
command -v atlas
```

### Microsoft 365

```bash
m365 auth status
```

### Ollama

```bash
curl -sS http://OLLAMA_HOST:11434/api/tags
```

If the Ollama server is on another PC and fails after a restart or sleep cycle:

1. Confirm the remote PC is awake.
2. Confirm Ollama is listening on port `11434`.
3. Confirm the host/IP is still correct.
4. Update `NOC_WEB_OLLAMA_BASE_URL` if the DHCP address changed.
5. Restart `noc-web.service`.

## Development

WSL/Ubuntu is the primary development and runtime environment.

From the repository:

```bash
source .venv/bin/activate
python -m pytest -q
```

Also run:

```bash
git diff --check
```

The project maintains regression coverage for:

- Backend workflow contracts
- Frontend/backend API consistency
- Provider isolation
- AI schema and evidence validation
- Datadog read-only guarantees
- Investigation generation
- Handover generation
- Ollama integration
- Local retry behavior
- Runtime installation
- Windows packaging

The exact test count is intentionally not documented here because the suite continues to grow.

## Building the Windows Installer

The Inno Setup source and build scripts remain supported for the Windows frontend.

Prerequisites:

- Windows PowerShell 5.1
- Inno Setup 6
- Approved SESAMI branding asset

Generate the icon:

```powershell
powershell.exe -ExecutionPolicy Bypass `
  -File .\packaging\windows\generate-icon.ps1
```

Build:

```powershell
powershell.exe -ExecutionPolicy Bypass `
  -File .\packaging\windows\build-installer.ps1
```

Output:

```text
dist\windows\SESAMI-NOC-Operations-Setup.exe
```

The current Windows installer should not be treated as Authenticode-signed unless signing has been independently verified.

## Repository Layout

| Path | Purpose |
|---|---|
| `backend/` | FastAPI routes, workflow services, providers, validation, persistence, and operational logic |
| `frontend/` | Static browser UI and API client |
| `scripts/` | Runtime, bootstrap, installer, and launcher tooling |
| `systemd/` | Managed WSL user-service template |
| `packaging/windows/` | Windows installer, manifest, icon, and build tooling |
| `assets/windows/` | SESAMI Windows branding |
| `tests/` | Backend, frontend-contract, integration, runtime, and security regression coverage |
| `specs/` | Feature specifications, plans, research, contracts, checklists, and task history |
| `docs/` | Runtime and supporting technical documentation |

## Legacy Compatibility

SESAMI NOC Operations is being migrated away from legacy shell-driven workflow orchestration.

Optional `noc-tools` compatibility may still provide:

```text
tix
noc-start
noc-status
noc-inv
noc-handover
```

However, the core modern workflows no longer require `noc-inv` or `noc-handover` for:

- AI Assistant
- Datadog evidence retrieval
- Investigation generation
- Handover generation

GitHub Copilot CLI may remain available as a compatibility capability but is not required for the provider-independent workflows.

Atlas Jira and `m365` are intentionally retained as bounded external adapters. The modernization target is **Python-owned workflow logic**, not necessarily zero subprocess calls.

## Project Status

The current architecture includes:

- Managed WSL runtime
- Browser-based operator interface
- Python/FastAPI workflow orchestration
- Jira ticket workflow through Atlas
- Direct read-only Datadog provider
- Provider-independent AI Assistant and AI Actions
- Evidence-grounded investigation generation
- Deterministic handover generation
- Microsoft 365 handover delivery
- DeepSeek primary AI inference
- Optional Ollama / `qwen3:8b` local inference
- Explicit provider selection
- Confirmation-gated local AI retry
- Strict AI output and evidence validation
- Fail-closed provider behavior

Feature-level design decisions, acceptance criteria, contracts, research, implementation plans, and task history are maintained under:

```text
specs/
```

The remaining modernization work is primarily around legacy shell compatibility and clean-workstation installation validation rather than the core provider-independent NOC workflows.

## Suggested Screenshots

Before publishing screenshots, sanitize customer names, internal ticket contents, email addresses, Datadog URLs, internal IP addresses, tokens, and other operationally sensitive information.

Recommended files:

```text
docs/images/
├── dashboard.png
├── start-shift.png
├── tickets.png
├── assistant-providers.png
├── investigation-preview.png
├── investigation-review.png
├── end-shift.png
└── health-providers.png
```
