# Implementation Plan: Bounded NOC AI Assistant

**Branch**: `006-ai-assistant` | **Date**: 2026-10-29 | **Spec**:
[spec.md](spec.md)

**Input**: Feature specification from `specs/006-ai-assistant/spec.md`

## Summary

Add a transient, selected-shift AI review surface to the FastAPI/static-web application. A
read-only backend mediator builds the minimum safe evidence envelope from existing selected-shift
projections, including the cached Jira queue without refreshing it, and vetted noc-inv/Copilot
investigation metadata. Its provider-neutral callable defaults to a bounded local GitHub Copilot
CLI adapter, using the operator's existing authenticated session, and remains replaceable by an
approved runtime provider. The CLI receives a temporary context file and has no available tools.
The assistant distinguishes
source-grounded facts, operator-reviewed investigation findings, AI-generated observations, and
AI-generated recommendations. Reviewed findings come only from existing human-reviewed
investigation context; the assistant never generates them. The mediator discards all request
material on completion or failure. The UI preserves `?shift=` context, discloses transient generic
question handling and the narrow predefined-action report persistence exception before
submission, routes recommendations only to existing workflows, and never opens an operational
action, command, refresh/sync, Datadog, or other external path.

## Technical Context

**Language/Version**: Python 3.x; browser JavaScript ES modules; HTML/CSS

**Primary Dependencies**: FastAPI/Pydantic/Starlette static files; Python standard library;
pytest; installed GitHub Copilot CLI using the operator's existing authenticated session (no new
inference service, credentials, or Datadog client/SDK)

**Storage**: Existing read-only NOC shift artifacts/projections during generic request processing;
only successful predefined AI Actions may add validated, normalized advisory reports to the
selected shift's existing `reports/` directory. No prompt/context logs, conversation store, cache,
database, or browser storage.

**Testing**: pytest with temporary NOC roots, mocked subprocess calls, and deterministic fake
provider callable; FastAPI TestClient; static frontend/source checks and Node ES-module validation

**Target Platform**: Existing local NOC Web service and modern browser on approved operator
workstations

**Project Type**: FastAPI web service with static frontend

**Performance Goals**: One bounded foreground answer completes within the existing configured
external timeout (maximum 60 seconds); no background retry, queue, or retained conversation work

**Constraints**: Explicit visible URL shift at submission; minimum selected-shift evidence only;
noc-inv/Copilot MCP for investigation evidence; provider-neutral callable with a default local
Copilot CLI adapter; no CLI tools or automatic approval; no direct Datadog; read-only mediation;
no operational action path or confirmation bypass; controlled failures; no prompt, raw evidence,
provider-output, or generic-response persistence/logging; only the four predefined actions may
persist validated normalized advisory reports; qualified provider-retention disclosure before
submit

**Scale/Scope**: One additive assistant page/API/service/adapter boundary plus focused tests and
contract documentation. Existing features 001–005, API schemas, data ownership, workflow URLs,
confirmation behavior, and direct-Datadog prohibition remain unchanged. The existing read-only
AI-report reader is extended for validated predefined-action reports. The Jira input is strictly
the existing local cache; no Jira request or cache refresh is introduced.

## Constitution Check

*GATE: Passed before Phase 0 research and re-checked after Phase 1 design.*

| Principle | Plan response | Status |
|---|---|---|
| I. Preserve Operational Data Integrity | Validate the shift/path/body at the API boundary, consume only safe existing projections, and permit only validated advisory reports in the selected shift's existing report directory. Do not pass raw evidence, credentials, or cross-shift data. | PASS |
| II. Fail Safely and Explain Failures | Independently label evidence availability and return controlled limitation/error states for invalid shift, insufficient context, provider timeout/failure, and invalid provider output. Never substitute old/broader context or a success-shaped answer. | PASS |
| III. Maintain API and UI Contract Consistency | Publish the additive assistant API/UI contract, update router/service/shared browser client/page together, and test request validation, structured response, errors, and routes. | PASS |
| IV. Test Operational Workflows | Use temporary NOC roots and fake provider responses only. Cover successful and failure paths, raw-evidence exclusion, no persistence/logging, prohibited operations, shift isolation, and regressions for features 001–005. | PASS |
| V. Prefer Simple, Observable Changes | Use one context collector, one read-only mediator, one provider-neutral callable adapter with a default local Copilot CLI implementation, one additive router/page, one bounded report writer, and controlled source statuses. No database, worker, arbitrary MCP integration, or external probing is added. | PASS |
| VI. Require Deliberate Operational Execution | The assistant has no operational write/tool/action API; its only write is the explicitly requested validated advisory report for a predefined action. Recommendation links only navigate to existing workflows, whose independent immediate confirmation remains mandatory. AI output is non-authoritative. | PASS |

**Post-design re-check**: PASS. The research, data model, and contract preserve the existing
service/router/frontend boundaries, have no retained conversation state or operational action
capability, disclose provider handling accurately, and make all assistant/evidence/provider
failures non-authorizing and isolated. The narrow report artifact is advisory and shift-scoped.
No constitutional exception is required.

## Project Structure

### Documentation (this feature)

```text
specs/006-ai-assistant/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── assistant-api.md
```

### Source Code (repository root)

