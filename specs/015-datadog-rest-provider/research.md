# Research: Direct Read-Only Datadog Evidence Provider

**Feature**: `015-datadog-rest-provider`  
**Date**: 2026-11-10

## Decision 1: Standard-library HTTPS transport with an allowlisted client

**Decision**: Use `urllib.request` with an opener that refuses redirects, explicit
timeouts, a 1,000,000-byte bounded read, strict UTF-8/JSON decoding, and a fixed
operation allowlist. Do not add an HTTP SDK or client dependency.

**Rationale**: The runtime dependency set is intentionally small, and the
existing DeepSeek adapter already uses this pattern. Refusing redirects prevents
the bearer token from being forwarded to another destination. A fixed allowlist
makes read-only behavior structural rather than a convention.

**Alternatives considered**:
- Datadog SDK: rejected as a large dependency and it exposes mutation APIs.
- `httpx`/`requests`: rejected because one JSON retrieval path does not justify
  a new production dependency.
- Following redirects: rejected because it can forward authorization headers.

**Sources**:
- https://docs.datadoghq.com/api/latest/incidents/
- https://docs.datadoghq.com/api/latest/notebooks/
- https://docs.datadoghq.com/api/latest/monitors/get-a-monitors-details/

## Decision 2: US1 default endpoint with an explicit base-URL override

**Decision**: Default `NOC_WEB_DATADOG_BASE_URL` to
`https://api.datadoghq.com`. Accept only HTTPS Datadog API hosts under
`datadoghq.com`, `datadoghq.eu`, or `ddog-gov.com`, with no userinfo, query,
fragment, or parent traversal. Derive the operator-facing app URL by replacing
the leading `api.` host label with `app.`.

**Rationale**: The feature requires the existing US1 API endpoint by default and
future site configurability. Deriving app links from the configured API host
keeps incident and monitor source URLs consistent without a second setting.

**Alternatives considered**:
- Hard-code `app.datadoghq.com`: rejected because it would break other sites.
- Accept arbitrary HTTPS hosts: rejected because it widens token destinations.
- Add a separate app-base setting: rejected as unnecessary configuration.

**Sources**:
- Datadog API site table for Incidents, Notebooks, and Monitors.

## Decision 3: Bearer token from the process environment only

**Decision**: Read `NOC_WEB_DATADOG_ACCESS_TOKEN` from the process environment
and send it only as `Authorization: Bearer <token>` to the configured Datadog
base URL. The configuration object records only credential presence; the client
keeps the token in a private, non-serialized, redacted field and never logs it.

**Rationale**: The clarification and specification require environment-only
credential supply and forbid disclosure through any API, frontend, log, report,
cache, exception, test artifact, or persisted application data. The official
Datadog examples use a bearer token header, so the transport matches Datadog's
supported authentication model.

**Alternatives considered**:
- `DD-API-KEY`/`DD-APPLICATION-KEY`: not the requested credential type.
- Token in URL/query: rejected because URLs are logged and cached.
- Token in a config file or application state: rejected by the credential rules.

**Sources**:
- Datadog incident API code examples: `Authorization: Bearer ${DD_BEARER_TOKEN}`.

## Decision 4: Read-only operation allowlist, not HTTP-method absolutism

**Decision**: Define a fixed allowlist of logical retrieval operations:
incident search, incident detail, notebook detail, and monitor detail. Every
request is constructed from a trusted path template and validated identifiers.
Any operation not on the allowlist is rejected before transport. A non-mutating
query may use POST if Datadog requires it, but no mutation operation is ever
present in the client.

**Rationale**: The clarification chose operation semantics plus a fixed
allowlist. This is stronger than allowing arbitrary GETs because it also blocks
new or unexpected paths. Current Datadog incident search is a GET, but the
allowlist keeps the boundary correct if a query endpoint changes transport.

**Alternatives considered**:
- Permit any GET to any Datadog path: rejected because it is a broader surface.
- Permit any non-2xx-free method: rejected because it is not structural.
- String-match method names at call sites: rejected as fragile.

## Decision 5: Incident search, pagination, and state handling

