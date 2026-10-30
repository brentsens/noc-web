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
| Investigations | `GET /api/shifts/{shift}/investigations` | Render available investigations or source-specific error/unavailable state. |
| Status | `GET /api/status/{shift}` | Render status, local work, and existing `jiraCache` freshness independently. |
| Start Shift | `GET /api/start-shift/{shift}` | Render preflight only. |
| End Shift | `GET /api/end-shift/{shift}` | Render preflight only. |

Read navigation, status inspection, and cache-health viewing must issue no POST/PATCH, Jira refresh,
or local write. A source failure must not replace unrelated valid content.

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
| Read-only | State that viewing did not alter Jira/local data. | Never initiate refresh or mutation. |
