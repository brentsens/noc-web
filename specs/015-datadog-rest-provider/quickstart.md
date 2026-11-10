# Quickstart: Direct Read-Only Datadog Evidence Provider

**Feature**: `015-datadog-rest-provider`

This guide validates the feature offline. No test requires Datadog access,
GitHub Copilot CLI, Datadog MCP, or a real credential.

## Prerequisites

- Repository checked out at `/home/bsmith/code/noc-web`
- Python environment with `requirements.txt` and `requirements-test.txt`
- Run commands from the repository root

```bash
python -m pip install -r requirements.txt -r requirements-test.txt
```

## 1. Static configuration and readiness (no network)

Set a sentinel token and inspect readiness directly:

```bash
export NOC_WEB_DATADOG_ACCESS_TOKEN='test-sentinel-datadog-token'
export NOC_WEB_DATADOG_BASE_URL='https://api.datadoghq.com'
export NOC_WEB_DATADOG_TIMEOUT_SECONDS='90'

python - <<'PY'
from backend.services.datadog_provider import datadog_provider_readiness
print(datadog_provider_readiness())
PY
```

Expected:
- `readiness` is `ready`.
- `credentialPresent` is `true`.
- No Datadog request or Copilot process is made.
- The sentinel token is not in the output.

Repeat with the token unset and with an invalid base URL to confirm
`notConfigured` and `notReady`.

## 2. Incident refresh without Copilot or MCP

Run the focused incident tests:

```bash
python -m pytest tests/test_datadog_incidents.py -q
```

Expected:
- Cache success, stale fallback, unavailable-first-refresh, empty-success,
  state transitions, concurrency, and malformed-response tests pass.
- Fake HTTP transports record only allowlisted retrieval operations.
- Subprocess and MCP invocation guards confirm zero Copilot/MCP calls.
- A failed refresh preserves the prior incidents and `lastSuccessfulAt`.

## 3. Provider allowlist, secrets, bounds, and timeouts

```bash
python -m pytest tests/test_datadog_provider.py -q
```

Expected:
- Base URL, token presence, and timeout validation behave as specified.
- Mutation operations are rejected before transport.
- Redirect, auth failure, malformed JSON, oversized response, and timeout
  produce controlled failures.
- A sentinel token appears in no exception, log record, representation, or
  persisted file.

## 4. Incident, notebook, and monitor evidence

```bash
python -m pytest tests/test_datadog_evidence.py -q
```

Expected:
- Incident detail preserves identity, exact state, source URL, fields, and
  references.
- Exact Datadog-relative `/notebook/<id>` and `/monitors/<id>` paths in bounded
  incident narrative fields are discovered as references.
- Notebook Markdown cells, order, time ranges, query definitions, and metadata
  are normalized.
- Unsupported notebook cell types are omitted and counted without exposing raw
  content.
- Monitor references in notebook Markdown and supported cell definitions are
  discovered with `source: notebook`, retrieved, and deduplicated across
  incident and notebook sources.
- Monitor identity, name, type, query, thresholds, tags, state, message, and
  assets are normalized.
- Relationships survive; missing references are `unavailable` and the bundle is
  `partial`; no evidence cache file is written.

## 5. Existing incident API and frontend contract

```bash
python -m pytest \
  tests/test_datadog_incidents_api.py \
  tests/test_datadog_incidents_frontend.py \
  tests/test_status.py \
  tests/test_readiness_api.py \
  tests/test_dependency_readiness.py \
  -q
```

Expected:
- `/api/datadog/incidents` and `/api/datadog/incidents/refresh` keep the same
  fields, freshness values, and error values.
- The frontend renderer remains unchanged and consumes the same payload.
- Health, status, and readiness expose static Datadog readiness without network
  calls.
- `external.datadog` replaces the old MCP readiness probe.

## 6. Full regression suite

```bash
python -m pytest -q
```

Expected: all tests pass. No test accesses the network, real NOC data, or a real
credential.

## 7. Optional live read-only smoke test

Only if an operator supplies a scoped Datadog token in the process environment:

1. Start NOC Web with the token configured.
2. Open Dashboard or Investigations.
3. Confirm current incidents render or an empty current-incident state renders.
4. Confirm a failed retrieval shows stale/unavailable rather than zero.
5. Confirm no Datadog create/update/acknowledge/mute/resolve/delete request is
   made.

Do not paste the token into logs, reports, issue trackers, or test artifacts.
