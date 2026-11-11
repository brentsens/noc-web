# Data Model: Provider-Independent AI Handover Generation

**Feature**: `017-ai-handover-generation`
**Date**: 2026-11-11

## Scope

This model adds the bounded handover evidence package, deterministic content, advisory AI output,
preview, provenance sidecar, and persistence extensions. It preserves the existing handover
Markdown, archive, End Shift, and Microsoft 365 delivery contracts.

## Entity Relationships

```text
HandoverEvidencePackage
  ├── ShiftNoteEvidence[]
  ├── TicketCompleteness
  │     ├── LocalOpenTicketEvidence[]
  │     └── RemoteOpenTicketEvidence[]
  ├── InvestigationEvidence[]
  ├── DatadogIncidentEvidence[]
  ├── StatusDashboardEvidence
  ├── ReadinessEvidence
  └── HandoverEvidenceReference map

DeterministicHandoverContent
  ├── intro/closing
  ├── mandatory sections
  └── availability/readiness disclosure

AdvisoryAIOutput
  └── internally validated advisory items, each citing supplied available references

HandoverPreview
  ├── deterministic content
  ├── evidence digest
  └── availability/readiness summary

HandoverGenerationRequest
  └── confirmed + optional previewDigest
        └── PersistedHandoverRecord
              ├── handover-<date>.md
              ├── handover-provenance.json
              └── archive/ (on regeneration)

DeliveryPreview / DeliveryRequest
  └── operates on persisted Markdown only; separate from AI generation
```

## Entity: HandoverEvidencePackage

**Purpose**: The bounded, validated evidence used to assemble mandatory content and advisory
citations for one selected shift.

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `shiftDate` | date string | yes | `YYYY-MM-DD`, selected shift |
| `packageVersion` | string | yes | Fixed current version |
| `shiftNotes` | list<ShiftNoteEvidence> | yes | ≤2,000 entries; bounded text |
| `tickets` | TicketCompleteness | yes | Complete union; ≤500 tickets |
| `investigations` | list<InvestigationEvidence> | yes | ≤200; reviewed/unreviewed flags |
| `datadogIncidents` | list<DatadogIncidentEvidence> | yes | ≤100; already-available snapshot only |
| `status` | StatusDashboardEvidence | yes | Read-only projection |
| `dashboard` | StatusDashboardEvidence | yes | Read-only projection |
| `readiness` | ReadinessEvidence | yes | Preflight/readiness state |
| `references` | map<stableId, HandoverEvidenceReference> | yes | Unique exact IDs |
| `unavailable` | list<HandoverEvidenceReference> | yes | Explicit unavailable/stale/partial sources |
| `availability` | enum | yes | `complete`, `partial`, or `unavailable` |
| `digest` | string | yes | Canonical SHA-256 over the bounded package |
| `sizeBytes` | integer | yes | ≤1 MiB |

**Bounds**:
- Package ≤1 MiB.
- ≤500 open tickets, ≤2,000 shift-note entries, ≤200 investigations, ≤100 Datadog context items.
- Per-field text bounds follow existing source validators; no unbounded raw Markdown or provider
  payloads.
- Over-bound ticket or evidence sets fail closed; no truncation or omission.

**Rules**:
- Built only from validated local services and the already-available read-only Datadog snapshot.
- No credentials, Authorization headers, unrelated environment values, raw provider payloads, or
  unsupported fields.
- Strips or rejects credential-like content before prompt construction.
- Includes all open-ticket IDs even if the AI would not mention them.
- `digest` is canonical and used by preview/generation consistency checks.

## Entity: TicketCompleteness

**Purpose**: Guarantee the mandatory open-ticket list is complete and independent of AI judgment.

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `localOpen` | list<TicketEvidence> | yes | All locally tracked active/open tickets |
| `remoteOpen` | list<TicketEvidence> | yes | All cached remote open tickets |
| `merged` | list<TicketEvidence> | yes | Union deduplicated by canonical ticket ID |
| `sourcesAvailable` | map<source, bool> | yes | Local and remote source availability |
| `freshness` | enum/map | yes | `current`, `stale`, `partial`, or `unavailable` per source |
| `complete` | boolean | yes | True only when a validated source can establish the open set |
| `count` | integer | yes | Must equal `merged` length |

