# Quickstart: Local NOC Tracking

## Prerequisites

- Run commands from the repository root.
- Use the repository's isolated test environment; do not use a real NOC directory, Jira service,
  or credentials.

## Focused validation

1. Run ticket tracking, synchronization, and handover tests:

   ```bash
   .venv/bin/python -m pytest tests/test_tickets.py tests/test_ticket_sync.py tests/test_handover.py
   ```

2. Verify the contract scenarios in [ticket-tracking.md](contracts/ticket-tracking.md):
   - create a record only after explicit confirmation;
   - update Next Action and NOC Notes only after explicit confirmation;
   - sync only after explicit confirmation and retain NOC context;
   - close and reactivate local tracking only after explicit confirmation;
   - verify every local operation leaves Jira unchanged;
   - verify a sync failure preserves local context;
   - verify an existing tracked ticket remains available to handover.

3. Run the full suite:

   ```bash
   .venv/bin/python -m pytest tests
   ```

## Operator validation

1. Start the local application using the repository's normal development command and open the
   Tickets experience.
2. Select a Jira-only ticket, choose to start local tracking, and confirm the action. Verify the
   new active state, Next Action, and NOC Notes are clear and Jira-managed information has not
   changed.
3. Update the local context and confirm the save. Verify cancelling the confirmation instead
   leaves the saved context unchanged.
4. Request and confirm a sync. Verify Jira-managed display information refreshes, local context
   remains unchanged, and an unavailable Jira ticket produces a clear error without data loss.
5. Request and confirm local tracking closure. Verify the Jira ticket is unchanged and the local
   tracking state is closed. Reactivate only through a separate explicit confirmation.
6. Open or prepare a handover and verify both legacy and newly tracked tickets remain available
   with their NOC context.
