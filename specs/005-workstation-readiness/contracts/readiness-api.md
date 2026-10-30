# Readiness API Contract

## `GET /api/readiness/{shift_date}`

Returns an additive, read-only workstation assessment.

### Request

| Part | Requirement |
|---|---|
| `shift_date` | Required `YYYY-MM-DD` path value. Invalid syntax returns `400`. |
| Environment | Only the documented `NOC_WEB_*` settings in `docs/workstation-readiness.md` may alter the profile. There are no request overrides. |
| Side effects | No Jira refresh, ticket/workflow action, cache write, data conversion, secret discovery, or retained diagnostic record. The sole write-capability probe creates and removes its unique file in the approved probe directory. |

### Successful assessment response (`200`)

An unavailable dependency or failed capability remains a normal `200` assessment; clients must
use `overallStatus` and individual checks, not HTTP success, to decide whether the workstation is
ready.

```json
{
  "assessedAt": "2026-10-29T21:00:00Z",
  "shiftDate": "2026-10-29",
  "overallStatus": "notReady",
  "readOnly": true,
  "configuration": {
    "id": "configuration.profile",
    "category": "configuration",
    "status": "ready",
    "required": true,
    "capability": "Approved workstation configuration",
    "impact": "Readiness checks use the documented configuration profile.",
    "correctiveAction": "No action required."
  },
  "checks": [
    {
      "id": "cache.jiraOpenTickets",
      "category": "cache",
      "status": "notReady",
      "required": true,
      "capability": "Jira open-ticket cache",
      "sourceId": "jiraOpenTickets",
      "ageSeconds": 1801,
      "impact": "Cached ticket data cannot be relied on for operational work.",
      "correctiveAction": "Restore the approved cache through the normal confirmed workflow."
    }
  ],
  "liveness": [
    {
      "id": "liveness.jira",
      "category": "liveness",
      "status": "available",
      "required": false,
      "capability": "Jira dependency response",
      "sourceId": "jira",
      "impact": "The dependency responded, but this alone does not establish write or cache readiness.",
      "correctiveAction": "Continue with the individual readiness results."
    }
  ]
}
```

`checks` contains distinct NOC-data, per-cache, command, and write-capability results. A cache
source is not ready when unavailable, unreadable, malformed, incompatible, missing an age, or at
least its configured maximum age. Liveness has `available`, `unavailable`, or `notConfigured`;
it never converts another failed check to `ready`.

### Invalid explicit configuration (`422`)

When an explicitly present override is blank, malformed, unsafe, conflicting, inaccessible, or
unusable, the server must return before any operational probe:

```json
{
  "detail": {
    "overallStatus": "notReady",
    "configuration": {
      "id": "configuration.NOC_WEB_NOC_ROOT",
      "category": "configuration",
      "status": "notReady",
      "required": true,
      "capability": "Approved workstation configuration",
      "impact": "Readiness checks were not run.",
      "correctiveAction": "Correct the documented override and run readiness again."
    },
    "checks": [],
    "liveness": []
  }
}
```

The response must not expose the supplied value, a fallback value, a filesystem path, command
output, secret, credential, record content, or raw exception. A missing/invalid default similarly
reports not ready, but no alternate location is discovered.

### Compatibility and client behavior

This route is additive. Existing `/api/health`, `/api/status`, cache, tickets, and operational
action contracts retain their response shape and behavior. The readiness page may render the
result but must not call a mutating endpoint or treat `overallStatus: "ready"` as confirmation.
