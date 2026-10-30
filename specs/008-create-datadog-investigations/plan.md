# Implementation Plan: Confirmation-Gated Datadog Investigation Creation

**Branch**: `main` (planning workspace; feature identifier `008-create-datadog-investigations`) | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)

**Input**: `specs/008-create-datadog-investigations/spec.md`

## Summary

Add a distinct preview-and-confirm creation path to the read-only Investigations experience. Keep `noc-inv` authoritative through a bounded backend adapter, validate and preserve its shift-scoped output as advisory, and reuse existing explicit Review/Reject gates so only concise reviewed findings can propagate. Preview is stateless and read-only; confirmed creation revalidates the request, checks for conflicts, invokes the configured non-interactive command, validates output, and publishes a durable record without exposing command diagnostics.

## Technical Context

**Language/Version**: Python (repository manifests do not pin a version); static JavaScript ES modules
**Primary Dependencies**: FastAPI, Pydantic, existing filesystem-backed NOC services, configured `noc-inv`, GitHub Copilot CLI, Datadog MCP
**Storage**: Existing shift-scoped investigation files under the configured NOC workstation paths
**Testing**: pytest from repository root with temporary storage and mocked command execution; frontend ES-module integrity tests
**Target Platform**: Operator workstation environment supported by the existing NOC Web configuration profile
**Project Type**: Python/FastAPI backend with static HTML/CSS/JavaScript frontend
**Performance Goals**: Preview performs local validation only; generation completes within the configured bounded command timeout
**Constraints**: No shell interpretation, browser/API fetch of Notebook URLs, direct Datadog integration, credential exposure, overwrite, cross-shift writes, or propagation of unreviewed output; preserve Features 001–007
**Scale/Scope**: One explicitly confirmed shift-scoped investigation per request; reuse existing listing, review, readiness, and downstream projection mechanisms

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Plan |
|---|---|---|
| I. Preserve Operational Data Integrity | Validate request values and shift paths; prevent overwrite and isolate historical shifts | Pass: strict validation, conflict handling, staged output and shift-scoped publication |
| II. Fail Safely and Explain Failures | Bound execution, distinguish unavailable/timeout/failure/validation outcomes, sanitize diagnostics | Pass: controlled API states and operator-visible failures without raw output |
| III. Maintain API and UI Contract Consistency | Keep request/response schemas, API client, routes, and UI synchronized | Pass: document the contract before implementation and update all consumers together |
| IV. Test Operational Workflows | Test success/failure using temporary paths and mocks; no real NOC data, network, or credentials | Pass: focused service/API/UI tests and full pytest regression |
| V. Prefer Simple, Observable Changes | Reuse existing service/router/readiness boundaries and surface state | Pass: add a narrow generation adapter while preserving existing inspection and review services |
| VI. Require Deliberate Operational Execution | Require explicit confirmation; generated analysis remains advisory until reviewed | Pass: read-only preview, explicit confirmed create, unchanged Review/Reject gate |

**Pre-research gate**: Pass. No constitution exception is required.

## Project Structure

### Documentation

```text
specs/008-create-datadog-investigations/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── investigations-api.md
│   └── noc-inv-invocation.md
└── tasks.md                 # Created by /speckit-tasks
```

### Source Code

```text
backend/
├── api/investigations.py             # Shift-scoped preview/create API
├── config.py                         # Existing approved workstation profile
└── services/
    ├── investigations.py             # Existing inspection/review/projection gates
    ├── investigation_generation.py   # New bounded noc-inv adapter and output validation
    └── readiness.py                  # Generation command and storage capability readiness

frontend/
├── investigations.html               # Create form, preview, confirm, refreshed selection
└── js/api.js                          # Preview/create API client methods

tests/
├── test_investigations.py             # Existing listing/review/propagation regressions
├── test_investigation_generation.py   # New validation, adapter, timeout, failure cases
├── test_readiness.py                  # Readiness and configured-path cases
├── test_handover.py                   # Reviewed-only handover propagation
├── test_end_shift.py                  # Pending review readiness
├── test_assistant.py                  # Reviewed-only Assistant context
└── test_frontend_modules.py           # Frontend API/module integrity
```

**Structure Decision**: Extend the existing FastAPI investigation router and service surface. Isolate command execution and generated-output validation in a dedicated generation service so listing/review logic and the future operator-facing contract do not depend on subprocess details. Keep the form in the existing Investigations page and use the shared API client and selected-shift context.

## Phase 0 Research

Completed in [research.md](research.md). Existing inspection, explicit review/reject, readiness, selected-shift, and reviewed-only propagation boundaries were identified. The current repository readiness-probes `noc-inv` but has no invocation contract; this plan defines a non-interactive boundary and forbids an interactive fallback.

## Phase 1 Design

- [Data model](data-model.md): request, generated record, validation/review state, and readiness.
- [API and invocation contracts](contracts/): stateless preview, explicitly confirmed creation, and bounded non-interactive command boundary.
- [Quickstart](quickstart.md): isolated regression and end-to-end validation scenarios.

## Constitution Check (Post-Design)

| Principle | Re-evaluation |
|---|---|
| I. Preserve Operational Data Integrity | Pass: input validation and duplicate checks precede generation; output is validated before publication; historical shift is explicit |
| II. Fail Safely and Explain Failures | Pass: bounded process execution, cleanup, sanitized error states, and distinct creation/list-refresh outcomes |
| III. Maintain API and UI Contract Consistency | Pass: API contract is documented and frontend uses the same schemas and explicit confirmation |
| IV. Test Operational Workflows | Pass: command and filesystem cases are mocked/temp-isolated; downstream review gates receive regression coverage |
| V. Prefer Simple, Observable Changes | Pass: no direct Datadog client or second generator; existing service boundaries and readiness are reused |
| VI. Require Deliberate Operational Execution | Pass: preview cannot execute; create requires a confirmed request; generated findings remain unreviewed |

**Post-design gate**: Pass. No unjustified constitution violations or unresolved design clarifications remain.
