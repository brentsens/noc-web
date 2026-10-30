# Data Model: Workstation Operational Readiness

## Configuration Profile

An in-memory, immutable profile resolved once per assessment. It is not persisted.

| Field | Type | Rules |
|---|---|---|
| `settings` | map of approved logical setting | Only the five documented environment settings; each has `source` of `default` or `explicit`. |
| `nocRoot` | approved path (internal only) | Default is current `Path.home() / "noc"`; explicit value is absolute, normalized, and safe. Never serialize it. |
| `nocBin` | approved path (internal only) | Default is current `Path.home() / ".local" / "bin"`; explicit value is absolute and normalized. Never serialize it. |
| `probeDirectory` | approved path (internal only) | Explicit/default directory must be inside `nocRoot`; it is the only destination for a write probe. |
| `cacheSources` | map of Cache Source Policy | Every source has its own positive configured maximum age. |
| `commandTimeoutSeconds` | integer | Positive, bounded configured duration used by every command/liveness probe. |

**Validation state**: `valid` when all defaults/overrides validate; `invalid-explicit` for any
explicit setting that is blank, malformed, unsafe, conflicting, or unusable; `invalid-default` for
an absent/invalid default. `invalid-explicit` stops the assessment before any probe and never
falls back. Existing compatible configuration/data remains unchanged; incompatible values are not
migrated.

## Cache Source Policy

| Field | Type | Rules |
|---|---|---|
| `sourceId` | string | Stable logical identifier, initially `jiraOpenTickets`. |
| `maximumAgeSeconds` | integer | Source-specific, positive configured limit; `age < limit` is ready and `age >= limit` is not ready. |
| `recordReader` | internal function | Reads existing format without modifying it. |
| `compatibility` | enum | `compatible` or `incompatible`; incompatibility is not repaired. |

The initial source reads existing `.jira-open-tickets.json` through the established Jira-cache
reader. Its record format and existing Status cache-health model remain authoritative.

## Readiness Check

| Field | Type | Rules |
|---|---|---|
| `id` | string | Stable logical check id, never a path/secret. |
| `category` | enum | `configuration`, `nocData`, `cache`, `command`, `writeCapability`, or `liveness`. |
| `status` | enum | `ready`, `notReady`, `limited`, `unavailable`, or `notConfigured`. |
| `required` | boolean | Only required operational checks gate overall readiness. Liveness is diagnostic. |
| `capability` | string | Human-readable capability name. |
| `impact` | string | Operational consequence of this result. |
| `correctiveAction` | string | Non-sensitive, actionable recovery step. |
| `sourceId` | string/null | Present for cache/liveness checks. |
| `ageSeconds` | integer/null | Present only for valid cache age; never substitutes for status. |

No field contains a resolved path, environment value, command output, credential, exception text,
or record content.

## Write-Capability Result

A specialized `Readiness Check` with category `writeCapability`.

| Evidence | Rule |
|---|---|
| Destination reachability | Reported separately from write success; it cannot make the check ready. |
| Probe file | New random exclusive file in the approved probe directory only. |
| Write evidence | A tiny sentinel write followed by flush/sync succeeds. |
| Cleanup | The same created file is deleted in `finally`; an existing file is never replaced or deleted. |
| Failure | Permission, capacity, I/O, missing directory, or cleanup failure is `notReady`/`limited` with generic guidance. |

## Readiness Assessment

| Field | Type | Rules |
|---|---|---|
| `assessedAt` | UTC ISO-8601 timestamp | Time assessment began/completed; no operator identity. |
| `shiftDate` | ISO date | Validated route value; used only for NOC-data context. |
| `overallStatus` | enum | `ready` or `notReady`. |
| `configuration` | Readiness Check | Always present. |
| `checks` | list of Readiness Check | Contains each required non-liveness capability independently. |
| `liveness` | list of Readiness Check | Always separate; it does not upgrade readiness. |
| `readOnly` | boolean | `true`; describes no workflow/ticket/cache mutation. The transient approved probe is recorded as non-destructive capability evidence. |

**Transitions**: None. An assessment is a new ephemeral snapshot. It cannot authorize a command,
ticket action, Jira update, or handover; existing confirmation state transitions are unchanged.
