<!--
Sync Impact Report
Version change: 1.1.0 -> 1.2.0
Modified principles:
- IV. Test Operational Workflows -> IV. Test Operational Workflows
Added sections: VI. Require Deliberate Operational Execution
Removed sections: none
Follow-up TODOs: TODO(RATIFICATION_DATE): The original adoption date is unknown.
-->
# NOC Web Constitution

## Core Principles

### I. Preserve Operational Data Integrity
NOC Web MUST validate untrusted input at API boundaries, preserve the intended shift-date
association for stored artifacts, and reject malformed or unsafe paths before filesystem access.
State-changing operations MUST prevent unintended overwrites and preserve sufficient context to
trace handoffs, tickets, investigations, and shift notes. This protects the accuracy of the
operational record used to run and transfer shifts.

### II. Fail Safely and Explain Failures
External integrations and file-backed operations MUST expose actionable failures rather than
return success-shaped fallback data. Each integration MUST define its timeout, failure, and
stale-data behavior before an operator workflow depends on it. The API MUST return explicit error
responses, and the frontend MUST present request failures to operators. This prevents a broken
dependency from being mistaken for a healthy NOC state.

### III. Maintain API and UI Contract Consistency
Every backend endpoint change MUST keep the corresponding frontend API client and consuming UI
consistent, or deliberately version the contract. Request and response schemas, validation rules,
and error responses MUST be explicit at the boundary. Contract changes MUST update all in-repository
consumers in the same change. This keeps operator workflows reliable as the FastAPI backend and
static frontend evolve independently.

### IV. Test Operational Workflows
Behavior changes to shift lifecycle, handover, ticket synchronization, API contracts, or persistent
operational data MUST include focused pytest coverage for successful and failure paths. Tests MUST
isolate filesystem state using temporary directories and MUST NOT access a developer's real NOC
data, network services, or credentials. Existing pytest tests MUST pass before a change is
considered complete. This verifies workflows without risking live operational artifacts or making
test outcomes environment-dependent.

### V. Prefer Simple, Observable Changes
New functionality MUST use the existing backend service, schema, API-router, and frontend client
boundaries unless a documented constraint requires otherwise. Changes that add external calls or
persistent state MUST make their resulting state and failures observable through explicit responses
or existing status mechanisms, without exposing secrets or sensitive operational content. This
minimizes operational complexity and supports timely troubleshooting.

### VI. Require Deliberate Operational Execution
Read-only behavior MUST be the default for NOC workflows. Actions that send email, modify external
systems or tickets, or execute an operational workflow MUST require explicit operator confirmation
immediately before execution. AI-generated operational analysis is advisory and MUST be
human-reviewed; AI output MUST NOT become an authoritative source of operational state. Start Shift
and End Shift workflows MUST use distinct validation and execution gates before any state-changing
action. These controls prevent unintended operational effects and preserve human accountability.

## Operational Constraints

The backend is Python/FastAPI and the frontend is a static HTML, CSS, and JavaScript application.
Persistent files and integration caches are operational data: implementations MUST validate paths
before access, avoid hard-coded developer-local paths, and keep credentials out of source control,
responses, and logs. Dependencies and configuration MUST be explicit and reproducible from the
repository. New external integrations MUST define their timeout, error, and stale-data behavior
before use in an operator workflow. Confirmation and execution-gate state MUST be represented
explicitly and MUST NOT be inferred from AI-generated output.

## Development Workflow

Each change MUST identify its affected user workflow, data boundary, and API contract before
implementation. Implementation MUST keep backend schemas, service behavior, route handling,
frontend API calls, and user-facing error handling synchronized. Contributors MUST run focused
existing pytest tests for affected services before review; changes spanning a backend API and
frontend behavior MUST exercise the contract end to end. Reviews MUST verify data integrity, safe
failure behavior, observability, and the absence of access to real NOC data.

## Governance

This constitution supersedes conflicting development practices for NOC Web. Amendments MUST be
documented in this file, include a Sync Impact Report while under review, and receive maintainer
approval before the report is removed for commit. Versioning follows semantic versioning: MAJOR
for incompatible principle removals or redefinitions, MINOR for added principles or materially
expanded guidance, and PATCH for clarifications that do not alter governance requirements.
Every specification, plan, task list, implementation, and review MUST assess applicable principles;
noncompliance requires an explicit, time-bound exception recorded in the relevant change.

**Version**: 1.2.0 | **Ratified**: TODO(RATIFICATION_DATE): Original adoption date unknown |
**Last Amended**: 2026-10-29
