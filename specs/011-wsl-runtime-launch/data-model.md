# Data Model: WSL Runtime and Windows Launch

## Workstation Runtime Configuration

A credential-free, versioned configuration owned by the current operator and
stored by default at `${XDG_CONFIG_HOME:-$HOME/.config}/noc-web/runtime.json`.
Setup validates an existing configuration before reuse or migration and writes
updates atomically. The configuration is not stored under the operational NOC
workspace.

| Field | Type | Constraints |
|---|---|---|
| `schemaVersion` | integer | Supported positive schema version; unknown versions fail before changing runtime artifacts. |
| `repositoryRoot` | absolute Linux path | Existing expected NOC Web checkout; no root path, traversal component, or unsafe symlink target. |
| `virtualEnvironment` | absolute Linux path | Existing/creatable NOC Web virtual environment associated with this checkout. |
| `wslDistribution` | string | Exact current/configured distribution name; derived during setup or explicitly selected, never inferred from the mutable default at launch. |
| `linuxUser` | string | Current non-root WSL user; validated against the current account. |
| `linuxUid` | integer | Current user's UID, used only to address the user runtime manager when necessary. Must not be zero. |
| `port` | integer | `1..65535`; default `8000`. |
| `applicationUrl` | URL | HTTP URL whose hostname is `127.0.0.1` or `localhost`, whose port matches `port`, and which contains no credentials or non-localhost target. Default `http://127.0.0.1:8000`. |
| `healthTimeoutSeconds` | integer | Positive bounded timeout; default `60`, with a documented upper bound. |
| `shortcutDirectory` | Windows per-user path or known-folder token | Optional; defaults to the exact current-user Desktop path returned by `Environment.GetFolderPath("DesktopDirectory")`. An empty API result is a safe setup failure. Only that OS-reported path may be a reparse point; arbitrary configured destinations may not. |
| `feature005Settings` | object | Allowlisted existing `NOC_WEB_*` paths/limits only; each setting is validated through the existing Feature 005 configuration rules. |

No field may contain a password, token, authentication file contents, prompt,
or raw provider output. Setup must not copy ambient process environment
wholesale into this object.

## Managed NOC Web Service

An OS-managed process represented by a per-user `noc-web.service` unit. Its
configuration is generated from validated workstation settings, not from
operator-supplied shell fragments.

| Attribute | Meaning |
|---|---|
| `ownerUid` | Current unprivileged user; implicit in the user service manager. |
| `workingDirectory` | `repositoryRoot`. |
| `executable` | Python interpreter inside `virtualEnvironment`. |
| `entryPoint` | `-m scripts.run_service --config <runtime-config>`; `scripts` is an explicit package, and both it and `backend` resolve from `repositoryRoot`. |
| `listener` | `127.0.0.1:<port>` only. |
| `restartPolicy` | Restart on unexpected failure with bounded rate and delay. |
| `environment` | Explicit `HOME`, a fixed `PATH` including `~/.local/bin` and `/home/linuxbrew/.linuxbrew/Homebrew/bin`, and the allowlisted Feature 005 settings; no authentication values are copied and startup does not require inherited `VIRTUAL_ENV`, `PYTHONPATH`, an interactive-shell PATH, or Windows PATH entries. |
| `state` | Read-only observation such as active, inactive, failed, or unmanaged; obtained from the user manager when available. |
| `logs` | Journal entries limited to safe operation/status/duration/error-code metadata. |
| `unitSyntax` | Generated directive values follow systemd's unit-file syntax; absolute paths are parsed as configured paths, and automated regression tests require `systemd-analyze --user verify` to succeed. |

Starting an active unit is idempotent and must not spawn another Uvicorn
process. A manual troubleshooting run must first stop the managed unit.
The service-context regression executes the generated unit's `ExecStart` as a
subprocess with its declared working directory and environment, with inherited
`VIRTUAL_ENV` and `PYTHONPATH` removed, and verifies startup passes the
`backend` import boundary. Native unit verification and this automated test
do not replace T029's real workstation acceptance.

