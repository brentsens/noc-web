# Data Model: NOC Data Flow

## Local NOC Context

The canonical local-only representation of active operational work.

| Field | Type | Rules |
|-------|------|-------|
| `jiraKey` | string | Required unique Jira ticket reference for one local-work entry. |
| `trackingState` | `active` | Only active records appear in an Operational Work Summary. |
| `nextAction` | string | NOC-owned next step; may be empty and must not be invented. |
| `nocNotes` | string | NOC-owned notes; may be empty and must not be replaced with Jira details. |

## Operational Work Summary

An additive projection consumed by Dashboard, Status, shift notes, handover, and End Shift.

| Field | Type | Rules |
|-------|------|-------|
| `items` | list of Local NOC Context | Contains at most one entry per `jiraKey`. |
| `count` | integer | Equals the number of active local-work entries. |
| `available` | boolean | False only when local tracking data cannot be read safely. |
| `error` | string or null | Actionable local-data failure when unavailable. |

### Relationships and lifecycle

- One active Local NOC Context maps to one active local tracking record and one Jira ticket
  reference.
- Closed local records are historical context and are excluded from every active Operational Work
  Summary.
- Each Shift Artifact receives one snapshot of an Operational Work Summary during generation.

### Validation and integrity rules

1. The ticket service is the single source for the Operational Work Summary.
2. No summary or artifact may include Jira-managed ticket fields as Local NOC Context.
3. Every summary item has a unique `jiraKey`; duplicates are rejected before rendering or artifact
   generation.
4. An unavailable summary cannot be silently replaced with Jira data.
5. A failed summary read cannot overwrite an existing shift artifact.