**Rules**:
- Merged set is sorted deterministically by ticket ID.
- Local-only open tickets are included.
- Remote-only open tickets are included.
- Duplicate IDs are merged once; local tracking fields enrich the record.
- Stale/partial entries remain in the list with qualification.
- If no validated source can establish the open set, generation fails closed.
- Over-bound count fails closed; never drop tickets.
- AI cannot add, remove, reorder, or summarize tickets in the mandatory section.

## Entity: TicketEvidence

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `id` | stable ID (`ticket:<key>`) | yes | Exact Jira/ticket key |
| `jiraKey` | string | yes | Existing key validation |
| `summary` | string | yes | Bounded |
| `status` | string | yes | Bounded |
| `priority` | string or null | no | Bounded |
| `nextAction` | string | no | Bounded local field |
| `tracked` | boolean | yes | Local tracking indicator |
| `trackingState` | enum | yes | `active`, `closed`, `jira-only` |
| `source` | enum | yes | `local`, `remote`, `merged` |
| `freshness` | enum | yes | `current`, `stale`, `partial`, `unavailable` |
| `needsReview` | boolean | yes | Existing review flag |

**Rules**: No ticket may be omitted from the mandatory Markdown section because of AI or narrative
relevance. Private local NOC notes are excluded from handover and AI evidence.

## Entity: ShiftNoteEvidence

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `id` | stable ID (`shift-note:<date>:<hash>`) | yes | Deterministic hash |
| `section` | string | yes | Bounded |
| `time` | string or null | no | Existing time shape |
| `text` | string | yes | Bounded |
| `source` | string | yes | Shift notes |
| `availability` | enum | yes | `available`, `partial`, `unavailable` |

## Entity: InvestigationEvidence

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `id` | stable ID (`investigation:<name>`) | yes | Existing safe investigation identifier |
| `name` | string | yes | Bounded |
| `displayTitle` | string | yes | Bounded |
| `lifecycleStatus` | enum | yes | Existing lifecycle status |
| `reviewState` | enum | yes | `reviewed`, `unreviewed`, `rejected` |
| `authoritative` | boolean | yes | True only for reviewed findings |
| `reviewedFinding` | object or null | yes | Existing reviewed finding shape |
| `availability` | enum | yes | Existing projection availability |
| `sourceReference` | object | yes | Shift/name provenance |

**Rules**:
- Reviewed findings may appear in mandatory Investigation Updates.
- Unreviewed/rejected investigations may appear only in advisory evidence or explicit
  non-authoritative lifecycle summaries, never as reviewed findings.
- AI must not promote unreviewed content to reviewed status.

## Entity: DatadogIncidentEvidence

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `id` | stable ID (`incident:<uuid>`) | yes | Existing read-only incident identifier |
| `title` | string | yes | Bounded |
| `state` | string | yes | Existing exact text |
| `severity` | string or null | no | Bounded |
| `sourceUrl` | HTTPS URL | no | Existing validated URL |
| `freshness` | enum | yes | `current`, `stale`, `partial`, `unavailable` |
| `source` | string | yes | Existing read-only snapshot/cache provenance |

**Rules**: Use only already-available read-only incident context; no mutations and no new Datadog
retrieval behavior.

## Entity: StatusDashboardEvidence / ReadinessEvidence

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `id` | stable ID (`status:<date>`, `dashboard:<date>`, `readiness:<date>`) | yes | Exact |
| `available` | boolean | yes | Existing source availability |
| `summary` | object | yes | Bounded read-only projection |
| `freshness` | enum | yes | Existing freshness semantics |
| `blockers` | list<string> | for readiness | Bounded |
| `warnings` | list<string> | for readiness | Bounded |

