# Investigations API Contract

**Feature**: [spec.md](../spec.md)
**Data model**: [../data-model.md](../data-model.md)

These are additions to the existing shift-scoped Investigations API. Existing list/detail/review/reject contracts remain compatible. Errors use the existing FastAPI JSON `detail` field.

## Preview

`POST /api/shifts/{shift_date}/investigations/preview`

Preview validates values only. It MUST NOT invoke `noc-inv`, create or modify files, fetch the Notebook URL, or alter operational state.

Request:

```json
{
  "name": "Checkout latency",
  "notebookUrl": "https://app.datadoghq.com/notebook/123456/example-notebook"
}
```

Success response:

```json
{
  "shiftDate": "2026-10-30",
  "normalizedName": "checkout-latency",
  "notebookUrl": "https://app.datadoghq.com/notebook/123456/example-notebook",
  "target": "2026-10-30/checkout-latency",
  "generation": "noc-inv via GitHub Copilot CLI and Datadog MCP",
  "datadogReadOnly": true,
  "requiresOperatorReview": true
}
```

`target` is a logical identifier, not an absolute path. Input and shift validation failures use the repository's standard validation-error response. The route does not create a durable preview token or reservation.

## Confirmed creation

`POST /api/shifts/{shift_date}/investigations`

The UI must display the preview values and call this route only after the operator explicitly chooses **Create Investigation**. The backend revalidates the request and duplicate state. `confirmed` is required and must be `true`; no execution occurs otherwise.

Request:

```json
{
  "name": "Checkout latency",
  "notebookUrl": "https://app.datadoghq.com/notebook/123456/example-notebook",
  "confirmed": true
}
```

Created record response (HTTP `201`):

```json
{
  "shiftDate": "2026-10-30",
  "name": "checkout-latency",
  "title": "Checkout latency",
  "generationStatus": "completed",
  "validationStatus": "ready_for_review",
  "lifecycle": {
    "state": "ready_for_review",
    "reviewState": "unreviewed"
  },
  "evidence": {
    "provenance": "noc-inv",
    "availability": "available",
    "access": "read-only",
    "reference": "https://app.datadoghq.com/notebook/123456/example-notebook"
  },
  "notebookUrl": "https://app.datadoghq.com/notebook/123456/example-notebook",
  "reviewedFinding": null
}
```

A safely retained malformed record may also return `201`, with `validationStatus: "needs_review"` and `lifecycle.reviewState: "unreviewed"`. It must be visible to the operator and excluded from propagation. The projection uses the existing `lifecycle`, `evidence`, `advisory`, and `reviewedFinding` field structure. Raw command output and diagnostics are never returned.

## Failure states

Use the existing API error envelope and status conventions:

| Condition | HTTP status | Required behavior |
|---|---:|---|
| Invalid shift, name, URL, or confirmation | 422 | No process or record creation |
| Same normalized name already exists | 409 | Never overwrite |
| Required command/storage unavailable | 503 | Sanitized unavailable state |
| Configured execution timeout | 504 | Sanitized timeout state; report retained safe record separately if any |
| Non-zero execution, invalid provenance, unsafe/missing output, or storage failure | 500 | Sanitized failure; never claim creation unless a durable record exists |

Errors must use a controlled `detail` message/code and must not include raw command output, credentials, tokens, prompts, or absolute paths. If creation succeeds but the subsequent frontend list refresh fails, the create response remains successful and the UI presents the creation and refresh states separately.
