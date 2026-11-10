# Feature Specification: Direct Read-Only Datadog Evidence Provider

**Feature Branch**: `015-datadog-rest-provider`

**Created**: 2026-11-10

**Status**: Draft

**Input**: User description: "Replace NOC Web's Copilot CLI and Datadog MCP dependency for Datadog evidence retrieval with a direct read-only Datadog REST API provider using a scoped bearer access token. The provider must work when GitHub Copilot CLI is completely unavailable or has exhausted its allowance. Support read-only retrieval of active/live Datadog incidents, incident details, referenced investigation notebooks, and referenced monitor definitions. Preserve relationships between incidents, notebooks, monitors, and their source URLs/identifiers in normalized local evidence. Authentication must use a Datadog bearer access token supplied only through the process environment. The token must never appear in API responses, frontend output, logs, reports, cache files, test artifacts, exceptions, or persisted application data. The Datadog integration must be structurally read-only. NOC Web must issue only retrieval operations to Datadog and must not create, update, acknowledge, mute, resolve, delete, or otherwise modify Datadog resources. Preserve the existing active-incident cache contract, freshness states, stale-cache fallback, refresh coalescing, bounded timeouts, and fail-closed behavior. If a refresh fails, preserve the last successful cache as stale rather than replacing it with untrusted or empty success-shaped data. Provider readiness must be static and non-networked: validate provider configuration and credential presence without calling Datadog simply because readiness, status, or health pages are loaded. Normalize and validate retrieved Datadog data before it becomes trusted NOC Web evidence. Bound response sizes and reject malformed, unexpected, or incompatible responses. Incident retrieval must support the current live-incident workflow without using Copilot or MCP. Notebook retrieval must support Datadog investigation notebooks and expose their Markdown cells, time ranges, metric/query definitions, and appropriate metadata as read-only evidence. Monitor retrieval must expose the monitor identity, name, type, query, thresholds, tags, current state, and relevant message/reference data. Use the existing Datadog US1 API endpoint by default, while keeping the site/base URL explicitly configurable for future environments. Do not send retrieved evidence to an AI model as part of this feature. DeepSeek analysis and replacement of noc-inv investigation generation are explicitly out of scope and will be handled separately. Do not change noc-handover generation in this feature. Do not require GitHub Copilot CLI or Datadog MCP for any Feature 015 acceptance criterion. Add regression tests proving zero Copilot invocation, zero Datadog MCP invocation, read-only Datadog requests, credential non-disclosure, stale-cache preservation, malformed-response rejection, bounded responses/timeouts, and compatibility with the existing incident frontend/API contract."

## Clarifications

### Session 2026-11-10

- Q: Should notebook and monitor evidence be retrieved on demand when requested, or pre-fetched and cached during every incident refresh? → A: Retrieved on demand per explicit request; no addition to the persistent incident cache.
- Q: May the provider use an explicitly allowlisted Datadog query operation that is transported as an HTTP POST but only reads data? → A: Yes; read-only is enforced by operation semantics plus a fixed allowlist, not by HTTP method alone.
- Q: Should normalized incident-detail, notebook, and monitor evidence be exposed through a new read-only HTTP API in this feature, or only through the internal backend service? → A: Internal backend evidence service only; no new HTTP route and no frontend change.
- Q: How should NOC Web determine which notebooks and monitors are referenced by an incident? → A: Use only explicit notebook/monitor identifiers or links present in the incident, incident-detail, or retrieved notebook evidence, including exact Datadog-relative paths in bounded narrative text and supported notebook cell definitions; do not list unrelated resources or scan unsupported content.
- Q: How should notebook evidence handle cell types that are neither Markdown nor a supported query or metric definition? → A: Preserve supported cells, explicitly mark unsupported cells as omitted in metadata, and keep the notebook usable unless its structure is invalid or it has no supported content.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Retrieve live incidents without Copilot or MCP (Priority: P1)

