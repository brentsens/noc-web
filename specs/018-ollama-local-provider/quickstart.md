# Quickstart: Ollama Local AI Provider

**Feature**: `018-ollama-local-provider`
**Purpose**: Validate local-provider configuration, explicit probing/retry, response-only parsing, and
workflow validator compatibility without requiring a live Ollama host.

## Prerequisites

- Repository root: `/home/bsmith/code/noc-web`
- Python virtual environment: `.venv`
- Node.js 18+ for frontend tests
- No live Ollama, DeepSeek, Datadog, or Microsoft 365 credentials are required for default tests;
  fake HTTP transports and provider fixtures are used.

## Focused Validation

```bash
.venv/bin/python -m pytest \
  tests/test_ollama_provider.py \
  tests/test_local_retry.py \
  tests/test_ai_provider.py \
  tests/test_assistant.py \
  tests/test_assistant_api.py \
  tests/test_investigation_generation.py \
  tests/test_handover.py \
  tests/test_handover_ai.py \
  tests/test_ollama_provider_security.py \
  tests/test_readiness.py \
  tests/test_dependency_readiness.py \
  tests/test_readiness_api.py \
  tests/test_status.py \
  tests/test_frontend_modules.py \
  tests/test_datadog_readonly.py \
  tests/test_datadog_secrets.py \
  -q
```

Full regression:

```bash
.venv/bin/python -m pytest -q
```

## Scenario 1: Configure Ollama without changing existing installations

**Setup**: Set `NOC_WEB_OLLAMA_BASE_URL` and optionally `NOC_WEB_OLLAMA_MODEL`; leave
`NOC_WEB_AI_PROVIDER` unset or set to DeepSeek for an existing installation.

**Expected**:
- Existing installations remain on DeepSeek.
- The local provider is shown as configured/optional.
- `qwen3:8b` is the documented recommended default model; a configured model overrides it.
- Static health/readiness makes no Ollama request and performs no inference.

## Scenario 2: Explicit probe checks endpoint and model presence

**Setup**: Use a fake Ollama model-list response containing the configured model, then an unreachable
host, a refused connection, a timeout, and a model-missing response.

**Expected**:
- Probe reports available only for reachable endpoint plus configured model.
- No inference or model loading occurs.
- Unreachable/refused/timeout/model-missing are sanitized.
- Core readiness remains usable when DeepSeek is healthy.

## Scenario 3: Explicit provider selection/default

**Setup**: Configure both DeepSeek and Ollama; select Ollama explicitly or configure it as the
default.

**Expected**:
- Ollama is used only on explicit selection/configuration.
- DeepSeek remains the default for existing installations.
- No automatic migration occurs.
- Provider provenance identifies `ollama` and the configured model.

## Scenario 4: Primary failure does not automatically fall back

**Setup**: Make the primary provider fail; configure Ollama but do not confirm local retry.

**Expected**:
- Primary request fails closed.
- No Ollama generation request occurs.
- Failure includes local retry availability metadata only when a valid snapshot exists.
- No evidence is silently refreshed or changed.

## Scenario 5: Explicit Retry with Local AI

**Setup**: Use a primary failure with a valid 10-minute retry snapshot; confirm local retry.

**Expected**:
- Retry requires explicit confirmation.
- Same exact evidence snapshot is used.
- Ollama output passes the existing workflow validator.
- Provenance identifies `ollama` and model.
- Token is single-use.
- Expired/used/missing tokens fail closed.
- Failed local retry does not replace prior valid records.

## Scenario 6: Response-only parsing and metadata exclusion

**Setup**: Fake Ollama responses containing:
- valid `response` plus `thinking`, context, durations, model metadata;
- thinking-only without `response`;
- missing/non-string/empty `response`;
- malformed JSON, unsupported content, oversized response/output.

**Expected**:
- Only `response` is consumed.
- Thinking/context/duration/model metadata never enter outputs, prompts, records, or validators.
- All invalid cases fail closed.

## Scenario 7: Endpoint and secret boundaries

**Setup**: Test endpoint credentials, query, fragment, subpath, redirects, unexpected hosts, and
missing endpoint/model.

**Expected**:
- Invalid endpoints are rejected.
- Redirects are not followed.
- No Authorization headers, DeepSeek keys, Datadog tokens, M365 credentials, environment values, or
  process secrets are sent to Ollama.
- no Ollama authentication secret is invented or persisted.

## Scenario 8: Workflow validator compatibility

Run Assistant, AI Actions, investigation, and handover fixtures through both DeepSeek and Ollama.

**Expected**:
- Assistant/AI Actions schema/evidence/stale/credential/size validation is identical.
- Feature 016 exact citations, partial/stale, lifecycle, provenance, and review boundaries are
  identical.
- Feature 017 bracketed citations, stale/partial qualification, count claims, deterministic
  mandatory sections, all open tickets, final handover format, and provenance are identical.
- Local inference receives no additional authority.

## Scenario 9: Readiness/UI distinction

**Setup**: Render health/status/UI with Ollama unconfigured, configured but sleeping, probed
unavailable, and probed available.

**Expected**:
- Primary DeepSeek and optional local Ollama states are distinct.
- Endpoint/model/probe/retry availability are visible.
- No static page triggers inference or implicit probing.
- DeepSeek remains the default primary.

## Scenario 10: No external mutations and delivery compatibility

**Expected**:
- Ollama inference does not modify Datadog, Jira, tickets, investigations, shift notes, handover
  state, Microsoft 365 objects, or recipients.
- Microsoft 365 delivery behavior remains unchanged.
- Existing preview/confirmation, all-ticket inclusion, investigation lifecycle, and reviewed
  boundaries remain intact.

## Optional Manual Live Check

Only run in an approved LAN environment. Never print credentials.

1. Set `NOC_WEB_OLLAMA_BASE_URL` to the Ollama host base URL and model to `qwen3:8b`.
2. Leave the primary provider configured as DeepSeek to verify default behavior.
3. Use the explicit local probe and confirm it makes no inference.
4. Explicitly select Ollama or confirm Retry with Local AI after a primary failure.
5. Inspect outputs/provenance for `ollama` and model identity.
6. Confirm no secrets, thinking/context metadata, or external mutations appear.
