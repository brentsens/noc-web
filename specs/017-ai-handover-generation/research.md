# Phase 0 Research: Provider-Independent AI Handover Generation

**Feature**: `017-ai-handover-generation`
**Date**: 2026-11-11
**Status**: Complete — technical unknowns resolved

## Decision 1: Assemble from validated NOC Web evidence and union all open-ticket sources

**Decision**: Build the handover evidence package from existing validated services only:

- shift notes via `backend/services/shift_notes.py`;
- locally tracked open tickets via `backend/services/tickets.py`;
- remote open-ticket cache via `backend/services/jira_ticket_queue.py` and
  `backend/services/jira_cache.py`;
- reviewed findings and investigation lifecycle via `backend/services/investigations.py`;
- already-available Datadog incident snapshot via `backend/services/datadog_incidents.py`;
- dashboard/status projections via `backend/services/dashboard.py` and
  `backend/services/status.py`;
- End Shift readiness/preflight via `backend/services/end_shift.py` and
  `backend/services/readiness.py`.

The open-ticket set is the union of locally tracked open tickets and all remote cached open
tickets, deduplicated by canonical ticket ID. Locally tracked tickets that are not present in the
remote cache are still included. The set is deterministically sorted and every entry is rendered in
the mandatory Open Tickets section.

Stale/partial cache entries are included with explicit qualification. If neither a validated local
nor remote source can establish the open-ticket set, generation fails closed. If the complete set
exceeds the bounded package capacity, generation fails closed rather than omitting or summarizing
any ticket.

**Rationale**: The mandatory completeness requirement cannot depend on AI judgment or a single
cache. The union/deduplication approach preserves all known open work while keeping the source of
truth local and validated.

**Alternatives considered**:
- Use only the remote Jira queue — rejected: local-only tickets would be omitted.
- Use only locally tracked tickets — rejected: untracked open Jira tickets would be omitted.
- Drop stale cache entries — rejected: the operator needs to see known open work with qualification.
- Truncate or AI-summarize an over-bound ticket set — rejected by the completeness requirement.

## Decision 2: Deterministic mandatory content plus internal advisory validation

**Decision**: NOC Web assembles the mandatory handover content before AI:

- intro/selected-shift context;
- Summary;
- Open Salesforce Tickets preserving the section; if a validated Salesforce source reports zero,
  state that none are open, and if no validated source is available, state that the source is
  unavailable rather than claiming zero;
- Open Jira Tickets containing the complete open-ticket union;
- Investigation Updates from reviewed findings and lifecycle state only;
- Next Shift Actions derived deterministically from ticket next actions, reviewed findings, and
  readiness;
- system-authored evidence availability/readiness disclosure;
- existing closing/signature shape.

The AI provider may produce only bounded advisory analysis that is validated internally. It cannot
author or modify any mandatory section. AI advisory text and `[evidence:...]` citation syntax are
not emitted into the final user-facing handover; validated citations are retained only in
provenance/internal validation. The final Markdown uses the established NOC intro, deterministic
sections, and signature.

**Rationale**: Separating deterministic facts from AI analysis prevents ticket omissions, keeps
reviewed findings authoritative, and makes the AI contribution auditable. Final Markdown remains
compatible with the existing section parser and delivery body; provenance metadata is additive.

**Alternatives considered**:
- Let AI write the whole handover — rejected: violates ticket completeness and review boundaries.
- Mix advisory content into existing sections — rejected: makes authoritative/advisory content hard
  to distinguish.
- Emit AI advisory subsections into the delivered handover — rejected by the final presentation
  requirement and deterministic-count safety.

## Decision 3: Use a bounded, minimized evidence package with stable handover IDs

**Decision**: Add `backend/services/handover_evidence.py` to build a bounded package containing:

- shift-note entries with stable IDs based on shift date and a canonical hash;
- every open ticket with `ticket:<jira-key>`, status, priority, summary, next action, source, and
  freshness; private local NOC notes are excluded from handover and AI evidence;
- reviewed investigation findings and lifecycle state with `investigation:<name>`, plus
  `reviewState`/`authoritative` flags;
- Datadog incident context with `incident:<uuid>` only when already available;
- status/dashboard/readiness references (`status:<shift-date>`, `dashboard:<shift-date>`,
  `readiness:<shift-date>`);
- source links, provenance, availability, and authoritative flags.