**Decision**: Call `GET /api/v2/incidents/search` with
`query=state:(active OR stable)`, `page[size]=100`, and no other filters. Accept
only records whose state is `ACTIVE` or `STABLE` (case-insensitive), preserve
the exact returned state text, and reject duplicate IDs. If the reported total
or the retrieved count exceeds 100, fail the whole refresh. Follow pagination
only while the total remains within the bound and the overall 90-second deadline
has time remaining.

**Rationale**: Feature 009 requires `ACTIVE` and `STABLE` as current incidents,
a 100-incident maximum, and no partial snapshot. Local state validation protects
against a provider query broadening unexpectedly. A total-count check prevents
silent truncation.

**Alternatives considered**:
- Two queries, one per state: rejected because it complicates coalescing and
  duplicate detection without adding value.
- List endpoint without a query: rejected because it could return resolved or
  excessive records.
- Truncate at 100: rejected by the specification; the refresh must fail.

**Sources**:
- Datadog "Search for incidents": `GET /api/v2/incidents/search`, `page[size]`
  maximum 100, `state` facet.

## Decision 6: Preserve the existing incident projection and cache contract

**Decision**: Map Datadog search records into the existing local projection:
`id`, `title`, exact `state`, optional `severity`, `createdAt`, `updatedAt`,
`summary`, and `url`. Map Datadog `created`/`modified` to timestamps,
`customer_impact_scope` to the bounded summary, and construct the app incident
URL. Keep the existing cache schema, 60-second interval, atomic writes,
cross-process lock/coalescing, freshness values, error values, and API response
shape unchanged. Keep `copilot-unavailable` as an accepted historical error
value but do not emit it from the new provider.

**Rationale**: The feature explicitly requires the existing active-incident
cache contract, stale-cache fallback, coalescing, and frontend compatibility.
The new provider should replace the retrieval source, not redesign the cache.

**Alternatives considered**:
- Return the raw Datadog search envelope: rejected; it would break the
  frontend and persist unnecessary evidence.
- Add notebook/monitor data to the incident snapshot: rejected by the
  clarification; evidence is on demand.
- Change freshness/error values: rejected because it would break consumers.

## Decision 7: On-demand evidence with no new persistent cache

**Decision**: Retrieve incident details, notebooks, and monitors on explicit
backend requests only. Do not write them to the incident cache or any new
persistent store. Normalize and return them through the internal evidence
service.

**Rationale**: The clarification selected on-demand retrieval. This preserves
the existing cache contract, keeps refreshes fast, avoids persisting raw Datadog
content, and ensures failures in evidence retrieval cannot corrupt incident
state.

**Alternatives considered**:
- Pre-fetch during every refresh: rejected as unbounded, slower, and cache
  contract-breaking.
- Separate persistent evidence cache: rejected because no durable requirement
  exists and it widens the data-boundary surface.

## Decision 8: Structured-only reference discovery

**Decision**: Discover notebook and monitor references only from explicit,
structured values:
- incident link attachments and their `documentUrl`;
- incident user-defined field values that exactly match a supported Datadog
  notebook or monitor URL/identifier, or contain exact Datadog-relative
  notebook/monitor paths;
- monitor `assets` whose `resource_type` is `notebook`, using `resource_key` or
  `url`;
- retrieved notebook Markdown and supported cell definitions containing exact
  Datadog-relative `/monitors/<numeric-id>` paths.

Do not list organization notebooks/monitors, scan unsupported cell content, or
infer references from names or tags. Deduplicate by kind and ID across sources.
Bound traversal to the Feature 015 evidence graph and do not recurse through
notebook-discovered monitor assets. If a reference kind exceeds 10 entries, fail
the evidence request as invalid rather than truncate.

**Rationale**: The clarification selected explicit references only. This keeps
outbound scope deterministic, avoids unrelated resource enumeration, and
prevents accidental evidence expansion. The 10-reference bound prevents
unbounded fan-out.

**Alternatives considered**:
- Scan all incident text for URLs: rejected by the clarification.
- List all notebooks/monitors: rejected as broad and expensive.
- Silently truncate references: rejected because it hides missing evidence.

