# Implementation Plan: Ollama Local AI Provider

**Branch**: `018-ollama-local-provider` | **Date**: 2026-11-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/018-ollama-local-provider/spec.md`

## Summary

Extend the existing provider-independent AI architecture with an explicitly selectable Ollama
provider. DeepSeek remains the default for existing installations, but operators may explicitly
configure Ollama as the default or select it per request/retry. A new bounded Ollama adapter will
use a configurable LAN base URL and model, consume only the `response` field, ignore all thinking and
metadata, reject redirects/unexpected hosts, use no authentication secret, and enforce explicit
LAN connection/read deadlines.

Primary-provider failures remain fail-closed. When a primary request fails, NOC Web may retain the
exact failed request evidence in a bounded in-memory retry snapshot for 10 minutes and expose an
explicit **Retry with Local AI** action. The retry requires operator confirmation and runs the local
provider against the same evidence through the same Assistant, AI Actions, Feature 016, or Feature
017 validators. There is no automatic fallback or automatic retry. Provider provenance identifies
`ollama` and the configured model. Static health/readiness never probes the host; an explicit probe
checks endpoint reachability and configured-model presence without inference.

## Technical Context

**Language/Version**: Python 3.15.2 (project virtual environment); vanilla ES modules for the
frontend.

**Primary Dependencies**: FastAPI, Pydantic, Python standard library (`urllib`, `json`, `threading`,
`time`), pytest, and the existing Node-based frontend test harness. No new runtime dependency.

**Storage**: Existing local operational files and in-memory retry snapshots only. Failed-request
retry evidence is retained for 10 minutes with no disk persistence. Existing investigation and
handover provenance files are extended only to record `ollama` and the configured model.

**Testing**: pytest for provider configuration, Ollama adapter/probe, retry snapshots, workflow
validators, readiness/status, and security; Node-based frontend checks for provider visibility,
retry confirmation, and no automatic retry behavior.

**Target Platform**: Linux workstation/server, including the existing WSL-hosted runtime, with an
optional Ollama host on the LAN.

**Project Type**: Web application with a FastAPI backend and static HTML/JavaScript frontend.

**Performance Goals**: Static readiness/probe-free views make no Ollama calls. Explicit probes are
bounded and perform no inference. Local inference is bounded by configurable LAN connection/read
deadlines. Retry snapshots are capped at 32 entries and 10 minutes.

**Constraints**: No automatic fallback or retry. No credentials or Authorization headers to Ollama.
No thinking/context/duration/model metadata in outputs or persisted data. Endpoint must be an
HTTP/HTTPS base URL with no credentials/query/fragment/arbitrary path and no redirects. All existing
workflow validators remain authoritative. No external mutation caused by inference.

**Scale/Scope**: Small NOC deployment; one optional Ollama host; recommended `qwen3:8b`; up to 32
in-memory retry snapshots; bounded provider responses (1 MiB) and output sizes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Preserve Operational Data Integrity | Retry snapshots are memory-only and bounded; existing investigation/handover persistence rules remain unchanged; provenance explicitly records local provider identity/model. | PASS |
| II. Fail Safely and Explain Failures | Unreachable/refused/timeout/missing-model/malformed/missing-response/oversized/validator-rejected local output fails closed with actionable, sanitized errors. | PASS |
| III. Maintain API and UI Contract Consistency | Provider selection, retry tokens, readiness/probe fields, and frontend consumers are updated together; existing workflow contracts remain compatible. | PASS |
| IV. Test Operational Workflows | Focused tests cover all workflows, local retry, validators, readiness, endpoint validation, metadata exclusion, secrets, and no fallback. | PASS |
| V. Prefer Simple, Observable Changes | Reuse the existing provider runtime, workflow services, validators, error mapping, and local persistence; add one adapter, one retry store, and additive readiness fields. | PASS |
| VI. Require Deliberate Operational Execution | Local inference requires explicit configuration/selection or explicit Retry with Local AI confirmation; no automatic retry/fallback; AI remains advisory and human-reviewed. | PASS |

No constitution violations or justified exceptions.

## Project Structure

### Documentation (this feature)

```text
specs/018-ollama-local-provider/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── ollama-provider.md
│   ├── local-retry.md
│   ├── provider-readiness.md
│   └── provider-selection.md
└── tasks.md              # Created later by /speckit.tasks
```

### Source Code (repository root)

```text
backend/
├── api/
│   ├── assistant.py                   # provider selection, retry metadata/endpoints
│   ├── investigations.py              # explicit local selection/retry wiring
│   └── handover.py                    # explicit local selection/retry wiring
├── services/
│   ├── ai_provider.py                 # Ollama config/readiness/runtime resolution
│   ├── ollama_provider.py             # NEW: bounded /api/generate adapter and /api/tags probe
│   ├── local_retry.py                 # NEW: 10-minute in-memory failed-request snapshots
│   ├── assistant.py                   # retry envelope capture and local validation path
│   ├── investigation_generation.py    # local retry with same evidence/validators
│   ├── handover.py                    # local retry with same evidence/validators
│   ├── health.py                      # primary/local provider readiness
│   ├── status.py                      # primary/local provider visibility
│   ├── dependency_readiness.py        # distinct external.aiProvider/local state
│   └── investigations.py              # existing provenance compatibility where needed
└── app.py                             # expose additive provider readiness fields

