# Implementation Plan: Direct Read-Only Datadog Evidence Provider

**Branch**: `015-datadog-rest-provider` | **Date**: 2026-11-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/015-datadog-rest-provider/spec.md`

## Summary

Replace the Copilot CLI and Datadog MCP incident-retrieval path with a direct,
structurally read-only Datadog API provider authenticated by a process-environment
bearer token. Preserve the existing incident cache, freshness, stale fallback,
cross-process refresh coalescing, timeouts, and `/api/datadog/incidents`
contract. Add on-demand, normalized incident-detail, notebook, and monitor
evidence behind an internal backend service, without a new HTTP route, frontend
change, AI call, or change to `noc-inv`/`noc-handover`. Expose static,
non-networked Datadog provider readiness through existing diagnostics.

## Technical Context

**Language/Version**: Python 3.10+ (the application already requires this at runtime)

**Primary Dependencies**: FastAPI, Pydantic, Python standard library
`urllib.request`/`json`; pytest for tests. No new runtime HTTP/SDK dependency.

**Storage**: Existing JSON incident cache at `<NOC_ROOT>/.datadog-active-incidents.json`
plus its lock file. No new persistent cache for evidence. No database.

**Testing**: pytest, FastAPI `TestClient`, injected fake Datadog transports.
Tests use temporary directories and never call Datadog or require a token.

**Target Platform**: Linux/WSL local NOC Web user service; static HTML/CSS/JS frontend.

**Project Type**: Web application (FastAPI backend plus static frontend).

**Performance Goals**: Preserve the 60-second target refresh interval and
non-blocking page reads. Keep an individual Datadog refresh within a 90-second
overall deadline. Bound every response to 1,000,000 bytes and 100 current incidents.
On-demand evidence is bounded by the same deadline and per-category item limits.

**Constraints**: Only an allowlisted set of read-only operations may be issued;
no mutation methods or arbitrary paths. The token comes only from the process
environment, appears only in the `Authorization: Bearer` header, and never in
responses, logs, cache, exceptions, reports, or test artifacts. Readiness makes
zero Datadog calls. No AI model receives retrieved evidence.

**Scale/Scope**: One NOC operator workstation; up to 100 current incidents; up
to 10 notebook references and 10 monitor references per incident; up to 200
notebook cells per notebook; up to 100 monitor tags; no new UI.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Plan Evidence |
|-----------|------------|---------------|
| I. Preserve Operational Data Integrity | PASS | Datadog responses are untrusted input validated at the provider boundary; cache writes remain atomic and path-scoped; evidence is normalized and bounded; no partial snapshot replaces a valid cache. |
| II. Fail Safely and Explain Failures | PASS | Explicit provider-unavailable, timeout, invalid-response, and cache-unavailable states; stale cache preserved on every failure; readiness is static and accurate; no success-shaped empty fallback. |
| III. Maintain API and UI Contract Consistency | PASS | `/api/datadog/incidents` fields, types, freshness/error values, and frontend behavior remain unchanged. Evidence is internal-only. Diagnostics changes are additive and updated with their consumers. |
| IV. Test Operational Workflows | PASS | Focused pytest coverage for success/failure paths, cache preservation, concurrency, malformed/oversized responses, secrets, and the existing API/frontend contract; tests use fake transports and temp directories. |
| V. Prefer Simple, Observable Changes | PASS | Reuses the existing cache, service, API, and diagnostics boundaries; new provider/evidence modules are narrow; failures remain visible through existing freshness/error and readiness surfaces. |
| VI. Require Deliberate Operational Execution | PASS | Every Datadog operation is retrieval-only; no acknowledgement, mute, resolve, or mutation exists; no AI or operational action is added; evidence remains read-only. |

**Post-design re-check**: PASS. No violations or exceptions are required.

## Project Structure

### Documentation (this feature)

```text
specs/015-datadog-rest-provider/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── datadog-provider.md
│   ├── datadog-evidence.md
│   ├── incidents-api.md
│   └── diagnostics.md
└── tasks.md                 # Created later by /speckit.tasks
```

### Source Code (repository root)

```text
backend/
├── app.py                              # health: add static datadogProvider
├── api/
│   ├── datadog_incidents.py            # existing GET/POST contract unchanged
│   └── readiness.py                    # existing route; external capability data updated
└── services/
    ├── datadog_provider.py             # NEW: env config, static readiness, allowlisted client, transport
    ├── datadog_validation.py           # NEW: shared bounded text/timestamp/URL/ID validation
    ├── datadog_incidents.py            # replace Copilot path with direct provider; cache contract preserved
    ├── datadog_evidence.py             # NEW: on-demand detail/notebook/monitor normalization and relationships
    ├── dependency_readiness.py         # static external.datadog capability; no MCP probe
    └── status.py                       # add static datadogProvider to status payload

