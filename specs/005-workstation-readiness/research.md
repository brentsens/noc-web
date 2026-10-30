# Research: Workstation Operational Readiness

## Decision: Resolve a small allowlist of environment variables at one configuration boundary

**Rationale**: The repository currently derives `NOC_ROOT` and `NOC_BIN` from `Path.home()`.
Preserving those expressions as defaults keeps current workstations unchanged. A resolver can
distinguish an absent variable from an explicitly empty one and reject an unsafe explicit value
before anything accesses the filesystem or starts a process. It also lets tests inject a complete
profile without reading real workstation state.

Supported settings are `NOC_WEB_NOC_ROOT`, `NOC_WEB_NOC_BIN`,
`NOC_WEB_READINESS_PROBE_DIR`, `NOC_WEB_JIRA_CACHE_MAX_AGE_SECONDS`, and
`NOC_WEB_COMMAND_TIMEOUT_SECONDS`. Explicit path values must be absolute and normalized; the probe
directory must remain under the approved NOC root. Numeric values must be finite positive integers
within documented bounds. The resolver records logical names and source only, not values.

**Alternatives considered**:

- Accept arbitrary environment variables or configuration files: rejected because they expand the
  attack/diagnostic surface and make no-fallback reasoning ambiguous.
- Silently use defaults for malformed values: rejected by FR-003/004.
- Discover paths from user profiles, PATH, or mounted drives: rejected by FR-011 and cross-machine
  unpredictability.

## Decision: Make invalid explicit configuration terminal for the assessment

**Rationale**: An explicit override conveys intent. If it is invalid, accessing the default root,
running default commands, or probing an alternate destination would conceal a dangerous mismatch.
The API will return 422 with a redacted configuration result, generic corrective action, and an
empty probe list; the UI presents it as not ready. An absent override continues with the documented
default.

**Alternatives considered**:

- Return a partial assessment after an override error: rejected because it can accidentally touch
  the wrong workstation resources.
- Treat explicit blank as absent: rejected because blank is an explicit unsafe configuration.

## Decision: Generalize cache policy to source-keyed configured ages

**Rationale**: The current Jira cache has a fixed 30-minute constant and a stable
`.jira-open-tickets.json` format. A readiness source catalog keeps that parser/record intact while
pairing each source with a required maximum age. The initial `jiraOpenTickets` source gets its age
from the profile; a missing, invalid, unreadable, malformed, naive, or over-age source is a
separate failed check. The exact boundary is stale when `age >= configuredMaximumAge`; it is ready
only when `age < configuredMaximumAge`.

**Alternatives considered**:

- One global freshness setting: rejected because sources can have different operational limits.
- Refresh a stale cache: rejected because readiness must be read-only.
- Report stale cache as current usable data: rejected because readiness must not overstate it.

## Decision: Treat liveness as diagnostic evidence, not readiness evidence

**Rationale**: A dependency can respond while a command fails, NOC data is malformed, or the write
destination is non-writable. The response exposes independent liveness checks (`available`,
`unavailable`, or `not-configured`) and capability readiness checks. Only all required readiness
checks can produce the overall `ready` result. Liveness probes have explicit argv/timeout settings,
use `shell=False`, emit no output, and do not occur unless documented/configured.

**Alternatives considered**:

- Infer readiness from TCP/HTTP reachability: rejected because it cannot prove the operational duty.
- Run external network checks by default: rejected because the application has no documented,
  credential-safe dependency probe and must avoid side effects.

## Decision: Use bounded non-destructive command and write probes

**Rationale**: `shutil.which` alone proves neither executable permission nor completion. The command
catalog will use explicit fixed, non-mutating argv (such as a version/help or script syntax check)
and `subprocess.run(..., shell=False, timeout=...)`; output is discarded/redacted. The write probe
uses `O_CREAT | O_EXCL` for a uniquely named file inside the approved existing probe directory,
flushes/syncs a tiny sentinel, then unlinks only that created file in `finally`. This demonstrates
write capability without overwriting an operational artifact.

**Alternatives considered**:

- `os.access`: rejected because it is advisory and does not prove a write succeeds.
- Create a predictable probe name: rejected because it risks collision/overwrite.
- Run normal operational commands: rejected because readiness must not execute a workflow.

## Decision: Redact at construction, not after retaining diagnostics

**Rationale**: Probe output, exception messages, resolved paths, and environment values may contain
sensitive data. Result objects will use controlled status codes/messages and logical identifiers
only; raw exceptions/output are neither persisted nor sent to the browser. Tests will seed token
and user-path strings and assert their absence from JSON and logs.

**Alternatives considered**:

- Save raw diagnostics and redact when displaying: rejected because stored data remains sensitive.
- Return command stderr for recovery: rejected because it can disclose secrets or paths.

## Decision: Support Windows and WSL by explicit profiles, never path guessing

**Rationale**: Native Windows and WSL have distinct path syntaxes, homes, executable lookup, and
permissions. The documentation tells operators to run the application and provide configuration in
one environment: Windows uses Windows absolute paths and command catalog entries; WSL uses Linux
absolute paths and Linux commands. The server does not translate `C:\...` to `/mnt/c/...`, share a
profile across environments, or infer a mounted path.

**Alternatives considered**:

- Automatic WSL drive translation: rejected because it can select an unintended location.
- Treat Windows permission semantics as POSIX mode checks: rejected because the exclusive write
  probe is the portable capability evidence.
