# Quickstart: Validate Operator Workflow

## Prerequisites

Use the repository Python environment and an isolated NOC root used by pytest. Do not point tests
at real operational data or Jira credentials.

## Focused automated validation

After implementation, run:

```bash
./.venv/bin/python -m pytest tests/test_start_shift.py tests/test_dashboard.py tests/test_tickets.py \
  tests/test_status.py tests/test_end_shift.py tests/test_jira_cache.py
```

Expected: all tests pass, including false/missing Start Shift confirmation, existing ticket
confirmation behavior, cache read-only behavior, and preservation of valid local work when another
source is unavailable. Include focused investigation tests for `noc-inv`/Copilot MCP provenance,
read-only evidence failures/no-result, advisory-versus-reviewed state, and reviewed-only
propagation with no raw evidence. Add the focused frontend test command used by the repository if
static-page behavior is given a test harness.

The shared workflow module can be parsed as an ES module without starting the app:

```bash
node --input-type=module --check < frontend/js/workflow-context.js
```

## Manual workflow validation

1. Serve the app using the project’s documented FastAPI command and open
   `start-shift.html?shift=2026-10-29`.
2. Follow Start Shift → Dashboard → Tickets → Investigations → Status → End Shift. Confirm every
   URL retains exactly `?shift=2026-10-29`, the workflow bar highlights the page, and selected
   context/next step remain clear.
3. Open an in-scope URL without `shift`; verify it normalizes to today. Use `?shift=invalid` and
   verify an actionable error appears with safe navigation and no date API request.
4. With a stale and then unavailable Jira cache, verify the distinction is explicit, cached data
   remains visible when stale, and local/investigation content remains when available. Verify a
   failed investigation request affects only its panel.
5. Inspect Dashboard, Tickets, and Status; verify no cache refresh, Jira mutation, or local write
   occurs. See [operational-workflow.md](contracts/operational-workflow.md) for read guarantees.
6. Attempt each visible state-changing action. Cancel its confirmation and verify no network
   mutation/no artifact change; confirm and verify only the stated local or Jira effect. Include
   Start Shift and verify its POST includes `{ "confirmed": true }`.
7. Open an investigation with `noc-inv` or Copilot MCP evidence. Verify it identifies the source as
   read-only, does not make a direct Datadog request, and labels AI analysis advisory. Simulate an
   evidence failure/no-result; verify its source state is actionable while the rest of the workflow
   remains visible.
8. Leave an advisory unreviewed and verify it appears in none of notes, Dashboard, Status, End
   Shift, or handover. Review a concise finding through its confirmation gate, then verify only
   that finding/state is propagated. Inspect each destination and confirm raw notebook/log/MCP
   evidence and Jira-ticket investigation material are absent.

Refer to [data-model.md](data-model.md) for state and confirmation semantics and
[operational-workflow.md](contracts/operational-workflow.md) for compatibility requirements.
