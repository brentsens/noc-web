# Contract: Datadog Incidents API

**Feature**: `015-datadog-rest-provider`

This contract is unchanged from Feature 009 except for the retrieval mechanism
behind it. The provider is now the direct read-only Datadog API. No Copilot CLI
or Datadog MCP server is required, invoked, or consulted.

## Read shared snapshot

`GET /api/datadog/incidents`

Returns the current cache immediately. If refresh is due, it may schedule one
background refresh but does not wait for external retrieval.

```json
{
  "incidents": [],
  "count": 0,
  "lastAttemptedAt": "2026-11-10T20:00:00Z",
  "lastSuccessfulAt": "2026-11-10T20:00:00Z",
  "freshness": "current",
  "error": null
}
```

`count` is the number of incidents in a valid snapshot; clients must use
`freshness` to distinguish a successful empty result from unavailable data.
Each incident's `state` is the exact Datadog state returned by the provider;
`ACTIVE` and `STABLE` are both current incidents. `freshness` is a separate
cache status and MUST NOT be substituted for incident state.

`error` is either null or one of:

- `copilot-unavailable` (retained for historical contract compatibility; not
  emitted by the new provider)
- `provider-unavailable`
- `timeout`
- `invalid-response`
- `cache-unavailable`

It never contains raw provider content, response bodies, request URLs, or
credentials. If no valid cache exists, `incidents` is empty,
`lastSuccessfulAt` is null, freshness is `unavailable`, and `count` is not
presented by the UI as a successful zero.

## Request refresh

`POST /api/datadog/incidents/refresh`

No request body is accepted or needed. It schedules a bounded read-only refresh
and returns the shared snapshot immediately. If a refresh is already running,
the operation is coalesced and the response reports `refreshing`. Refreshing
never creates or updates local investigations or other operational records.

Example response while work is in flight:

```json
{
  "incidents": [],
  "count": 0,
  "lastAttemptedAt": "2026-11-10T20:00:00Z",
  "lastSuccessfulAt": "2026-11-10T19:59:00Z",
  "freshness": "refreshing",
  "error": null
}
```

## Failure semantics

- Provider, validation, timeout, or storage failure with a valid prior snapshot
  returns the preserved incident list, its previous success timestamp, and
  `freshness: "stale"`; each preserved incident retains its last-known Datadog
  state.
- Failure without a prior valid snapshot returns an empty list with
  `freshness: "unavailable"` and no successful-refresh timestamp.
- A successful empty result returns `freshness: "current"` and `count: 0`.
- A provider result with more than 100 current incidents fails the whole
  refresh; it is never truncated.
- Responses never contain raw Datadog payloads, provider error bodies,
  Authorization headers, tokens, prompts, or credentials.

## Investigation navigation

“Create Investigation” navigates to `investigations.html` with a one-time
session-local incident title hint. The hint is treated as plain display text,
does not enter the URL, does not fill the Notebook URL, and does not create
anything. Existing preview and confirmation endpoints remain the only path to
investigation generation. `ACTIVE` and `STABLE` incidents are both eligible for
this operator-controlled action.

## Provider independence

- `GET /api/datadog/incidents` and `POST /api/datadog/incidents/refresh` MUST
  succeed with Copilot CLI absent and with no Datadog MCP configuration.
- No request to these endpoints may spawn a Copilot process or invoke an MCP
  tool.
- The frontend continues to consume the same fields and renderer.
