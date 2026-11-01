# Workstation Readiness Contract

## Endpoint

Continue using the existing read-only endpoint:

```http
GET /api/readiness/{shift_date}
```

`shift_date` remains `YYYY-MM-DD`; invalid dates return HTTP 400. A valid
assessment returns HTTP 200 even when a capability is unavailable. Invalid
explicit workstation configuration returns a redacted HTTP 422 response and
does not run probes.

The response retains the existing `assessedAt`, `shiftDate`, `readOnly`,
`configuration`, `checks`, and `liveness` properties, and adds a core runtime
assessment and individually identified external capabilities. Status values
are stable machine values (`ready`, `setup_required`, `unavailable`); the
frontend presents the user-facing labels `READY`, `SETUP REQUIRED`, and
`UNAVAILABLE`. The overall application/runtime status is separate from
optional dependency statuses.

Each result includes a stable `id`, capability, status, required flag, safe
impact, and corrective action. It may include a source identifier, cache age,
and UTC check time. It must not include raw command output, credential
contents, authentication values, sensitive operational paths, customer/ticket
content, or provider evidence.

## Capability behavior

The assessment covers:

- NOC Web process/runtime and Python environment.
- Validated workstation configuration and writable NOC workspace.
- User-managed service state.
- Atlas, GitHub Copilot CLI, Datadog MCP, Microsoft 365 CLI, and noc-tools
  compatibility, each as a separate optional capability.

Probes are bounded and non-mutating. Probe output is discarded except for a
strictly allowlisted, non-sensitive contract token where an existing command
requires it. A dependency is not marked `ready` based only on the presence of
a credential file. If authentication or MCP usability cannot be verified
safely, report `setup_required` with the verification limitation. A transient
probe timeout/failure reports `unavailable`.

Optional dependency failures do not prevent app startup or make unrelated
workflows unavailable. Endpoints for dependent actions return an explicit,
safe unavailable result; they do not silently substitute an integration.

## Recheck UI

The existing Workstation Readiness page renders core runtime and individual
capability results and exposes a keyboard-accessible `Recheck` button. Recheck
performs the same GET assessment again, refreshes the assessment timestamp and
results, and does not mutate local operational data or invoke external
state-changing operations. A request failure is shown as an explicit page
error, not as successful readiness.
