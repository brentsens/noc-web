# NOC Web workstation runtime

The managed runtime lets the Windows operator open NOC Web from the
**SESAMI NOC Operations** shortcut without leaving a WSL terminal running.
Development, maintenance, Git operations, troubleshooting, and manual
`noc-tools` work may still use a terminal.

## Prerequisites and setup

Run setup from the expected NOC Web checkout inside the configured WSL
distribution:

```bash
./scripts/install.sh
```

Setup requires Python 3.10 or later, WSL systemd and Windows interoperability,
an unprivileged Linux account, and the permission needed to enable systemd
user lingering when it is not already enabled. Setup fails with a safe error
code if the user service manager or Windows shortcut cannot be configured; it
does not install a root-owned service.

The installer creates or updates the NOC-Web-owned virtual environment from
the pinned `requirements.txt`, validates the workstation configuration,
installs the per-user `noc-web.service`, starts it, checks localhost health,
and creates or updates one Windows shortcut named **SESAMI NOC Operations**.
It resolves the Windows Desktop through the current Windows user's known
folder; a configured shortcut folder is retained across updates. Re-running
setup updates the same shortcut and service.

The credential-free runtime configuration is stored at
`${XDG_CONFIG_HOME:-$HOME/.config}/noc-web/runtime.json`. The selected WSL
distribution is captured at setup and used explicitly by the launcher. Safe
defaults are localhost `http://127.0.0.1:8000` and a 60-second health wait;
the port and timeout are validated and bounded. Existing valid configuration
is reused, backed up before replacement, and never replaced by ambient
environment values. Invalid or unknown configuration stops setup before
managed runtime artifacts are replaced.

The installer owns only the NOC Web virtual environment, runtime
configuration, user unit, launcher support files, and named shortcut. It
never deletes or resets `~/noc` records, handovers, AI reports, Feature 009
incident cache, Feature 010 investigation history/lifecycle state, or external
tool authentication. Existing runtime configuration and service-unit
replacements retain `.bak` recovery copies.

## External capabilities

External tools are independently installed and authenticated. Setup and
readiness never install them, authenticate them, copy their credentials, or
substitute another provider.

| Capability | When unavailable | Setup ownership |
|---|---|---|
| Atlas | Jira discovery/refresh and Jira create actions are unavailable; cached/local ticket work remains available. | Use the organization's approved Atlas CLI installation and authentication procedure. |
| GitHub Copilot CLI | When `github-copilot-cli` is the configured Assistant provider, Assistant and AI Actions are unavailable; non-AI workflows continue. A `deepseek-api` deployment does not require this capability. | Use GitHub's official Copilot CLI installation and sign-in instructions. |
| Datadog API | Live incident refresh and Datadog evidence retrieval are unavailable; the preserved incident cache contract remains in effect. | Supply a scoped read-only bearer token through the process environment as described below. |
| Microsoft 365 CLI | Email preview/send are unavailable; local handover generation and preview continue. | Use the official Microsoft 365 CLI installation and authentication instructions. |
| noc-tools | Only workflows using a missing or incompatible command are unavailable; native local NOC Web workflows continue. | Use the organization's approved noc-tools release and compatibility procedure. |

The Workstation Readiness page reports each capability separately as `READY`,
`SETUP REQUIRED`, or `UNAVAILABLE`. It does not show credentials, tokens,
configuration contents, or raw subprocess output. Datadog API readiness checks
configuration and token presence only; it never calls Datadog and never asserts
that the token was accepted or that Datadog is reachable. Use **Recheck** after
completing dependency setup.

## AI inference provider

Assistant and AI Action inference use exactly one explicitly configured provider.
No provider is selected by default; an unconfigured deployment still starts and
keeps every non-Assistant workflow available. Provider settings are read from the
process environment at application start, and changing them requires a service
restart.

