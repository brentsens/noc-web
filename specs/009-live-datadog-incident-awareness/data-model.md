# Data Model: Live Datadog Incident Awareness

## Current Datadog Incident Projection

A validated, minimal representation of one current Datadog incident.
This is cache data, not a local investigation.

| Field | Type | Required | Validation |
|---|---|---:|---|
| `id` | string | yes | Non-empty, at most 128 characters, unique within a snapshot |
| `title` | string | yes | Non-empty, at most 200 characters |
| `state` | string | yes | Recognized values are `ACTIVE`, `STABLE`, and `RESOLVED`. Preserve the exact provider value; retain `ACTIVE`/`STABLE` and exclude `RESOLVED` after successful refresh. Existing lowercase values remain readable without rewriting. |
| `severity` | string | no | Non-empty and at most 32 characters when supplied |
| `createdAt` | string | no | RFC 3339 timestamp of at most 40 characters when supplied |
| `updatedAt` | string | no | RFC 3339 timestamp of at most 40 characters when supplied |
| `summary` | string | no | At most 500 characters when supplied |
| `url` | string | no | At most 2048 characters; HTTPS Datadog incident URL on a `datadoghq.com` or `datadoghq.eu` host when supplied |

Unknown fields are rejected. Optional fields are omitted when not available;
the service does not invent values. Raw source evidence, prompts, and provider
responses are not part of this entity.

## Incident Snapshot

One shared successfully retrieved set of current incident projections and
refresh metadata.

| Field | Type | Meaning |
|---|---|---|
| `incidents` | array of Current Datadog Incident Projection | Last fully validated successful result; may be empty |
| `lastAttemptedAt` | timestamp or null | Most recent retrieval attempt, successful or failed |
| `lastSuccessfulAt` | timestamp or null | Most recent successful complete retrieval |
| `freshness` | enum | `current`, `stale`, `unavailable`, or `refreshing` |

Datadog state and cache freshness are independent fields. The incident's
`state` records the exact provider value; snapshot `freshness` describes only
the cache and retrieval lifecycle.

State rules:

- **current**: A successful snapshot exists, remains within the 60-second
  target, and no later failed attempt has marked it stale.
- **stale**: A successful snapshot exists but is older than target or the
  latest attempt failed. Keep its incident list and last-success timestamp.
- **unavailable**: No valid successful snapshot exists.
- **refreshing**: One refresh operation is active. The response may still
  include the previous snapshot and its last-success timestamp.

A successful refresh atomically replaces the whole `incidents` list and both
refresh timestamps, including with an empty list. `ACTIVE` to `STABLE` and
`STABLE` to `ACTIVE` transitions replace the state without removing the
incident. A confirmed `RESOLVED` state removes it from the current list only
when the complete refresh succeeds. A failed refresh updates `lastAttemptedAt`
and freshness while preserving the previous `incidents`, exact Datadog states,
and `lastSuccessfulAt`.

## Refresh Operation

A read-only, bounded request to retrieve, validate, and project current Datadog
incidents. At most one operation may run at a time. Automatic cache-age
refreshes and explicit operator refreshes use the same service and cannot
launch independent provider calls.

## Investigation Handoff

A browser navigation from an incident card to the existing investigation
creation form. Only the incident display title may be prefilled. The operator
must supply the existing required Notebook URL, review the Preview, and
explicitly confirm creation. This handoff is not persisted incident state.
