# Operational Workflow UI and API Contract

## URL/UI contract

Each in-scope page uses `?shift=YYYY-MM-DD`:

```text
start-shift.html?shift=2026-10-29
index.html?shift=2026-10-29
tickets.html?shift=2026-10-29
investigations.html?shift=2026-10-29
status.html?shift=2026-10-29
end-shift.html?shift=2026-10-29
```

Absent `shift` is normalized to browser-local today and written with `history.replaceState`; a
malformed date renders an actionable context error and avoids date-scoped requests. All six pages
render the shared workflow bar and preserve `shift` in workflow/deep links. The Tickets view keeps
its existing global `GET /api/tickets` contract; the query supplies operator context only.

## Read contracts (unchanged)

| View | Existing read | Required behavior |
|---|---|---|
| Dashboard | `GET /api/dashboard/{shift}` | Render dashboard/local work and Jira-cache state without refresh. |
| Tickets | `GET /api/tickets` | Render ticket/local tracking and separately label Jira cache state already available to the page. |
| Investigations | `GET /api/shifts/{shift}/investigations` | Render investigation lifecycle, evidence provenance/availability, advisory/review state, and concise reviewed findings; never raw evidence. |
| Status | `GET /api/status/{shift}` | Render status, local work, and existing `jiraCache` freshness independently. |
| Start Shift | `GET /api/start-shift/{shift}` | Render preflight only. |
| End Shift | `GET /api/end-shift/{shift}` | Render preflight only. |

Read navigation, status inspection, and cache-health viewing must issue no POST/PATCH, Jira refresh,
or local write. A source failure must not replace unrelated valid content.

## Evidence and reviewed-finding contract

Evidence access is constrained to existing `noc-inv` and Copilot MCP paths. NOC Web MUST NOT expose
or introduce a direct Datadog endpoint, SDK/client, credential, browser request, source mutation,
or automatic retry. An evidence result is read-only and its failure/no-result is a source-specific
state, not an instruction to query Datadog by another path.

Investigation responses and presentation may contain only:

- an existing source/notebook reference and the `noc-inv` or `copilot-mcp` provenance;
- source availability/read-only state;
- AI advisory summary and `unreviewed`, `reviewed`, or `rejected` review state; and
- an operator-reviewed concise finding/state when review is complete.

They MUST NOT contain raw Datadog evidence, raw notebook/log/MCP output, prompts, credentials, or
Jira-ticket investigation data. AI advisory content MUST be visibly non-authoritative and excluded
from operational state until reviewed.

`POST /api/shifts/{shift}/investigations/{name}/review` and
`POST /api/shifts/{shift}/investigations/{name}/reject` require `{ "confirmed": true }`.
They change only noc-web's local review lifecycle/context; neither endpoint invokes nor modifies
noc-inv, Copilot MCP, Datadog, or Jira.

Notes, Dashboard, Status, End Shift, and handover may receive only the concise reviewed finding and
state. They MUST NOT receive an advisory, raw source evidence, or copied evidence reference body.
This is a one-way projection of NOC Web-owned reviewed context; it does not extend `noc-inv` into
Jira-ticket investigation behavior.

## Additive execution contract

`POST /api/start-shift/{shift}` gains a JSON body while retaining its URL and success/error response
shapes:

```json
{ "confirmed": true }
```

`confirmed` is required and boolean. Missing or `false` returns a client error before preflight
execution/service mutation. A true value proceeds through the existing preflight and execution
semantics. Existing consumers must be updated together; no other response or route changes.

Existing state-changing contracts remain confirmation-gated: ticket-tracking create/update/sync/
close/reactivate, Jira creation, handover delivery, and any in-scope generate/regenerate action
send `confirmed: true` only after UI confirmation. Cancellation sends no request. Local actions
must not perform Jira mutations; Jira actions must identify their external effect in the dialog.
Reviewing, rejecting, or publishing a finding is likewise a local NOC-context action: its dialog
names the concise context and destinations, cancellation sends no request, and it does not mutate
the evidence source, Datadog, or Jira.

## Implemented presentation details

`frontend/js/workflow-context.js` owns URL normalization, the ordered workflow bar, query-preserving
links, active-step/next-step presentation, and source-state panels. It issues no requests. The
shared bar replaces duplicated in-scope sidebar links; unrelated navigation remains available.
Dashboard, Tickets, Status, and Investigations show independent source panels, so a failed cache
or request does not erase retained local or page content.

## State presentation contract

| State | Presentation | Safe behavior |
|---|---|---|
| Current | Source and current/updated time where available. | Inspection only. |
| Stale | Explicitly name stale Jira cache and age; keep cached data visible. | No automatic refresh. |
| Unavailable | Name unavailable source and what remains usable. | Keep other sections visible. |
| Error | Show actionable request/action error near affected panel. | Preserve last valid screen content; retry only on operator input. |
| Read-only | State that viewing did not alter Jira/local data or an evidence source. | Never initiate refresh, mutation, or evidence retrieval by another path. |