An NOC operator continues to see current Datadog incidents on the Dashboard and
Investigations views even when GitHub Copilot CLI is not installed,
unauthenticated, or has exhausted its allowance, and without any Datadog MCP
server being configured.

**Why this priority**: Live incident awareness is an operational safety feature.
It must not fail because an unrelated AI tool is unavailable or over quota.

**Independent Test**: Remove, unauthenticate, and quota-exhaust the Copilot CLI
and remove all Datadog MCP configuration, then perform incident refreshes
against a substituted Datadog retrieval response. Verify that the same incident
snapshot, counts, freshness, and Datadog links appear as before with no Copilot
or MCP invocation.

**Acceptance Scenarios**:

1. **Given** Copilot CLI is absent and no Datadog MCP server is configured,
   **When** an operator opens Dashboard or Investigations, **Then** the
   existing incident view renders from the shared snapshot without error.
2. **Given** Copilot CLI is unavailable and the Datadog provider is correctly
   configured, **When** incident refresh succeeds, **Then** the resulting
   snapshot matches the existing incident projection contract and displays in
   both views.
3. **Given** a successful refresh produces an empty current-incident set,
   **When** the view renders, **Then** it reports zero current incidents rather
   than unavailable data.

---

### User Story 2 - Retrieve incident, notebook, and monitor evidence (Priority: P1)

An NOC operator or downstream NOC workflow can obtain normalized, read-only
Datadog evidence for a live incident, its detail record, the investigation
notebooks it references, and the monitor definitions referenced by the incident
or its retrieved notebooks, including the relationships and source identifiers
that connect them.

**Why this priority**: Incident awareness alone is insufficient for
investigation; operators need the authoritative notebooks and monitors behind an
incident, with traceable links, without relying on an AI tool to fetch them.

**Independent Test**: Provide a fixture incident that references a notebook and
a monitor, where the notebook Markdown also references another monitor, retrieve
all evidence levels, and verify normalized evidence contains the incident
projection and details, notebook Markdown cells, time ranges, and metric/query
definitions, monitor identity, name, type, query, thresholds, tags, current
state, and message/reference data, plus intact relationships, deduplication, and
source URLs or identifiers.

**Acceptance Scenarios**:

1. **Given** a live incident exists, **When** details are retrieved, **Then**
   the normalized detail evidence preserves the incident identifier, state,
   fields, references, and source link without inventing missing values.
2. **Given** an incident references a Datadog investigation notebook, **When**
   evidence is retrieved, **Then** the notebook's Markdown cells, time ranges,
   metric/query definitions, metadata, and source identifier are exposed
   read-only and linked to the incident.
3. **Given** an incident references a Datadog monitor, **When** evidence is
   retrieved, **Then** the monitor's identity, name, type, query, thresholds,
   tags, current state, message/reference data, and source identifier are
   exposed read-only and linked to the incident.
4. **Given** a referenced notebook or monitor is missing, inaccessible, or
   malformed, **When** evidence is assembled, **Then** the incident evidence
   remains usable, the affected reference is explicitly reported as
   unavailable, and no fabricated placeholder evidence is produced.
5. **Given** a referenced notebook contains exact Datadog monitor references in
   Markdown or a supported cell definition, **When** evidence is retrieved,
   **Then** those monitors are retrieved and normalized, linked through the
   notebook relationship, and deduplicated with monitors referenced by the
   incident.

---

### User Story 3 - Fail closed and preserve the last trusted cache (Priority: P1)

An NOC operator can distinguish current, stale, unavailable, and refreshing
incident data. When a provider refresh fails for any reason, the last
successful snapshot and successful timestamp remain available and are marked
stale instead of being replaced by an empty or untrusted result.

**Why this priority**: An authentication or network failure must never look like
a healthy NOC with zero incidents. Stale evidence preserves operator
situational awareness during an outage.

