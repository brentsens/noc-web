# Local Work Summary Contract

## Additive response field

Dashboard, Status, and End Shift responses gain the same additive `localWork` object:

```json
{
  "localWork": {
    "available": true,
    "error": null,
    "count": 1,
    "items": [
      {
        "jiraKey": "NOC-100",
        "trackingState": "active",
        "nextAction": "Collect service logs",
        "nocNotes": "Awaiting the next maintenance window"
      }
    ]
  }
}
```

Existing response fields retain their current meaning.

## Field semantics

| Field | Required | Meaning |
|-------|----------|---------|
| `available` | Yes | Whether active local tracking context was read safely. |
| `error` | Yes | `null` when available; otherwise an actionable local-data failure. |
| `count` | Yes | Number of active local-work entries. |
| `items` | Yes | Unique active local NOC context entries. |
| `items[].jiraKey` | Yes | Jira ticket reference only. |
| `items[].trackingState` | Yes | Always `active` for this summary. |
| `items[].nextAction` | Yes | Local NOC next action. |
| `items[].nocNotes` | Yes | Local NOC notes. |

The object contains no Jira-managed summary, description, status, priority, assignee, or other
Jira-owned fields.

## Shift artifact contract

When shift notes or handover generation includes outstanding local work, it emits one local-work
section from the same summary:

```text
## Active Local NOC Work

- NOC-100
  - Next Action: Collect service logs
  - NOC Notes: Awaiting the next maintenance window
```

The section is absent when there is no active local work. It excludes closed records and all
Jira-managed ticket fields. Duplicate `jiraKey` entries are invalid. An unavailable summary
returns an actionable failure and does not overwrite an existing shift artifact.

## Read-only guarantee

Dashboard, Status, shift-note display, handover generation, and End Shift preflight read local
tracking data only. They do not create, update, transition, close, or otherwise modify Jira
tickets.
