# Implementation Plan: Provider-Independent AI Investigation Generation

**Branch**: `016-ai-investigation-generation` | **Date**: 2026-11-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/016-ai-investigation-generation/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command; its definition describes the execution workflow.

## Summary

Replace the subprocess-based `noc-inv` → GitHub Copilot CLI → Datadog MCP investigation
generator with a provider-independent workflow. Investigation creation will consume only
Feature 015's validated read-only Datadog evidence, minimize it into a bounded package with
stable evidence identifiers, retain the exact previewed snapshot in a bounded in-memory store,
and call the configured Feature 014 AI provider only after explicit confirmation. DeepSeek Flash
is supported through the existing DeepSeek configuration; no provider fallback is permitted.

AI responses are structured JSON, server-validated for required sections, evidence citations,
partial-evidence honesty, bounds, and secret non-disclosure, then rendered into the existing
Markdown investigation format. New investigations carry `ai-evidence` provenance plus a
system-authored evidence provenance and availability map. Existing local persistence, collision
protection, lifecycle, review, inspection, Datadog attachment, and selected-shift behavior remain
intact. Legacy `noc-inv` and `copilot-mcp` investigations remain readable and reviewable.

## Technical Context

**Language/Version**: Python 3.15.2 (project virtual environment); vanilla ES modules for the
frontend.

**Primary Dependencies**: FastAPI 0.162, Pydantic 2.14, Python standard library (`json`, `secrets`,
`threading`, `time`, `urllib`), pytest, and the existing Node-based frontend test harness. No new
runtime dependency is introduced.

**Storage**: Local NOC filesystem for investigation records and reviewed context; a bounded,
process-local in-memory preview store for exact evidence snapshots. No database and no on-disk
preview/evidence cache.

**Testing**: pytest for backend/API/contracts; Node-based DOM/module checks in
`tests/test_frontend_modules.py` for the create/preview UI; existing focused and full-suite
regression commands.

**Target Platform**: Linux workstation/server, including the existing WSL-hosted runtime.

**Project Type**: Web application with a FastAPI backend and static HTML/JavaScript frontend.

**Performance Goals**: Preview completes within the existing Feature 015 Datadog timeout; one
confirmed generation completes within the existing AI provider timeout plus bounded persistence;
no additional AI call occurs before confirmation; preview snapshots are capped at 32 entries and
256 KiB each.

**Constraints**: Feature 015 remains structurally read-only; no Datadog/Jira/ticket/incident/
monitor/notebook/shift mutation; no automatic provider fallback; no credentials in prompts,
logs, responses, exceptions, Markdown, or persisted operational data; no noc-handover changes;
selected-shift synchronization and existing investigation contracts remain compatible.

**Scale/Scope**: Single-workstation NOC deployment with a small number of operators and
investigations; per incident, at most 10 notebook and 10 monitor evidence items from Feature 015;
AI output capped at 64 KiB and 8 items per required section; preview snapshots expire after 10
minutes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Preserve operational data integrity | Existing local investigation files remain authoritative; staging/atomic replace, collision protection, provenance, and reviewed context are reused; no existing record is overwritten. | PASS |
| II. Fail safely and explain failures | Evidence, provider, output, citation, bounds, and configuration failures map to controlled, sanitized errors; no partial record is published. | PASS |
| III. Maintain API/UI contract consistency | Preview/create request and response models, `frontend/js/api.js`, `investigations.html`, and active-incident handoff are updated together; contracts are documented. | PASS |
| IV. Test operational workflows with normal use | Regression coverage spans valid generation, preview, citation failure, partial evidence, provider failure, persistence, lifecycle, and zero-mutation behavior. | PASS |
| V. Prefer simple, observable changes | Reuse Feature 014/015, existing persistence, and existing provider adapters; add only bounded preview/package modules; no new external service or dependency. | PASS |
| VI. Require deliberate operational execution | Preview is non-generative; AI runs only after explicit confirmation; AI output remains advisory and unreviewed until human review. | PASS |

No constitution violations or justified exceptions.

## Project Structure

### Documentation (this feature)

```text
specs/016-ai-investigation-generation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── investigation-generation-api.md
│   ├── investigation-evidence-package.md
│   └── investigation-record-provenance.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created here)
```

### Source Code (repository root)