Bounds: package ≤1 MiB, ≤500 open tickets, ≤2,000 shift-note entries, ≤200 investigations, ≤100
Datadog context items. Over-bound content fails closed. No credential-like content, Authorization
headers, unrelated environment values, or raw provider payloads may enter the package.

**Rationale**: Stable IDs make AI citations deterministic and independently verifiable. Bounds
prevent unbounded prompts and response-size abuse. Including all ticket IDs in the package while
keeping fields minimal supports mandatory completeness without sending unnecessary data.

**Alternatives considered**:
- Use ticket names or URLs as citations — rejected: aliases are ambiguous and can be invented.
- Omit ticket details from the AI package — rejected: the AI could not reference ticket evidence
  accurately.
- Truncate a large package — rejected: would violate completeness or citation integrity.

## Decision 4: Mirror the strict exact-citation model in a handover-specific AI module

**Decision**: Add `backend/services/handover_ai.py` with:

- a provider-neutral handover system prompt;
- an envelope containing `citationContract.allowedEvidenceIds`,
  `citationContract.unavailableEvidenceIds`, the exact allowed IDs, forbidden citation forms, and an
  example;
- a fixed advisory output schema with four arrays: `advisorySummary`, `operationalRisks`,
  `recommendedFocus`, `watchItems`;
- each array 1–8 non-empty items, each item ≤2 KiB, total output ≤64 KiB;
- every item must contain at least one exact bracketed citation `[evidence:<stable-id>]` whose
  stable ID is in the allowed set;
- unsupported, invented, unavailable, shortened, aliased, URL-form, or malformed citations fail
  closed;
- stale/partial evidence contradictions fail closed;
- no repair, remapping, fuzzy matching, or post-processing.

The implementation mirrors Feature 016's strict model and tests. It does not weaken or alter
Feature 016's validator.

**Rationale**: Reusing the exact-citation contract keeps AI output verifiable and fail-closed while
allowing handover-specific advisory categories. A separate module avoids coupling handover section
validation to investigation output.

**Alternatives considered**:
- Ask the AI for free-form Markdown — rejected: citation and section validation is brittle.
- Repair invalid citations or map aliases — rejected by the specification.
- Share Feature 016's validator directly — rejected: different section schema and evidence IDs;
  shared behavior is mirrored and tested instead.

## Decision 5: Always invoke the configured provider; fail closed on failure

**Decision**: Every confirmed generation invokes the configured Feature 014 provider for internal
advisory validation. DeepSeek Flash is supported through the existing DeepSeek configuration. If the
provider is not configured, not ready, times out, is unavailable, or returns invalid output,
generation fails closed, persists no new handover, and preserves any existing handover. There is no
deterministic-only final-generation path and no automatic provider fallback.

**Rationale**: The operator confirmed a generation that includes advisory synthesis. Silent omission
or fallback would make the result ambiguous and could hide failures. Preview remains available
without AI, so operators can inspect deterministic content before deciding whether to generate.

**Alternatives considered**:
- Persist deterministic-only content on provider failure — rejected by clarification.
- Fall back to Copilot/another provider — rejected by the specification.
- Let the operator choose deterministic-only after failure — rejected by clarification.

## Decision 6: Add deterministic generation preview with optional evidence digest

**Decision**: Add a read-only `POST /api/shifts/{shift_date}/handover/generation-preview` endpoint
that assembles deterministic mandatory content and evidence/readiness summary without AI, file
writes, replacement, archive, or delivery. Response includes an `evidenceDigest` and section data.
The existing `GET /handover` and delivery preview endpoint remain unchanged.

Generate/regenerate requests may include an optional `previewDigest`. If supplied and the current
evidence digest differs, generation fails closed with `preview-stale` and requires a new preview.
The UI always previews before generation and clears preview state when the selected shift or target
changes.

**Rationale**: This satisfies the read-only/non-generative preview requirement without breaking the
existing generation contract. The optional digest prevents generating from evidence the operator
did not review while preserving callers that do not supply a preview digest.

**Alternatives considered**:
- Require a server-side preview snapshot — rejected: adds state and expiry complexity while the
  handover is generated immediately after confirmation.
- Reuse the delivery preview endpoint — rejected: it operates on a persisted handover and would
  confuse two different previews.
- Re-fetch silently — rejected: preview would not correspond to generated evidence.

## Decision 7: Preserve Markdown contract, add a versioned sidecar, archive both