**Independent Test**: Seed a successful snapshot, then exercise authentication
failure, timeout, malformed response, oversized response, server error, and
cache-write failure. Verify the prior snapshot and timestamp survive with stale
status; with no prior snapshot, verify unavailable status and zero
success-shaped data.

**Acceptance Scenarios**:

1. **Given** a successful snapshot exists, **When** any later retrieval fails,
   **Then** the incident list and last successful timestamp remain visible and
   freshness becomes stale.
2. **Given** no successful snapshot exists, **When** retrieval fails, **Then**
   freshness is unavailable and the view does not claim zero incidents.
3. **Given** a refresh is in progress, **When** another refresh is requested,
   **Then** freshness reports refreshing and overlapping retrieval is
   prevented or safely coalesced across processes.
4. **Given** Datadog reports an incident as resolved, **When** a later refresh
   succeeds, **Then** it is removed only from the successful snapshot and no
   local investigation, shift, or handover state changes.

---

### User Story 4 - Keep the access token secret and the integration read-only (Priority: P1)

An NOC administrator can supply a scoped, read-only Datadog bearer token
through the process environment, knowing the token never appears in any
operator-facing or persisted output and that NOC Web cannot modify Datadog.

**Why this priority**: Credential disclosure and accidental mutation are
security and safety failures. The integration must be incapable of both by
construction, not merely by convention.

**Independent Test**: Configure a recognizable sentinel token, exercise
successful and failing refreshes and evidence retrievals, then search every API
response, frontend payload, log, exception message, report, cache file, test
artifact, and persisted application file for the sentinel. Record every
outbound Datadog request and verify all are retrieval-only.

**Acceptance Scenarios**:

1. **Given** a configured bearer token, **When** any API response or persisted
   file is produced, **Then** it contains no token value, fragment, or
   reversible representation.
2. **Given** Datadog returns an error echoing authentication material, **When**
   the failure is surfaced or logged, **Then** the message is sanitized and
   contains no credential value.
3. **Given** any incident, notebook, or monitor retrieval, **When** outbound
   requests are inspected, **Then** every request uses only read-only retrieval
   operations and no create, update, acknowledge, mute, resolve, or delete
   operation is ever issued.
4. **Given** readiness, health, or status surfaces are loaded, **When** provider
   configuration is valid, **Then** readiness is reported from static
   configuration only with no Datadog network request.

---

### User Story 5 - Diagnose provider readiness without network calls (Priority: P2)

An NOC operator or administrator can see whether the Datadog provider is
configured, whether the required token is present, and the effective Datadog
site, without readiness or health checks triggering a Datadog request.

**Why this priority**: Configuration mistakes must be distinguishable from
Datadog outages, and diagnostics must never cause external traffic or quota use.

**Independent Test**: View readiness, health, and status with a valid
configuration, without a token, with an invalid base URL, and with all
configuration absent. Record outbound requests and verify zero Datadog calls,
accurate non-secret status, and safe corrective guidance.

**Acceptance Scenarios**:

1. **Given** valid configuration and a present token, **When** readiness is
   viewed, **Then** the provider is reported ready without claiming Datadog was
   contacted or the token was validated.
2. **Given** the token is absent or the base URL is invalid, **When**
   readiness is viewed, **Then** the provider is reported not ready with
   corrective guidance that contains no credential value.
3. **Given** no Datadog provider configuration exists, **When** readiness is
   viewed, **Then** it reports not configured and does not infer readiness from
   an unrelated tool.

---

### Edge Cases

- The configured token is absent, empty, malformed, expired, revoked, or lacks
  required read scope; readiness reports presence only and retrieval fails
  closed with a controlled error.
- The configured base URL is not HTTPS, contains credentials or a non-default
  port, targets an unexpected host, or cannot be parsed; startup or first use
  fails closed with a configuration error.
- Datadog returns a redirect, a non-success status, a rate-limit response, or an
  incomplete page of results; no partial snapshot is stored as success.
