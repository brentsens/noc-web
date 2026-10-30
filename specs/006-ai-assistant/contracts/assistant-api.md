# Assistant API and UI Contract

## Boundary

The generic question endpoint is an additive, transient mediation endpoint. It uses a
provider-neutral callable boundary and selected-shift NOC Web projections. The default local provider invokes the
operator's installed and authenticated GitHub Copilot CLI using `copilot -p`; an approved
application runtime may inject another callable as described in [Provider integration](#provider-integration).
The CLI has no available tools, and it does not query Datadog, Microsoft 365, or Atlas MCP servers.

The assistant MUST NOT directly call Datadog, invoke a command, refresh/synchronize data, write NOC
operational data, or expose raw evidence. It reads Jira only from the existing cache and never
refreshes it. Generic questions do not create AI reports or reuse persisted reports as chat history.
The four predefined AI Actions use a separate fixed-action endpoint that writes only a validated,
normalized advisory report in the selected shift's existing reports directory.

## Provider integration

`CopilotProvider` remains the provider-neutral interface:

```python
Callable[[dict[str, Any]], dict[str, Any]]
```

The provider receives the transient envelope with `shiftDate`, `question`, `evidence`, and a
read-only `policy`. Evidence contains only selected-shift projections marked `available`; it may
include bounded Jira-cache, Local NOC Tracking, handover/shift-note, Dashboard/Status/readiness,
and investigation summaries. It never includes raw Datadog evidence, credentials, or other-shift
records. The callback must not execute tools or operational actions, query other systems, persist
the envelope, or log request/context content.

The callback must return exactly this JSON-shaped dictionary (no extra top-level keys):

```json
{
  "aiObservations": [
    {"text": "Advisory observation.", "evidenceIds": ["local-work"]}
  ],
  "recommendations": [
    {
      "text": "Review the tracked ticket.",
      "evidenceIds": ["local-work"],
      "route": {
        "label": "Open Tickets",
        "href": "tickets.html",
        "requiresConfirmation": true
      }
    }
  ]
}
```

Both arrays may be empty only when the supplied evidence supports no applicable analysis. Every
item requires non-empty text and one or more evidence IDs that reference available envelope
evidence. Each recommendation must include exactly one route from the server-side allow-list;
`href` is the bare page name without query or fragment, and the server adds the selected `shift`
query. The route object contains exactly `label`, `href`, and `requiresConfirmation`. `facts` and
`reviewedFindings` are not provider fields and are derived only by NOC Web.

### Default local Copilot CLI adapter

NOC Web configures `answer_with_copilot_cli` as the default `CopilotProvider`. For each request, the
adapter creates a private system temporary directory, writes only the minimized request envelope
to `context.json`, and launches the CLI with a fixed prompt that references `@context.json`. The
operator question and operational records are never placed in the process argument list. The
subprocess uses an argument array, runs from the temporary directory, has `--available-tools` with
no entries, and does not use `shell=True`, tool auto-approval, `--allow-all`, or `--yolo`:

```text
copilot --trust-folder --available-tools --silent -p <fixed read-only prompt>
```

`--trust-folder` applies only to the disposable directory; it does not approve tools or paths. The
CLI uses its own existing authenticated operator session. NOC Web does not read, store, or pass
authentication tokens. The fixed prompt treats the operator question as the requested analysis
scope, describes the four AI Actions, requires useful evidence-supported analysis rather than
default empty arrays, and prohibits stale Jira claims, unsupported facts, writes, and prose outside
JSON. CLI stdout must be one JSON object matching the provider shape above; the existing assistant
service validates evidence IDs, exact keys, and allowlisted routes. The temporary directory
is deleted on success, missing output, malformed output, non-zero exit, timeout, and subprocess
failure. The subprocess timeout is 55 seconds; the enclosing provider boundary retains its
60-second maximum.

If `copilot` is missing, the CLI session is unauthenticated/unavailable, it exits non-zero, times
out, or returns malformed output, the adapter raises a content-free provider error. The endpoint
returns the existing controlled `status: "unavailable"` answer. Normal NOC Web workflows remain
available.

An approved host may inject a replacement callable before serving requests:

```python
from backend.app import app, configure_assistant_provider
from approved_runtime import answer_noc_context

configure_assistant_provider(answer_noc_context)
```

`configure_assistant_provider(None)` restores the default Copilot CLI callable. A non-callable
replacement provider, provider exception, timeout, or malformed structured response produces a
controlled unavailable answer, never raw provider details. Application liveness and other NOC Web
workflows remain operational.

The CLI is strictly an inference adapter for the already bounded context. Datadog investigation
retrieval remains in the separate `Datadog MCP -> GitHub Copilot CLI -> noc-inv` workflow; the
general assistant cannot call MCP tools.

## `POST /api/shifts/{shiftDate}/assistant/questions`

This is a read-only advisory request despite using POST to carry an ephemeral question. The router
validates path `shiftDate` as ISO `YYYY-MM-DD`; body `shiftDate` must equal it.

### Request

```json
{
  "shiftDate": "2026-10-29",
  "question": "What requires attention?",
  "providerDisclosureAcknowledged": true
}
```

`shiftDate` and `question` must be JSON strings. `question` is required, trimmed, and limited to
1,000 characters; it is handled only in request memory. A false/missing disclosure acknowledgement
receives `422`; malformed/mismatched shift receives `400`/`422` as appropriate. No request-body
value is placed in application logs, files, cache, browser storage, or response diagnostics.

### Complete or limited response (`200`)

```json
{
  "shiftDate": "2026-10-29",
  "status": "complete",
  "provider": "github-copilot-cli",
  "providerInvoked": true,
  "providerStatus": "success",
  "facts": [{"text": "One active local work item is recorded.", "evidenceIds": ["local-work"]}],
  "reviewedFindings": [{"text": "Operator-reviewed investigation finding.", "evidenceIds": ["investigation:service-latency"]}],
  "aiObservations": [{"text": "This is advisory analysis, not operational state.", "evidenceIds": ["local-work"]}],
  "recommendations": [{"text": "Review the tracked item.", "evidenceIds": ["local-work"], "route": {"label": "Open Tickets", "href": "tickets.html?shift=2026-10-29", "requiresConfirmation": true}}],
  "evidence": [{"id": "jira-cache", "kind": "jira-cache", "provenance": "noc-web", "availability": "available", "reference": null}, {"id": "local-work", "kind": "local-work", "provenance": "noc-web", "availability": "available", "reference": null}],
  "limitations": []
}
```

The response exposes only fixed provider provenance: `provider` is `github-copilot-cli`;
`providerInvoked` is true only when the CLI process was launched; and `providerStatus` is one of
`success`, `unavailable`, `timeout`, `invalid`, or `not-invoked`. Refusal or insufficient
question-relevant context returns `providerInvoked: false` and `providerStatus: "not-invoked"`.
A missing/unstartable CLI is unavailable and not invoked; an unavailable CLI session after launch
is invoked. Timeout and invalid-output statuses indicate the CLI was invoked. These fields contain
no prompt, temporary path, subprocess output, credentials, authentication data, or exception detail.

Context sufficiency depends on the question. A missing Shift Notes file does not prevent useful
ticket analysis when Local NOC Tracking and Jira cache evidence are available. Stale Jira evidence
may be included with its stale availability/freshness labels and must never be represented as
current. Timeline questions require timestamped selected-shift activity; another date's Shift
Notes are never substituted. When that activity is absent, the Assistant returns a grounded
explanation without invoking the provider.

`providerStatus: "success"` means a schema-valid provider result was received, not that it
contained advice. If both `aiObservations` and `recommendations` are empty, the Assistant views
explicitly state that Copilot completed without returning AI-generated observations or
recommendations.

The UI renders source-grounded Facts, operator-reviewed investigation findings, AI observations,
and Recommendations as distinct labeled sections. `reviewedFindings` are projected from the
existing reviewed investigation source and are not generated by Copilot. The provider may author
only `aiObservations` and `recommendations`; source-grounded facts are assembled from existing
NOC Web projections. `limited` and `unavailable` results use the same shape, retain independently
available source-grounded facts and reviewed findings, omit unsupported provider advice, and
include explicit limitations. Evidence entries contain references/status only; no raw logs,
notebook body, credentials, prompt, or provider response are returned.

### Refusal

A prohibited action request returns `200` with `status: "limited"`, no source facts, reviewed
findings, or AI observations, and `limitations` stating that nothing was changed. It may include a
navigation-only recommendation to an existing workflow. It must not invoke Copilot or any action
endpoint. Prohibited requests include writes, closes/reopens, synchronization, refresh, commands,
Datadog, and other external-system queries/actions. Asking about existing operator-reviewed
investigation findings is allowed and does not query Datadog.

### Service/evidence failure

Provider timeout/unavailability, invalid provider schema, or evidence failure returns either a
controlled `503` or a `200` `status: "unavailable"`/`"limited"` response according to whether the
request can safely expose independent evidence availability. It includes a controlled operator
message and source status; it never returns provider exception text or fabricated content. Existing
NOC Web APIs/pages continue independently.

## `POST /api/shifts/{shiftDate}/assistant/actions/{actionType}`

This endpoint is reserved for the four predefined AI Actions: `analysis`, `summary`, `followups`,
and `handover`. It accepts no operator-supplied prompt; each action maps to a fixed bounded
server-side question and uses the selected shift from the URL. The request body contains only:

```json
{"providerDisclosureAcknowledged": true}
```

The acknowledgement is required. The endpoint returns the validated Assistant response inside an
action wrapper:

```json
{
  "assistant": {"shiftDate": "2026-10-29", "status": "complete"},
  "report": {
    "name": "ai-shift-summary-20261029T120000123456Z-a1b2c3d4.md",
    "title": "Summarize Current Shift",
    "file": "ai-shift-summary-20261029T120000123456Z-a1b2c3d4.md",
    "available": true
  },
  "reportSaveWarning": null
}
```

Only a validated response with `status: "complete"`, `provider: "github-copilot-cli"`,
`providerInvoked: true`, and `providerStatus: "success"` is eligible for report persistence.
Unavailable, timeout, invalid, or malformed results return no report. If report persistence fails
after a successful answer, `assistant` remains intact, `report` is null, and
`reportSaveWarning` contains a fixed, content-free warning.

Reports are created exclusively under
`NOC_ROOT/<selected-shift>/reports/` with
`ai-<action-slug>-<UTC timestamp>-<8 hexadecimal characters>.md`. The shift and reports
directories must already exist; exclusive creation prevents overwrites. The action slugs are
`shift-analysis`, `shift-summary`, `followups`, and `handover-review`. The report contains only
normalized Facts, operator-reviewed findings, AI observations, Recommendations, source/freshness
statuses, and Limitations. It identifies the selected shift, action, generated timestamp, GitHub
Copilot CLI provider, and advisory/non-authoritative status. It never contains prompts, temporary
context, raw provider output, credentials, tokens, hidden provider details, or raw Datadog evidence.

The existing `GET /api/shifts/{shiftDate}/ai-reports` list includes generated reports. Its
read-only detail endpoint accepts the returned `name` and opens the generated file through the
existing viewer. Recent AI Reports refreshes after a successful save; save failure leaves the
successful analysis visible with a separate warning.

Recommendations to `investigations.html` are valid only when their evidence IDs cite available
`investigation` evidence with `noc-inv` or `copilot-mcp` provenance. Jira/Salesforce correlation
without that provenance must not route to Investigations.

## Assistant page contract

- The entry page runs `initializeWorkflow` and requires a valid visible `?shift=YYYY-MM-DD`; it
  does not normalize or select a substitute shift at submit time.
- Before enabling submit, it displays: “NOC Web does not persist or log your prompt, supplied
  context, response, or derived assistant context. GitHub Copilot CLI or another configured
  inference provider may apply its own handling or retention; NOC Web cannot claim it is absent.”
- It sends only the request above through the shared browser client and retains rendered data only
  in the current DOM. Refresh/navigation clears it; no local/session storage or console logging of
  prompt/context/response is allowed.
- Recommendation links preserve `shift` and enter existing workflows; they cannot submit a
  confirmation or change a destination's existing behavior.
- AI Actions use fixed action IDs and server-side prompts, disable duplicate submissions, and
  refresh Recent AI Reports after a successful report save. A report-save warning is separate from
  the displayed Assistant response.
- The AI Actions disclosure distinguishes generic transient questions from the narrowly scoped
  persistence of a validated report for successful predefined actions.
