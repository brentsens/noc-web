# Quickstart Validation: Provider-Independent AI Support

**Feature**: `014-ai-provider-architecture`

This guide validates the feature end to end without covering implementation bodies. Contracts and data rules are in [contracts/](./contracts/) and [data-model.md](./data-model.md).

## Prerequisites

- Repository root: `/home/bsmith/code/noc-web`
- Python virtual environment at `.venv`
- Existing NOC Web test setup and a temporary `NOC_ROOT` supplied by pytest fixtures
- A DeepSeek API key for live DeepSeek validation (use a sentinel/test key for offline tests)
- Optional: GitHub Copilot CLI installed and authenticated for Copilot validation

## 1. Run the focused offline test suite

```bash
.venv/bin/python -m pytest \
  tests/test_ai_provider.py \
  tests/test_deepseek_provider.py \
  tests/test_assistant.py \
  tests/test_assistant_api.py \
  tests/test_ai_reports.py \
  tests/test_dependency_readiness.py \
  tests/test_readiness_api.py \
  tests/test_frontend_modules.py \
  -q
```

Expected: all tests pass; no test requires a live network call or a real credential.

## 2. DeepSeek configuration and Assistant validation

Set a test/sentinel key in the environment. Do not commit it.

```bash
export NOC_WEB_AI_PROVIDER=deepseek-api
export NOC_WEB_DEEPSEEK_API_KEY='test-sentinel-deepseek-key'
export NOC_WEB_DEEPSEEK_MODEL=deepseek-flash
export NOC_WEB_DEEPSEEK_BASE_URL=https://api.deepseek.com
```

Start the application using the repository's normal runtime command (see `README.md`), then:

```bash
curl -s http://127.0.0.1:8000/api/health | jq '.aiProvider'
```

For the managed systemd user service, create the optional operator-managed environment file outside application data:

```bash
install -m 600 /dev/null ~/.config/noc-web/ai-provider.env
cat > ~/.config/noc-web/ai-provider.env <<'EOF'
NOC_WEB_AI_PROVIDER=deepseek-api
NOC_WEB_DEEPSEEK_API_KEY=test-sentinel-deepseek-key
NOC_WEB_DEEPSEEK_MODEL=deepseek-flash
EOF
```

Restart the user service and re-run the health/readiness checks. The generated unit must reference the file with `EnvironmentFile=-.../ai-provider.env`; the file must never be committed or placed in NOC Web application data.

Expected shape:

```json
{
  "configuredProvider": "deepseek-api",
  "readiness": "ready",
  "label": "DeepSeek API",
  "model": "deepseek-flash",
  "impact": "...",
  "correctiveAction": "..."
}
```

Check readiness:

```bash
curl -s "http://127.0.0.1:8000/api/readiness/$(date +%F)" \
  | jq '.externalCapabilities[] | select(.id == "external.aiProvider")'
```

Expected: `status: "ready"`, `required: false`, provider identity `deepseek-api`, no credential value. The shift health `AI Provider` check should be `pass` when ready and warning-only when not configured or not ready; it must not add an End Shift/handover blocker.

Run the Assistant page and all four AI Actions against a selected shift with evidence. Verify:
- The response provider is `deepseek-api`.
- The response schema, evidence labels, advisory categories, limitations, and routes are unchanged.
- A successful AI Action creates one `ai-*.md` report whose provider line reads `DeepSeek API`.
- No report contains the sentinel key, prompt, raw output, or reasoning content.

## 3. Copilot configuration validation

```bash
export NOC_WEB_AI_PROVIDER=github-copilot-cli
unset NOC_WEB_DEEPSEEK_API_KEY
```

Restart the application. Verify:
- `/api/health` reports `configuredProvider: "github-copilot-cli"`.
- If the CLI is installed, readiness is `ready` with a note that authentication is not verified by the static check.
- If the CLI is absent, readiness is `notReady` and Assistant requests fail closed.
- A DeepSeek-selected deployment remains healthy when Copilot is absent.

## 4. Not-configured validation

```bash
unset NOC_WEB_AI_PROVIDER
unset NOC_WEB_DEEPSEEK_API_KEY
```

Restart the application. Verify:
- `/api/health` reports `readiness: "notConfigured"`.
- `/api/readiness/...` reports `external.aiProvider.status: "notConfigured"`.
- Assistant and AI Action requests return the controlled 503 (`assistant-provider-not-configured`) from [contracts/assistant-api.md](./contracts/assistant-api.md).
- Non-Assistant workflows remain available.
- No report is created.

## 5. No-fallback validation

With `deepseek-api` selected and an invalid/missing key, while Copilot is installed and authenticated:

```bash
export NOC_WEB_AI_PROVIDER=deepseek-api
unset NOC_WEB_DEEPSEEK_API_KEY
```

Restart and submit an Assistant request. Verify:
- The request fails closed with the `assistant-provider-not-ready` 503.
- No request reaches Copilot.
- No report is created.
- Diagnostics identify DeepSeek as not ready.

## 6. Credential non-disclosure scan

Use a unique sentinel value for the DeepSeek key. After successful and failing requests:

```bash
grep -R "test-sentinel-deepseek-key" backend frontend tests specs || true
```

Also inspect:
- Assistant and AI Action HTTP responses.
- Application logs.
- Generated `reports/ai-*.md` files.
- `/api/health` and `/api/readiness` output.

Expected: zero matches outside the test's own intentionally isolated fixtures.

## 7. Regression validation

```bash
.venv/bin/python -m pytest -q
```

Expected: full suite passes. Confirm no changes to Datadog incident retrieval, noc-inv investigation generation, or noc-handover generation behavior.

## 8. Failure-path checks

Exercise and verify:
- Missing/invalid DeepSeek key → controlled `unavailable`/not-configured; no report.
- DeepSeek timeout → `providerStatus: "timeout"`; no report.
- DeepSeek 429/5xx → `providerStatus: "unavailable"`; no report.
- Blank, truncated, or malformed DeepSeek JSON → `providerStatus: "invalid"`; no report.
- Insufficient context → `providerStatus: "not-invoked"`; no provider call; no report.
- Copilot unauthenticated/absent → controlled failure; no fallback.

## Validation status

- 2026-11-10: Section 1 focused offline suite, section 6 sentinel scan, and section 7 full pytest suite were executed successfully (638 tests passed; zero sentinel matches in `backend/` and `frontend/`).
- Sections 2-5 and 8 require a live DeepSeek credential and/or an authenticated GitHub Copilot CLI, which are not available in this environment. Their request construction, response-contract, credential non-disclosure, fail-closed, no-fallback, diagnostics, and scope-isolation paths are covered by offline pytest with injected providers and transports.
