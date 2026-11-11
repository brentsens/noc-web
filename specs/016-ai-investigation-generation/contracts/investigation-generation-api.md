# Contract: Investigation Preview and Create API

**Feature**: `016-ai-investigation-generation`
**Scope**: FastAPI investigation preview/create endpoints and their frontend consumers

## Preview

`POST /api/shifts/{shift_date}/investigations/preview`

### Request

```json
{
  "incidentId": "aadf7955-1945-4ce6-b6ca-41e7fa734a78",
  "displayTitle": "[PROD] SITEF integration backlog: export service heap exhaustion / CPU saturation (tenant 6)",
  "name": null,
  "notebookUrl": "https://app.datadoghq.com/notebook/16295624/runbook"
}
```

**Rules**:
- `shift_date` must be a valid selected shift.
- `incidentId` must identify a current ACTIVE or STABLE Datadog incident.
- `displayTitle` preserves the full Datadog incident title for display and auditing.
- `name` is the optional local investigation identifier. When omitted entirely with a
  `displayTitle`, the server derives a deterministic safe slug from the title.
- A provided `name` (including an empty string) still uses the existing strict
  investigation-name validation and is never relaxed by the presence of `displayTitle`.
- `notebookUrl` uses existing investigation validation.
- The endpoint obtains evidence exclusively through Feature 015.
- The endpoint MUST NOT invoke the AI provider, create a record, or mutate Datadog/external
  systems.
- Provider readiness is checked statically; an unconfigured/not-ready provider fails closed before
  a preview is issued.

### Success Response

`200 OK`

```json
{
  "previewId": "opaque-single-use-identifier",
  "expiresAt": "2026-11-10T23:20:00Z",
  "shiftDate": "2026-11-10",
  "displayTitle": "[PROD] SITEF integration backlog: export service heap exhaustion / CPU saturation (tenant 6)",
  "normalizedName": "prod-sitef-integration-backlog-export-service-heap-exhaustion-cpu-satur-bedd2675",
  "notebookUrl": "https://app.datadoghq.com/notebook/16295624/runbook",
  "incident": {
    "id": "aadf7955-1945-4ce6-b6ca-41e7fa734a78",
    "title": "Checkout latency elevated",
    "state": "ACTIVE",
    "severity": "SEV-2"
  },
  "evidence": {
    "status": "complete",
    "incidentId": "incident:aadf7955-1945-4ce6-b6ca-41e7fa734a78",
    "notebookCount": 1,
    "monitorCount": 2,
    "unavailable": [],
    "references": {
      "incident:aadf7955-1945-4ce6-b6ca-41e7fa734a78": {
        "kind": "incident",
        "sourceUrl": "https://app.datadoghq.com/incidents/aadf7955-1945-4ce6-b6ca-41e7fa734a78",
        "source": "incident_field",
        "availability": "available"
      }
    }
  },
  "provider": {
    "configuredProvider": "deepseek-api",
    "label": "DeepSeek API",
    "model": "deepseek-flash",
    "readiness": "ready"
  },
  "generation": "Feature 015 read-only Datadog evidence -> configured AI provider",
  "datadogReadOnly": true,
  "requiresOperatorReview": true
}
```

**Rules**:
- `previewId` is server-issued, opaque, single-use, and expires after 10 minutes.
- The response exposes only a bounded evidence summary; raw evidence, credentials, Authorization
  headers, and provider payloads are never returned.
- Preview response is non-generative and may be shown without an AI call.

### Preview Errors

| Status | Code | Meaning |
|--------|------|---------|
| 409 | `investigation-conflict` | Normalized name already exists |
| 409 | `preview-stale` | Evidence changed during preview construction |
| 422 | `invalid_incident_id` | Incident ID is malformed |
| 422 | `incident-not-current` | Incident is not ACTIVE/STABLE |
| 422 | `invalid-name` | Provided local investigation name is invalid |
| 422 | `invalid_display_title` | Datadog incident display title is invalid |
| 422 | `invalid-notebook-url` | FINAL notebook URL is invalid |
| 422 | `evidence-invalid` | Feature 015 evidence is invalid or malformed |
| 422 | `evidence-too-large` | Evidence exceeds package bounds |
| 422 | `evidence-credential-detected` | Credential-like content detected |
| 503 | `provider-not-configured` | No AI provider selected |
| 503 | `provider-not-ready` | Selected provider configuration is incomplete |
| 503 | `evidence-unavailable` | Feature 015 cannot provide incident evidence |
| 504 | `evidence-timeout` | Feature 015 evidence retrieval timed out |

