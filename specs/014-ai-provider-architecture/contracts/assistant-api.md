# Contract: Assistant and AI Action API

**Feature**: `014-ai-provider-architecture`

The existing Assistant response schema and semantics are preserved. The only extension is the canonical provider value domain.

## Endpoints

- `POST /api/shifts/{shift_date}/assistant/questions`
- `POST /api/shifts/{shift_date}/assistant/actions/{action_type}`

Request bodies and validation remain unchanged, including `providerDisclosureAcknowledged: true`.

## Assistant response

```json
{
  "shiftDate": "YYYY-MM-DD",
  "status": "complete | limited | unavailable",
  "provider": "deepseek-api | github-copilot-cli",
  "providerInvoked": true,
  "providerStatus": "success | unavailable | timeout | invalid | not-invoked",
  "facts": [],
  "reviewedFindings": [],
  "aiObservations": [],
  "recommendations": [],
  "evidence": [],
  "limitations": []
}
```

Unchanged rules:
- Exactly these top-level keys.
- Existing status/providerStatus relationships.
- Existing evidence, fact, reviewed-finding, observation, recommendation, route, and limitation validation.
- No prompt, raw provider output, reasoning content, credential, or raw evidence.
- Operator-reviewed findings remain source-derived only.

Provider rules:
- `provider` MUST be one of `deepseek-api` or `github-copilot-cli`.
- `provider` MUST identify the active provider that produced the response, including not-invoked and failure responses.
- The API MUST validate the response against the expected active provider.

## Not-configured and not-ready responses

When no provider is configured, the API returns a controlled 503:

```json
{
  "detail": {
    "code": "assistant-provider-not-configured",
    "message": "The assistant provider is not configured."
  }
}
```

When a provider is selected but its configuration is invalid or required material is missing, the API returns a controlled 503:

```json
{
  "detail": {
    "code": "assistant-provider-not-ready",
    "message": "The assistant provider is not ready."
  }
}
```

In both cases no Assistant response contract object is fabricated and no AI Action report is saved. The two codes preserve the distinction between `notConfigured` and `notReady`.

## Provider failure response

A configured provider that fails returns HTTP 200 with the existing contract:

| Failure | `status` | `providerStatus` | `providerInvoked` |
|---------|----------|------------------|-------------------|
| Unavailable/auth/network/rate limit | `unavailable` | `unavailable` | true or false as applicable |
| Timeout | `unavailable` | `timeout` | true |
| Invalid/truncated/malformed output | `unavailable` | `invalid` | true |
| Context insufficient | `limited` | `not-invoked` | false |

A failed or invalid AI Action MUST NOT create a report. A successful AI Action report response remains `{ assistant, report, reportSaveWarning }` with existing validation.

## No fallback

The API MUST NOT send a request to a non-selected provider under any failure condition. Another configured provider's availability MUST NOT affect the selected provider's result.
