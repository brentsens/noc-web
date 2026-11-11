# Quickstart: Provider-Independent AI Investigation Generation

**Feature**: `016-ai-investigation-generation`
**Purpose**: Validate the new investigation preview/create workflow without requiring live Datadog
or AI credentials.

## Prerequisites

- Repository root: `/home/bsmith/code/noc-web`
- Python virtual environment: `.venv`
- Node.js 18+ for frontend module tests
- No live Datadog, Copilot, or DeepSeek credentials are required for the default test scenarios;
  tests inject fake evidence and provider implementations.
- Do not print or commit any credential value while running manual checks.

## Focused Validation

Run the feature-focused suites:

```bash
.venv/bin/python -m pytest \
  tests/test_investigation_ai_evidence.py \
  tests/test_investigation_preview_store.py \
  tests/test_investigation_generation.py \
  tests/test_investigation_output_validation.py \
  tests/test_investigation_lifecycle.py \
  tests/test_investigation_projection.py \
  tests/test_investigations.py \
  tests/test_investigation_creation.py \
  tests/test_investigation_attachments.py \
  tests/test_deepseek_provider.py \
  tests/test_ai_provider.py \
  tests/test_assistant.py \
  tests/test_assistant_api.py \
  tests/test_frontend_modules.py \
  tests/test_datadog_readonly.py \
  tests/test_datadog_secrets.py \
  -q
```

Expected: all focused suites pass. The full regression command is:

```bash
.venv/bin/python -m pytest -q
```

## Scenario 1: Preview is non-generative and read-only

**Setup**: Use a fake Feature 015 evidence loader returning a complete incident bundle with one
notebook and one monitor. Use a fake AI provider that records any invocation.

**Steps**:
1. Call the preview endpoint with the selected shift, incident ID, investigation name, and FINAL
   notebook URL.
2. Inspect the response and preview store/provider fake.

**Expected**:
- Preview returns `previewId`, expiry, incident identity, evidence counts/status, and provider
  identity/model.
- The fake AI provider is invoked 0 times.
- No investigation directory or `investigation.md` is created.
- No Datadog mutation request is issued.

## Scenario 2: Confirmed DeepSeek generation persists a reviewable record

**Setup**: Use a fake evidence loader returning a complete bundle and a fake configured DeepSeek
provider returning the required five-section JSON object with only supplied stable evidence IDs.
Use `confirmed: true` with the `previewId`.

**Steps**:
1. Preview the investigation using the full Datadog incident title as `displayTitle` and either
   a strict local `name` or no `name` so the server derives a safe slug.
2. Confirm creation with the returned `previewId` and the previewed local identifier.
3. Inspect the created record and projection.

**Expected**:
- `201 Created` with `validationStatus: "ready_for_review"`.
- `evidence.provenance: "ai-evidence"` and `evidence.status: "complete"`.
- Files exist: `investigation.md`, `generation-status.json`, `evidence-provenance.json`,
  `reviewed-context.json`.
- `reviewed-context.json` starts unreviewed with `lifecycleStatus: "ready_for_review"`.
- Existing lifecycle, review, Datadog attachment, and inspection behavior remains available.
- The fake provider receives the minimized package and no credentials/Authorization headers.

## Scenario 3: Partial evidence is disclosed and never presented as complete

**Setup**: Return a bundle where the incident is valid but one referenced monitor is unavailable.

**Expected**:
- Preview and create show evidence status `PARTIAL` and the unavailable monitor ID/error.
- `evidence-provenance.json` records the unavailable reference.
- `investigation.md` contains the system-authored `## Evidence Availability` section.
- AI output claiming complete/current evidence is rejected with `ai-output-invalid`.
- Valid AI output that stays bounded by the partial state is accepted and persisted.

## Scenario 4: Invalid citations, missing sections, and malformed output fail closed

**Setup**: Use fake provider responses with:
- an unsupported/fabricated evidence ID;
- an unavailable evidence ID cited as if it were available;
- a missing required section;
- a non-object or malformed JSON response;
- a non-canonical citation form (for example, a bare ID or URL).

**Expected**:
- Each create request fails with a controlled `422`/`502` error.
- A preview is consumed exactly once and must be re-created for another attempt.
- No investigation directory or partial files are published.

## Scenario 5: Provider failure, timeout, and incomplete configuration fail closed

**Setup**: Exercise fake providers that raise unavailability, timeout, and invalid-response
errors, and a runtime with no configured provider or missing DeepSeek key.

**Expected**:
- Unavailable/not-configured → `503`; timeout → `504`; invalid response → `502`.
- No automatic fallback to another provider is attempted.
- No investigation record is created.
- Error responses are sanitized and contain no credentials, Authorization headers, or raw
  provider payloads.

## Scenario 6: Credential non-disclosure

**Setup**: Include credential sentinels in the fake environment and a sentinel-bearing fake
provider response/log path.

**Expected**:
- Sentinels do not appear in preview/create responses, logs, generated Markdown,
  `generation-status.json`, `evidence-provenance.json`, exceptions, or frontend output.
- Evidence containing credential-like content is redacted or fails closed with
  `evidence-credential-detected`.
- The AI provider envelope contains only the minimized evidence package and instructions.

## Scenario 7: Zero Datadog mutation requests

**Setup**: Use the fake Datadog transport and fake evidence loader.

**Expected**:
- All Datadog interactions are Feature 015 evidence reads only.
- The transport records only GET requests for existing read-only endpoints.
- No POST/PATCH/PUT/DELETE request is issued.
- Feature 015 source files and retrieval behavior remain unchanged.

## Scenario 8: Legacy and existing workflow compatibility

**Setup**: Include legacy `noc-inv` and `copilot-mcp` investigation fixtures plus a promoted
Feature 016 record.

**Expected**:
- Legacy records remain readable, inspectable, reviewable, and routeable.
- New `ai-evidence` records pass lifecycle transitions, reviewed-finding publication, rejection,
  Datadog incident attachment, and cross-shift projection.
- Selected-shift synchronization and active-incident handoff (incident ID + title) work.
- noc-handover fixtures and tests are unchanged.

## Scenario 9: Frontend preview and confirmation behavior

Run the frontend module tests. Verify:

- Initial `?shift=YYYY-MM-DD` is honored.
- Changing Selected Shift updates the URL, workflow links, create shift, and invalidates the
  pending preview.
- The Datadog incident title is displayed separately from the generated local identifier.
- Preview displays the new architecture wording, not noc-inv/Copilot/MCP requirements.
- The confirmation dialog is the only action that authorizes AI generation.

## Optional Manual Live Check

Only run this in an approved environment. Never echo credential values.

1. Configure the existing Feature 014 provider and Feature 015 Datadog settings, including
   `NOC_WEB_AI_PROVIDER=deepseek-api`, the approved DeepSeek Flash model setting, and the required
   credentials in the service environment.
2. Start NOC Web using the documented workstation/runtime command.
3. Select a current Datadog incident and choose **Create Investigation**.
4. Enter the investigation name and FINAL notebook URL, then choose **Preview**.
5. Confirm that Preview shows evidence status/provenance and did not create a record.
6. Confirm creation and inspect the local record/projection.
7. Verify no credential appears in the UI, API response, logs, generated Markdown, or persisted
   JSON; verify no Datadog mutation occurred.

Expected: a locally persisted, unreviewed advisory investigation with system-authored provenance
and availability disclosure, using the configured AI provider and Feature 015 evidence only.