```text
backend/
├── api/
│   └── investigations.py              # preview/create request models, previewId/incidentId, error mapping
├── services/
│   ├── ai_provider.py                 # investigation prompt profile; provider resolution without fallback
│   ├── copilot_cli.py                 # optional prompt override for configured providers
│   ├── deepseek_provider.py           # optional system prompt; investigation JSON completion
│   ├── investigation_ai.py            # NEW: investigation prompt, envelope, output validation
│   ├── investigation_evidence.py      # NEW: Feature 015 evidence package minimization/bounds
│   ├── investigation_generation.py    # preview/create orchestration, Markdown rendering, persistence
│   ├── investigation_preview_store.py # NEW: bounded TTL in-memory exact preview snapshots
│   ├── investigations.py              # ai-evidence provenance, projection, lifecycle/review compatibility
│   ├── assistant.py                   # accept ai-evidence in investigation routing
│   ├── assistant_context.py           # expose ai-evidence investigation evidence
│   ├── ai_reports.py                  # accept ai-evidence in report routing
│   ├── readiness.py                   # external.datadog + external.aiProvider; legacy tools optional
│   ├── dependency_readiness.py        # existing external.datadog + external.aiProvider surfaces
│   ├── health.py                      # provider/evidence readiness wording
│   └── status.py                      # investigation capability wording
└── config.py                          # existing runtime paths/timeouts; no new credential store

frontend/
├── investigations.html                # create/preview/confirm UI, evidence/provider wording
└── js/
    ├── active-incidents.js            # bounded incidentId/title handoff
    └── api.js                         # preview/create signatures, provenance routing compatibility

docs/
└── workstation-runtime.md             # investigation architecture/provider and readiness wording
README.md                              # operator-facing investigation workflow wording

tests/
├── test_investigation_ai_evidence.py  # NEW: package minimization, citations, partial evidence
├── test_investigation_preview_store.py# NEW: TTL, single-use, bounds, no persistence
├── test_investigation_generation.py   # replace noc-inv tests with evidence/AI generation
├── test_investigation_output_validation.py
├── test_investigation_lifecycle.py
├── test_investigation_projection.py
├── test_investigations.py
├── test_investigation_creation.py
├── test_investigation_attachments.py
├── test_deepseek_provider.py
├── test_ai_provider.py
├── test_assistant.py
├── test_assistant_api.py
├── test_frontend_modules.py
├── test_datadog_readonly.py
└── test_datadog_secrets.py
```

**Structure Decision**: Keep the existing web-application split. Backend orchestration lives in the
existing investigation services and FastAPI router; the only new modules are the evidence package
builder, the bounded preview store, and the investigation AI prompt/validator. The static frontend
continues to call `frontend/js/api.js`; no new framework or service is introduced.

## Phase 0 Research Summary

See [research.md](research.md). Key decisions:

- Consume Feature 015 `get_incident_evidence` only; do not modify Feature 015 retrieval behavior.
- Build a bounded, stable-ID evidence package with explicit availability and no secrets.
- Use a process-local TTL/single-use preview store for the exact previewed snapshot.
- Use structured JSON AI output rendered server-side into the existing investigation Markdown.
- Extend the existing provider adapters with an investigation prompt profile; no fallback.
- Add `ai-evidence` provenance while accepting legacy provenance for existing records.
- Hand off `incidentId` plus title from Active Incidents and require it for preview.
- Keep readiness, lifecycle, review, attachment, and selected-shift behavior compatible.

## Phase 1 Design Summary

See [data-model.md](data-model.md) and [contracts/](contracts/). The design adds:

- `InvestigationPreviewSnapshot` and `EvidencePackage` entities with hard bounds.
- `Investigation AI output` schema with five required sections and inline stable citations.
- Preview/create API contract with `previewId`, `incidentId`, explicit confirmation, and
  sanitized failure codes.
- Persisted `evidence-provenance.json` and extended `generation-status.json` for provenance,
  availability, provider identity, and validation issues.
- Compatibility rules for legacy investigation records and the existing lifecycle/review flow.

## Post-Design Constitution Re-check

| Principle | Post-design result |
|-----------|--------------------|
| I. Preserve operational data integrity | PASS — existing staged publication, collision checks, and reviewed context are reused; new provenance files are system-authored and bounded. |
| II. Fail safely and explain failures | PASS — preview/create contracts define sanitized fail-closed codes for evidence, provider, citation, bounds, and storage failures. |
| III. Maintain API/UI contract consistency | PASS — API, `api.js`, active-incident handoff, and Investigations UI changes are captured together. |
| IV. Test operational workflows with normal use | PASS — quickstart and data-model define focused tests for generation, preview, failure, persistence, legacy compatibility, and zero mutations. |
| V. Prefer simple, observable changes | PASS — no new runtime dependency or external service; existing Feature 014/015 and local persistence are reused. |
| VI. Require deliberate operational execution | PASS — preview remains non-generative; single-use snapshots require explicit confirmation before AI generation. |

No new violations or unresolved design risks were introduced.

## Complexity Tracking

No violations or justified exceptions.
