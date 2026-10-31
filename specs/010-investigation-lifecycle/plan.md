# Implementation Plan: Operator-Controlled Investigation Lifecycle

**Branch**: `010-investigation-lifecycle` | **Date**: 2026-10-31 | **Spec**:
[spec.md](spec.md)

**Input**: Feature specification from
`/specs/010-investigation-lifecycle/spec.md`

## Summary

Add one operator-controlled lifecycle to each local investigation, independent
of AI generation, validation, and review metadata. Extend the existing
investigation projection to carry active work across shifts without copying
source evidence. Reuse Feature 009's shared incident snapshot for explicitly
confirmed, bounded incident attachments. Make list/detail, Dashboard, Status,
End Shift, and handover consume the same lifecycle projection, with atomic
local writes and no external side effects.

## Technical Context

**Language/Version**: Python 3.x backend; browser-native JavaScript ES modules.

**Primary Dependencies**: Existing FastAPI and Pydantic boundaries, standard
library filesystem/date utilities, existing Feature 009 incident service and
frontend API client. No new dependency is planned.

**Storage**: Existing shift-scoped investigation directories under the
configured NOC root. Keep generation and validation in `generation-status.json`;
extend the existing operator-reviewed context with lifecycle and bounded
attachment metadata. Derive cross-shift views from source records rather than
copying evidence or maintaining a second authoritative index.

**Testing**: Focused pytest coverage with temporary NOC roots and mocked
Feature 009 snapshots; full pytest suite; Python compilation; ES-module syntax
validation; `git diff --check`.

**Target Platform**: Existing local NOC web application: FastAPI backend and
static HTML/CSS/JavaScript frontend.

**Project Type**: Existing web application with file-backed operational
records.

**Performance Goals**: Cross-shift projection reads local metadata only and
must not block on Datadog, Jira, AI generation, or other network services.
Incident selection uses the existing shared snapshot; it does not initiate a
second retrieval.

**Constraints**: Preserve Features 001-009; validate shift dates, investigation
identifiers, and source references before filesystem access; atomically update
local lifecycle records; preserve complete prior records on failure; require
explicit confirmation; keep generated content advisory; never mutate Datadog,
Jira, Local NOC Tracking, Shift Notes, email, or investigation evidence.

**Scale/Scope**: Multiple shifts and investigations under one configured local
NOC root; one optional Datadog incident reference per investigation. The feature
changes investigation lifecycle, cross-shift visibility, incident attachment,
readiness, and handover consumers only.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Research Gate

- **I. Preserve Operational Data Integrity — PASS**: Source records remain at
  their creation shift; paths and identifiers are validated; migration is
  conservative; writes are atomic.
- **II. Fail Safely and Explain Failures — PASS**: Invalid transitions,
  unavailable/stale snapshots, and file-write failures return explicit errors;
  no success-shaped fallback is planned.
- **III. Maintain API and UI Contract Consistency — PASS**: Existing API,
  frontend API client, and all listed lifecycle consumers are updated together.
- **IV. Test Operational Workflows — PASS**: Focused success/failure tests use
  temporary storage and mocked provider snapshots; no live service or operator
  data is needed.
- **V. Prefer Simple, Observable Changes — PASS**: Reuse existing investigation
  and Feature 009 boundaries; no new dependency, integration, or competing
  persistent index.
- **VI. Require Deliberate Operational Execution — PASS**: Lifecycle and
  attachment updates require immediate explicit confirmation; AI and Datadog
  remain advisory/non-authoritative; no external write is introduced.

No constitution exception is required.

## Project Structure

### Documentation

```text
specs/010-investigation-lifecycle/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── investigations-api.md
└── tasks.md                 # Created by /speckit-tasks, not by this plan
```

### Source Code Touchpoints

```text
backend/
├── api/
│   └── investigations.py
└── services/
    ├── investigations.py
    ├── investigation_generation.py
    ├── dashboard.py
    ├── status.py
    ├── end_shift.py
    ├── handover.py
    └── datadog_incidents.py

frontend/
├── investigations.html
├── index.html
├── status.html
├── end-shift.html
└── js/
    └── api.js

tests/
├── test_investigations.py
├── test_investigation_generation.py
├── test_dashboard.py
├── test_status.py
├── test_end_shift.py
├── test_handover.py
└── test_datadog_incidents_api.py
```

**Structure Decision**: Keep this in the existing FastAPI/static-web project.
The investigation service remains the shared source for lifecycle, migration,
and cross-shift projection. Existing API routes and frontend consumers are
extended in place; Feature 009 remains the sole incident snapshot provider.
No new top-level project, service dependency, or persistent cross-shift index
is planned.

## Design Decisions

1. **Lifecycle persistence and migration**: Extend existing operator-reviewed
   context; keep generation/validation metadata unchanged. Migrate only
   explicitly reviewed records using existing normalized exact full-match
   state classifications. The existing active/resolved allowlists are
   documented in [research.md](research.md); add exact `done (cured)` handling
   from the Feature 010 migration requirement. Unknown values fall back to
   Ready for Review. Generated Markdown `Status` alone never sets lifecycle.
2. **Transition graph**: Apply the forward-only graph confirmed for planning:
   Ready for Review → Escalated to Incident or Cured; Escalated to Incident →
   Cured; Cured is terminal. Require explicit confirmation for every transition
   and a non-empty reviewed finding for escalation/cure.
3. **Cross-shift visibility**: Derive active and historical projections from
   validated source records. Include creation shift, selected shift, lifecycle,
   last-change time/shift, finding, safe source identity, and bounded incident
   reference. Never copy raw generated evidence to later shifts.
4. **Datadog attachment**: At confirmation, read the shared Feature 009
   snapshot without initiating a refresh. Require CURRENT freshness and exact
   ACTIVE/STABLE state. Preserve the exact bounded reference; a later successful
   current snapshot omitting the ID creates a warning, not a local transition.
5. **Readiness and handover**: Dashboard, Status, End Shift, and handover
   consume the same projection. Ready blocks and is excluded; reviewed
   escalation may contribute concise operator context; cure does not produce
   future work and may appear as a cure-shift outcome.
6. **API/UI contract**: Extend the existing review route with an enum lifecycle
   value and selected-shift context; add a confirmed attachment route and an
   active/history list view. Keep selected shift visible and use the exact
   Datadog link with safe new-tab attributes.

## Post-Design Constitution Check

- **I — PASS**: One source record remains authoritative; safe source identity,
  conservative migration, atomic writes, and no evidence duplication are
  defined.
- **II — PASS**: Stale/unavailable cache and storage/validation failures are
  explicit; failed writes preserve the prior complete record.
- **III — PASS**: API request/response changes, frontend client, UI, Dashboard,
  Status, End Shift, and handover are in the same scope.
- **IV — PASS**: Quickstart and focused regression coverage include success,
  failure, migration, atomicity, and cross-shift workflows with isolated data.
- **V — PASS**: Existing services, route boundaries, storage, and shared
  snapshot are reused; no redundant index or external integration is added.
- **VI — PASS**: Confirmation is explicit; cured is operator-only; no external
  mutation or generated-content authority is introduced.

No constitution exception is required. Phase 0 research and Phase 1 design
artifacts are complete; task decomposition belongs to `/speckit-tasks`.

## Complexity Tracking

No constitution violations or additional architectural projects are planned.
