# Status API Contract: Jira Cache Health

## Existing Status Response Extension

**Request**: `GET /api/status/{shift_date}`

The existing response gains this additive field:

```json
{
  "jiraCache": {
    "available": true,
    "refreshedAt": "2026-10-29T23:30:00+00:00",
    "freshness": "current"
  }
}
```

### Field semantics

| Field | Required | Values | Meaning |
|-------|----------|--------|---------|
| `available` | Yes | `true`, `false` | Whether valid local cache data is readable. |
| `refreshedAt` | Yes | ISO 8601 timestamp or `null` | Last successful cache refresh, when valid. |
| `freshness` | Yes | `current`, `stale`, `unavailable` | Freshness classification for operator display. |

### Required states

| Condition | `available` | `refreshedAt` | `freshness` |
|-----------|-------------|---------------|-------------|
| Valid cache refreshed less than 30 minutes ago | `true` | Valid timestamp | `current` |
| Valid cache refreshed 30 minutes ago or longer | `true` | Valid timestamp | `stale` |
| Missing, unreadable, malformed, or invalid-timestamp cache | `false` | `null` | `unavailable` |

The endpoint remains read-only. This field MUST NOT cause a Jira request, cache refresh, ticket
change, or cache write. A stale state is informational only and MUST NOT trigger a Jira refresh.
Existing Status response fields retain their current meanings.