## Capability Readiness Result

Each check is transient, read-only, bounded, and redacted. It is returned by
the existing readiness API rather than persisted as operational data.

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Stable capability check identifier. |
| `category` | string | `core`, `service`, `external`, `storage`, or existing readiness category. |
| `capability` | string | Operator-facing capability name. |
| `status` | enum | `ready`, `setup_required`, or `unavailable`; UI labels are `READY`, `SETUP REQUIRED`, or `UNAVAILABLE`. |
| `required` | boolean | Whether failure affects core application readiness; optional dependencies do not gate startup. |
| `impact` | string | Safe description of affected NOC workflows. |
| `correctiveAction` | string | Safe, capability-specific setup/recovery guidance. |
| `checkedAt` | timestamp | UTC assessment time. |
| `sourceId` | optional string | Stable identifier for a dependency or cache source. |

Raw command output, filesystem credential contents, sensitive paths, ticket
data, and authentication material are not result fields. `ready` is reported
only when a safe check verifies the capability. If authentication or MCP
usability cannot be verified without exposing credentials or performing an
unsafe operation, the result is `setup_required` with an explicit
unverified/setup guidance message.

Core checks include application/Python runtime, validated configuration,
writable NOC workspace, and managed-service state. External capabilities are
independently represented for Atlas, GitHub Copilot CLI, Datadog MCP, Microsoft
365 CLI, and noc-tools compatibility. Missing optional capabilities do not
change core service startup status.

## Windows Launcher

A current-user shortcut and its generated Windows-side configuration.

| Field | Type | Constraints |
|---|---|---|
| `name` | string | Exactly `SESAMI NOC Operations`. |
| `shortcutPath` | Windows path | One stable per-user shortcut path; Desktop by default or configured per-user location. |
| `target` | Windows executable | Windows Script Host (`wscript.exe`) running the installed hidden launcher. |
| `distribution` | string | Exact validated `wslDistribution` from workstation configuration. |
| `linuxUser` | string | Exact validated unprivileged operator account. |
| `applicationUrl` | URL | Validated localhost-only URL. |
| `healthTimeoutSeconds` | integer | Bounded deadline from 1 through 300 seconds; default 60 seconds. |
| `lastResult` | transient enum | Success, verified WSL/distribution unavailable, service unavailable, health timeout, browser launch failure, or `WINDOWS_LAUNCH_EXECUTION_FAILED`; never includes subprocess output. |
| `installFailureReason` | optional transient enum | Safe allowlisted category (for example, Desktop unavailable, destination unsafe, install path unsafe, or shortcut write failed) accompanying `SHORTCUT_INSTALL_FAILED`; never raw exception text or subprocess output. |

The `.lnk` and adjacent launcher configuration contain only navigation and
runtime identifiers. The launcher checks WSL/service startup, polls health,
opens the default browser only after success, and exits without a persistent
terminal. Windows PowerShell 5.1 installer code defines or loads helper
functions before use. The exact Desktop known-folder path may be a redirected
reparse point; other configured shortcut destinations and LocalAppData
installation paths retain strict reparse-point rejection.

The generated VBScript resolves the Windows `wsl.exe` executable and applies
Windows command-line quoting to every configured argument. Its `Run` result is
classified from documented launcher exit codes only. An invocation error or
unexpected result, including `-1`, is
`WINDOWS_LAUNCH_EXECUTION_FAILED` with safe guidance; it is not evidence that
WSL or the configured distribution is unavailable.

## Operational Data

Existing NOC records, shift handovers, AI reports, Feature 009 incident cache,
Feature 010 investigation history/lifecycle, and external authentication
remain in their existing owner-managed locations. They are outside the
installer's write/delete boundary and are not entities migrated by this
feature.