## Decision 9: Notebook normalization and unsupported cells

**Decision**: Validate the notebook envelope (`data.type`, matching ID, cells
list, and bounds), preserve cell order, and normalize:
- `markdown` cells to bounded Markdown text;
- non-Markdown supported cells (`timeseries`, `toplist`, `heatmap`,
  `distribution`, `log_stream`) to their cell type, title/description, time
  range, and bounded query/metric definitions;
- unsupported cell types to an explicit `omittedCellTypes` metadata entry
  without raw content.

Reject a notebook whose structure is invalid, has no supported content, or
exceeds 200 cells. Empty Markdown remains a supported cell.

**Rationale**: The clarification requires supported cells to remain usable while
unsupported cells are explicitly omitted. Bounding cells and extracted query
definitions prevents oversized evidence. Retaining Markdown and query
definitions satisfies the investigation-evidence requirement.

**Alternatives considered**:
- Reject any notebook with an unknown cell type: rejected by the clarification
  and too brittle for Datadog notebook evolution.
- Include raw unsupported cell content: rejected as unvalidated evidence.
- Flatten only Markdown and discard query cells: rejected because metric/query
  definitions are required evidence.

**Sources**:
- Datadog "Get a notebook": `data.attributes.cells[].attributes.definition`,
  valid cell types `markdown`, `timeseries`, `toplist`, `heatmap`,
  `distribution`, `log_stream`.

## Decision 10: Monitor normalization

**Decision**: Validate monitor identity and required shape, then normalize
`id`, `name`, `type`, `query`, `options.thresholds`, `tags`, current state
(`overall_state` or `state`), `message`, `assets`, timestamps, and a constructed
source URL. Request `with_assets=true` so notebook assets are available. Require
a non-empty name and type; allow an empty query only when the provider supplies
one. Bound tags to 100 and message/threshold content by shared text and count
limits.

**Rationale**: The specification requires monitor identity, name, type, query,
thresholds, tags, current state, and message/reference data. Bounding each
collection avoids oversized evidence and keeps normalization deterministic.

**Alternatives considered**:
- Return the raw monitor object: rejected; too broad and unvalidated.
- Require thresholds for every monitor: rejected because some monitor types
  legitimately omit them.

**Sources**:
- Datadog "Get a monitor's details": monitor fields, `options.thresholds`,
  `tags`, `overall_state`, `message`, and `assets` with notebook resource type.

## Decision 11: Incident detail normalization

**Decision**: Validate the incident detail envelope, preserve the incident ID,
title, exact state, optional severity, timestamps, impact scope, impact flag,
and a bounded projection of user-defined fields. Extract only explicit
notebook/monitor references from link attachments and matching field values.
Do not persist the detail.

**Rationale**: Incident details must be useful evidence while remaining bounded
and traceable. Structured extraction follows the clarification and prevents
free-text scanning.

**Alternatives considered**:
- Store the whole incident payload: rejected; unnecessary and unsafe.
- Parse arbitrary field text for links: rejected by the clarification.

## Decision 12: Static readiness and diagnostics

**Decision**: Add `datadog_provider_readiness()` that validates configuration
and token presence only. Return `ready` when a token is present and the base URL
and timeout are valid; `notConfigured` when the token is absent; `notReady` when
configuration is invalid. Expose the non-secret object through:
- `/api/health` as `datadogProvider`;
- `/api/status/{shift_date}` as `datadogProvider`;
- `/api/readiness/{shift_date}` as an optional `external.datadog` capability.

Replace the old `external.datadogMcp` readiness probe so diagnostics no longer
invoke Copilot `mcp list`. Keep `external.copilot` for the separate AI provider
capability. Readiness makes zero Datadog requests and never asserts token
validity or reachability.

**Rationale**: The specification requires static, non-networked readiness across
readiness, status, and health. Removing the MCP probe prevents Datadog evidence
readiness from depending on Copilot. Additive fields preserve existing
consumers, and the readiness capability remains optional so it cannot block
unrelated workflows.

