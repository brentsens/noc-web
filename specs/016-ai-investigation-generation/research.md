# Phase 0 Research: Provider-Independent AI Investigation Generation

**Feature**: `016-ai-investigation-generation`
**Date**: 2026-11-10
**Status**: Complete — all technical unknowns resolved

## Decision 1: Use Feature 015 as the only Datadog evidence source

**Decision**: Investigation preview and generation will call
`backend.services.datadog_evidence.get_incident_evidence(incident_id)` exclusively. No service
will call `DatadogClient` directly, invoke `noc-inv`, use Datadog MCP, or inspect raw Datadog
payloads. Feature 015's existing credential, GET-only, timeout, response-size, schema, and
fail-closed protections remain unchanged.

**Rationale**: Feature 015 already provides validated incident detail, referenced notebooks and
monitors, availability, provenance, relationship metadata, and partial/complete status. Reusing
that contract avoids duplicate retrieval logic and keeps the read-only boundary auditable.

**Validation**: Require an active/stable incident state from the normalized evidence, a valid
incident identifier, and a well-formed bundle. A resolved, unavailable, or malformed incident
fails closed. Referenced notebook/monitor failures remain partial evidence and are disclosed.

**Alternatives considered**:
- Direct Datadog REST calls from investigation generation — rejected: duplicates Feature 015 and
  risks bypassing its protections.
- Reuse the existing incident snapshot cache for evidence — rejected: the snapshot lacks the full
  validated evidence bundle and referenced notebook/monitor content.

## Decision 2: Build a bounded, minimized, secret-free evidence package

**Decision**: Add `backend/services/investigation_evidence.py` to transform the Feature 015 bundle
into an `EvidencePackage` containing only generation-relevant fields:

- incident identity, title, state, severity, timestamps, impact scope, customer-impact flag, and a
  bounded selection of validated fields;
- available notebooks with identifiers, titles, source links, Markdown, bounded query/time-range
  data, and availability;
- available monitors with identifiers, names, types, queries, thresholds, tags, state, messages,
  and availability;
- stable evidence identifiers (`incident:<id>`, `notebook:<id>`, `monitor:<id>`), source links,
  feature-015 source/provenance, and availability states;
- explicit unavailable/partial references and their controlled error codes;
- a canonical digest used to detect preview changes.

Hard bounds: package ≤256 KiB, ≤10 notebooks, ≤10 monitors, notebook Markdown ≤16 KiB per
notebook and ≤64 KiB total, monitor message/query ≤2 KiB each, and bounded field/tag/threshold
counts inherited from Feature 015. Exceeding a bound raises `evidence-too-large` rather than
truncating. A credential-pattern scan runs before the package is stored or sent to a provider; a
match fails closed with `evidence-credential-detected`.

**Rationale**: The AI provider should receive only what is needed to produce an evidence-grounded
advisory investigation. Minimization reduces prompt-injection surface, response size, and secret
exposure. A canonical digest supports exact snapshot validation.

**Alternatives considered**:
- Send the entire Feature 015 bundle — rejected: unbounded, includes unnecessary raw fields, and
  increases credential/injection exposure.
- Store the package on disk for preview reuse — rejected: operational evidence should not become
  an unreviewed cache artifact.

## Decision 3: Keep exact preview snapshots in a bounded process-local store

**Decision**: Add `backend/services/investigation_preview_store.py` with an in-memory,
thread-safe, TTL store:

- random `previewId` generated with `secrets.token_urlsafe(32)`;
- max 32 active snapshots, 10-minute TTL, 256 KiB package cap;
- single-use entries consumed atomically by create;
- no disk, log, response-body, or database persistence of the raw package;
- injectable clock for deterministic tests.

Preview stores the exact validated `EvidencePackage` plus request identity, provider
identifier/model, package digest, and expiry. Create consumes the snapshot, verifies the request
still matches the previewed shift/name/notebook URL, and re-fetches Feature 015 evidence to compare
the digest before generation. A changed or unavailable digest invalidates the preview and requires
re-review.

**Rationale**: The operator must review exactly what the AI will use. Server-side snapshots avoid
sending raw evidence or a large signed blob to the browser. Single-use entries prevent replay and
unexpected duplicate provider calls.

**Alternatives considered**:
- Re-fetch and silently use the latest evidence — rejected by the clarification: generation must
  use the previewed snapshot.
- Persist previews on disk — rejected: stale evidence cache and extra credential/exposure surface.
- Client-held signed snapshot — rejected: exposes raw evidence and grows request size.

