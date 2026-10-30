# Implementation Plan: Workstation Operational Readiness

**Branch**: `005-workstation-readiness` | **Date**: 2026-10-29 | **Spec**:
[spec.md](spec.md)

## Summary

Add a read-only readiness assessment to the existing FastAPI application. A single assessment
resolves only documented environment overrides (or preserved defaults), rejects an invalid explicit
setting before any operational probe, and returns separate configuration, NOC data, per-cache,
command, write-capability, and liveness results. The feature reuses the service/router/static-page
boundaries, preserves existing ticket and cache models, and never discovers, stores, or reports
credentials or personal filesystem paths.

## Technical Context

**Language/Version**: Python 3.x; browser JavaScript (ES modules); HTML/CSS

**Primary Dependencies**: FastAPI, Pydantic/Starlette static files, Python standard library;
pytest

**Storage**: Existing local NOC workspace, ticket records, and Jira cache; no new persistent
readiness record or credential store

**Testing**: pytest with temporary NOC roots and mocked command/liveness execution; static UI tests
where established

**Target Platform**: Approved local NOC workstations on Linux, Windows, and WSL; modern browser

**Project Type**: FastAPI web service with static frontend

**Performance Goals**: A complete assessment finishes within 60 seconds; each configured command
or liveness probe has a bounded timeout and assessments run no background work.

**Constraints**: Defaults remain behaviorally identical when no environment override is supplied.
An explicitly present but blank, malformed, unsafe, conflicting, inaccessible, or unusable override
is a configuration failure and is never replaced with a default, discovered value, or alternate
override. All probes are read-only except the explicitly approved, create-and-remove write probe;
no shell invocation, credential discovery, directory scanning outside approved roots, persistent
diagnostic storage, or action authorization is permitted.

**Scale/Scope**: One additive readiness API/page, centralized configuration and readiness service,
existing single Jira cache source generalized to a source-keyed policy, documentation, and focused
tests. Existing domain models, local tracking lifecycle, Jira cache format, and confirmation-gated
operational actions remain unchanged.

## Constitution Check

*GATE: Passed before Phase 0 research and re-checked after Phase 1 design.*

| Principle | Plan response | Status |
|---|---|---|
| I. Preserve Operational Data Integrity | Resolve approved paths before access, validate records without mutation, and use only exclusive temporary probe files that are removed in `finally`. Preserve existing configuration/data formats and reject incompatibility. | PASS |
| II. Fail Safely and Explain Failures | Return an explicit failed/limited check for invalid configuration, unavailable liveness, inaccessible data, cache age/format, command timeout/failure, and write failure. No fallback follows an explicit invalid override. | PASS |
| III. Maintain API and UI Contract Consistency | Publish the additive `/api/readiness/{shift_date}` contract, update the shared browser client and readiness page together, and retain every existing health/status response. | PASS |
| IV. Test Operational Workflows | Add isolated pytest coverage for defaults, overrides/no fallback, every probe result, redaction, compatibility, timeout, and recovery guidance without real NOC data, commands, or network calls. | PASS |
| V. Prefer Simple, Observable Changes | Introduce one configuration resolver and one readiness service; reuse current config, Jira-cache reader, routers, static frontend, and tests. No database, worker, secret store, or external integration is added. | PASS |
| VI. Require Deliberate Operational Execution | The readiness endpoint/page is inspection-only. It neither refreshes Jira nor changes tickets/artifacts, and it cannot satisfy or bypass the confirmation required by existing writes. | PASS |

**Post-design re-check**: PASS. The data model and API contract keep probes observable,
bounded, redacted, and non-authorizing. The transient exclusive write probe is the documented
non-destructive evidence for an approved destination; it overwrites nothing and is removed even on
failure. No exception is required.

## Project Structure

### Documentation (this feature)

```text
specs/005-workstation-readiness/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── readiness-api.md
```

### Source Code (repository root)