**Alternatives considered**:
- Probe Datadog on page load: rejected by the specification.
- Keep MCP readiness as the authoritative Datadog check: rejected because it
  reintroduces the dependency being removed.
- New diagnostics page/endpoint: rejected; existing surfaces are sufficient.

## Decision 13: Secret handling and managed-service propagation

**Decision**: Add `NOC_WEB_DATADOG_ACCESS_TOKEN`,
`NOC_WEB_DATADOG_BASE_URL`, and `NOC_WEB_DATADOG_TIMEOUT_SECONDS` to the managed
service environment allowlist. Add an optional operator-managed
`datadog-provider.env` loaded with `EnvironmentFile=-` and mode `0600`. Never
write the token to the unit file, runtime configuration, logs, or application
data. Redacted errors name only the setting.

**Rationale**: The existing systemd service sanitizes the environment, so
without an allowlist and environment file the token would never reach the
application. A separate file keeps the Datadog credential independent of the AI
provider credential.

**Alternatives considered**:
- Reuse `ai-provider.env`: rejected because unrelated provider lifecycle owners
  and rotation scopes would be mixed.
- Store the token in `runtime.json`: rejected by the credential rules.
- Copy the entire inherited environment: rejected; it widens secret propagation.

## Decision 14: Failure taxonomy and bounds

**Decision**: Map failures to the existing incident error values:
- missing/invalid configuration, 401/403/429/5xx, network failure, redirect, or
  unavailable transport -> `provider-unavailable`;
- deadline/timeout -> `timeout`;
- malformed JSON, wrong schema, duplicate IDs, unsupported states, over-limit
  data, invalid identifiers, or invalid URLs -> `invalid-response`;
- cache read/write/lock failure -> `cache-unavailable`.

Every response is bounded to 1,000,000 bytes; incident snapshots to 100; references to
10 per kind; notebooks to 200 cells; tags to 100. Any over-bound response fails
instead of truncating. Reference-level unavailability is recorded per
reference; incident-level failure is explicit and never success-shaped.

**Rationale**: Preserving the error domain keeps the existing API contract.
Failing closed on over-bound or malformed data preserves the last trusted
snapshot and prevents partial evidence from becoming authoritative.

**Alternatives considered**:
- New error codes: rejected because the frontend contract must remain stable.
- Best-effort schema repair: rejected by the specification.
- Truncation: rejected because it silently drops operational evidence.

## Decision 15: Test strategy

**Decision**: Use injected fake transports and monkeypatched environment for all
tests. Add coverage for:
- configuration validation and static readiness with zero Datadog requests;
- allowlist enforcement and rejection of mutation operations;
- bearer-header construction without token disclosure;
- incident search mapping, pagination, 100-incident bound, and duplicate IDs;
- existing cache/freshness/stale/coalescing contract;
- zero Copilot process and zero MCP invocation while refresh succeeds;
- malformed, oversized, redirect, auth, timeout, and cache-write failures;
- incident detail, notebook, monitor, relationship, unavailable-reference, and
  unsupported-cell normalization;
- no evidence cache writes;
- existing incident API and frontend contract compatibility;
- diagnostics updates and environment propagation.

Run the focused suites and then the full pytest suite. No test uses live network
or real credentials.

The existing `test_backend_retrieval_does_not_add_direct_datadog_api_or_sdk`
test is an obsolete architecture assertion for the Copilot/MCP implementation,
not an incident API or frontend contract assertion. Replace it with direct
provider, zero-Copilot, and zero-MCP checks while preserving every frontend
renderer and API contract test.

**Rationale**: The constitution requires successful and failure-path coverage
with isolated filesystem state and no real credentials or network services. The
regression list directly maps to the specification's acceptance criteria.

**Alternatives considered**:
- Live Datadog smoke tests in CI: rejected because they require credentials and
  make results environment-dependent.
- Only unit tests for the client: rejected because the cache/API/frontend
  contract must be protected.

## Open Questions

None. The specification clarification session resolved the retrieval mode,
read-only allowlist semantics, evidence exposure boundary, reference discovery,
and unsupported notebook-cell behavior. Remaining decisions are implementation
choices documented above.