| Variable | Required | Default | Secret |
|---|---|---|---|
| `NOC_WEB_AI_PROVIDER` | For Assistant/AI Actions | unset (`notConfigured`) | No |
| `NOC_WEB_DEEPSEEK_API_KEY` | When `deepseek-api` is selected | none | Yes |
| `NOC_WEB_DEEPSEEK_MODEL` | No | `deepseek-flash` | No |
| `NOC_WEB_DEEPSEEK_BASE_URL` | No | `https://api.deepseek.com` | No |
| `NOC_WEB_AI_TIMEOUT_SECONDS` | No | `55` | No |

`NOC_WEB_AI_PROVIDER` must be exactly `deepseek-api` or `github-copilot-cli`.
Selecting `deepseek-api` does not require the GitHub Copilot CLI to be installed
or authenticated. Selecting `github-copilot-cli` preserves the existing
authenticated-session behavior. There is no automatic fallback between
providers.

For the managed systemd user service, place provider settings in
`${XDG_CONFIG_HOME:-$HOME/.config}/noc-web/ai-provider.env`. The generated unit
loads that file with `EnvironmentFile=-`, so it is optional. The file is
operator-managed, lives outside NOC Web operational data, and must be mode
`0600` when it contains a credential. Never commit it and never put the key in
`runtime.json`, the unit file, or application logs.

```bash
install -m 600 /dev/null ~/.config/noc-web/ai-provider.env
cat > ~/.config/noc-web/ai-provider.env <<'EOF'
NOC_WEB_AI_PROVIDER=deepseek-api
NOC_WEB_DEEPSEEK_API_KEY=<secret>
NOC_WEB_DEEPSEEK_MODEL=deepseek-flash
EOF
```

Readiness reports `READY`, `SETUP REQUIRED`, or `NOT CONFIGURED` from static
configuration and required-material presence only. It never makes a provider
request and does not assert that credentials were accepted or that the provider
is reachable. Provider readiness is warning-only in shift health so it does not
block End Shift preflight or deterministic handover preview. Confirmed handover
generation still fails closed if the configured provider is unavailable; it never
falls back to another provider or to a deterministic-only final record.

## Datadog evidence provider and investigation generation

The Investigations page uses the direct read-only Datadog API provider for
Feature 015 evidence and the configured AI provider for investigation generation.
Preview is non-generative and read-only. The configured AI provider is called
only after explicit operator confirmation; it receives a bounded evidence package
with stable evidence identifiers, not Datadog credentials, Authorization
headers, unrelated environment values, or raw provider payloads. Datadog remains
structurally read-only. `noc-inv`, GitHub Copilot CLI, and Datadog MCP are not
requirements for this path.

Generated investigations are advisory until reviewed. They use the existing
local persistence, collision protection, provenance, lifecycle, and review rules,
and record system-authored evidence availability plus a provenance map. DeepSeek
Flash is supported through the existing `deepseek-api` configuration; there is no
automatic fallback between DeepSeek and Copilot.

Live incident retrieval and on-demand incident, notebook, and monitor evidence
use a direct read-only Datadog API provider. This path does not require,
invoke, or depend on GitHub Copilot CLI or Datadog MCP. The provider issues only
allowlisted retrieval operations; it cannot create, update, acknowledge, mute,
resolve, delete, or otherwise modify Datadog resources.

## Handover generation

End Shift handover generation assembles mandatory factual content deterministically
from validated shift evidence: shift notes, all locally tracked and remote open
tickets, reviewed investigation findings and lifecycle state, already-available
read-only Datadog context, dashboard/status information, and handover readiness.
Every validated open ticket is included; ticket completeness never depends on AI
judgment. If no validated ticket source can establish the open set, or the set
exceeds the bound, generation fails closed rather than omitting tickets.

Preview is deterministic, read-only, and non-generative. Every confirmed generation
invokes the configured AI provider for internal advisory validation; the AI cannot author or
modify mandatory sections and never receives credentials. AI advisory text and internal
`[evidence:...]` citation markers are not emitted in the final handover. The final Markdown uses
the established `Hi Team` intro, deterministic mandatory sections, and signature, with
deterministic ticket counts authoritative. Validated advisory citations are retained only in
`handover-provenance.json`. Provider failure fails closed and preserves any existing handover.
There is no deterministic-only generation path and no automatic provider fallback. Regeneration
archives the previous Markdown and provenance sidecar and restores them on failure.

