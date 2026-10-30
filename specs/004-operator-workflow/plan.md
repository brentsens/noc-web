# Implementation Plan: Operator Workflow

**Branch**: `004-operator-workflow` | **Date**: 2026-10-29 | **Spec**: [spec.md](spec.md)

## Summary

Unify Start Shift, Dashboard, Tickets, Investigations, Status, and End Shift around a URL-backed
`shift` context. A shared frontend workflow shell will preserve that context in every navigation
link, show the current operational step and source state, and keep inspection read-only. Existing
FastAPI read contracts, the Jira cache, local tracking, and handover remain authoritative; only an
additive Start Shift confirmation request field is required to make its execution gate explicit.

## Technical Context

**Language/Version**: Python 3.x; browser JavaScript (ES modules); HTML/CSS

**Primary Dependencies**: FastAPI, Pydantic, Starlette static files; pytest

**Storage**: Existing local NOC workspace, shift artifacts, local ticket-tracking files, and Jira
cache (`.jira-open-tickets.json`)

**Testing**: pytest with temporary NOC roots; focused static-UI/JS tests where established

**Target Platform**: Local NOC operator web application in a modern browser

**Project Type**: FastAPI web service with static frontend

**Performance Goals**: Changing or following workflow navigation updates context without a Jira
refresh; each view uses its existing read request(s) only.

**Constraints**: `shift` is an ISO `YYYY-MM-DD` query parameter; absent means browser-local today;
invalid values never call shift APIs; read-only views never refresh Jira or mutate local data;
state changes require an immediately preceding explicit confirmation.

**Scale/Scope**: Six existing workflow views, their shared links/context presentation, existing
backend contracts, and focused regression coverage.

## Constitution Check

*GATE: Passed before Phase 0 research and re-checked after Phase 1 design.*

| Principle | Plan response | Status |
|---|---|---|
| I. Preserve Operational Data Integrity | Validate URL dates before API use; retain current artifacts, cache, and local-tracking ownership. | PASS |
| II. Fail Safely and Explain Failures | Render source-specific current/stale/unavailable/error/read-only states; retain independent data. | PASS |
| III. Maintain API and UI Contract Consistency | Preserve all existing reads and document the only additive Start Shift confirmation body. | PASS |
| IV. Test Operational Workflows | Add isolated API/service and frontend behavior coverage for URL context, failures, and confirmation cancellation. | PASS |
| V. Prefer Simple, Observable Changes | Reuse current routers, services, client, static pages, cache-health response, and local-work projection. | PASS |
| VI. Require Deliberate Operational Execution | Make Start Shift confirmation explicit; preserve existing confirmed bodies for tracking/Jira/handover delivery and never mutate during reads. | PASS |

**Post-design re-check**: PASS. No exception is required: the design neither introduces an external
integration nor changes data ownership, and its sole contract addition makes an existing mutation
safer and observable.

## Project Structure

### Documentation (this feature)

```text
specs/004-operator-workflow/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── operational-workflow.md
```

### Source Code (repository root)

```text
backend/
├── api/
│   ├── dashboard.py          # GET /api/dashboard/{shift_date}
│   ├── investigations.py     # GET shift investigation endpoints
│   ├── start_shift.py        # Start Shift preflight/execution gate
│   ├── status.py             # Status and Jira cache health response
│   └── tickets.py            # Local tracking confirmation-gated actions
└── services/
    ├── dashboard.py          # Dashboard aggregation
    ├── end_shift.py          # End Shift preflight
    ├── jira_cache.py         # Cache health (read-only)
    ├── start_shift.py        # Workspace creation/Jira refresh execution
    ├── status.py             # Status aggregation
    └── tickets.py            # Local NOC tracking model

frontend/
├── js/api.js                 # Shared request client
├── index.html                # Dashboard
├── tickets.html
├── investigations.html
├── start-shift.html
├── status.html
└── end-shift.html

tests/
├── test_dashboard.py
├── test_end_shift.py
├── test_jira_cache.py
├── test_start_shift.py
├── test_status.py
└── test_tickets.py
```

**Structure Decision**: Add a small shared frontend workflow-context/navigation module (and shared
CSS component where needed), then have the six pages initialize it before their existing view
loader. Keep aggregation and persistence inside existing backend services; no workflow database,
new router, or cache is introduced.

## Implementation Outline

1. Normalize `shift` on each named page: accept only ISO dates, use local today when absent, replace
   the URL with `?shift=YYYY-MM-DD`, render an actionable invalid-context state otherwise, and pass
   the value to its existing date-based loader. Tickets carries the context in navigation/UI but
   keeps its existing unscoped ticket endpoint.
2. Render one shared workflow bar with selected date, active step, ordered links (Start Shift →
   Dashboard → Tickets → Investigations → Status → End Shift), and a concise next-action link based
   only on already-loaded/preflight state. Every workflow link and dashboard deep link preserves
   `shift`.
3. Standardize source panels: current (timestamp/normal), stale (data remains usable with age),
   unavailable (source did not provide data), error (request/action failed with retry or safe next
   step), and read-only (no mutation/refresh occurred). Dashboard, Tickets, and Status identify
   Jira cache separately from local work; investigations identifies its own unavailable/error state.
4. Remove page-local duplicate date/navigation/action controls only after the shared bar supplies
   their information. Keep Jira-managed ticket fields out of local-work summaries and retain
   existing handover content/links.
5. Route every mutating control through an immediate modal/dialog that names the exact local or
   Jira effect. Cancel closes without a request; confirm sends the existing `confirmed: true` body.
   Change Start Shift POST to require the same explicit boolean body and return existing error
   semantics; no read endpoint gets a mutation or refresh.
6. Add focused tests for date/query propagation and invalid dates, state rendering, confirmation
   cancel/confirm behavior, Start Shift missing/false confirmation, and no-write read paths.

## Complexity Tracking

No constitutional violations or complexity exceptions are required.
