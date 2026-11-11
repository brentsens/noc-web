# Implementation Plan: Provider-Independent AI Handover Generation

**Branch**: `017-ai-handover-generation` | **Date**: 2026-11-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/017-ai-handover-generation/spec.md`

## Summary

Replace the `noc-handover` → GitHub Copilot CLI generation path with a provider-independent
handover workflow. NOC Web will assemble mandatory factual handover sections deterministically
from validated shift evidence, including every open ticket across validated local and remote
sources. It will then invoke the configured Feature 014 AI provider for bounded advisory analysis,
validate exact evidence citations and stale/partial disclosure internally with a strict fail-closed
model, and persist the existing deterministic handover Markdown format plus a versioned provenance
sidecar. AI-validated citations are retained in provenance/internal validation, not emitted as
internal citation syntax in the final email body.

Preview is deterministic and read-only. Every confirmed generation invokes the configured
provider; provider failure fails closed and preserves any existing handover. Regeneration
archives the previous handover and restores it on failure. Existing End Shift readiness,
delivery preview/confirmation, recipient handling, Microsoft 365 transport, selected-shift
behavior, investigation review boundaries, and local persistence remain compatible.
`noc-handover` and Copilot CLI become optional compatibility capabilities rather than
requirements.

## Technical Context

**Language/Version**: Python 3.15.2 (project virtual environment); vanilla ES modules for the
frontend.

**Primary Dependencies**: FastAPI, Pydantic, Python standard library, pytest, and the existing
Node-based frontend test harness. No new runtime dependency is introduced.

**Storage**: Existing local NOC filesystem for handover Markdown, archives, and shift artifacts;
one additive `handover-provenance.json` sidecar per handover. No database.

**Testing**: pytest for backend/API/evidence/AI validation; Node-based frontend module tests for
End Shift preview/generation/delivery wording and handover API client behavior.

**Target Platform**: Linux workstation/server, including the existing WSL-hosted runtime.

**Project Type**: Web application with a FastAPI backend and static HTML/JavaScript frontend.

**Performance Goals**: Deterministic preview returns without an AI call; confirmed generation makes
one bounded AI provider call within the existing provider timeout, then persists atomically.
Evidence assembly and validation are bounded by configured package and ticket limits.

**Constraints**: All open tickets must be included; over-bound ticket or evidence sets fail closed
rather than truncating. No automatic provider fallback. No credentials in prompts, logs, handover
Markdown, API responses, frontend output, exceptions, sidecars, archives, or persisted data. No
Datadog mutation. No AI-authored mandatory factual sections. No change to Microsoft 365 transport.

**Scale/Scope**: One handover per selected shift; at most 1 MiB evidence package, 500 open tickets,
2,000 shift-note entries, 200 investigations, and 100 Datadog incident context items; AI advisory
output capped at 64 KiB and eight items per advisory subsection. Over-bound content fails closed.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Preserve operational data integrity | Existing handover path/format, selected-shift association, atomic persistence, collision protection, and archive/restore behavior are reused; the new sidecar is additive and versioned. | PASS |
| II. Fail safely and explain failures | Evidence, ticket-source, readiness, provider, citation, bounds, and storage failures map to controlled sanitized errors; no partial handover is published. | PASS |
| III. Maintain API/UI contract consistency | Generation-preview, generate/regenerate request extensions, `frontend/js/api.js`, and End Shift UI are updated together; delivery endpoints remain unchanged. | PASS |
| IV. Test operational workflows with normal use | Focused tests cover all ticket completeness, valid DeepSeek generation, citations, stale/partial evidence, provider failures, credentials, regeneration, persistence, readiness, and delivery compatibility. | PASS |
| V. Prefer simple, observable changes | Reuse existing handover, ticket, investigation, status, readiness, and AI provider boundaries; add only focused evidence/AI helpers and an additive sidecar. | PASS |
| VI. Require deliberate operational execution | Preview is non-generative; every confirmed generation invokes AI; generation/regeneration/replacement/delivery require explicit confirmation; AI remains advisory and unreviewed. | PASS |

No constitution violations or justified exceptions.

## Project Structure

### Documentation (this feature)

```text
specs/017-ai-handover-generation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── handover-generation-api.md
│   ├── handover-evidence-package.md
│   └── handover-record-format.md
└── tasks.md              # Created later by /speckit.tasks
```

### Source Code (repository root)

```text
backend/
├── api/
│   └── handover.py                    # generation-preview endpoint, previewDigest, error mapping
├── services/
│   ├── handover.py                    # deterministic assembly, generation, regeneration, persistence
│   ├── handover_ai.py                 # NEW: handover prompt, envelope, exact-citation validator
│   ├── handover_evidence.py           # NEW: bounded evidence package, ticket union, stable IDs, digest
│   ├── handover_delivery.py           # unchanged delivery transport; compatibility verification only
│   ├── end_shift.py                   # readiness/preflight wording and gates
│   ├── readiness.py                   # noc-handover optional; handover capability wording
│   ├── health.py                      # remove noc-handover requirement
│   ├── status.py                      # optional compatibility wording
│   ├── dependency_readiness.py        # legacy noc-tools optional wording
│   ├── tickets.py                     # local open-ticket evidence (read-only)
│   ├── jira_ticket_queue.py           # remote open-ticket evidence (read-only)
│   ├── shift_notes.py                 # shift-note evidence (read-only)
│   ├── investigations.py              # reviewed-findings/lifecycle evidence (read-only)
│   ├── datadog_incidents.py           # already-available read-only incident snapshot
│   ├── dashboard.py                   # dashboard/status evidence (read-only)
│   └── ai_provider.py                 # existing prompt-profile provider resolution
└── config.py                          # existing runtime paths/timeouts