**Rules**: Status/dashboard summaries exclude private local NOC work notes; only bounded counts,
flags, and operational status are included.

## Entity: HandoverEvidenceReference

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `id` | stable ID | yes | Exact canonical ID |
| `kind` | enum | yes | `shift-note`, `ticket`, `investigation`, `incident`, `status`, `dashboard`, `readiness` |
| `source` | string | yes | Validated source |
| `availability` | enum | yes | `available`, `partial`, `stale`, `unavailable` |
| `authoritative` | boolean | yes | Reviewed facts vs advisory/unreviewed |
| `sourceUrl` | URL or null | no | Sanitized |
| `reviewState` | enum or null | no | Investigation references |
| `freshness` | enum or null | no | Source freshness |

**Allowed citation forms**:
- `shift-note:<shift-date>:<hash>`
- `ticket:<ticket-key>`
- `investigation:<safe-name>`
- `incident:<uuid>`
- `status:<shift-date>`
- `dashboard:<shift-date>`
- `readiness:<shift-date>`
- `datadog-context:<shift-date>` (availability/provenance only; not a citable fact)

IDs are canonical, case-sensitive, and must exactly match a reference with
`availability: available`. URLs, aliases, display names, bare IDs, unavailable IDs, and altered
punctuation are invalid citations.

## Entity: DeterministicHandoverContent

**Purpose**: System-authored mandatory Markdown content assembled before AI.

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `intro` | string | yes | Existing intro shape |
| `sections` | list<HandoverSection> | yes | Existing section parser compatibility |
| `openTicketSection` | section | yes | Contains every merged ticket |
| `closing` | string | yes | Existing closing/signature shape |
| `availabilityDisclosure` | object | yes | Stale/partial/missing/unavailable sources |
| `readinessDisclosure` | object | yes | Blockers/warnings and evidence summary |

**Mandatory section behavior**:
- Summary is deterministic and factual.
- Open Jira Tickets includes every merged open ticket.
- Investigation Updates includes reviewed findings/lifecycle only.
- Next Shift Actions is deterministic from ticket actions/reviewed findings/readiness.
- Open Salesforce Tickets preserves the existing section. A validated source reporting zero yields
  an explicit none; an unavailable source is reported as unavailable, never as zero tickets.
- No AI-authored text appears in any mandatory section.

## Entity: AdvisoryAIOutput

**Purpose**: Bounded, cited AI analysis validated internally. It is not emitted into the final
handover body.

```json
{
  "advisorySummary": ["text with ticket:NOC-556"],
  "operationalRisks": ["text with investigation:checkout-latency"],
  "recommendedFocus": ["text with incident:aadf7955-1945-4ce6-b6ca-41e7fa734a78"],
  "watchItems": ["text with readiness:2026-11-10"]
}
```

**Validation**:
- Exactly four required keys.
- Each value is a non-empty list of non-empty strings; 1–8 items per array.
- Each item ≤2 KiB; total output ≤64 KiB.
- Every item contains at least one exact citation in the bracketed form
  `[evidence:<stable-id>]`, where the stable ID matches `allowedEvidenceIds` byte-for-byte.
- Unsupported, invented, unavailable, shortened, aliased, URL-form, bare-ID, or malformed citations
  fail closed.
- No stale/partial/missing/unavailable evidence may be described as current or complete.
- No credentials, Authorization headers, environment values, or secret-like sentinels.
- No repair, remapping, fuzzy matching, or post-processing.
- Advisory text and `[evidence:...]` markers are never rendered in the final handover; validated
  citation IDs are retained only in `handover-provenance.json`.

## Entity: HandoverPreview

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `shiftDate` | date | yes | Selected shift |
| `preview` | boolean | yes | Always true |
| `evidenceDigest` | string | yes | Canonical digest |
| `intro` | string | yes | Deterministic content |
| `sections` | list<HandoverSection> | yes | Deterministic content |
| `closing` | string | yes | Deterministic closing |
| `evidence` | object | yes | Bounded summary/availability |
| `readiness` | object | yes | Generation gate summary |
| `generationMode` | string | yes | `deterministic-preview` |
| `requiresConfirmation` | boolean | yes | True for subsequent generation |

