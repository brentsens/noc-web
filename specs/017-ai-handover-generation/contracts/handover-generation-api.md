# Contract: Handover Generation API

**Feature**: `017-ai-handover-generation`
**Scope**: Handover read, deterministic generation preview, generation, regeneration, and unchanged
delivery endpoints

## Existing Handover Read

`GET /api/shifts/{shift_date}/handover`

Preserves the existing response shape: `shiftDate`, `exists`, `file`, `intro`, `sections`,
`closing`, `content`, `localWork`, `reviewedFindings`.

**Rules**:
- Read-only.
- Existing handover records remain readable without a provenance sidecar.
- Responses MUST NOT expose credentials, raw evidence packages, prompts, or provider payloads.

## Deterministic Generation Preview

`POST /api/shifts/{shift_date}/handover/generation-preview`

**Purpose**: Assemble mandatory factual handover content for operator review without AI or state
changes.

### Success Response

`200 OK`

```json
{
  "shiftDate": "2026-11-10",
  "preview": true,
  "evidenceDigest": "sha256:...",
  "intro": "Shift handover",
  "sections": [
    {"name": "Summary", "content": "..."},
    {"name": "Open Jira Tickets", "content": "- NOC-556 — ...\n- NOC-557 — ..."},
    {"name": "Investigation Updates", "content": "..."},
    {"name": "Next Shift Actions", "content": "..."}
  ],
  "closing": "Please tag me if any clarification is needed.\n\nRegards,\n\nBrentsen Smith\nNOC Engineer\n\n2025 W. Belt Line Rd. #114\nCarrollton, TX 75006\n\n[sesami.io](https://www.sesami.io/) | [LinkedIn](https://www.linkedin.com/company/sesami-cash-management-technologies-corporation)",
  "evidence": {
    "availability": "partial",
    "ticketCount": 2,
    "investigationCount": 1,
    "incidentCount": 0,
    "unavailable": []
  },
  "readiness": {
    "enabled": true,
    "blockers": [],
    "warnings": []
  },
  "generationMode": "deterministic-preview",
  "requiresConfirmation": true
}
```

**Rules**:
- MUST NOT invoke the AI provider.
- MUST NOT create, replace, archive, or deliver a handover.
- MUST include every open ticket in the deterministic Open Tickets section.
- MUST identify stale, partial, missing, or unavailable evidence.
- MUST return `readiness.enabled: false` with blockers/warnings when End Shift preflight blocks generation; readiness gate failures apply to generation, not the read-only preview.
- MUST use only validated NOC Web evidence and already-available read-only Datadog context.
- MUST return bounded responses with no credentials or raw provider payloads.

### Preview Errors

| Status | Code | Meaning |
|--------|------|---------|
| 422 | `tickets-unavailable` | No validated source can establish the open-ticket set |
| 422 | `tickets-over-bound` | Open-ticket set exceeds the validated bound |
| 422 | `evidence-invalid` | Evidence is malformed or unsupported |
| 422 | `evidence-too-large` | Evidence exceeds package bounds |
| 422 | `evidence-credential-detected` | Credential-like content detected |
| 503 | `evidence-unavailable` | A required validated source is unavailable |
| 504 | `evidence-timeout` | A required source timed out |

## Generate Handover

`POST /api/shifts/{shift_date}/handover`

### Request

```json
{
  "confirmed": true,
  "previewDigest": "sha256:..."
}
```

**Rules**:
- `confirmed` MUST be exactly `true`.
- `previewDigest` is optional. When supplied, it MUST match the current evidence digest; otherwise
  generation fails with `409 preview-stale`.
- Every confirmed generation invokes the configured Feature 014 provider for the dedicated advisory
  section. No deterministic-only path exists.
- Provider failure fails closed; no new handover is persisted and an existing handover remains
  intact.
- An existing handover without regeneration fails with the existing conflict behavior.
- Mandatory deterministic sections are assembled before AI.
- The AI provider cannot author or modify mandatory sections.
- The advisory envelope includes `citationContract.staleEvidenceIds` and
  `citationContract.partialEvidenceIds`. Every item citing stale evidence must include "stale";
  every item citing partial evidence must include "partial" or an explicit incompleteness
  qualifier. Describing those references as current, complete, verified-current, comprehensive, or
  fully available fails closed.
