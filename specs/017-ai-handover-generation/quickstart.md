# Quickstart: Provider-Independent AI Handover Generation

**Feature**: `017-ai-handover-generation`
**Purpose**: Validate deterministic handover assembly, advisory AI generation, fail-closed behavior,
and existing delivery compatibility without live NOC data or credentials.

## Prerequisites

- Repository root: `/home/bsmith/code/noc-web`
- Python virtual environment: `.venv`
- Node.js 18+ for frontend module tests
- No live Datadog, Jira, Microsoft 365, Copilot, or DeepSeek credentials are required for the default
  scenarios; tests inject validated fixtures and fake providers.
- Do not print or commit credential values during manual checks.

## Focused Validation

```bash
.venv/bin/python -m pytest \
  tests/test_handover_evidence.py \
  tests/test_handover_ai.py \
  tests/test_handover_preview.py \
  tests/test_handover.py \
  tests/test_handover_delivery.py \
  tests/test_ai_provider.py \
  tests/test_deepseek_provider.py \
  tests/test_end_shift.py \
  tests/test_readiness.py \
  tests/test_readiness_api.py \
  tests/test_dependency_readiness.py \
  tests/test_status.py \
  tests/test_tickets.py \
  tests/test_shift_notes.py \
  tests/test_investigations.py \
  tests/test_datadog_readonly.py \
  tests/test_datadog_secrets.py \
  tests/test_frontend_modules.py \
  -q
```

Full regression:

```bash
.venv/bin/python -m pytest -q
```

## Scenario 1: Every validated open ticket is included

**Setup**: Provide local open tickets, remote cached open tickets, a local-only ticket, a
remote-only ticket, a stale cache entry, and a duplicate ticket across sources.

**Steps**:
1. Build the handover evidence package.
2. Run deterministic preview.

**Expected**:
- The merged ticket set is the deduplicated union of local and remote open tickets.
- Every ticket appears exactly once in the mandatory Open Jira Tickets section.
- Stale/partial entries are present and qualified.
- Duplicate tickets are merged without loss.
- If no validated source can establish the open set, preview/generation fails closed.
- If the ticket count exceeds the bound, generation fails closed without truncation.

## Scenario 2: Preview is deterministic and non-generative

**Setup**: Use complete evidence and a fake AI provider that records calls.

**Steps**:
1. Request handover generation preview.
2. Inspect the response, filesystem, and provider fake.

**Expected**:
- Preview returns deterministic mandatory sections, evidence availability, readiness, and an
  `evidenceDigest`.
- The AI provider is invoked 0 times.
- No handover Markdown, sidecar, archive, or delivery action is created.
- The response contains no raw evidence package, prompt, or credentials.

## Scenario 3: Confirmed generation uses DeepSeek and persists a compatible handover

**Setup**: Use deterministic preview plus a fake configured DeepSeek provider returning valid
advisory JSON with exact supplied IDs.

**Steps**:
1. Preview.
2. Confirm generation with the preview digest.

**Expected**:
- The configured provider is invoked exactly once.
- Mandatory sections remain system-authored and contain all open tickets.
- The final handover uses the established `Hi Team` intro, deterministic sections, and signature;
  no AI-specific sections or `[evidence:...]` markers are emitted.
- `handover-<date>.md` and `handover-provenance.json` are persisted atomically.
- The sidecar records provider/model, evidence digest, availability, exact references, and the
  validated advisory citation IDs.
- Existing handover response shape remains compatible.
- Reviewed findings remain authoritative; unreviewed content is advisory only.

## Scenario 4: Stale/partial evidence is qualified

**Setup**: Provide stale/partial ticket cache, partial investigation evidence, and an unavailable
Datadog/status source.

**Expected**:
- Preview and handover explicitly identify stale/partial/missing/unavailable sources.
- All known open tickets are still included.
- AI output describing stale/partial evidence as current/complete is rejected.
- A valid advisory response remains bounded by the availability disclosure.

