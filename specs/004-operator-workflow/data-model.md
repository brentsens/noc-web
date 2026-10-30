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
| `source` | `jira-cache`, `local-tracking`, `investigations`, `noc-inv`, `copilot-mcp`, or page request. |
| `kind` | `current`, `stale`, `unavailable`, `error`, `read-only`. |
| `message` | Operator-facing meaning and safe next action; no sensitive backend detail. |
| `updatedAt` | Display when supplied by existing source; otherwise omitted. |
| `dataAvailable` | Independent of other sources; false never clears another valid section. |

Mapping: Jira cache `freshness=current` maps to current, `freshness=stale` maps to stale, and
missing/invalid cache maps to unavailable. A failed HTTP request maps to error. Read-only annotates
an inspection path and may coexist with a source state.

## EvidenceSource

| Field | Source/rules |
|---|---|
| `path` | One of existing `noc-inv` or Copilot MCP; no direct Datadog path is valid. |
| `access` | Always `read-only`; NOC Web does not issue source writes, retries, or queries. |
| `availability` | `available`, `unavailable`, `error`, or `no-result`, presented independently of other workflow data. |
| `reference` | Optional existing source/notebook reference; identifies provenance without copying source content. |

Relationship: an investigation may reference an EvidenceSource. The source evidence, raw logs,
notebook body, MCP response, and prompt/output are not NOC Web entities and must not be persisted
or returned by the workflow contract.

## AdvisoryFinding

| Field | Rules |
|---|---|
| `summary` | Concise AI-generated candidate conclusion; displayed as advisory, never as operational state. |
| `sourcePath` | `noc-inv` or `copilot-mcp`, retained as provenance only. |
| `reviewState` | `unreviewed`, `reviewed`, or `rejected`; only an operator transition may leave `unreviewed`. |

Transitions: `unreviewed → reviewed` or `unreviewed → rejected` require an immediate explicit
confirmation. `unreviewed` and `rejected` findings never propagate to operational summaries.

## ReviewedFinding

| Field | Rules |
|---|---|
| `finding` | Concise operator-reviewed operational conclusion or state; no raw evidence. |
| `state` | Current concise investigation state suitable for operational views. |
| `reviewedAt` / `reviewedBy` | Review traceability fields when the existing lifecycle supports them. |
| `destinations` | Notes, Dashboard, Status, End Shift, and handover only. |

Relationship: a ReviewedFinding is NOC Web-owned context linked to an investigation lifecycle and
may be projected to destinations. It must not include Jira-ticket investigation content, Datadog
records, raw notebook/log text, or unreviewed AI analysis.

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