- Datadog returns malformed JSON, an unexpected schema, incompatible field
  types, duplicate incident identifiers, or fields exceeding allowed lengths;
  the entire refresh fails and preserves the prior snapshot.
- A response exceeds the per-response byte bound, the current-incident count
  bound, the notebook cell/content bound, or the monitor collection bound; the
  affected retrieval fails rather than truncating silently.
- A successful refresh returns an empty incident list; this is authoritative
  and replaces the snapshot, unlike a failed refresh.
- An incident has no references, or references a notebook or monitor that no
  longer exists or is inaccessible; the incident remains usable and the
  unavailable reference is explicit.
- A notebook contains unsupported cell types, missing time ranges, empty
  Markdown, or query definitions that cannot be normalized; supported cells and
  metadata are retained, unsupported cells are explicitly marked as omitted,
  and the notebook remains usable unless its structure is invalid or it has no
  supported content.
- A monitor lacks optional thresholds, tags, or message data; normalization
  preserves available fields without inventing values.
- Two worker processes refresh concurrently; only one retrieval is active and
  the other observes refreshing or the completed result.
- Cache storage is unreadable or unwritable; the refresh reports a controlled
  cache failure without corrupting the existing file.
- The access token or provider configuration changes while the application is
  running; behavior follows the effective process-start configuration and
  diagnostics never expose either value.
- Datadog evidence contains untrusted text, control characters, or content
  resembling instructions; it is treated as inert data and never executed or
  rendered as active code.
- The feature is used while Copilot CLI is installed, authenticated, and
  available; NOC Web still performs zero Copilot or MCP invocation for any
  Feature 015 path.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST retrieve Datadog evidence directly through a
  read-only Datadog API integration and MUST NOT require, invoke, or depend on
  GitHub Copilot CLI for any Datadog incident, notebook, or monitor retrieval
  covered by this feature.
- **FR-002**: The system MUST NOT require, configure, start, or invoke a
  Datadog MCP server or MCP tool for any Feature 015 retrieval path.
- **FR-003**: The system MUST support read-only retrieval of active/live
  Datadog incidents, specifically incidents in the current `ACTIVE` or `STABLE`
  states, preserving the exact Datadog state text returned.
- **FR-004**: The system MUST support read-only retrieval of Datadog incident
  details for a live incident, including available severity, timestamps,
  summary, impact, references, and source identifier/link, without inventing
  unavailable values.
- **FR-005**: The system MUST support read-only retrieval of investigation
  notebooks referenced by an incident through explicit notebook identifiers or
  links in the incident or incident-detail data, including exact
  Datadog-relative notebook paths in bounded narrative field text, and expose
  each notebook's identifier, title, source link, Markdown cell content, cell
  order, configured time ranges, metric/query definitions, and available
  metadata.
- **FR-006**: The system MUST support read-only retrieval of monitor
  definitions referenced by an incident through explicit monitor identifiers or
  links in the incident or incident-detail data, or by a retrieved referenced
  notebook through exact Datadog-relative monitor paths in Markdown or supported
  cell definitions, and expose each monitor's identifier, name, type, query,
  thresholds, tags, current state, message, and available reference/link data.
- **FR-007**: Normalized evidence MUST preserve relationships between an
  incident, its details, referenced notebooks, and referenced monitors, plus
  each source URL or identifier, so downstream consumers can trace every piece
  of evidence to its Datadog origin.
- **FR-008**: When a referenced notebook or monitor cannot be retrieved,
  validated, or is absent, the system MUST report that reference as unavailable
  without fabricating evidence, and MUST NOT invalidate otherwise usable
  incident evidence unless the incident evidence itself is untrustworthy.
- **FR-009**: Authentication MUST use a scoped Datadog bearer access token
  supplied only through the process environment at application start, and the
  token MUST be presented only to the configured Datadog destination.
- **FR-010**: The token value, any token fragment, and any reversible
  representation of the token MUST NOT appear in API responses, frontend
  output, logs, reports, exception messages, cache files, test artifacts, or
  persisted application data.
