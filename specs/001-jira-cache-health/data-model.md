# Data Model: Jira Cache Health Visibility

## Jira Cache Health

An additive, derived status object. It is not persisted and is computed only while reading the
existing local Jira cache.

| Field | Type | Rules |
|-------|------|-------|
| `available` | boolean | `true` only when the existing cache reader returns structurally valid cache data. |
| `refreshedAt` | string or null | The valid recorded ISO 8601 refresh time; `null` when unavailable. |
| `freshness` | string | `current`, `stale`, or `unavailable`. |

### Validation and state rules

1. Missing, unreadable, malformed, or structurally invalid cache data produces
   `available: false`, `refreshedAt: null`, and `freshness: "unavailable"`.
2. A cache with a missing, invalid, or timezone-naive refresh time produces the same unavailable
   health state.
3. A valid cache refreshed less than 30 minutes ago produces `freshness: "current"`.
4. A valid cache refreshed 30 minutes ago or longer produces `freshness: "stale"`.
5. Computing health MUST NOT write the cache, refresh Jira, or modify tickets; a stale result is
   informational only.

## Status Response Relationship

The existing Status response gains one `jiraCache` object containing Jira Cache Health. Existing
response fields remain unchanged. The Status page renders this object alongside its existing
metrics and does not issue a second request.
