# Data Model: Operator Workflow

No new persistent model is introduced. These are frontend/view models derived from existing
responses and URL state.

## OperationalWorkflowContext

| Field | Source | Rules |
|---|---|---|
| `shift` | URL query | Required after normalization; ISO `YYYY-MM-DD`; absent resolves to local today; invalid is non-executable. |
| `activeStep` | Page identity | One of `start-shift`, `dashboard`, `tickets`, `investigations`, `status`, `end-shift`. |
| `nextStep` | Existing preflight/loaded state | A navigation suggestion only; never invokes an action. |
| `readOnly` | View/action mode | True for all inspection/navigation and cache-health display. |

Relationship: one context is rendered by every in-scope page and is propagated in each workflow
link. It is not stored in local tracking, shift artifacts, or Jira cache.

## OperationalDataState

| Field | Values/rules |
|---|---|
| `source` | `jira-cache`, `local-tracking`, `investigations`, or page request. |
| `kind` | `current`, `stale`, `unavailable`, `error`, `read-only`. |
| `message` | Operator-facing meaning and safe next action; no sensitive backend detail. |
| `updatedAt` | Display when supplied by existing source; otherwise omitted. |
| `dataAvailable` | Independent of other sources; false never clears another valid section. |

Mapping: Jira cache `freshness=current` maps to current, `freshness=stale` maps to stale, and
missing/invalid cache maps to unavailable. A failed HTTP request maps to error. Read-only annotates
an inspection path and may coexist with a source state.

## ConfirmationGate

| Field | Rule |
|---|---|
| `action` | Exact requested local/Jira effect shown before execution. |
| `scope` | `local` or `jira`; a local action must not claim or perform a Jira effect. |
| `confirmed` | False/absent sends no request. True is sent only from the confirm control. |
| `outcome` | Success refreshes only the relevant displayed data; failure remains visible as error. |

Transitions: `idle → pending confirmation → cancelled` produces no request or mutation;
`idle → pending confirmation → confirmed → executing → success/error`. The dialog must be the last
interactive step before the request.

## Existing authoritative entities

- **Jira cache**: Existing cache file and health response remain the source of Jira queue freshness.
- **Local NOC tracking**: Existing active tracking records retain only local next action and notes;
  `jiraKey` is a reference, not a local copy of Jira fields.
- **Shift artifacts/handover**: Existing Start Shift, notes, handover, and End Shift services retain
  their paths and lifecycle. This feature adds no duplicate artifact or workflow record.
