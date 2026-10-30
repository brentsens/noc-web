# Research: Bounded NOC AI Assistant

## Decision: use a transient, read-only assistant mediator

**Rationale**: A new backend service constructs the minimum context for one explicitly selected
shift, sends it through the provider-neutral callable (defaulting to the operator's authenticated
Copilot CLI session), validates a structured response, and discards generic question material when
the request ends. The four predefined AI Actions have a separate fixed-action endpoint that may
persist only the validated normalized advisory result in the selected shift's existing reports
directory. The browser holds the rendered result only in the current page DOM.

**Alternatives considered**:

- Persist conversations or generic summaries for later shifts: rejected; this violates FR-013.
- Call an inference provider directly from browser JavaScript: rejected; it would bypass NOC Web's evidence
  boundary and failure handling.
- Reuse the file-backed AI report reader as a conversation store: rejected. The existing report
  viewer is extended only for validated predefined-action reports; it is not chat history.

## Decision: define a strict selected-shift context envelope

**Rationale**: The request accepts an ISO shift date only in the URL-derived page context and a
bounded question. The backend revalidates the date and builds a context envelope from existing,
read-only selected-shift projections: cached Jira queue with freshness, Local NOC Tracking,
shift-note/handover summaries, Dashboard/Status/readiness warnings, and investigation projections.
Investigation material is limited to published operator-reviewed findings, provenance,
availability, and reference. Raw `noc-inv` logs, notebooks, credentials, and other-shift records
never enter the envelope. Jira is read from the existing cache only; the assistant never refreshes
or queries Jira.

**Alternatives considered**:

- Infer the shift from a browser session or current date server-side: rejected; it can cross a
  shift boundary and conflicts with FR-002.
- Pass complete NOC files or raw investigation evidence: rejected; it exceeds minimum evidence and
  existing provenance protections.
- Let the provider search the workstation or other NOC systems: rejected; it broadens authority.

## Decision: use Copilot CLI as a tool-less default inference adapter

**Rationale**: `noc-tools` documents its AI Actions flow as operational records -> temporary
context file -> `copilot -p` -> advisory result -> cleanup. NOC Web keeps its provider-neutral
`Callable[[dict], dict]` boundary but implements the default callable with the locally installed
GitHub Copilot CLI and the operator's existing authenticated CLI session. The adapter starts the
CLI in a private temporary directory containing only `context.json`; it passes a fixed prompt
argument that references that file, while the operator question and records remain file data rather
than command-line arguments. The CLI is invoked with an empty `--available-tools` set, without
`--allow-all-tools`, `--allow-all`, `--yolo`, or shell execution. The temporary directory is removed
on success and every failure path. Missing CLI, unauthenticated session, timeout, non-zero exit,
and malformed output become controlled unavailable responses.

**Alternatives considered**:

- Add another model API or credentials: rejected; the operator's authenticated Copilot CLI session
  is the approved inference path.
- Invoke Copilot with automatic tool approvals: rejected; the assistant must not gain shell,
  filesystem-write, or MCP action authority.
- Pass the question or records as command-line arguments: rejected; only the fixed prompt is an
  argument, and bounded request data is supplied through the temporary file.

## Decision: retain noc-inv/Copilot evidence boundaries and prohibit direct Datadog

**Rationale**: Existing investigation projections already distinguish `noc-inv` and `copilot-mcp`
provenance and exclude raw evidence. The assistant context collector consumes only those safe
projections. The CLI adapter has no available tools, so it cannot query Datadog MCP, Atlas, or
Microsoft 365. A provider-neutral callable remains the only assistant inference interface; the
default implementation does not add a direct Datadog SDK, HTTP client, or independent evidence
retrieval path.

**Alternatives considered**:

- Query Datadog to enrich an answer: rejected by FR-009 and the existing no-direct-Datadog safety
  boundary.
- Treat a tool-providing MCP server as a model provider: rejected because MCP tool access does not
  itself provide approved inference.

## Decision: keep operator-reviewed findings separate from AI-generated categories

**Rationale**: Source-grounded `facts` require available evidence references. Operator-reviewed
investigation findings are projected directly from existing reviewed investigation context and are
never written or authored by a provider. The provider may return only `aiObservations` and
`recommendations`; both remain advisory and carry evidence references, while recommendations may
include only a safe existing-workflow route. No AI-generated interpretation may be labeled as
operator-reviewed. If evidence is insufficient, stale, malformed, conflicting, unavailable, or out
of scope, the response uses a limitation and omits unsupported items.

**Alternatives considered**:

- Render provider prose as one untyped answer: rejected; operators cannot distinguish evidence
  from AI interpretation or recommendation.
- Let the provider generate entries in a “reviewed” category: rejected; only the operator may review
  and approve investigation findings.
- Treat a provider claim as a fact without evidence references: rejected; it permits invented
  operational state.

## Decision: action requests are refusal/navigation only

**Rationale**: The mediator detects requested write, command, refresh, sync, external query, or
Datadog action before provider invocation when possible and also supplies a non-action policy to
the provider. Its output can contain only a route to an existing page/workflow; it never includes an
execution request, prefilled confirmation, or confirmation token. Existing action pages retain
all independent immediate confirmation gates.

**Alternatives considered**:

- Add provider function calls to existing APIs: rejected; it would create a second action path.
- Use assistant submission as implied confirmation: rejected by FR-010 and Constitution VI.

## Decision: disclose provider handling before submission

**Rationale**: The assistant page disables submission until the operator is shown a concise,
pre-submit disclosure: generic questions remain transient, while only a validated normalized
report from a successful predefined AI Action is retained; prompts, temporary context, raw
evidence, and provider output are never persisted/logged. Injected-provider handling or retention
may apply and is outside NOC Web control. The disclosure does not claim provider retention is
absent and is rendered for every assistant entry point.

**Alternatives considered**:

- State “private” or “no retention” without qualification: rejected as inaccurate.
- Put disclosure only in documentation: rejected because FR-017 requires it before submission.

## Decision: isolate failures with bounded status and no diagnostic payload retention

**Rationale**: Context sources are collected independently. Their availability is listed in the
answer even when another source succeeds. Provider timeout, transport failure, or invalid schema
returns an explicit assistant limitation, not a partial/success-shaped answer. Controlled error
codes/messages replace raw exceptions. The service does not log request/response bodies, persist
failures, retry in the background, or alter existing pages/workflows.

**Alternatives considered**:

- Fail the whole dashboard when one evidence source fails: rejected; it violates FR-012.
- Fall back to a prior answer or broad context: rejected; it violates shift isolation and no
  retention.