- **FR-011**: The Datadog integration MUST be structurally read-only: NOC Web
  MUST issue only retrieval operations from a fixed allowlist and MUST NOT
  create, update, acknowledge, mute, resolve, delete, or otherwise modify any
  Datadog resource, including incidents, notebooks, monitors, or related
  objects. A non-mutating query operation MAY use POST when it is on the
  allowlist; read-only status is defined by operation semantics and the
  allowlist, not by the HTTP method alone.
- **FR-012**: The system MUST reject any attempted Datadog operation outside
  the approved read-only retrieval set rather than forwarding it.
- **FR-013**: The Datadog API base URL MUST default to the existing US1
  endpoint and MUST be explicitly configurable for other sites; configuration
  MUST reject insecure, malformed, or unexpected destinations.
- **FR-014**: Provider readiness, status, and health MUST be determined from
  static configuration validation and credential presence only, MUST complete
  without any Datadog network request, and MUST distinguish ready, not ready,
  and not configured states with safe corrective guidance.
- **FR-015**: The system MUST preserve the existing active-incident cache
  contract exactly, including response field names, field types, count,
  freshness values `current`, `stale`, `unavailable`, and `refreshing`,
  last-attempted and last-successful timestamps, error values, and the existing
  frontend consumption behavior.
- **FR-016**: The system MUST preserve the existing 60-second target refresh
  interval, explicit refresh action, shared short-lived cache behavior, and
  cross-process refresh coalescing so that at most one retrieval is active at a
  time.
- **FR-017**: Every Datadog retrieval MUST use a bounded, explicit timeout and
  MUST NOT leave an unbounded request active after the timeout is reached.
- **FR-018**: If any refresh fails, the system MUST preserve the last
  successful incident snapshot and successful timestamp, mark freshness stale,
  and MUST NOT write empty, partial, or unvalidated data as a successful
  snapshot.
- **FR-019**: With no prior successful snapshot, a failed refresh MUST report
  unavailable rather than zero current incidents.
- **FR-020**: A successful empty current-incident result MUST be treated as
  authoritative and replace the snapshot as zero incidents.
- **FR-021**: All retrieved Datadog data MUST be normalized and validated
  before becoming trusted NOC Web evidence; malformed, unexpected,
  incompatible, duplicate, or out-of-bound data MUST be rejected with a
  controlled failure, and validation MUST NOT repair or invent values.
- **FR-022**: Response sizes MUST be bounded for every retrieval category,
  including a maximum of 100 current incidents per snapshot, a per-response
  byte bound, bounded notebook cell counts and content, and bounded monitor
  collections; an over-bound response MUST fail rather than be silently
  truncated.
- **FR-023**: Retrieved Datadog evidence MUST NOT be sent to an AI model as
  part of this feature, and this feature MUST NOT change DeepSeek analysis,
  `noc-inv` investigation generation, or `noc-handover` generation.
- **FR-024**: Incidents, notebooks, and monitors MUST be exposed as read-only,
  normalized evidence through the existing internal backend evidence/service
  boundary only, without adding a new HTTP route or frontend change and without
  introducing new mutation, acknowledgement, or workflow-gating behavior.
- **FR-025**: Incident details, notebook evidence, and monitor evidence MUST be
  retrieved on demand per explicit request and MUST NOT be added to the
  persistent active-incident cache.
- **FR-026**: Datadog retrieval and refresh failures MUST NOT block Dashboard,
  Investigations, Start Shift, End Shift, Jira/Tickets, Assistant, or handover
  workflows, and stale/unavailable incident data MUST remain isolated to the
  incident view.
- **FR-027**: The system MUST include regression coverage proving zero Copilot
  invocation, zero Datadog MCP invocation, retrieval-only Datadog requests,
  credential non-disclosure, stale-cache preservation, malformed and oversized
  response rejection, bounded timeouts, static non-networked readiness, and
  compatibility with the existing incident API and frontend contract.