- AI advisory text is validated internally and is not emitted in the final handover. Validated
  citation IDs are retained only in `handover-provenance.json`.
- AI count claims are rejected; deterministic ticket counts are authoritative.
- Safe diagnostics for stale qualification failures use `code=ai-output-invalid`,
  `reason=stale-evidence-unqualified`, and only the cited stale evidence IDs; no generated text or
  evidence contents are logged.
- The persisted Markdown uses the established NOC operational/email presentation: `Hi Team` intro,
  deterministic mandatory sections, and signature as the absolute end. It contains no AI-specific
  sections and no internal `[evidence:...]` citation markers.
- A versioned `handover-provenance.json` sidecar is written with evidence/availability/provider
  provenance and no secrets.
- No Datadog mutation request is issued.

### Success Response

`200 OK` using the existing handover response shape, with additive metadata if needed:
`generationMode`, `advisoryStatus`, `evidenceDigest`, and bounded evidence availability.

### Generate Errors

| Status | Code | Meaning |
|--------|------|---------|
| 409 | `handover-exists` | A handover already exists; use regeneration |
| 409 | `handover-readiness-blocked` | End Shift preflight blocks generation |
| 409 | `preview-stale` | Evidence changed since preview |
| 422 | `tickets-unavailable` | No validated source can establish the open-ticket set |
| 422 | `tickets-over-bound` | Open-ticket set exceeds the validated bound |
| 422 | `evidence-invalid` / `evidence-too-large` | Evidence validation failed |
| 422 | `evidence-reference-invalid` | AI cited unsupported/invalid evidence |
| 422 | `ai-output-invalid` / `ai-output-too-large` | Advisory output failed validation |
| 503 | `provider-not-configured` / `provider-not-ready` | Provider configuration unavailable |
| 503 | `provider-unavailable` | Provider/network/auth unavailable |
| 504 | `provider-timeout` | Advisory generation timed out |
| 502 | `provider-invalid-response` | Provider returned a nonconforming object |
| 500 | `storage-failed` | Handover could not be stored atomically |
| 500 | `generated-output-invalid` | Rendered handover failed final validation |

## Regenerate Handover

`POST /api/shifts/{shift_date}/handover/regenerate`

Same request rules as generation, plus:

- An existing handover is required.
- Explicit confirmation is required.
- The previous Markdown and sidecar are archived before generation.
- If generation fails, both archived files are restored.
- The existing archive behavior remains compatible; the sidecar archive is additive.

### Regenerate Errors

Use the generation error set plus:

| Status | Code | Meaning |
|--------|------|---------|
| 404 | `handover-not-found` | No existing handover to regenerate |
| 500 | `archive-failed` | Previous handover could not be archived/verified |
| 500 | `restore-failed` | Failed generation could not restore the archive |

## Delivery Endpoints (Unchanged)

`POST /api/shifts/{shift_date}/handover/preview`
`POST /api/shifts/{shift_date}/handover/send`

Existing delivery behavior remains unchanged:

- operates on the persisted Markdown file;
- validates recipients;
- requires explicit confirmation for send;
- uses the existing Microsoft 365 transport;
- never invokes the AI provider;
- does not deliver the provenance sidecar.

## Frontend Contract

- `frontend/js/api.js` adds a deterministic generation-preview client function distinct from the
  existing delivery preview.
- End Shift preview displays deterministic mandatory sections and evidence availability.
- Generation/regeneration confirmation describes Feature 015/validated evidence and the configured
  AI provider, not noc-handover or Copilot.
- Preview is cleared/invalidated when the selected shift or preview inputs change.
- Delivery preview/send UI and recipient handling remain unchanged.
- No credentials, raw evidence, prompts, or provider payloads are displayed or persisted in the
  browser.

## Non-Negotiable Invariants

- Preview: zero AI calls, zero file/archive/delivery changes.
- Every confirmed generation invokes the configured provider; failure fails closed.
- AI is advisory only and cannot modify mandatory sections or external systems.
- All open tickets are present in the mandatory section.
- No provider fallback.
- No credentials in prompts, logs, Markdown, API responses, frontend output, exceptions, sidecars,
  archives, or persisted data.
- Zero Datadog mutation requests.
- Microsoft 365 delivery remains separate and unchanged.
