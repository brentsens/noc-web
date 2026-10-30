# Implementation Plan: Jira Cache Health Visibility

**Branch**: `001-jira-cache-health` | **Date**: 2026-10-29 | **Spec**:
[spec.md](spec.md)

**Input**: Feature specification from
`/specs/001-jira-cache-health/spec.md`

## Summary

Expose an additive, read-only Jira-cache health object in the existing Status response and render
it as an additional Status page metric. Health is derived from the local cache file's availability
and recorded refresh time: a cache is current when refreshed less than 30 minutes ago and stale
when refreshed 30 minutes ago or longer. The feature does not call Jira, write the cache, or
change tickets.

## Technical Context

**Language/Version**: Python 3.x (repository does not pin a version); browser JavaScript

**Primary Dependencies**: FastAPI; static browser UI

**Storage**: Local JSON Jira ticket-cache file under the configured NOC root

**Testing**: pytest

**Target Platform**: Local NOC operator web application served by the backend

**Project Type**: Web application with backend API and static frontend

**Performance Goals**: Cache health is shown with the existing Status page load; it adds no network
requests and no background work.

**Constraints**: Read-only by default; no Jira refresh, ticket mutation, cache write, or unrelated
Status page redesign. Missing, unreadable, malformed, or missing-refresh-time cache data is
unavailable. The informational freshness policy is: current when less than 30 minutes old and stale
when 30 minutes old or older; stale cache data MUST NOT trigger a Jira refresh.

**Scale/Scope**: One additive field in the existing Status response, one Status page metric, and
focused service and Status aggregation tests.

## Constitution Check

| Principle | Plan Response | Status |
|-----------|---------------|--------|
| I. Preserve Operational Data Integrity | Read only the existing cache and validate its refresh timestamp before presenting health. | PASS |
| II. Fail Safely and Explain Failures | Treat missing, unreadable, malformed, and invalid-timestamp caches as explicit unavailable states; classify valid timestamps with the approved 30-minute policy. | PASS |
| III. Maintain API and UI Contract Consistency | Add and document one status-response object, then update the existing UI consumer in the same change. | PASS |
| IV. Test Operational Workflows | Add focused pytest cases for current, stale (including exactly 30 minutes), and unavailable health, including no-write behavior; run existing tests. | PASS |
| V. Prefer Simple, Observable Changes | Reuse the cache reader and existing Status endpoint/page instead of adding a refresh path or service. | PASS |
| VI. Require Deliberate Operational Execution | The feature is strictly read-only; it offers no action, confirmation, AI output, or execution gate. | PASS |

**Post-design re-check**: PASS. The API contract, data model, and quickstart preserve all
constitutional gates without exceptions.

## Project Structure

### Documentation (this feature)

```text
specs/001-jira-cache-health/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── status-api.md
└── tasks.md             # Created later by /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── api/
│   └── status.py                    # Existing Status API route
└── services/
    ├── jira_cache.py                # Cache-health derivation
    └── status.py                    # Status response aggregation

frontend/
├── js/
│   └── api.js                       # Existing Status request client
└── status.html                      # Status metric markup and rendering

tests/
├── test_jira_cache.py               # Cache-health unit coverage
└── test_status.py                   # Status aggregation coverage
```

**Structure Decision**: Extend the existing service-to-route-to-static-page flow. The cache
service owns validation and 30-minute freshness classification; the status service aggregates the
result; the existing Status client and page render the additive response field.

## Complexity Tracking

No constitutional violations or complexity exceptions are required.
