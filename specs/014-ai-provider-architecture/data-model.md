# Data Model: Provider-Independent AI Support

**Feature**: `014-ai-provider-architecture`  
**Date**: 2026-11-10

## Provider Selection

Represents the explicit configuration resolved from the process environment.

| Field | Type | Required | Rules |
|-------|------|----------|-------|
| `identifier` | string | yes | One of `deepseek-api`, `github-copilot-cli` |
| `model` | string or null | DeepSeek only | Defaults to `deepseek-flash`; non-empty, bounded, no control characters |
| `base_url` | string or null | DeepSeek only | Defaults to `https://api.deepseek.com`; HTTPS only; non-empty host; no userinfo, query, fragment, or parent traversal |
| `timeout_seconds` | integer | yes | 1–60; defaults to 55 |
| `credential_present` | boolean | yes | True when the DeepSeek API key is non-empty; for Copilot, readiness uses executable presence instead |

**Validation rules**:
- An unset or empty `NOC_WEB_AI_PROVIDER` produces no selection (`notConfigured`), not a default selection.
- An unknown provider value produces a redacted configuration error and a `notReady` state.
- Missing DeepSeek credentials produce a `notReady` state; no provider callable is built.
- Invalid DeepSeek URL/model/timeout values produce a `notReady` state; the error names only the setting.
- Provider configuration is read at process start; changing it requires a restart.

## Provider Readiness

A non-secret diagnostic state exposed to operators.

| Field | Type | Rules |
|-------|------|-------|
| `configuredProvider` | string or null | Canonical identifier, or null when not configured |
| `readiness` | enum | `ready`, `notReady`, `notConfigured` |
| `label` | string or null | Safe display label: `DeepSeek API`, `GitHub Copilot CLI`, or null |
| `model` | string or null | DeepSeek model identifier; null for Copilot or not configured |
| `impact` | string | Operator-facing, fixed, non-secret description |
| `correctiveAction` | string | Safe guidance; names settings but never values |

**State transitions**:

```text
notConfigured ──select valid provider + required material present──> ready
notConfigured ──select provider with missing/invalid material─────> notReady
ready ──configuration removed or invalidated (restart)────────────> notConfigured / notReady
notReady ──correct configuration + restart────────────────────────> ready
```

Readiness is static:
- No inference/model request is made.
- DeepSeek readiness asserts configuration validity and key presence only, not credential acceptance or reachability.
- Copilot readiness asserts executable presence only, not authentication or reachability.

## Provider Runtime

The effective runtime state held by the application.

| Field | Type | Rules |
|-------|------|-------|
| `identifier` | string or null | Canonical active identifier; null when not configured or invalid |
| `provider` | callable or null | The selected provider callable; null when not configured/invalid |
| `readiness` | Provider Readiness | Captured at resolution time |

The credential is captured inside the provider closure. It is not a field, is not serialized, and is not exposed through application state.

## Provider Request Envelope

Existing structure, unchanged:

| Field | Type | Rules |
|-------|------|-------|
| `shiftDate` | string | `YYYY-MM-DD` |
| `question` | string | Existing validated operator question or predefined action question |
| `evidence` | array | Existing minimized selected-shift evidence; available/stale items only for provider use |
| `policy` | string | Fixed read-only advisory policy |

The envelope content and minimization rules are identical for both providers.

## Assistant Response

Existing contract, unchanged except the provider value domain.

| Field | Type | Rules |
|-------|------|-------|
| `shiftDate` | string | Matches the request |
| `status` | enum | `complete`, `limited`, `unavailable` |
| `provider` | enum | `deepseek-api` or `github-copilot-cli`; identifies the active provider |
| `providerInvoked` | boolean | Existing state relationship |
| `providerStatus` | enum | `success`, `unavailable`, `timeout`, `invalid`, `not-invoked` |
| `facts` | array | Existing validation |
| `reviewedFindings` | array | Existing validation; source-derived only |
| `aiObservations` | array | Existing validation; advisory |
| `recommendations` | array | Existing validation; advisory with allowed routes |
| `evidence` | array | Existing validation; no `summary` exposed |
| `limitations` | array of strings | Existing validation |

**Cross-field rules**:
- `success` requires `providerInvoked = true`, `status = complete`.
- `unavailable` requires `status = unavailable`; `timeout`/`invalid` require `providerInvoked = true` and `status = unavailable`.
- `not-invoked` requires `providerInvoked = false` and `status = limited`.
- The API validates the response against the expected active provider; a mismatch is rejected.
- No provider-supplied content may add facts or operator-reviewed findings.

## Assistant Action Report

Existing report contract with one attribution change.

| Field | Type | Rules |
|-------|------|-------|
| Selected shift | string | Existing |
| AI Action | string | Existing |
| Generated | timestamp | Existing |
| Provider | string | Display label derived from the validated canonical provider identifier |
| Status | string | Existing `Advisory / non-authoritative` |
| Facts, findings, observations, recommendations, evidence, limitations | sections | Existing validation and rendering |
| Filename | string | Existing collision-safe `ai-*.md` pattern |

**Persistence rules**:
- Only a validated `complete`/`success` Assistant response may produce a report.
- The report contains no prompt, raw provider output, reasoning content, credential, token, or raw evidence.
- No provider failure or not-configured attempt produces a report.

## Provider Failure

| Failure | Contract status | Provider invoked | Report |
|---------|-----------------|------------------|--------|
| No provider configured | HTTP 503 (`assistant-provider-not-configured`) | false | none |
| Selected provider configuration invalid/missing material | HTTP 503 (`assistant-provider-not-ready`) | false | none |
| DeepSeek 401/402/403 | `unavailable` | true | none |
| DeepSeek 429/5xx/network failure | `unavailable` | true | none |
| DeepSeek timeout | `timeout` | true | none |
| DeepSeek blank/truncated/malformed/non-dict JSON | `invalid` | true | none |
| DeepSeek response fails Assistant validation | `invalid` | true | none |
| Copilot executable missing | `unavailable` | false | none |
| Copilot unauthenticated/non-zero exit | `unavailable` | true | none |
| Copilot timeout | `timeout` | true | none |
| Copilot malformed output | `invalid` | true | none |
| Context insufficient | `limited` / `not-invoked` | false | none |

No failure path retries or switches providers automatically.

## Credential

A runtime-only secret.

| Property | Rule |
|----------|------|
| Source | Process environment only |
| Persistence | None |
| API exposure | None |
| Frontend exposure | None |
| Logs | None |
| Reports | None |
| Transport | DeepSeek `Authorization: Bearer <key>` header only; Copilot existing authenticated session |
| Diagnostics | Never included; only presence/readiness is reported |
| Serialization | Never part of a dataclass or diagnostic object |
