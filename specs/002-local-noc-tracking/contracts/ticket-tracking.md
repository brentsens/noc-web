# Ticket Tracking Contract

## Ticket view

Each ticket returned to the Tickets experience includes additive tracking information:

| Field | Meaning |
|-------|---------|
| `trackingState` | `jira-only`, `active`, or `closed`. |
| `localTracking` | Local NOC context when a tracking record exists; absent for Jira-only tickets. |
| `localTracking.nextAction` | NOC-owned next step. |
| `localTracking.nocNotes` | NOC-owned operator notes. |
| `localTracking.closedAt` | Closure time when the local tracking state is closed. |

Jira-managed ticket fields remain read-only in this contract.

## Explicit local tracking operations

The Tickets interface submits one explicit operation at a time:

| Operation | Required input | Confirmation | Success result | Jira effect |
|-----------|----------------|--------------|----------------|-------------|
| Create tracking | Jira ticket reference, initial NOC context | Required | Active local record | None |
| Update context | Active tracking record, Next Action, NOC Notes | Required | Updated local context | None |
| Sync Jira view | Active tracking record | Required | Refreshed Jira-managed projection | Read only |
| Close tracking | Active tracking record | Required | Closed local record | None |
| Reactivate tracking | Closed tracking record | Required | Active local record | None |

The confirmation is part of each operation request. A missing, false, stale, or mismatched
confirmation fails without changing local tracking or Jira.

## Failure contract

| Condition | Required result |
|-----------|-----------------|
| Invalid ticket reference or malformed local tracking data | Clear validation failure; no data change. |
| Duplicate active tracking record | Conflict result that preserves the existing record. |
| Ticket unavailable during requested sync | Clear sync failure; saved local context and tracking state remain unchanged. |
| Operation targets a record in the wrong lifecycle state | Clear state failure; no data change. |
| Any attempted local operation | Jira remains unchanged. |

## Compatibility contract

Existing tracked tickets continue to appear as tracked, retain existing NOC context, and remain
available to existing handover behavior. New fields are additive; consumers that do not use
tracking-state detail continue to receive their existing ticket information.
