# Data Model: Provider-Independent AI Investigation Generation

**Feature**: `016-ai-investigation-generation`
**Date**: 2026-11-10

## Scope

This model adds the evidence package, preview snapshot, AI output, and provenance records needed
by Feature 016. It reuses the existing investigation record, reviewed context, lifecycle, and
projection structures. No new database or external data store is introduced.

## Entity Relationships

```text
InvestigationGenerationRequest
  └── creates one InvestigationPreviewSnapshot
        ├── contains one EvidencePackage
        │     ├── one incident EvidenceItem
        │     ├── zero-to-many notebook EvidenceItems (≤10)
        │     ├── zero-to-many monitor EvidenceItems (≤10)
        │     └── zero-to-many unavailable EvidenceReferences
        └── references one configured AI provider identity

Operator Confirmation
  └── consumes one active InvestigationPreviewSnapshot
        └── produces one InvestigationAIResult
              ├── on validation success -> one GeneratedInvestigationRecord
              └── on failure -> zero persisted investigations

GeneratedInvestigationRecord
  ├── investigation.md
  ├── generation-status.json
  ├── evidence-provenance.json
  └── reviewed-context.json
        └── existing lifecycle/review state (ready_for_review, escalated_to_incident, cured,
            rejected)
```

## Entity: InvestigationGenerationRequest

**Purpose**: The operator's request to preview or create an investigation for a current Datadog
incident.

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `shiftDate` | date string | yes | `YYYY-MM-DD`, valid calendar date, selected shift |
| `incidentId` | string | yes for preview | Valid Datadog incident identifier from the active-incident handoff |
| `displayTitle` | string | no | Full Datadog incident title; ≤200 characters; punctuation is preserved for display |
| `name` | string | no for preview, yes for create | Local identifier. When provided (including blank), existing strict name validation applies; when omitted with a display title, a deterministic safe slug is generated. |
| `notebookUrl` | string | yes | Existing `app.datadoghq.com/notebook/<numeric-id>` validation |
| `previewId` | string | yes for create | Opaque server-issued preview identifier |
| `confirmed` | boolean | yes for create | Must be exactly `true`; preview never implies confirmation |

**Rules**:
- The incident must resolve to an ACTIVE or STABLE normalized Feature 015 incident.
- The selected shift governs the local target path; the incident evidence remains globally
  current.
- Create must match the shift, normalized name, and notebook URL stored in the preview snapshot.
- No request field may contain credentials or control characters.

## Entity: EvidencePackage

**Purpose**: The bounded, minimized, validated input to the AI provider and the source of all
citations and availability metadata.

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `packageVersion` | string | yes | Fixed current package version |
| `incident` | EvidenceItem | yes | Validated Feature 015 incident detail |
| `notebooks` | list<EvidenceItem> | yes | Available notebooks, 0–10 |
| `monitors` | list<EvidenceItem> | yes | Available monitors, 0–10 |
| `references` | map<stableId, EvidenceReference> | yes | Unique stable IDs; source links; availability |
| `unavailable` | list<EvidenceReference> | yes | Explicit referenced-but-unavailable items with controlled error codes |
| `availability` | enum | yes | `complete` or `partial` |
| `digest` | string | yes | Canonical digest of the bounded package |
| `sizeBytes` | integer | yes | ≤256 KiB |

**Stable evidence IDs**:
- `incident:<incident-id>`
- `notebook:<numeric-id>`
- `monitor:<numeric-id>`

**Minimized item fields**:
- Incident: id, title, state, severity, created/updated/detected/resolved timestamps, impact
  scope, customer-impacted flag, bounded validated fields.
- Notebook: id, title, source URL, bounded Markdown, bounded query/metric definitions, time
  ranges, availability.
- Monitor: id, name, type, query, thresholds, tags, state, message, availability.

**Bounds**:
- Package ≤256 KiB; notebook Markdown ≤16 KiB each and ≤64 KiB total.
- ≤10 notebooks, ≤10 monitors; inherited Feature 015 bounds for tags/thresholds/assets.
- Over-bound evidence fails closed; content is never silently truncated.
- Credential-like keys or sentinel values fail closed before storage or provider submission.

## Entity: EvidenceReference

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `id` | stable ID string | yes | Must match a supplied package item |
| `kind` | enum | yes | `incident`, `notebook`, or `monitor` |
| `sourceUrl` | HTTPS URL | yes | Canonical Datadog app URL |
| `source` | string | yes | Feature 015 provenance (`incident_field`, `monitor_asset`, `notebook`, etc.) |
| `availability` | enum | yes | `available` or `unavailable` |
| `error` | enum or null | when unavailable | `not-found`, `forbidden`, `invalid-response`, `timeout`, `provider-unavailable` |

## Entity: InvestigationPreviewSnapshot

**Purpose**: Server-side exact snapshot of the evidence and request reviewed by the operator.

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `previewId` | opaque string | yes | Cryptographically random, single-use |
| `createdAt` | timestamp | yes | Server clock |
| `expiresAt` | timestamp | yes | Created + 10 minutes |
| `status` | enum | yes | `active`, `consumed`, or `expired` |
| `request` | snapshot request fields | yes | Shift, incident ID, name, notebook URL |
| `package` | EvidencePackage | yes | ≤256 KiB |
| `packageDigest` | string | yes | Matches package digest |
| `provider` | provider identity | yes | Configured Feature 014 identifier |
| `model` | string or null | yes | DeepSeek Flash model when applicable |
| `providerReady` | boolean | yes | Static readiness only; no provider invocation |