**Rules**:
- No AI invocation.
- No file creation, replacement, archive, or delivery.
- No state-changing side effects.
- Preview can be generated even if the AI provider is unavailable; generation still requires the
  configured provider.

## Entity: HandoverGenerationRequest

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `confirmed` | boolean | yes | Exactly true |
| `previewDigest` | string or null | no | If supplied, must match current evidence digest |

**Rules**:
- Generation/regeneration requires explicit confirmation.
- A stale preview digest fails closed with `preview-stale`.
- An existing handover without regeneration fails with the existing conflict behavior.
- Regeneration archives the previous Markdown/sidecar and restores both on failure.

## Entity: PersistedHandoverRecord

| File | Purpose | Versioning |
|------|---------|------------|
| `handover-<date>.md` | Authoritative operational/email handover Markdown: established NOC intro, deterministic mandatory sections, closing/signature; no AI-specific sections or internal citation markers | Existing format |
| `handover-provenance.json` | Machine-readable evidence/availability/provider provenance plus advisory validation citations | `formatVersion: "2"` sidecar; additive |
| `archive/handover-<date>-<timestamp>.md` | Existing archive of previous Markdown | Unchanged |
| `archive/handover-provenance-<date>-<timestamp>.json` | Archived sidecar, when present | Additive compatible |

Existing handover records without a sidecar remain readable/deliverable. The sidecar is not delivered
through Microsoft 365.

## Entity: HandoverProvenanceRecord

```json
{
  "formatVersion": "2",
  "shiftDate": "2026-11-10",
  "evidenceDigest": "sha256:...",
  "availability": "partial",
  "provider": {
    "configuredProvider": "deepseek-api",
    "model": "deepseek-flash"
  },
  "advisoryStatus": "completed",
  "advisoryMode": "internal-validation-only",
  "advisoryCitations": ["ticket:NOC-556", "readiness:2026-11-10"],
  "references": {
    "ticket:NOC-556": {
      "kind": "ticket",
      "source": "remote",
      "availability": "available",
      "authoritative": true
    }
  },
  "unavailable": [],
  "generatedAt": "2026-11-10T23:15:00Z"
}
```

**Rules**:
- No credentials, prompts, raw provider payloads, or unbounded evidence.
- References are sanitized and bounded.
- Sidecar absence is tolerated for legacy records.
- Sidecar is system-authored; AI cannot modify it.

## Entity: DeliveryPreview / DeliveryRequest

Existing entities remain unchanged:

- Delivery preview uses the persisted Markdown file.
- Delivery send requires explicit confirmation and validates recipients.
- Microsoft 365 transport behavior is unchanged.
- AI generation is separate; delivery never invokes the AI provider.

## State Transitions

### Preview/generation

```text
previewed -> confirmed -> assembling-evidence -> invoking-provider
          -> validating-advisory -> persisted
          \-> failed (no new record; existing intact)
```

### Regeneration

```text
existing record -> archive verified -> generating replacement
                 -> persisted replacement
                 \-> failed -> restore archived Markdown/sidecar
```

### Delivery (unchanged)

```text
record exists -> delivery preview -> explicit confirmation -> send
              \-> failure reported; local record unchanged
```

### Investigation review boundary

```text
unreviewed/advisory -> never promoted by handover generation
reviewed -> authoritative mandatory content only
```

## Compatibility Rules

- Existing handover Markdown sections, parser, archives, and delivery remain compatible.
- The provenance sidecar is additive and versioned; AI advisory content is not emitted into the
  final handover.
- Existing handover records remain readable, previewable, and deliverable.
- `noc-handover` and Copilot are not required by the generation path.
- Feature 015 read-only Datadog behavior and Feature 016 investigation validation/lifecycle behavior
  remain unchanged.
- Microsoft 365 delivery is out of the AI generation path.
