# Implementation Plan: Local NOC Tracking

**Branch**: `002-local-noc-tracking` | **Date**: 2026-10-29 | **Spec**:
[spec.md](spec.md)

**Input**: Feature specification from `/specs/002-local-noc-tracking/spec.md`

## Summary

Extend the Jira-first Tickets workflow so an operator can deliberately create, update,
synchronize, close, and reactivate local NOC tracking for a Jira ticket. Jira-owned data remains
read-only in these operations; the local tracking record holds only NOC context and lifecycle
state. The implementation uses the existing ticket, ticket-sync, handover, API, and Tickets-page
boundaries, with an explicit confirmation immediately before every local state change.

## Technical Context

**Language/Version**: Python 3.x; browser JavaScript

**Primary Dependencies**: FastAPI; static browser UI

**Storage**: Existing local NOC files, extended compatibly to hold local tracking context

**Testing**: pytest with temporary NOC roots

**Target Platform**: Local NOC operator web application

**Project Type**: Web application with backend API and static frontend

**Performance Goals**: Local tracking actions and Ticket-list refreshes complete within the
existing Tickets workflow without additional background Jira writes.

**Constraints**: Explicit confirmation is required for every local state change; local actions
must never write, transition, or close Jira issues; sync must preserve NOC context; malformed
local data and Jira-refresh failures must be explicit and non-destructive.

**Scale/Scope**: One Tickets-page workflow, additive local tracking context and lifecycle state,
and compatible handover presentation for existing and newly tracked tickets.

## Constitution Check

*GATE: Passed before Phase 0 research and re-checked after Phase 1 design.*

| Principle | Plan Response | Status |
|-----------|---------------|--------|
| I. Preserve Operational Data Integrity | Validate ticket identifiers and local record state; prevent duplicate active records; preserve existing ticket and handover data. | PASS |
| II. Fail Safely and Explain Failures | Surface malformed local state and explicit-sync failures without overwriting saved NOC context or implying Jira changed. | PASS |
| III. Maintain API and UI Contract Consistency | Define additive ticket-tracking contracts and update the Tickets consumer with the same change. | PASS |
| IV. Test Operational Workflows | Add focused pytest coverage using temporary roots for confirmations, lifecycle transitions, no-Jira-write behavior, sync failure, and handover compatibility. | PASS |
| V. Prefer Simple, Observable Changes | Reuse existing ticket, ticket-sync, handover, API, and Tickets-page boundaries; add no new external integration. | PASS |
| VI. Require Deliberate Operational Execution | Require confirmation immediately before create, update, sync, close, and reactivate actions; Jira remains read-only. | PASS |

**Post-design re-check**: PASS. The data model and contracts keep local tracking lifecycle state
separate from Jira-managed fields and require deliberate operator actions without exceptions.

## Project Structure

### Documentation (this feature)

```text
specs/002-local-noc-tracking/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── api/
│   └── tickets.py                 # Ticket workflow HTTP contract
└── services/
    ├── tickets.py                 # Local ticket records and Jira-ticket projection
    ├── ticket_sync.py             # Explicit Jira-to-local synchronization
    ├── handover.py                # Handover data compatibility
    └── handover_delivery.py       # Existing handover delivery boundary

frontend/
└── tickets.html                   # Ticket list, tracking controls, and confirmations

tests/
├── test_ticket_sync.py            # Sync behavior and local/Jira boundaries
├── test_handover.py               # Existing handover compatibility
└── test_tickets.py                # Ticket tracking lifecycle and API behavior
```

**Structure Decision**: Extend the existing web-application boundaries. The ticket service owns
local tracking persistence and validation; ticket synchronization reads Jira into an explicit,
local-only operation; the ticket API exposes the additive contract; and the Tickets page owns
operator confirmations and state rendering. Handover services remain consumers of compatible
tracked-ticket data.

## Complexity Tracking

No constitutional violations or complexity exceptions are required.
