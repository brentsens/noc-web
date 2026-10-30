# Implementation Plan: NOC Data Flow

**Branch**: `003-noc-data-flow` | **Date**: 2026-10-29 | **Spec**:
[spec.md](spec.md)

**Input**: Feature specification from `/specs/003-noc-data-flow/spec.md`

## Summary

Expose one active local NOC-work projection from the existing ticket service and reuse it across
Dashboard, Status, shift notes, handover generation, and End Shift. The projection carries only
the Jira ticket reference, tracking state, Next Action, and NOC Notes; it intentionally excludes
Jira-owned ticket details. All affected read and artifact-generation workflows remain read-only
toward Jira.

## Technical Context

**Language/Version**: Python 3.x; browser JavaScript

**Primary Dependencies**: FastAPI; static browser UI

**Storage**: Existing local ticket files and shift artifacts

**Testing**: pytest with temporary NOC roots

**Target Platform**: Local NOC operator web application

**Project Type**: Web application with backend API and static frontend

**Performance Goals**: Each workflow obtains its local-work summary during its existing request or
artifact generation, without external Jira refreshes or duplicate ticket scans.

**Constraints**: Local-work summaries contain only local state, Jira ticket references, Next
Action, and NOC Notes; closed records are excluded from active summaries; malformed local data
must produce explicit, non-destructive failure behavior; no affected workflow may write Jira.

**Scale/Scope**: One shared local-work projection, additive Dashboard/Status/End Shift response
fields, shift-note and handover inclusion, and focused workflow regression coverage.

## Constitution Check

*GATE: Passed before Phase 0 research and re-checked after Phase 1 design.*

| Principle | Plan Response | Status |
|-----------|---------------|--------|
| I. Preserve Operational Data Integrity | Derive summaries from validated active local records, preserve existing shift artifacts, and prevent duplicate entries by Jira ticket reference. | PASS |
| II. Fail Safely and Explain Failures | Surface unreadable local tracking data explicitly without substituting Jira data or overwriting artifacts. | PASS |
| III. Maintain API and UI Contract Consistency | Add documented, additive local-work summaries and update all Dashboard, Status, and End Shift consumers together. | PASS |
| IV. Test Operational Workflows | Add isolated pytest coverage for every affected read/generation flow, including closed data, malformed data, duplication, and no Jira writes. | PASS |
| V. Prefer Simple, Observable Changes | Reuse the ticket, dashboard, status, shift-note, handover, and End Shift boundaries with no new integration. | PASS |
| VI. Require Deliberate Operational Execution | All new projection reads are read-only; existing End Shift execution gates remain unchanged and no Jira action is added. | PASS |

**Post-design re-check**: PASS. The shared projection and additive contracts preserve local/Jira
ownership, artifact integrity, and existing confirmation boundaries without exceptions.

## Project Structure

### Documentation (this feature)

```text
specs/003-noc-data-flow/
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
│   ├── dashboard.py               # Dashboard response contract
│   ├── status.py                  # Status response contract
│   ├── shift_notes.py             # Shift-note workflow contract
│   ├── handover.py                # Handover-generation contract
│   └── end_shift.py               # End Shift preflight and execution contract
└── services/
    ├── tickets.py                 # Canonical active local-work projection
    ├── dashboard.py               # Dashboard aggregation
    ├── status.py                  # Status aggregation
    ├── shift_notes.py             # Shift-note persistence and presentation
    ├── handover.py                # Handover artifact generation
    └── end_shift.py               # End Shift aggregation and safeguards

frontend/
├── index.html                     # Dashboard local-work display
├── status.html                    # Status local-work display
└── end-shift.html                 # End Shift local-work display

tests/
├── test_tickets.py                # Local-work projection behavior
├── test_dashboard.py              # Dashboard aggregation
├── test_status.py                 # Status aggregation
├── test_shift_notes.py            # Shift-note local-context behavior
├── test_handover.py               # Handover content and deduplication
└── test_end_shift.py              # End Shift local-work behavior
```

**Structure Decision**: The ticket service owns a single active local-work projection. Each
operational service consumes it as an additive input, preserving its own existing data and
workflow behavior. API routes expose additive response fields, while the three affected static
views render the same local-only summary.

## Complexity Tracking

No constitutional violations or complexity exceptions are required.
