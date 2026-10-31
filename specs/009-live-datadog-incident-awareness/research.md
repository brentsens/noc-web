# Research: Live Datadog Incident Awareness

## Decision: Reuse the authenticated Copilot CLI and restrict the MCP tool set

**Rationale**: The repository already invokes the operator's Copilot CLI with
an argument array, isolated working directory, environment allowlist, and a
strictly filtered available-tools list. The local CLI help confirms that MCP
tools can be exposed using a server/tool-specific filter. The Datadog MCP
incident search is the only retrieval capability required; the provider
contract must not expose unrelated tools.

**Alternatives considered**: Direct Datadog REST or SDK integration and browser
retrieval were rejected because they bypass the approved architecture and
credential boundary. A broad MCP tool set was rejected because incident
awareness requires only read-only incident search.

## Decision: Treat Copilot output as untrusted and validate a narrow projection

**Rationale**: Provider success does not establish that the returned content is
safe or current. The service must accept only a strict JSON object with an
incident list, reject malformed records, exclude recognized resolved records,
and avoid returning or
logging raw stdout/stderr. A complete valid response, including an empty list,
is required before the cache can be replaced.

**Alternatives considered**: Best-effort filtering of invalid incident entries
was rejected because it can make a partial response look authoritative and can
incorrectly erase incidents. Automatic repair or normalization of malformed
provider output was rejected because it weakens fail-closed behavior.

## Decision: Use a shared short-lived file cache and nonblocking refresh

**Rationale**: Existing workstation services use the configured NOC root for
file-backed state. A single atomic snapshot allows both pages and all requests
to share the same source, keeps ordinary page loading independent of Copilot
latency, and preserves the last good data if retrieval or validation fails.

**Alternatives considered**: Independent page requests were rejected because
they can overlap and show conflicting data. Persisting raw MCP evidence or
prompts was rejected because only concise operational fields are needed.

## Decision: Keep investigation creation and handover operator-controlled

**Rationale**: The existing investigation workflow owns its validation,
Preview, confirmation, and review controls. Live incident status is a
situational-awareness source only; cache changes must not write investigations
or handover.

**Alternatives considered**: Automatically creating or closing local
investigations based on Datadog state was rejected because external resolution
does not constitute operator review.

## Repository Evidence

- `backend/services/copilot_cli.py` uses a fixed prompt, an isolated temporary
  working directory, an environment allowlist, `subprocess.run`, and a bounded
  timeout.
- `backend/services/investigation_generation.py` demonstrates the existing
  noc-inv flow and strict separate Preview and confirmed creation endpoints.
- `backend/services/investigations.py` resolves the configured NOC root and
  keeps operator review state in separate local records.
- `backend/services/jira_cache.py` demonstrates the repository's file-backed
  snapshot and freshness convention; the new cache will additionally use
  atomic replacement and preserve failed-refresh history.
- `backend/api/investigations.py` and `backend/api/dashboard.py` show the
  existing router and API registration patterns.
- `frontend/js/api.js`, `frontend/index.html`, and
  `frontend/investigations.html` show the current API client and static ES
  module conventions.
- Local Copilot CLI help confirms `--available-tools` controls model-visible
  tools, and MCP permission patterns can identify a tool as
  `server-name(tool-name)`. No unrestricted permission flag is required.