frontend/
├── assistant.html                     # provider selection, Retry with Local AI confirmation
├── investigations.html                # local retry action after primary failure
├── end-shift.html                     # local retry action after primary handover failure
├── status.html                        # primary/local provider visibility and explicit probe
└── js/
    ├── api.js                         # provider selection/retry/probe clients
    └── provider-status.js             # NEW: shared primary/local provider UI behavior

docs/
└── workstation-runtime.md             # provider configuration, probe, retry, security
README.md                              # operator-facing Ollama configuration

tests/
├── test_ollama_provider.py            # NEW: endpoint, response-only parsing, limits, probe
├── test_local_retry.py                # NEW: TTL, bounds, single-use, exact snapshot
├── test_ai_provider.py                # Ollama config/readiness/no-fallback
├── test_assistant.py                  # Assistant/AI Actions local compatibility and retry
├── test_assistant_api.py
├── test_investigation_generation.py   # local retry same evidence/validators
├── test_handover.py                   # local retry same evidence/validators
├── test_handover_ai.py
├── test_ollama_provider_security.py   # NEW: secrets, redirects, hosts, metadata exclusion
├── test_readiness.py
├── test_dependency_readiness.py
├── test_readiness_api.py
├── test_status.py
├── test_frontend_modules.py
├── test_datadog_readonly.py
└── test_datadog_secrets.py
```

**Structure Decision**: Keep the existing web-application split. Extend the existing provider
configuration/runtime rather than creating a parallel AI system. Add one Ollama transport adapter
and one bounded retry store; route each workflow through its existing service and validators.

## Phase 0 Research Summary

See [research.md](research.md). Key decisions:

- Add `ollama` as an explicitly selectable provider while preserving DeepSeek as the existing
  installation default.
- Use a configurable HTTP/HTTPS LAN base URL and `qwen3:8b` default model recommendation.
- Consume only the Ollama `response` field; ignore thinking/context/duration/model metadata.
- Add explicit provider selection and Retry with Local AI confirmation; no automatic fallback/retry.
- Store exact failed-request evidence in a 10-minute, 32-entry, single-use in-memory retry store.
- Reuse every existing workflow validator; local inference receives no additional authority.
- Add explicit local probe (`/api/tags`, no inference) distinct from static readiness.
- Reject redirects, unexpected hosts, embedded credentials, query/fragment/path, and secrets.
- Add provider provenance fields for `ollama` and the configured model.
- Keep Microsoft 365, Datadog read-only behavior, investigation lifecycle, reviewed boundaries,
  and handover completeness unchanged.

## Phase 1 Design Summary

See [data-model.md](data-model.md) and [contracts/](contracts/). The design adds:

- Ollama provider configuration, endpoint validation, static readiness, and explicit probe result.
- `LocalRetrySnapshot` with exact evidence/envelope, workflow identity, 10-minute TTL, single-use.
- Additive provider-selection and retry fields on Assistant, AI Actions, investigation, and handover
  APIs without changing existing success contracts.
- Shared provider provenance fields identifying `ollama` and model.
- Primary/local provider visibility and retry availability in health/status/UI.
- Metadata-exclusion and secret-exclusion rules for the Ollama adapter.
- Existing validators as the sole authority for local output.

## Post-Design Constitution Re-check

| Principle | Post-design result |
|-----------|--------------------|
| I. Preserve Operational Data Integrity | PASS — retry evidence is memory-only and bounded; existing records/provenance remain authoritative and additive. |
| II. Fail Safely and Explain Failures | PASS — provider/probe/retry contracts define sanitized fail-closed outcomes for all required failure modes. |
| III. Maintain API and UI Contract Consistency | PASS — selection, retry, readiness, probe, and error fields are defined across backend and frontend. |
| IV. Test Operational Workflows | PASS — quickstart/data model define focused tests for all four workflows and security boundaries. |
| V. Prefer Simple, Observable Changes | PASS — one adapter, one retry store, existing services/validators, and additive readiness/UI. |
| VI. Require Deliberate Operational Execution | PASS — no automatic local fallback/retry; explicit selection/confirmation and advisory-only output are enforced. |

No new violations or unresolved design risks.

## Complexity Tracking

No violations or justified exceptions.