**Rules**:
- Stored only in process memory; never written to disk or logs.
- Maximum 32 active snapshots; oldest/expired entries are removed first.
- Create atomically consumes the snapshot; a consumed or expired preview is rejected.
- A provider identity/model change between preview and create invalidates the preview.
- The exact snapshot is the only evidence input to confirmed generation.

## Entity: InvestigationAIOutput

**Purpose**: The advisory JSON object returned by the configured provider.

```json
{
  "summary": ["text with incident:<id>"],
  "confirmedFindings": ["text with notebook:<id>"],
  "currentStatus": ["text with monitor:<id>"],
  "nextActions": ["text with monitor:<id>"],
  "handoverSummary": ["text with incident:<id>"]
}
```

**Validation rules**:
- Exactly the five required keys; no extra keys.
- Each value is a non-empty list of non-empty strings; ≤8 items per section.
- Each item ≤2 KiB; total output ≤64 KiB.
- Each item contains at least one stable evidence ID whose package reference is available.
- The provider envelope lists the exact allowed IDs in
  `citationContract.allowedEvidenceIds`, requires byte-for-byte copying, lists unavailable IDs
  that must not be cited, and forbids shortened IDs, aliases, URLs, names, and bare numbers.
- No citation repair, remapping, fuzzy matching, or post-processing is permitted.
- No unsupported, unknown, fabricated, or non-canonical identifiers.
- No placeholder-only content.
- No evidence availability/completeness claims that contradict the system-authored disclosure.
- No credentials, Authorization headers, environment values, or secret-like sentinels.
- Malformed, missing-section, or over-bound output fails closed with no record.

## Entity: EvidenceAvailabilityDisclosure

**Purpose**: System-authored availability metadata and operator-visible disclosure.

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `availability` | enum | yes | `complete` or `partial` |
| `unavailable` | list<EvidenceReference> | yes | Referenced-but-unavailable evidence |
| `partialReasons` | list<string> | yes | Controlled, bounded reasons |
| `renderedText` | string | yes | System-authored Markdown section when partial |

**Rules**:
- Generated outside AI output from the evidence package.
- Persisted in `evidence-provenance.json` and reflected in `investigation.md`.
- AI output that contradicts the disclosure is rejected.
- A partial package can still produce an advisory investigation when incident detail is valid.

## Entity: GeneratedInvestigationRecord

**Purpose**: Existing local investigation files, extended with system-authored provenance.

| File | Purpose | New/changed fields |
|------|---------|--------------------|
| `investigation.md` | Human-readable record | Existing metadata and five required sections; `Evidence Provenance: ai-evidence`; `Evidence Status: complete|partial`; system `## Evidence Availability` section when partial |
| `generation-status.json` | Generation/validation metadata | `provenance: ai-evidence`, `evidenceStatus`, `provider`, `model`, `validationIssues`, incident ID, existing fields |
| `evidence-provenance.json` | Evidence reference/provenance map | Stable ID → source URL, Feature 015 source, availability; unavailable list; package digest |
| `reviewed-context.json` | Existing lifecycle/review state | Unchanged schema and defaults |

**Rules**:
- Written through the existing staging directory and atomic replace.
- Collision protection and safe path checks remain unchanged.
- No partial record is published on failure.
- `reviewed-context.json` starts unreviewed with `ready_for_review`.
- Existing records are never overwritten or mutated by generation.

## Entity: InvestigationProjection (extended)

Existing projection fields remain. `evidence` gains:

| Field | Type | Validation |
|-------|------|------------|
| `provenance` | string | `ai-evidence`, legacy `noc-inv`/`copilot-mcp`, or unavailable |
| `availability` | enum | `available`, `partial`, or `unavailable` |
| `access` | string | Always `read-only` |
| `reference` | URL or null | Existing notebook reference behavior |
| `status` | enum | `complete` or `partial` for `ai-evidence` records |
| `references` | map or null | Sanitized stable-ID provenance map |

The projection never exposes raw provider payloads, credentials, Authorization headers, or
unbounded evidence content.

## Entity: ProviderFailure

| Code | HTTP status | Meaning |
|------|-------------|---------|
| `provider-not-configured` | 503 | No Feature 014 provider selected |
| `provider-not-ready` | 503 | Selected provider configuration is incomplete |
| `provider-timeout` | 504 | Provider timed out |
| `provider-unavailable` | 503 | Provider/network/auth unavailable |
| `provider-invalid-response` | 502 | Provider returned a nonconforming object |
| `generation-failed` | 500 | Controlled internal generation failure |

All messages are sanitized and never include credentials, Authorization headers, raw provider
payloads, or unrelated environment values.

## State Transitions

### Preview lifecycle

```text
created -> active
active -> consumed       (create attempted, single use)
active -> expired        (TTL exceeded or store eviction)
active -> invalidated    (evidence digest changed, provider changed, request mismatch)
```

### Generation lifecycle

```text
previewed -> confirmed -> generating -> validated -> persisted (ready_for_review)
                                      \-> failed (no record)
```

### Existing investigation lifecycle (unchanged)

```text
ready_for_review -> escalated_to_incident -> cured
ready_for_review -> cured
ready_for_review -> rejected
```

`ai-evidence` records participate in the same review, rejection, attachment, and lifecycle rules
as legacy records.

## Compatibility Rules

- Legacy `noc-inv` and `copilot-mcp` records remain readable, inspectable, reviewable, and
  routeable.
- New records use `ai-evidence`; the allowlists in investigation lifecycle, assistant routing,
  AI reports, and frontend routing are extended, not replaced.
- Existing selected-shift creation paths and cross-shift projection rules are preserved.
- Datadog incident attachment remains a separate local reference action and is not part of AI
  generation.
- noc-handover data, generation, and lifecycle are untouched.