The existing Markdown format and delivery workflow remain authoritative. A versioned
`handover-provenance.json` sidecar is additive and is not delivered. Microsoft 365
delivery remains separate from AI generation. `noc-handover` and Copilot CLI are
optional compatibility capabilities, not requirements for core handover generation.

| Variable | Required | Default | Secret |
|---|---|---|---|
| `NOC_WEB_DATADOG_ACCESS_TOKEN` | For Datadog retrieval | none | Yes |
| `NOC_WEB_DATADOG_BASE_URL` | No | `https://api.datadoghq.com` | No |
| `NOC_WEB_DATADOG_TIMEOUT_SECONDS` | No | `90` | No |

The token must be scoped externally to read-only Datadog access. It is read only
from the process environment, sent only as a bearer header to the configured
Datadog API base, and never returned, logged, cached, reported, or persisted.
`NOC_WEB_DATADOG_BASE_URL` is HTTPS-only and must point at a Datadog API host.
Changing any setting requires a service restart.

For the managed systemd user service, place Datadog settings in
`${XDG_CONFIG_HOME:-$HOME/.config}/noc-web/datadog-provider.env`. The generated
unit loads that optional file with `EnvironmentFile=-`. The file is
operator-managed, lives outside NOC Web operational data, and must be mode
`0600`. Never commit it and never put the token in `runtime.json`, the unit
file, or application logs.

```bash
install -m 600 /dev/null ~/.config/noc-web/datadog-provider.env
cat > ~/.config/noc-web/datadog-provider.env <<'EOF'
NOC_WEB_DATADOG_ACCESS_TOKEN=<secret>
NOC_WEB_DATADOG_BASE_URL=https://api.datadoghq.com
NOC_WEB_DATADOG_TIMEOUT_SECONDS=90
EOF
```

## Service management

The service runs in the current operator's systemd **user** manager, uses the
configured NOC Web virtual environment and repository, and binds only to
`127.0.0.1`. It has a bounded restart policy and uses the user's `HOME` and
`~/.local/bin` path without serializing authentication values.

```bash
systemctl --user status noc-web
systemctl --user restart noc-web
systemctl --user stop noc-web
systemctl --user start noc-web
journalctl --user -u noc-web
journalctl --user -u noc-web -f
```

The Windows shortcut wakes the configured WSL distribution, reuses an active
user service or starts a stopped one, waits for bounded localhost health, then
opens the default Windows browser. It exits without leaving a terminal
running. A WSL, service, health, or browser failure is shown as a safe
category; no browser is opened before health succeeds.

## Recovery and manual troubleshooting

Check service state and recent safe logs first. Restart or temporarily stop
the service using the commands above. If the managed service is stopped, a
manual troubleshooting process can use the same validated config and localhost
port:

```bash
CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/noc-web/runtime.json"
systemctl --user stop noc-web
./.venv/bin/python scripts/run_service.py --config "$CONFIG"
```

The manual runner refuses to start if the configured localhost port is
already occupied; it does not create a competing Uvicorn listener. Stop the
manual process with `Ctrl+C`, then return to managed operation:

```bash
systemctl --user start noc-web
systemctl --user status noc-web
```

Service output and HTTP request logs contain only safe operation/route,
status, duration, and error-code metadata. Uvicorn access logs are disabled.
Prompts, model output, Datadog evidence, Jira/ticket contents, Shift Notes,
handover contents, credentials, tokens, and raw external subprocess output
must not be written to the journal.

## Windows/WSL acceptance

The platform acceptance script is opt-in and must be run only against a
designated test workstation/distribution:

```powershell
powershell.exe -NoProfile -File .\tests\windows\test_launcher_acceptance.ps1 `
  -Distribution "<configured distribution>" `
  -LinuxUser "<configured operator>" `
  -Execute
```

It verifies the per-user Shell Link, hidden Windows Script Host target,
configured WSL identity, localhost URL, bounded launcher exit, service reuse,
and health. Linux tests mock Windows Shell Link and WSL boundaries; they do
not replace this Windows/WSL acceptance run.