```text
backend/
├── api/
│   └── assistant.py             # Additive transient question route
├── services/
│   ├── assistant_context.py     # Minimum selected-shift safe projection collector
│   ├── assistant.py             # Policy, refusal, response validation, failure isolation
│   ├── copilot_mcp.py           # Provider-neutral callable adapter boundary
│   └── copilot_cli.py           # Default isolated GitHub Copilot CLI provider
├── app.py                       # Register additive assistant router
└── services/investigations.py   # Existing safe provenance/review projections consumed, not widened

frontend/
├── assistant.html               # Selected-shift assistant UI/disclosure/result sections
├── js/
│   ├── api.js                   # Additive transient assistant request helper
│   └── workflow-context.js      # Existing URL shift propagation reused
└── css/components.css           # Scoped result/status presentation if needed

tests/
├── conftest.py                  # Existing isolated NOC-root fixture
├── test_assistant.py            # Context, policy, output/failure/no-retention tests
├── test_assistant_api.py        # Route/contract/redaction tests
├── test_investigations.py       # Existing noc-inv/Copilot raw-evidence regression coverage
└── test_safety.py               # Existing no-direct-Datadog/workflow safety regression coverage
```

**Structure Decision**: Keep request policy and lifecycle in `backend.services.assistant`, source
selection/minimization in a dedicated collector, and provider communication behind one explicit
provider-neutral callable adapter. By default, the adapter invokes `copilot -p` in a temporary
directory containing only the minimized context file, with an empty available-tools set and no
automatic approvals. The runtime may inject another approved callable through application state.
The router owns HTTP validation only. Reuse existing selected-shift workflow
context and safe investigation projections; extend the existing AI report reader only for
validated outputs from the four predefined actions and give frontend code no direct
provider/evidence access.

## Implementation Outline

1. Add immutable, request-scoped models for assistant question, safe evidence references,
   structured categories, limitations, and navigation-only recommendation routes. Apply strict
   length/type/shift validation; reject missing/mismatched URL/body shift and missing disclosure
   acknowledgement before collecting context or contacting a provider.
2. Implement a context collector that receives one validated shift and question, calls only
   existing read-only NOC Web projections, and minimizes data by relevance. Include cached Jira
   queue items with cache freshness, Local NOC Tracking context, shift-note/handover summaries,
   Dashboard/Status/readiness warnings, and investigation projections. Never trigger a Jira
   request/refresh. For investigations, pass only operator-reviewed findings plus provenance and
   reference; never pass raw logs/notebooks or unreviewed AI analysis. Keep Jira-owned fields
   separate from local tracking. Preserve each source's unavailable/stale/malformed/conflicting
   state independently.
3. Implement an explicit assistant policy that rejects out-of-scope/prompt-override requests and
   all requested writes, edits, close/reopen, delete, sync, refresh, command, Datadog, and external
   operations. Return a limitation and optional existing-page link without calling a provider. Do
   not add provider tool/function/action capabilities.
4. Add the provider-neutral callable adapter with an explicit bounded timeout and controlled,
   content-free failures. Its default provider writes the transient minimum context envelope to a
   private temporary directory and invokes the operator's authenticated Copilot CLI session with
   `copilot --trust-folder --available-tools --silent -p <fixed-prompt>`. No available tools or
   automatic approvals are enabled; operator questions and evidence stay in the temporary context
   file, not command arguments. An approved runtime may inject another callable. The provider may
   return only AI-generated observations and recommendations with valid evidence references.
   Source-grounded facts and
   operator-reviewed investigation findings are assembled from NOC Web projections, not generated
   or relabeled by the model. The adapter must not access noc-inv, Datadog, local filesystem, network
   tools, commands, or arbitrary MCP servers itself. Capture no prompt/context/output in app logs,
   exception details, traces, files, caches, histories, or metrics labels.
5. Validate every provider result before returning it: AI observations and recommendations must
   reference available evidence and remain visibly advisory. Source-grounded facts must derive from
   available NOC Web projections; operator-reviewed investigation findings are projected only from
   the existing reviewed source and are never authored by the model. Recommendations contain
   navigation-only existing workflow routes and no confirmation/pre-fill. Unsupported claims, bad
   schema, or forbidden content become controlled limitations rather than partial prose. Discard
   all transient objects in both success and `finally`/error paths.
6. Register `POST /api/shifts/{shiftDate}/assistant/questions` and implement the published
   transient contract. Add a separate fixed-action endpoint that persists only a validated
   normalized advisory report for the four predefined AI Actions under the selected shift's
   existing reports directory. Use safe controlled errors and leave all operational data workflows
   unchanged.
7. Add an assistant page to the existing shift workflow/navigation. Reuse `initializeWorkflow` and
   `workflowLink`; require a visible valid URL shift at submit, show accurate qualified persistence/
   provider-retention disclosures, render source-grounded facts, operator-reviewed findings, AI
   observations, recommendations, evidence, and limitations separately, and clear transient
   question/result state on navigation/refresh. Refresh Recent AI Reports after a successful
   predefined action and keep the existing read-only report viewer.
8. Add focused tests: strict context and shift isolation; cached Jira queue consumption without
   refresh; Jira cache freshness/error statuses; data minimization/raw-evidence exclusion; distinct
   facts, operator-reviewed findings, AI observations, and recommendations; source availability and
   insufficient-context behavior; action refusal/no provider call; recommendation routing/unchanged
   confirmation; direct-Datadog prohibition; provider timeout/schema failure isolation; no prompt,
   raw evidence, or provider-output persistence/logging; report success/failure/collision/shift
   isolation; disclosure; and feature 001–005 regression tests. Run
   the focused command in [quickstart.md](quickstart.md) followed by the full existing pytest suite
   if focused coverage passes.

## Complexity Tracking

No constitutional violations or complexity exceptions are required.
