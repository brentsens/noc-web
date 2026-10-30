# Data Model: Bounded NOC AI Assistant

No persistent assistant conversation or provider state is introduced. Generic questions and their
context/results are transient. A successful predefined AI Action may create the bounded
`AssistantActionReport` artifact described below; it is not chat history or authoritative
operational state.

## SelectedShiftContext

| Field | Source and validation |
|---|---|
| `shiftDate` | URL `shift` propagated by `workflow-context.js`; ISO `YYYY-MM-DD`; invalid or absent-at-submit is non-executable. |
| `visible` | UI workflow bar and assistant heading; always shows the same date sent to the API. |
| `scope` | Exactly one selected shift; no default, prior page, server session, or cross-shift substitute is valid for an assistant request. |

## AssistantQuestion

| Field | Rules |
|---|---|
| `question` | Required non-empty bounded operator text; request-only and never retained. |
| `shiftDate` | Must match `SelectedShiftContext`. |
| `providerDisclosureAcknowledged` | Required acknowledgement after the provider-retention disclosure is shown; it records consent for this request only and is not retained. |

## ReviewedEvidence

| Field | Rules |
|---|---|
| `id` | Stable, non-sensitive reference such as `jira-cache`, `local-work`, `shift-notes`, `handover`, `readiness`, or `investigation:<name>`. |
| `kind` | Permitted selected-shift summary type: cached Jira queue, local work, shift notes, handover, Dashboard/Status/readiness, or investigation summary. |
| `provenance` | `noc-web`, `noc-inv`, or `copilot-mcp`; only the latter two are valid for investigation-derived evidence. |
| `availability` | `available`, `unavailable`, `stale`, `malformed`, or `conflicting`. |
| `reference` | Bounded source/notebook reference when already safe to expose; never raw body/log. |
| `summary` | Minimum safe selected-shift summary supplied to the default Copilot CLI provider or an injected replacement only when available. |
| `freshness` | For `jira-cache`, whether cached data is current, stale, unavailable, or malformed; never triggers refresh. |

Relationships: one request has zero or more independent evidence items. An unavailable item remains
listed as a limitation and never causes an unrelated source to be substituted.

## AssistantResponse

| Field | Rules |
|---|---|
| `shiftDate` | Echoes the validated selected shift. |
| `facts` | Source-grounded statements; each has `text` and one or more available evidence IDs. |
| `reviewedFindings` | Existing operator-reviewed investigation findings projected unchanged with investigation evidence IDs; never authored by the assistant. |
| `aiObservations` | Clearly labeled advisory AI analysis; never a fact, command, or approved instruction. |
| `recommendations` | Optional operator choices with evidence IDs and an existing workflow route; navigation only. |
| `provider` | Fixed identifier `github-copilot-cli`; no provider diagnostics or execution details are exposed. |
| `providerInvoked` | True only when the Copilot CLI process was launched for this answer; false for refusal, insufficient context, or a CLI that could not be started. |
| `providerStatus` | `success`, `unavailable`, `timeout`, or `invalid`; success remains success when both AI-authored arrays are empty. |
| `evidence` | Reviewed item references and availability; raw evidence excluded. |
| `limitations` | Insufficient, unavailable, stale, malformed, conflicting, invalid-shift, out-of-scope, refusal, or provider-failure explanation. |
| `status` | `complete` only when a validated answer exists; otherwise `limited` or `unavailable`, never success-shaped. |

A substantive answer may have facts plus operator-reviewed findings, AI observations, and
recommendations. Only AI observations and recommendations are provider-authored. When the context
cannot support an item, the appropriate array is empty and `limitations` explains why.
Source-grounded facts and operator-reviewed findings are assembled from existing NOC Web
projections; a provider cannot create facts or write, revise, or approve reviewed findings.

## RecommendationRoute

| Field | Rules |
|---|---|
| `label` | Describes an existing NOC Web workflow, not an action to execute. |
| `href` | Existing shift-preserving page URL. |
| `requiresConfirmation` | True when the destination has a state-changing operation; navigation is not confirmation and must not prefill consent. |

## AssistantActionReport

| Field | Rules |
|---|---|
| `shiftDate` | The explicitly selected, validated shift; the report is written only under that shift's existing `reports/` directory. |
| `actionType` | One of `analysis`, `summary`, `followups`, or `handover`; the corresponding prompt is fixed server-side, not supplied by the browser. |
| `generatedAt` | UTC timestamp created after the action response passes strict validation. |
| `provider` | Fixed display value `GitHub Copilot CLI`; no process diagnostics or authentication details. |
| `filename` | `ai-<action-slug>-<UTC timestamp>-<random token>.md`; exclusive creation prevents overwrites. |
| `content` | Only normalized facts, operator-reviewed findings, AI observations, recommendations, evidence/source/freshness status, and limitations; no prompt, temporary context, raw provider output, credentials, tokens, or raw evidence. |
| `status` | Explicitly advisory and non-authoritative; never updates an operational record. |

No entity represents an assistant tool call, operational mutation, command, cache refresh, direct
Datadog query, prompt log, conversation history, or provider-retention assertion.