**Decision**: Keep `handover-<shift-date>.md` as the authoritative handover record and preserve its
existing section parser and delivery behavior. Restore the established NOC intro, deterministic
sections, and signature; do not append AI-specific sections or internal citation syntax. Add
`handover-provenance.json` as a versioned sidecar containing `formatVersion`, `evidenceDigest`,
`availability`, provider/model, evidence references, unavailable references, advisory status/mode,
validated advisory citation IDs, and generation timestamp. Archive both the Markdown and sidecar
during regeneration and restore both on failure.

Existing handover records without a sidecar remain readable and deliverable. The sidecar is not sent
through Microsoft 365 delivery.

**Rationale**: The Markdown remains the operator- and delivery-facing contract; the sidecar adds
machine-readable provenance without changing existing consumers. Archiving both preserves the
audit trail.

**Alternatives considered**:
- Put provenance only in Markdown comments — rejected: hard to validate and easy to lose.
- Replace the Markdown format with JSON — rejected: breaks delivery and existing records.
- Deliver the sidecar — rejected: delivery transport compatibility and unnecessary exposure.

## Decision 8: Preserve investigation review boundaries

**Decision**: Deterministic Investigation Updates sections use only
`get_reviewed_findings()`/reviewed lifecycle projections. Unreviewed investigations may be included
in the advisory evidence package with `authoritative: false` and `reviewState` metadata, but they
must never appear as reviewed findings in the mandatory sections. The AI prompt forbids describing
unreviewed content as reviewed. Tests cover reviewed/unreviewed separation and promotion attempts.

**Rationale**: Reviewed findings are operational evidence; AI and unreviewed content are advisory.
The boundary must remain visible in both Markdown and sidecar provenance.

**Alternatives considered**:
- Include all investigations in mandatory sections — rejected: promotes unreviewed content.
- Exclude unreviewed investigations from advisory evidence — rejected: advisory synthesis may need
  to flag them, as long as clearly labeled.

## Decision 9: Make noc-handover and Copilot optional compatibility capabilities

**Decision**: Update `backend/services/readiness.py`, `health.py`, `status.py`,
`dependency_readiness.py`, `frontend/end-shift.html`, `README.md`, and
`docs/workstation-runtime.md` so handover generation readiness depends on validated evidence,
End Shift preflight, the configured AI provider, and existing local services, not on noc-handover or
Copilot. Keep legacy tool checks optional for other workflows. Handover generation never invokes
those commands.

**Rationale**: Replacing one unavailable dependency with another would fail the feature. Optional
compatibility reporting preserves awareness for other workflows without blocking core handover
generation.

**Alternatives considered**:
- Keep noc-handover required for readiness — rejected: contradicts FR-020.
- Remove all legacy tool checks globally — rejected: other workflows may still use them.

## Decision 10: Keep Microsoft 365 delivery unchanged

**Decision**: Do not modify `backend/services/handover_delivery.py` behavior. Delivery preview and
send continue to operate on the Markdown file, validate recipients, require explicit confirmation,
and use the existing Microsoft 365 transport. Only deterministic operational Markdown is delivered;
AI advisory validation is internal and not emitted. AI generation and delivery remain separate
operations.

**Rationale**: Delivery already has a safe, confirmed transport. The feature changes how the
Markdown is produced, not how it is delivered.

**Alternatives considered**:
- Integrate AI into delivery — rejected: mixes generation and external delivery.
- Redesign delivery for the sidecar — rejected: unnecessary and out of scope.

## Decision 11: Test with injected evidence sources and fake AI providers

**Decision**: Add deterministic tests with:

- fake shift notes, local tickets, remote ticket cache, investigations, Datadog snapshot,
  status/dashboard, and readiness fixtures;
- explicit all-open-ticket union/dedup/over-bound cases;
- fake configured providers returning valid advisory JSON, unsupported citations, aliases, URLs,
  malformed output, stale/partial contradictions, timeout, unavailability, and credential sentinels;
- End Shift/API integration tests for preview non-generation, confirmation gates, generation,
  regeneration archive/restore, and delivery compatibility;
- frontend tests for preview, generation wording, and explicit confirmation;
- secret-sentinel and zero-Datadog-mutation audits.

**Rationale**: Real NOC data, Datadog, and AI providers are non-deterministic and unsafe for
default tests. Injection proves behavior and fail-closed paths without live dependencies.

**Alternatives considered**:
- Live integration tests — rejected for the default suite; optional manual quickstart only.