## Decision 4: Use structured AI JSON and server-rendered Markdown

**Decision**: The AI provider returns exactly one bounded JSON object with five required keys:

```json
{
  "summary": ["..."],
  "confirmedFindings": ["..."],
  "currentStatus": ["..."],
  "nextActions": ["..."],
  "handoverSummary": ["..."]
}
```

Each value is a non-empty list of non-empty strings (max 8 items per section, max 2 KiB per item,
max 64 KiB total). Every item must contain at least one inline stable evidence identifier from
the supplied package. Unknown keys, wrong types, extra fields, unsupported identifiers, absent
citations, placeholder-only content, and over-bound output are rejected. The server renders the
validated object into the existing Markdown investigation structure and supplies all metadata,
provenance, and availability disclosure outside AI-authored content.

**Rationale**: Structured JSON makes citation and section validation deterministic. The envelope
also carries `citationContract.allowedEvidenceIds` with the exact allowed IDs, an explicit
byte-for-byte copy rule, the unavailable IDs that must never be cited, forbidden citation forms,
and an example. No repair, remapping, fuzzy matching, or post-processing is performed. Server-side
Markdown rendering prevents the model from fabricating metadata, provenance, or availability
sections and preserves the existing investigation format.

**Alternatives considered**:
- Ask the AI to return complete Markdown — rejected: parsing/validating citations and metadata is
  brittle and lets the model fabricate provenance.
- Store raw provider JSON as the investigation — rejected: breaks existing inspection/lifecycle
  contracts.

## Decision 5: Extend the existing provider adapters with an investigation prompt profile

**Decision**: Keep the existing Feature 014 provider selection and readiness model. Extend the
provider adapters so a caller can supply a prompt profile:

- `deepseek_provider.answer_with_deepseek_api` accepts an optional system prompt, defaulting to the
  existing Assistant prompt;
- `copilot_cli.answer_with_copilot_cli` accepts an optional prompt, defaulting to the existing
  Assistant prompt;
- `ai_provider` exposes an investigation-provider resolution path using the same configuration,
  readiness, timeout, response-size, and no-fallback rules.

The investigation prompt is provider-neutral, treats all evidence as data, forbids tools/external
actions, requires the five-section JSON object, requires inline stable citations, and forbids
evidence-availability claims. Provider exceptions map to sanitized investigation errors:
not-configured/not-ready → 503, timeout → 504, unavailable → 503, invalid response → 502.
Credentials remain inside existing closures and are never included in envelopes, logs, or errors.

**Rationale**: DeepSeek Flash is already supported by the existing configuration, but its current
system prompt is Assistant-specific. A prompt profile lets investigation generation reuse provider
configuration without weakening the Assistant contract. Explicit provider selection preserves the
no-fallback requirement.

**Alternatives considered**:
- Build a separate DeepSeek client — rejected: duplicates credential/config handling and risks
  bypassing existing protections.
- Reuse the Assistant prompt — rejected: it returns the wrong schema and routing policy.
- Fall back to another provider — rejected by the feature requirement and existing readiness model.

## Decision 6: Make evidence availability system-authored and provider-independent

**Decision**: Build availability disclosure from the `EvidencePackage`, not from AI output. Persist
it in `evidence-provenance.json`, a Markdown metadata line, and a system-authored
`## Evidence Availability` section when the package is partial or has unavailable references. The
AI is instructed not to make availability/completeness claims. A bounded contradiction check
rejects output that explicitly claims complete/current evidence when the package is partial.

**Rationale**: Availability must remain trustworthy even if the model omits or contradicts it.
System-authored disclosure is deterministic and testable, and the validator prevents the model
from overriding it.

**Alternatives considered**:
- AI-authored disclosure only — rejected: model omission or contradiction makes availability
  unreliable.
- Mark the whole investigation unavailable on any partial evidence — rejected: the clarification
  allows validated incident detail to support advisory generation with explicit partial labeling.

## Decision 7: Introduce `ai-evidence` provenance while preserving legacy records

**Decision**: New records use provenance `ai-evidence`. Update provenance detection and allowlists
in `backend/services/investigations.py`, `assistant.py`, `assistant_context.py`, `ai_reports.py`,
and `frontend/js/api.js` to accept `ai-evidence` alongside legacy `noc-inv` and `copilot-mcp`.
Legacy records remain readable, reviewable, routeable, and subject to their existing metadata
rules. New records persist:

