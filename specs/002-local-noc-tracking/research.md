# Research: Local NOC Tracking

## Decision: Reuse the existing Tickets, ticket-sync, and handover boundaries

**Rationale**: The repository already separates ticket presentation, local ticket services,
explicit Jira synchronization, and handover workflows. Extending those boundaries keeps the new
workflow compatible with existing tracked tickets and avoids a second source of ticket state.

**Alternatives considered**:

- Introduce a separate tracking application: rejected because it would duplicate ticket and
  handover context.
- Store NOC context in Jira: rejected because the feature requires Jira-managed fields to remain
  authoritative and local operations to avoid Jira changes.

## Decision: Model local tracking as a separate lifecycle over a Jira ticket reference

**Rationale**: A local record can reference exactly one Jira ticket while retaining only
NOC-owned fields and lifecycle state. This makes ownership visible, prevents duplicate active
tracking, and allows closure without implying a Jira transition.

**Alternatives considered**:

- Copy Jira fields into the local record as authoritative values: rejected because it confuses
  ownership and risks stale or overwritten Jira information.
- Treat tracking closure as Jira closure: rejected because local NOC work can finish while the
  Jira issue remains open.

## Decision: Require a confirmation immediately before every local mutation

**Rationale**: Creating, editing, synchronizing, closing, and reactivating tracking affect
operational state. A confirmation immediately before each operation satisfies deliberate
execution requirements while allowing read-only ticket viewing without a prompt.

**Alternatives considered**:

- Save automatically while an operator types: rejected because it silently changes operational
  state.
- Use one global confirmation setting: rejected because it is not an immediate confirmation for
  each state-changing action.

## Decision: Make synchronization explicit and read-only toward Jira

**Rationale**: A requested sync refreshes the Jira-owned view for a tracked ticket while retaining
the saved local Next Action and NOC Notes. Failure leaves the existing local record unchanged and
is reported to the operator.

**Alternatives considered**:

- Refresh automatically when the Tickets page loads: rejected because the specification requires
  explicit operator intent.
- Push local context to Jira during sync: rejected because the feature expressly prohibits
  implicit Jira modification.