```text
backend/
├── api/
│   └── readiness.py             # Additive readiness route
├── config.py                    # Default/explicit environment resolution boundary
└── services/
    ├── jira_cache.py            # Existing cache parsing, retained format
    └── readiness.py             # Assessment and safe probe orchestration

frontend/
├── readiness.html               # Read-only assessment page
└── js/
    └── api.js                   # Additive readiness request

tests/
├── conftest.py                  # Existing isolated NOC-root fixture
├── test_readiness.py            # Resolver and assessment behavior
└── test_readiness_api.py        # Route/contract and redaction behavior

docs/
└── workstation-readiness.md     # Setup, overrides, recovery, Windows/WSL guidance
```

**Structure Decision**: Keep configuration parsing at `backend.config`, where current defaults
live; keep all assessment decisions and no-write guarantees in `backend.services.readiness`; let an
additive router serialize that service result. The static page only renders the published result.
Existing health, status, Jira cache, tickets, and domain-record services are consumers/providers,
not rewritten models.

## Implementation Outline

1. Replace direct home-derived constants with an immutable, validated configuration profile builder.
   When absent, defaults remain `Path.home() / "noc"` and `Path.home() / ".local" / "bin"` and the
   current required command catalog. Supported environment variables are exactly
   `NOC_WEB_NOC_ROOT`, `NOC_WEB_NOC_BIN`, `NOC_WEB_READINESS_PROBE_DIR`,
   `NOC_WEB_JIRA_CACHE_MAX_AGE_SECONDS`, and `NOC_WEB_COMMAND_TIMEOUT_SECONDS`. Presence includes
   an empty value. Validate explicit paths as absolute, normalized, approved (the probe directory
   must be inside the resolved NOC root), and non-conflicting; validate positive bounded integer
   ages/timeouts. Capture only the logical setting name and source (`default`/`explicit`) in output.
   Never call `Path.home`, scan environment aliases, or choose another value after an explicit
   validation error.
2. Add `GET /api/readiness/{shift_date}`. Validate the date as existing routes do; do not accept
   request-body/query overrides. Environment resolution occurs once for the request, before all
   data, command, or liveness probes. A rejected explicit configuration returns HTTP 422 with the
   redacted configuration check/result and no executed probes; a valid profile returns HTTP 200
   even when the assessment is not ready.
3. Implement independent checks: parse required NOC records without conversion; inspect each
   declared cache source using its own configured maximum age (initially `jiraOpenTickets`, retaining
   `.jira-open-tickets.json` format); locate and run each catalogued non-destructive argv via
   `subprocess.run(shell=False, timeout=...)`; and perform the approved write check by exclusively
   creating a random probe file in the approved probe directory, flushing it, and deleting only that
   file in `finally`. Report path logical names, never resolved paths.
4. Model liveness as a diagnostic capability with a separately configured, bounded, read-only
   probe per external dependency. A response to that probe means `available`, not operationally
   ready. A command/data/cache/write readiness check can therefore fail while liveness is
   available; unavailable liveness affects the overall decision only when its associated required
   operational duty cannot be proven ready. Do not make network calls unless a documented probe is
   explicitly configured.
5. Aggregate deterministic `ready` only when configuration and every required operational check
   are ready. Liveness is displayed separately and never upgrades readiness. Every non-ready check
   includes status, capability, impact, and generic corrective action. Redact exception text,
   command output, environment values, home/user paths, tokens, and file contents before response
   or logs.
6. Add the page/client and documentation. The UI shows the overall decision, separate liveness
   panel, per-source cache ages, and recovery actions; it offers no refresh or action button.
   Document exact defaults/overrides, Windows native path and WSL Linux-path expectations, no
   cross-environment automatic path translation, supported data compatibility, and the requirement
   to explicitly confirm existing state-changing workflows after readiness passes.
7. Test no-override default preservation; every invalid explicit override with no fallback/no probe;
   compatible/incompatible NOC/cache records; cache source age at, below, and above its own limit;
   missing/permission/timeout/error commands; liveness-ready/readiness-failed separation; probe
   cleanup/non-overwrite; API contract/redaction; and unchanged confirmation/read-only behavior.

## Complexity Tracking

No constitutional violations or complexity exceptions are required.