- `generation-status.json` with `provenance`, `evidenceStatus`, provider identifier/model,
  validation issues, and no secrets;
- `evidence-provenance.json` with stable references, source links, availability, and unavailable
  evidence;
- the existing `investigation.md` and `reviewed-context.json` files with existing lifecycle rules.

**Rationale**: The lifecycle/review model is valuable and should not be replaced. Extending the
provenance allowlist preserves existing records while making the new generation path reviewable.

**Alternatives considered**:
- Reuse `noc-inv` provenance for AI evidence — rejected: misleading and hides the new architecture.
- Reject legacy provenance — rejected: would break existing investigations.

## Decision 8: Hand off incident identity with selected-shift synchronization

**Decision**: Active Incidents will store a bounded session handoff containing `incidentId`,
`title`, and optionally `url` when the operator selects Create Investigation. Investigations will
read and clear that handoff, require the incident identifier for preview, and keep the existing
selected-shift date workflow. Preview/create continue to use the selected shift; Datadog incident
awareness remains globally current. The preview UI will show the incident identity, evidence
status, provider identity/model, and the read-only generation path.

**Rationale**: Feature 015 evidence requires an incident identifier; the existing title-only
handoff is insufficient. A bounded handoff preserves the current navigation flow without exposing
evidence in the URL or localStorage. The full Datadog title is sent as `displayTitle`; a supplied
local name still receives strict validation, while an omitted local name is deterministically
slugged by the server from the display title with length and byte bounds plus a hash suffix for
long titles.

**Alternatives considered**:
- Ask the operator to type an incident ID — rejected: error-prone and bypasses the active-incident
  selection.
- Put incident ID/evidence in query parameters — rejected: URL leakage and length limits.

## Decision 9: Make investigation readiness depend on the new providers, not legacy tools

**Decision**: Investigation-generation readiness and UI wording will reference the existing
`external.datadog` (Feature 015 provider) and `external.aiProvider` (Feature 014) readiness
surfaces. `noc-inv`, Copilot CLI, and Datadog MCP are no longer requirements for this workflow.
The `noc-inv` and `copilot` command checks in `readiness.py` are marked optional for investigation
readiness (or removed if no other workflow consumes them), and their impact text must not claim
investigation generation requires them. Readiness remains static and does not call Datadog or the
AI provider.

**Rationale**: Operators need actionable readiness for the actual dependencies. Keeping unrelated
legacy checks preserves other workflows without blocking Feature 016.

**Alternatives considered**:
- Remove all legacy readiness checks — rejected: other workflows may still use those tools and
  unrelated behavior is out of scope.
- Keep investigation readiness tied to noc-inv/Copilot — rejected: contradicts the feature and
  prevents generation when Copilot is absent.

## Decision 10: Reuse existing persistence and collision protection

**Decision**: Keep the current NOC-root path, name normalization, safe target checks, staging
directory, atomic `os.replace`, conflict handling, and reviewed-context defaults. Add the two new
system-authored JSON files to the same staged publication. Any evidence, provider, validation, or
storage failure removes the staging directory and leaves existing records untouched. Create
rechecks target existence before publication.

**Rationale**: These rules are already tested and satisfy operational data-integrity
requirements. The new workflow should not weaken them.

**Alternatives considered**:
- Overwrite or merge into an existing investigation — rejected: violates collision and review
  guarantees.
- Use a database transaction — rejected: changes the established local persistence model.

## Decision 11: Test with injected evidence providers and fake AI providers

**Decision**: Add deterministic tests using:

- a fake Feature 015 evidence loader returning complete, partial, unavailable, malformed, and
  over-bound bundles;
- a fake configured AI provider returning valid JSON, unsupported citations, malformed output,
  timeouts, unavailability, and credential-sentinel content;
- an injectable preview store clock and explicit store resets;
- fake Datadog transports that assert zero mutation requests;
- secret sentinel scans across responses, logs, Markdown, JSON files, and exceptions;
- regression tests for preview non-generation, explicit confirmation, local persistence,
  collision protection, lifecycle/review compatibility, selected-shift synchronization, and
  legacy provenance compatibility.

**Rationale**: Real Datadog and AI calls are non-deterministic and unsafe for regression tests.
Injection keeps the tests fast, bounded, and able to assert fail-closed behavior and zero external
mutations.

**Alternatives considered**:
- Live-provider integration tests — rejected for the default suite: non-deterministic and
  credential-dependent. A separate manual/quickstart check can cover live configuration.
