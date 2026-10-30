# Research: NOC Data Flow

## Decision: Create one canonical active local-work projection

**Rationale**: The existing ticket service already normalizes local tracking state and NOC fields.
Projecting active records once gives every operational workflow consistent data and avoids
reconstructing context from Jira or artifact content.

**Alternatives considered**:

- Build a separate summary in every workflow: rejected because divergent filtering and formatting
  would create inconsistent or duplicate operational context.
- Read the Jira cache for each summary: rejected because Jira-owned data must not become copied
  local context and it can be unavailable.

## Decision: Include only the Jira ticket reference and NOC-owned context

**Rationale**: A compact Jira reference identifies the work while tracking state, Next Action, and
NOC Notes provide the NOC-owned information needed for continuity. Excluding Jira description,
status, priority, assignee, and other Jira fields keeps ownership clear.

**Alternatives considered**:

- Embed a ticket snapshot in every artifact: rejected because it duplicates Jira-managed data and
  becomes stale.
- Omit the Jira reference: rejected because operators could not unambiguously connect context to
  its ticket.

## Decision: Restrict operational summaries to active local records

**Rationale**: Active records represent current work. Closed records remain historical in local
tracking storage but must not be presented as outstanding Dashboard, Status, handover, or End
Shift work.

**Alternatives considered**:

- Include all records with a closed label: rejected because it obscures the actionable work list.
- Delete closed records: rejected because it loses historical local context.

## Decision: Make aggregate failures explicit and non-destructive

**Rationale**: A malformed local record cannot safely be guessed or replaced with Jira data.
Affected workflows must expose a local-data issue while preserving their unrelated existing
content; handover generation must not overwrite an existing artifact after a failed read.

**Alternatives considered**:

- Silently skip malformed records: rejected because operators could miss outstanding work.
- Use cached Jira fields as a fallback: rejected because that violates data ownership and can hide
  the local-data problem.