- **FR-028**: The feature MUST NOT require GitHub Copilot CLI or Datadog MCP
  availability, authentication, allowance, configuration, or installation for
  any acceptance criterion of this feature.
- **FR-029**: Untrusted Datadog text MUST be handled as inert data and MUST
  NOT become executable commands, active markup, or trusted instructions.
- **FR-030**: Unsupported notebook cell types MUST be omitted from normalized
  evidence and explicitly reported as omitted in notebook metadata; the
  notebook MUST remain usable when it has valid structure and at least one
  supported cell, and MUST be rejected as invalid when its structure is invalid
  or it has no supported content.

### Key Entities

- **Datadog Provider Configuration**: The effective read-only Datadog
  connection settings, consisting of an explicitly configured base URL
  (US1 by default) and the presence of a bearer token supplied through the
  process environment. It contains no token value in any externally visible
  form.
- **Datadog Incident Projection**: The existing bounded, concise representation
  of one current `ACTIVE` or `STABLE` incident with identifier, exact state,
  severity, timestamps, summary, and source URL where available.
- **Incident Snapshot**: The most recently successful set of up to 100 current
  incident projections plus last-attempted and last-successful refresh times and
  a freshness state, preserved unchanged in meaning and shape.
- **Datadog Incident Detail Evidence**: Normalized read-only detail for one
  incident, including available fields, references, and the source identifier
  and link.
- **Datadog Notebook Evidence**: Normalized read-only representation of an
  investigation notebook, including identity, title, source link, Markdown
  cells in order, configured time ranges, metric/query definitions, metadata,
  and an explicit record of unsupported cell types omitted during
  normalization.
- **Datadog Monitor Evidence**: Normalized read-only representation of a
  monitor definition, including identity, name, type, query, thresholds, tags,
  current state, message, and reference data.
- **Evidence Relationship Map**: The explicit linkage from an incident to its
  detail evidence, referenced notebooks, and referenced monitors, preserving
  each source URL or identifier and the availability status of each reference.
- **Datadog Provider Readiness**: A non-secret, statically derived statement
  that the provider is ready, not ready, or not configured, without any Datadog
  network call or claim of credential validity.
- **Datadog Retrieval Failure**: A controlled, sanitized indication that a
  retrieval was unavailable, timed out, returned invalid or oversized data, or
  could not be cached, with no success-shaped substitute and no credential
  content.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of Feature 015 acceptance tests pass with GitHub Copilot CLI
  absent or unauthenticated and with no Datadog MCP server configured, while
  instrumentation records zero Copilot invocations and zero Datadog MCP
  invocations.
- **SC-002**: 100% of recorded Datadog requests in regression tests are
  retrieval-only; zero create, update, acknowledge, mute, resolve, or delete
  requests occur in any test path.
- **SC-003**: A sentinel access token appears in zero API responses, frontend
  payloads, logs, reports, exception messages, cache files, test artifacts, and
  persisted application files across success and failure runs.
- **SC-004**: In 100% of failure scenarios with a prior successful snapshot, the
  prior incidents and last successful timestamp are preserved and freshness is
  stale; with no prior snapshot, freshness is unavailable and the incident count
  is not presented as zero.
- **SC-005**: 100% of malformed, unexpected, incompatible, duplicate, or
  oversized fixture responses are rejected, and no partial snapshot replaces
  the prior successful snapshot.
- **SC-006**: No retrieval attempt remains active beyond its configured
  timeout, and every timeout produces a controlled freshness/error state within
  the bounded refresh operation.
- **SC-007**: Loading readiness, status, and health surfaces with any valid or
  invalid configuration causes zero Datadog network requests.
- **SC-008**: The existing incident API response fields, types, freshness
  values, error values, and frontend behavior are unchanged; existing incident
  API and frontend tests pass without modification to their contract
  expectations.
