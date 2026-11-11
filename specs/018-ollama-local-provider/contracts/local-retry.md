# Contract: Explicit Retry with Local AI

**Feature**: `018-ollama-local-provider`
**Scope**: Failed-request snapshot, retry availability metadata, confirmation, and workflow retry
endpoints

## Retry Availability

When a primary-provider request fails and Ollama is configured, the existing failure response may
include additive metadata:

```json
{
  "localRetry": {
    "available": true,
    "retryToken": "opaque-single-use-token",
    "expiresAt": "2026-11-11T16:30:00Z",
    "provider": "ollama",
    "model": "qwen3:8b"
  }
}
```

**Rules**:
- `available` is true only when a valid bounded snapshot exists and the local provider is configured.
- No token is returned for a successful primary request.
- No token is returned when Ollama is unconfigured or no exact snapshot exists.
- No local request occurs until a separate retry endpoint is explicitly confirmed.
- The failure remains fail-closed; retry availability does not change the failure response's success
  semantics.

## Snapshot Rules

- Snapshot is process-memory only; never persisted to disk or logged.
- Exact evidence/envelope from the failed primary request; no silent re-fetch or substitution.
- 10-minute TTL.
- Maximum 32 active snapshots.
- Single-use; a consumed token cannot be reused.
- Missing, expired, used, or mismatched tokens fail closed.
- Snapshot contains no credentials, Authorization headers, environment values, prompts returned to
  clients, or unrelated operational data.
- The client receives only the opaque token and bounded availability metadata.

## Retry Endpoints

Workflow-specific endpoints preserve existing response/persistence/lifecycle contracts:

| Workflow | Endpoint |
|----------|----------|
| Assistant question | `POST /api/shifts/{shift_date}/assistant/local-retry` |
| AI Actions | `POST /api/shifts/{shift_date}/assistant/actions/{action_type}/local-retry` |
| Investigation generation | `POST /api/shifts/{shift_date}/investigations/local-retry` |
| Handover generation | `POST /api/shifts/{shift_date}/handover/local-retry` |

### Retry Request

```json
{
  "retryToken": "opaque-single-use-token",
  "confirmed": true
}
```

**Rules**:
- `confirmed` MUST be exactly true.
- The endpoint consumes the token atomically before local inference.
- The local provider MUST be explicitly `ollama` and use the configured model.
- No provider fallback is attempted.
- No automatic retry occurs if local inference fails.

### Success

Return the existing workflow success response with provider provenance identifying `ollama` and the
configured model. Existing Assistant/AI Actions response fields, investigation record/lifecycle, and
handover Markdown/provenance/delivery contracts remain authoritative.

### Retry Errors

| Status | Code | Meaning |
|--------|------|---------|
| 409 | `retry-snapshot-expired` | 10-minute retry window elapsed |
| 409 | `retry-snapshot-used` | Token already consumed |
| 409 | `retry-snapshot-unavailable` | Exact failed-request snapshot unavailable |
| 422 | `retry-confirmation-required` | `confirmed` was not true |
| 422 | output validator codes | Existing workflow validator rejected local output |
| 503 | `provider-not-configured` / `provider-not-ready` | Ollama configuration unavailable |
| 503 | `provider-unavailable` | Ollama endpoint unreachable/refused |
| 504 | `provider-timeout` | Ollama connection/read deadline elapsed |
| 502 | `provider-invalid-response` | Malformed/missing/non-string/oversized response |
| 503 | `ollama-model-missing` | Configured model unavailable |

Errors remain sanitized and never include secrets, evidence contents, prompts, or Ollama metadata.

## Exact Evidence Rules

- Assistant/AI Actions retry uses the exact provider envelope from the failed request.
- Investigation retry uses the exact validated preview evidence package and request identity.
- Handover retry uses the exact evidence package/advisory envelope from the failed generation.
- If exact evidence is unavailable or expired, fail closed; do not silently refresh evidence.
- Preview/confirmation/stale-preview rules remain authoritative.

## Validator Reuse

Retry output MUST pass the same validators as primary output:

- Assistant/AI Actions schema/evidence/stale/credential/size rules.
- Feature 016 citations/freshness/partial/lifecycle/provenance.
- Feature 017 bracketed citations/stale-partial qualification/count claims/deterministic sections/
  all open tickets/provenance.

## Provenance

- Retry success records provider `ollama` and the configured model.
- Never mislabel local output as DeepSeek, Copilot, reviewed operator content, or deterministic
  system-authored evidence.
- Existing investigation/handover provenance files remain compatible and additive.

## No Automatic Behavior

- No automatic fallback from DeepSeek to Ollama.
- No automatic retry after failure.
- No automatic probe from static health/readiness.
- Retry requires explicit operator confirmation.