scripts/
├── run_service.py                      # propagate Datadog env allowlist
└── windows/bootstrap-status.ps1        # readiness ID updated
systemd/noc-web.service.in              # optional datadog-provider.env

docs/
└── workstation-runtime.md              # env vars, readiness, service setup
README.md                               # capability and credential notes

frontend/
└── js/active-incidents.js              # unchanged incident renderer/contract

tests/
├── test_datadog_provider.py            # NEW
├── test_datadog_evidence.py            # NEW
├── test_datadog_incidents.py           # extend direct-provider, zero-Copilot/MCP, secrets, bounds
├── test_datadog_incidents_api.py       # existing contract coverage retained
├── test_datadog_incidents_frontend.py  # replace obsolete no-direct-API assertion
├── test_dependency_readiness.py        # external.datadog expectations
├── test_readiness_api.py               # additive diagnostics coverage
├── test_runtime_service.py             # env-file/allowlist coverage
└── test_bootstrap_provisioning.py      # readiness ID expectations
```

**Structure Decision**: Reuse the existing backend service/API/cache boundaries.
The only new production modules are the provider, shared validation, and internal
evidence service. The frontend and existing incident API route remain unchanged.
No new HTTP route is added for evidence.

The existing
`test_backend_retrieval_does_not_add_direct_datadog_api_or_sdk` assertion in
`tests/test_datadog_incidents_frontend.py` encodes the superseded Copilot/MCP
architecture, not the incident API or frontend contract. It is replaced with
direct-provider, zero-Copilot, and zero-MCP assertions. All frontend renderer and
incident API contract assertions remain intact.

## Phase 0: Research Outcomes

See [research.md](./research.md). All technical unknowns are resolved:

- Datadog US1 API base and endpoint mapping.
- Bearer-token authentication and redirect refusal.
- Incident search/filter/pagination with local validation.
- Existing cache-contract projection mapping.
- Structured reference extraction with bounded relative-path discovery in
  incident narrative fields and supported notebook cell definitions.
- Notebook/monitor normalization and bounds.
- Static readiness and diagnostics integration.
- Secret handling, environment propagation, and test strategy.

## Phase 1: Design Outcomes

- [data-model.md](./data-model.md) defines provider configuration, readiness,
  incident projection, cache snapshot, incident detail, notebook, monitor,
  relationship, and failure entities.
- [contracts/datadog-provider.md](./contracts/datadog-provider.md) defines the
  environment configuration, readiness, transport, allowlist, timeout, and
  secret-handling contract.
- [contracts/datadog-evidence.md](./contracts/datadog-evidence.md) defines the
  internal evidence bundle and normalization rules.
- [contracts/incidents-api.md](./contracts/incidents-api.md) records the
  unchanged incident HTTP contract and failure semantics.
- [contracts/diagnostics.md](./contracts/diagnostics.md) defines the additive
  static readiness fields on health, status, and readiness surfaces.
- [quickstart.md](./quickstart.md) provides runnable, offline validation steps.

## Complexity Tracking

No constitution violations. No additional projects, repositories, databases,
HTTP routes, or runtime dependencies are introduced.
