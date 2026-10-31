# Datadog Incidents API Contract

## Read shared snapshot

`GET /api/datadog/incidents`

Returns the current cache immediately. If refresh is due, it may schedule one
background refresh but does not wait for Copilot CLI or Datadog MCP.

```json
{
  "incidents": [],
  "count": 0,
  "lastAttemptedAt": "2026-10-30T21:00:00Z",
  "lastSuccessfulAt": "2026-10-30T21:00:00Z",
  "freshness": "current",
  "error": null
}
```

`count` is the number of incidents in a valid snapshot; clients must use
`freshness` to distinguish a successful empty result from unavailable data.
Each incident's `state` is the exact Datadog state returned by the provider;
`ACTIVE` and `STABLE` are both current incidents. `freshness` is a separate
cache status and MUST NOT be substituted for incident state.
`error` is either null or a concise controlled state/code, never raw provider
content or diagnostics. If no valid cache exists, `incidents` is empty,
`lastSuccessfulAt` is null, freshness is `unavailable`, and `count` is not
presented by the UI as a successful zero.

## Request refresh

`POST /api/datadog/incidents/refresh`

No request body is accepted or needed. It schedules a bounded read-only
refresh and returns the shared snapshot immediately. If a refresh is already
running, the operation is coalesced and the response reports `refreshing`.
Refreshing never creates or updates local investigations or other operational
records.

Example response while work is in flight:

```json
{
  "incidents": [],
  "count": 0,
  "lastAttemptedAt": "2026-10-30T21:00:00Z",
  "lastSuccessfulAt": "2026-10-30T20:59:00Z",
  "freshness": "refreshing",
  "error": null
}
```

## Failure semantics

- Provider, validation, or storage failure with a valid prior snapshot returns
  the preserved incident list, its previous success timestamp, and
  `freshness: "stale"`; each preserved incident retains its last-known
  Datadog state.
- Failure without a prior valid snapshot returns an empty list with
  `freshness: "unavailable"` and no successful-refresh timestamp.
- A successful empty result returns `freshness: "current"` and `count: 0`.
- Responses never contain raw Copilot output, stderr, prompts, credentials, or
  raw Datadog evidence.

## Investigation navigation

“Create Investigation” navigates to `investigations.html` with a one-time
session-local incident title hint. The hint is treated as plain display text,
does not enter the URL, does not fill the Notebook URL, and does not create
anything. Existing preview and confirmation endpoints remain the only path to
investigation generation. `ACTIVE` and `STABLE` incidents are both eligible
for this operator-controlled action.
