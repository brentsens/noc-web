# Quickstart: NOC Data Flow

## Prerequisites

- Run commands from the repository root.
- Use the repository's isolated test environment; do not use a real NOC directory, Jira service,
  or credentials.

## Focused validation

1. Run the affected workflow tests:

   ```bash
   .venv/bin/python -m pytest tests/test_tickets.py tests/test_dashboard.py tests/test_status.py tests/test_shift_notes.py tests/test_handover.py tests/test_end_shift.py
   ```

2. Verify the contract scenarios in [local-work-summary.md](contracts/local-work-summary.md):
   - Dashboard, Status, and End Shift return the same active local-work summary;
   - the summary contains only the Jira reference, tracking state, Next Action, and NOC Notes;
   - closed work is absent from every active summary;
   - generated shift artifacts include each active ticket at most once;
   - a local-data failure is explicit and does not substitute Jira data or overwrite an artifact;
   - all affected workflows leave Jira unchanged.

3. Run the full suite:

   ```bash
   .venv/bin/python -m pytest tests
   ```

## Operator validation

1. Create active local tracking work with a Next Action and NOC Note, then open Dashboard, Status,
   and End Shift. Confirm all three show the same local work and no copied Jira details.
2. Generate a handover and inspect shift notes. Confirm one entry per active Jira reference with
   local context only.
3. Close the local tracking record and repeat the views and generation. Confirm it is absent from
   active work while unrelated existing information remains visible.
4. Use an isolated malformed local record. Confirm affected workflows report a local-data issue
   without replacing it with Jira data or modifying an existing handover.
