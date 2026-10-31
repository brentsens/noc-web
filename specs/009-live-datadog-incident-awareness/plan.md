# Implementation Plan: Live Datadog Incident Awareness

**Branch**: `009-live-datadog-incident-awareness` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/009-live-datadog-incident-awareness/spec.md`

## Summary

Add a bounded incident projection service using the authenticated Copilot CLI
and only the configured Datadog MCP incident-search tool. Persist a short-lived,
validated snapshot and freshness metadata atomically; failed or invalid
refreshes retain the prior good snapshot. Add one shared incident API contract
and reusable frontend card for Dashboard and Investigations, with explicit
refresh and a link into the existing Preview-gated investigation form.

## Technical Context

**Language/Version**: Python 3.x backend; browser-native JavaScript ES modules

**Primary Dependencies**: FastAPI, Pydantic, Python standard library, GitHub Copilot CLI, configured Datadog MCP server

**Storage**: Atomic JSON snapshot under the configured NOC root; no raw provider response or prompts

**Testing**: pytest, Python compilation, frontend ES-module syntax validation, `git diff --check`

**Target Platform**: Existing local NOC workstation deployment

**Project Type**: FastAPI web service with static HTML/CSS/JavaScript frontend

**Performance Goals**: Cached incident reads return without waiting for Copilot; one bounded retrieval at a time; refresh cadence targets 60 seconds

**Constraints**: No direct Datadog API/SDK/browser retrieval; no broad Copilot tool permissions; strict provider-output validation; no automatic investigation or handover changes; all failures preserve last successful data

**Scale/Scope**: One workstation cache and one current incident projection shared across Dashboard and Investigations; no new Assistant source or handover integration

## Constitution Check

- **I. Preserve Operational Data Integrity**: Pass. Validate provider records and atomically replace only after a fully valid response; never overwrite a prior good snapshot on failure.
- **II. Fail Safely and Explain Failures**: Pass. Persist refresh attempt metadata; show STALE with cached data or UNAVAILABLE without it; keep read paths nonblocking.
- **III. Maintain API and UI Contract Consistency**: Pass. Define one incidents API and use its response through one frontend client/renderer.
- **IV. Test Operational Workflows**: Pass. Add isolated service/API tests using temporary cache paths and mocked subprocesses; do not query real NOC data or Datadog in tests.
- **V. Prefer Simple, Observable Changes**: Pass. Reuse existing FastAPI, Copilot CLI, configured NOC root, and frontend conventions; expose only bounded cache metadata and status.
- **VI. Require Deliberate Operational Execution**: Pass. Retrieval is read-only. Investigation creation remains operator-triggered and Preview/confirmation-gated.

No constitution violations are anticipated.

## Project Structure

### Documentation (this feature)

```text
specs/009-live-datadog-incident-awareness/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── incidents-api.md
└── tasks.md
```

### Source Code

```text
backend/
├── api/
│   └── datadog_incidents.py
├── services/
│   └── datadog_incidents.py
└── app.py

frontend/
├── index.html
├── investigations.html
├── js/
│   ├── api.js
│   └── active-incidents.js
└── css/
    └── components.css

tests/
├── test_datadog_incidents.py
└── test_datadog_incidents_api.py
```

**Structure Decision**: Extend the existing single FastAPI application and static
frontend. The incidents service owns retrieval, validation, freshness, and the
shared cache. Both pages call the same read endpoint and use a shared renderer;
only the service may schedule retrieval. The existing investigation generation
API and its Preview/confirmation gates remain unchanged.

## Design Decisions

- Invoke Copilot CLI with JSONL transport, select only the final
  `assistant.message` content, and pass that content unchanged to the strict
  incident JSON parser. Expose the configured `datadog` MCP server to the
  model, but grant execution permission only to
  `datadog(search_datadog_incidents)`; do not allow shell, other MCP actions,
  or broad/all-tools permissions. The fixed prompt requires one exact JSON
  projection and treats incident text as untrusted data, never as a command
  argument.
- Validate the complete provider response before replacing the cache. Reject
  malformed entries, duplicate IDs, unknown keys, unsafe URLs, excessive
  field lengths, or invalid timestamps as a failed refresh. Retain both
  `ACTIVE` and `STABLE` incidents, exclude `RESOLVED` incidents only from a
  successful projection, and preserve the exact provider state string in the
  cache and UI. Cache freshness is independent of incident state. No provider
  text is logged or returned on failure.
- Store only the validated operational projection plus last-attempted,
  last-successful, and refresh-status metadata. Write a temporary file in the
  same cache directory and atomically replace the snapshot only on success.
- A shared service scheduler coalesces automatic and manual refresh requests.
  Cache reads return immediately; when due, they schedule one background
  refresh. Refresh uses a bounded subprocess timeout. A failure updates attempt
  and freshness metadata while preserving incidents and last success.
- Freshness is `current` while the last successful snapshot is within the
  60-second target and no failed attempt has superseded it; `stale` when an
  older snapshot remains after age or failure; `unavailable` without a valid
  snapshot; and `refreshing` while one retrieval is active.
- The incident card's Create Investigation link may prefill only the incident
  title in the existing form. It does not prefill a Notebook URL, call the
  generator, or bypass Preview and explicit confirmation.

## Complexity Tracking

No constitution violations or additional architectural projects are proposed.
