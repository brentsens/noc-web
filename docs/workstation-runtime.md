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
| Datadog MCP | Live incident refresh and Datadog-backed investigation generation are unavailable; the previous valid incident cache remains governed by Feature 009. | Configure the Datadog MCP server through the approved Copilot MCP setup. |
| Microsoft 365 CLI | Email preview/send are unavailable; local handover generation and preview continue. | Use the official Microsoft 365 CLI installation and authentication instructions. |
| noc-tools | Only workflows using a missing or incompatible command are unavailable; native local NOC Web workflows continue. | Use the organization's approved noc-tools release and compatibility procedure. |

The Workstation Readiness page reports each capability separately as `READY`,
`SETUP REQUIRED`, or `UNAVAILABLE`. It does not show credentials, tokens,
configuration contents, or raw subprocess output. Copilot authentication and
Datadog MCP configuration remain explicitly unverified when a safe check
cannot establish them. Use **Recheck** after completing dependency setup.

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
is reachable. Provider readiness is warning-only in shift health so it cannot
block End Shift or handover workflows.

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