frontend/
├── end-shift.html                     # deterministic preview, generation/regeneration wording
└── js/
    └── api.js                         # generation-preview/generate/regenerate client functions

docs/
└── workstation-runtime.md             # handover architecture, readiness, optional tooling
README.md                              # operator-facing handover workflow wording

tests/
├── test_handover_evidence.py          # NEW: ticket union/completeness, bounds, stable IDs, availability
├── test_handover_ai.py                # NEW: prompt/envelope/citations/advisory bounds
├── test_handover_preview.py           # NEW: deterministic preview/no AI/no state change
├── test_handover.py                   # generation/regeneration/format/sidecar compatibility
├── test_handover_delivery.py          # NEW: delivery preview/send/recipients/M365 compatibility
├── test_ai_provider.py                # provider prompt profile/no-fallback compatibility
├── test_deepseek_provider.py          # DeepSeek Flash prompt/response compatibility
├── test_end_shift.py                  # readiness/preflight/UI contract
├── test_readiness.py
├── test_readiness_api.py
├── test_dependency_readiness.py
├── test_status.py
├── test_tickets.py
├── test_shift_notes.py
├── test_investigations.py
├── test_datadog_readonly.py
├── test_datadog_secrets.py
└── test_frontend_modules.py
```

**Structure Decision**: Keep the existing web-application split. Refactor the existing handover
service as the orchestration boundary; add focused evidence and AI modules rather than a new
workflow service. End Shift remains the UI entry point, and Microsoft 365 delivery remains a
separate unchanged module.

## Phase 0 Research Summary

See [research.md](research.md). Key decisions:

- Build the mandatory handover first from validated shift evidence; AI analysis is validated
  internally and is never emitted as AI-specific sections in the final handover.
- Include every validated open ticket from the union of local and remote sources; stale/partial
  entries are included with qualification; over-bound or unestablishable ticket sets fail closed.
- Use exact handover-specific stable evidence IDs and the same strict fail-closed citation model
  as Feature 016, with no repair/remapping.
- Always invoke the configured provider for confirmed generation; fail closed on failure; no
  deterministic-only final path and no fallback.
- Add deterministic generation preview, an optional `previewDigest`, and a versioned provenance
  sidecar while preserving the Markdown format, archive, and delivery contracts.
- Preserve reviewed/unreviewed investigation boundaries and make `noc-handover`/Copilot optional.

## Phase 1 Design Summary

See [data-model.md](data-model.md) and [contracts/](contracts/). The design adds:

- `HandoverEvidencePackage`, `HandoverEvidenceReference`, `TicketCompleteness`,
  `DeterministicHandoverContent`, `AdvisoryAIOutput`, `HandoverPreview`, and
  `HandoverProvenanceRecord` entities.
- A deterministic preview endpoint and optional evidence digest validation.
- Deterministic final Markdown with the established intro/signature and no AI-specific sections or
  internal citation markers.
- A versioned `handover-provenance.json` sidecar retaining advisory validation citations and
  evidence provenance.
- Stable IDs for shift notes, tickets, investigations, incidents, status/dashboard, and readiness.
- Strict advisory output schema, exact citation validation, bounds, and availability contradiction
  rejection.
- Compatibility rules for existing handover Markdown, archives, delivery, and legacy records.

## Post-Design Constitution Re-check

| Principle | Post-design result |
|-----------|--------------------|
| I. Preserve operational data integrity | PASS — atomic Markdown/sidecar publication, archive/restore, selected-shift paths, and collision checks are preserved. |
| II. Fail safely and explain failures | PASS — preview/generate/regenerate contracts define sanitized fail-closed errors for evidence, tickets, readiness, provider, citations, bounds, and storage. |
| III. Maintain API/UI contract consistency | PASS — API models, `api.js`, End Shift UI, and delivery compatibility are updated together. |
| IV. Test operational workflows with normal use | PASS — quickstart and data model define focused tests for completeness, preview, AI validation, regeneration, persistence, and delivery. |
| V. Prefer simple, observable changes | PASS — existing services/provider boundaries are reused; the provenance sidecar is additive and AI advisory content stays internal. |
| VI. Require deliberate operational execution | PASS — preview is deterministic; generation always invokes AI only after confirmation; AI remains advisory and reviewed boundaries stay intact. |

No new violations or unresolved design risks.

## Complexity Tracking

No violations or justified exceptions.
