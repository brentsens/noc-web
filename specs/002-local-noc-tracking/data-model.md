# Data Model: Local NOC Tracking

## Jira Ticket Reference

The identifier and displayed Jira-managed information for the ticket associated with local work.
Jira remains authoritative for all Jira-managed fields.

| Field | Type | Rules |
|-------|------|-------|
| `jiraKey` | string | Required, valid ticket identifier, and immutable for a tracking record. |
| Jira-managed display fields | read-only projection | Refreshed only by an explicit sync; never edited by local tracking actions. |

## Local NOC Tracking Record

An additive local record linked to one Jira ticket.

| Field | Type | Rules |
|-------|------|-------|
| `jiraKey` | string | Identifies the linked Jira ticket. |
| `state` | `active` or `closed` | New records are active; lifecycle changes require confirmation. |
| `nextAction` | string | NOC-owned context, editable only through an explicitly confirmed update. |
| `nocNotes` | string | NOC-owned context, editable only through an explicitly confirmed update. |
| `createdAt` | timestamp | Set when local tracking is explicitly created. |
| `updatedAt` | timestamp | Set when local context or lifecycle state changes. |
| `closedAt` | timestamp or null | Set only when local tracking is explicitly closed. |

### Relationships and compatibility

- One Jira ticket has zero or one **active** local tracking record; prior closed records remain
  historical context.
- A tracking record has exactly one Jira Ticket Reference.
- Existing tracked-ticket records are interpreted as active local tracking records and retain their
  existing NOC context and handover visibility.
- Handover consumes active tracked records using the compatible ticket reference and NOC context.

### State transitions

```text
Jira-only --(explicit create + confirmation)--> Active
Active --(explicit update + confirmation)-----> Active
Active --(explicit sync + confirmation)-------> Active
Active --(explicit close + confirmation)------> Closed
Closed --(explicit reactivate + confirmation)-> Active
```

### Validation and integrity rules

1. Local records contain only the Jira ticket reference, lifecycle metadata, and NOC-managed
   context; Jira-managed fields are not locally editable.
2. Creation and reactivation reject a duplicate active record for the same Jira ticket.
3. Every mutation requires a matching explicit operation and confirmation; absent or cancelled
   confirmation produces no change.
4. Sync cannot change local Next Action, NOC Notes, or lifecycle state.
5. A failed sync cannot replace or delete saved local context.
6. Closing local tracking cannot cause a Jira transition, update, or closure.