Errors MUST be sanitized and MUST NOT contain credentials, Authorization headers, raw provider
payloads, or unrelated environment values.

## Create

`POST /api/shifts/{shift_date}/investigations`

### Request

```json
{
  "previewId": "opaque-single-use-identifier",
  "name": "Checkout Latency",
  "notebookUrl": "https://app.datadoghq.com/notebook/16295624/runbook",
  "confirmed": true
}
```

**Rules**:
- `confirmed` MUST be exactly `true`; a missing or false value returns 422.
- `previewId` MUST reference an active, unconsumed, unexpired preview.
- The request name/notebook URL MUST match the previewed request.
- The endpoint consumes the preview atomically before generation to prevent replay.
- The endpoint re-fetches Feature 015 evidence and compares the package digest; changed or
  unavailable evidence invalidates the preview and fails closed.
- The configured provider identity/model MUST match the preview; a change requires a new preview.
- The AI provider is called at most once for a consumed preview. No automatic fallback occurs.
- On failure, no investigation record, staging directory, or partial provenance file remains.

### Success Response

`201 Created` — existing investigation projection with:

- `generationStatus: "completed"`;
- `validationStatus: "ready_for_review"` for valid output;
- `evidence.provenance: "ai-evidence"`;
- `evidence.status: "complete" | "partial"`;
- existing lifecycle/review fields, `reviewedFinding`, and Datadog attachment fields;
- no raw evidence, provider payload, credentials, or Authorization headers.

### Create Errors

| Status | Code | Meaning |
|--------|------|---------|
| 409 | `investigation-conflict` | Name collision or existing record |
| 409 | `preview-required` | Missing or unknown preview |
| 409 | `preview-expired` | Preview TTL elapsed |
| 409 | `preview-used` | Preview already consumed |
| 409 | `preview-mismatch` | Request differs from preview |
| 409 | `preview-stale` | Evidence or provider changed since preview |
| 422 | `invalid-name` / `invalid-notebook-url` | Request validation failed |
| 422 | `evidence-invalid` / `evidence-too-large` | Evidence validation failed |
| 422 | `evidence-reference-invalid` | AI cited unsupported/fabricated evidence |
| 422 | `ai-output-invalid` | Missing sections, malformed output, or contradiction |
| 422 | `ai-output-too-large` | AI output exceeds bounds |
| 503 | `provider-not-configured` / `provider-not-ready` | Provider unavailable by configuration |
| 503 | `provider-unavailable` | Provider/network/auth unavailable |
| 503 | `evidence-unavailable` | Feature 015 evidence unavailable |
| 503 | `storage-unavailable` | Local investigation storage is unavailable |
| 504 | `provider-timeout` | AI provider timed out |
| 504 | `evidence-timeout` | Evidence revalidation timed out |
| 500 | `generated-output-invalid` | The rendered record failed final validation |
| 500 | `storage-failed` | Local record could not be stored atomically |

## Frontend Contract

- `frontend/js/api.js`:
  - `previewInvestigation(shiftDate, { incidentId, name, notebookUrl })`
  - `createInvestigation(shiftDate, { previewId, name, notebookUrl, confirmed })`
- Active Incidents handoff contains `incidentId` and `title`; Investigations requires the incident
  identity for preview.
- Preview displays evidence status, counts, unavailable references, provider identity/model, and
  the read-only generation path.
- Changing the selected shift or any preview input invalidates the pending preview.
- The confirmation dialog explicitly states that Datadog remains read-only and that the configured
  AI provider will be used after confirmation.
- No credentials, Authorization headers, or raw evidence are displayed or stored in the browser.

## Non-Negotiable Invariants

- Preview: zero AI calls, zero records, zero external mutations.
- AI generation: only after explicit `confirmed: true`.
- Evidence: Feature 015 only; zero direct Datadog retrieval.
- Datadog: structurally read-only; zero mutation requests.
- Provider: explicit configured provider only; zero automatic fallback.
- Local persistence: existing collision, staging, atomic replace, lifecycle, and review rules.