- **SC-009**: Notebook acceptance fixtures expose 100% of provided Markdown
  cells in order, their time ranges, metric/query definitions, metadata, and
  source identifiers as read-only evidence.
- **SC-010**: Monitor acceptance fixtures expose 100% of provided identity,
  name, type, query, thresholds, tags, current state, and message/reference data
  as read-only evidence.
- **SC-011**: For every incident fixture with references, the normalized
  evidence preserves all resolvable notebook and monitor relationships plus
  source identifiers, and explicitly marks every unresolvable reference as
  unavailable.
- **SC-012**: Every retrieval category enforces its configured byte and item
  bounds; over-bound fixtures fail with a controlled error rather than
  truncated evidence.
- **SC-013**: Existing pytest suites and full frontend module validation pass,
  with new regression coverage for all behaviours in FR-027.
- **SC-014**: Notebook and monitor evidence is available to backend acceptance
  tests without adding a new HTTP route or frontend change, and the existing
  incident API remains the only operator-facing Datadog HTTP surface.
- **SC-015**: In every notebook fixture containing unsupported cell types,
  supported cells are preserved, omitted cells are explicitly reported, and no
  unsupported raw content is presented as validated evidence; notebooks with
  invalid structure or no supported content are rejected.

## Assumptions

- The bearer token is supplied through the environment variable
  `NOC_WEB_DATADOG_ACCESS_TOKEN`, consistent with the existing
  `NOC_WEB_DEEPSEEK_API_KEY` convention. It is scoped externally to read-only
  Datadog access and is provisioned outside NOC Web.
- The Datadog API base URL is supplied through
  `NOC_WEB_DATADOG_BASE_URL` and defaults to the existing US1 endpoint
  `https://api.datadoghq.com`. Other sites are configured by changing that
  value before process start.
- The existing US1 host and API path conventions remain valid; this feature
  does not migrate to a new regional endpoint by default.
- "Active/live" has the same meaning as Feature 009: `ACTIVE` and `STABLE`
  incidents are current, and only a successful refresh may remove a `RESOLVED`
  incident.
- Referenced notebooks and monitors are discovered only from explicit
  identifiers or links present in the incident, incident-detail, or retrieved
  notebook evidence. Notebook discovery accepts only exact Datadog monitor paths
  in Markdown and supported cell definitions. NOC Web does not list unrelated
  Datadog resources or infer references from tags or naming conventions.
- The existing cache path, 60-second refresh interval, 90-second retrieval
  timeout, 100-incident cap, and 1 MB provider-response bound are the defaults
  to preserve unless a stricter category-specific bound is required.
- Normalized local evidence is a bounded, validated projection. Raw Datadog
  payloads, request traces, prompts, and credential material are not persisted.
  Incident details, notebook evidence, and monitor evidence are retrieved on
  demand and are not added to the persistent active-incident cache.
- The existing API error value `copilot-unavailable` remains accepted for
  contract compatibility, but the new provider does not depend on Copilot and
  reports its own failures using the existing controlled error categories.
- Notebook and monitor evidence is made available to backend consumers and
  future investigation work as read-only normalized data through the internal
  backend service only. This feature does not add a new HTTP route, frontend
  display, AI analysis, `noc-inv` generation changes, or handover changes.
- Feature 015 does not change the Assistant or AI Action provider architecture
  delivered by Feature 014; those paths continue to use their own configured
  provider and are not given Datadog evidence by this feature.
- Existing concurrency and cache semantics are preserved across worker
  processes sharing the incident cache; no new database or external cache is
  introduced.
- Read-only behaviour is enforced by a fixed operation allowlist. A Datadog
  query operation that only reads data may use POST, but no operation that can
  create, update, acknowledge, mute, resolve, delete, or otherwise modify a
  Datadog resource is permitted.
- Datadog API responses are untrusted input and may change over time, so
  incompatible schemas fail closed rather than being best-effort interpreted.