## Scenario 5: Invalid citations, malformed output, and provider failures fail closed

**Setup**: Use fake provider responses with unsupported IDs, aliases, URLs, unavailable IDs,
malformed/missing sections, over-bound output, timeout, unavailability, and incomplete configuration.

**Expected**:
- Invalid citations fail with `evidence-reference-invalid`.
- Malformed/missing/over-bound output fails with `ai-output-invalid` or `ai-output-too-large`.
- Provider timeout/unavailability/configuration failures map to controlled `504`/`503` failures.
- No new handover or sidecar is persisted; an existing handover remains intact.
- Exactly one provider call is attempted; no automatic fallback occurs.
- No citation repair, remapping, fuzzy matching, or post-processing occurs.

## Scenario 6: Credential non-disclosure and zero Datadog mutations

**Setup**: Include credential sentinels in the environment and credential-like content in fake
evidence/AI output. Use a fake Datadog transport/snapshot.

**Expected**:
- Sentinels do not appear in API responses, logs, handover Markdown, sidecar, archives, frontend
  output, or exceptions.
- Credential-like evidence fails closed or is redacted.
- The AI envelope contains only bounded evidence and instructions.
- All Datadog interactions are read-only/from the existing snapshot; zero POST/PATCH/PUT/DELETE
  requests occur.

## Scenario 7: Regeneration archives and restores

**Setup**: Generate a handover, then regenerate with a failing provider and with a successful
provider.

**Expected**:
- Regeneration requires explicit confirmation.
- Successful regeneration archives the previous Markdown/sidecar and persists the replacement.
- Failed regeneration restores both archived files and reports a sanitized error.
- Archive verification failure is controlled and does not corrupt the existing record.
- Existing archive consumers remain compatible.

## Scenario 8: End Shift readiness and optional legacy tooling

**Setup**: Remove `noc-handover` and Copilot from the environment; keep validated evidence,
readiness, and the configured AI provider.

**Expected**:
- Handover preview and generation are available without either legacy tool.
- End Shift readiness/health/status/docs describe `noc-handover` and Copilot as optional
  compatibility capabilities.
- Missing legacy tools do not make the core workstation unready.
- Handover readiness still gates generation and reports blockers/warnings.

## Scenario 9: Delivery compatibility

**Setup**: Generate a handover and exercise delivery preview/send with the existing Microsoft 365
fake/transport behavior.

**Expected**:
- Delivery preview/send operate on the Markdown file and remain separate from AI generation.
- Recipient validation, confirmation gates, and M365 transport behavior are unchanged.
- The final Markdown contains deterministic operational content only; the provenance sidecar is not
  delivered.
- Delivery failure leaves the local handover unchanged.

## Scenario 10: Frontend preview, confirmation, and investigation boundaries

Run `tests/test_frontend_modules.py`. Verify:

- Preview displays deterministic content and evidence availability without AI.
- Generation/regeneration wording references validated evidence and the configured AI provider,
  not `noc-handover` or Copilot.
- Generate/regenerate/delivery require explicit confirmation.
- Preview is invalidated when the selected shift or preview inputs change.
- Reviewed findings remain authoritative and distinguishable; AI advisory content is validated
  internally and is not emitted into the final handover.
- Existing delivery preview/send UI remains unchanged.

## Optional Manual Live Check

Only run in an approved environment. Never echo credential values.

1. Configure Feature 014 DeepSeek Flash and the existing read-only Datadog/Jira/M365 settings.
2. Start NOC Web.
3. Open End Shift for the selected shift and preview the handover; confirm no record was created.
4. Confirm generation and inspect the deterministic Markdown, provenance sidecar, and archive absence.
5. Regenerate and verify archive/restore behavior.
6. Preview delivery and confirm no credentials or sidecar are included.
7. Verify the handover contains every open ticket and that no Datadog mutation occurred.

Expected: a locally persisted, delivery-compatible handover with deterministic mandatory content and
a clearly labeled advisory AI section, produced without `noc-handover` or Copilot.
