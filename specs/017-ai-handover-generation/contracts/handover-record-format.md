# Contract: Handover Record Format and Provenance

**Feature**: `017-ai-handover-generation`
**Scope**: Persisted handover Markdown, internal advisory validation provenance, archive, and
delivery compatibility

## Persisted Files

```text
<selected-shift>/handover/
├── handover-<date>.md
├── handover-provenance.json
└── archive/
    ├── handover-<date>-<timestamp>.md
    └── handover-provenance-<date>-<timestamp>.json
```

Existing records without `handover-provenance.json` remain valid and deliverable.

## Handover Markdown

The existing Markdown format and section parser remain authoritative. New generation produces:

```markdown
Hi Team,

Please see the handover for the <day|night> shift on <date>.

## Summary
<deterministic factual summary and authoritative counts>

## Open Salesforce Tickets
<explicit none, or source unavailable; never a fabricated zero>

## Open Jira Tickets
- NOC-556 — <summary> (<status>, <priority>) — Assignee: <assignee> — Environment: <environment> — Next action: <action>
- NOC-557 — <summary> (<status>, <priority>) — Assignee: <assignee> — Environment: <environment> — Next action: <action>

## Investigation Updates
<reviewed findings and lifecycle only; no advisory or unreviewed promotion>

## Next Shift Actions
<deterministic actions from ticket next actions, reviewed findings, readiness>

Please tag me if any clarification is needed.

Regards,

Brentsen Smith
NOC Engineer

2025 W. Belt Line Rd. #114
Carrollton, TX 75006

[sesami.io](https://www.sesami.io/) | [LinkedIn](https://www.linkedin.com/company/sesami-cash-management-technologies-corporation)
```

**Rules**:
- Mandatory sections are system-authored and contain no AI content.
- The Open Jira Tickets section contains every merged open ticket, including locally tracked
  tickets, remote tickets, and stale/partial entries with qualification.
- The Open Salesforce Tickets section is preserved; a validated zero is explicit, and an unavailable
  source is labeled unavailable rather than represented as zero.
- Investigation Updates contains reviewed findings only.
- The established `Hi Team` intro and exact Brentsen Smith/NOC Engineer signature block are system-authored and restored.
- The final Markdown contains only deterministic mandatory sections; no AI advisory sections or
  `[evidence:...]` markers are emitted.
- Every advisory item cites at least one exact allowed available evidence ID internally.
- No advisory content or internal citation syntax appears in the final handover body.
- The linked `sesami.io | LinkedIn` line is the final nonblank line of the handover; nothing is
  appended after it. Its Markdown links preserve clickable hyperlinks in email/HTML delivery.
- Availability/readiness disclosure is system-authored and cannot be overridden by AI.
- Existing section names and parser behavior remain compatible.
- The closing shape is preserved.

## Provenance Sidecar

`handover-provenance.json`

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
      "source": "merged",
      "availability": "available",
      "authoritative": true,
      "freshness": "current"
    }
  },
  "unavailable": [],
  "generatedAt": "2026-11-10T23:15:00Z"
}
```

**Rules**:
- `formatVersion` starts at `"2"` for the advisory-aware format.
- `evidenceDigest` matches the previewed/generated package.
- `availability` is `complete`, `partial`, or `unavailable`.
- Provider identity/model contains no credentials.
- References are sanitized, bounded, and exact.
- `advisoryStatus` is `completed`; failed generation persists no sidecar.
- The sidecar is not delivered through Microsoft 365.
- Existing records without the sidecar remain readable and deliverable.

## Generation Metadata

The existing handover response shape is preserved. Additive response fields may include:

- `generationMode`: `deterministic-preview` or `ai-advisory`;
- `advisoryStatus`: `completed`;
- `evidenceDigest`;
- bounded `evidence` availability summary.

No raw evidence package, prompt, provider payload, or credential is returned.

## Archive and Regeneration Contract

- Normal generation refuses to overwrite an existing handover.
- Regeneration requires explicit confirmation.
- The previous Markdown is archived using the existing naming/verification behavior.
- When a sidecar is present, it is archived alongside the Markdown.
- If generation fails, both archived files are restored.
- If archive verification or restore fails, generation fails with a controlled error and the
  existing handover remains the best available record.
- Archive behavior is additive; existing archive consumers remain compatible.

## Delivery Compatibility

- Microsoft 365 delivery continues to use the persisted Markdown file only.
- Recipient validation, delivery preview, delivery confirmation, and transport behavior are
  unchanged.
- The provenance sidecar is never delivered.
- Advisory content is delivered only because it is part of the Markdown.
- Delivery never invokes the AI provider.

## Investigation Review Boundary

- Reviewed findings appear only in mandatory authoritative sections.
- Unreviewed or advisory content is not emitted into the final handover; reviewed findings remain
  authoritative and distinguishable.
- AI cannot promote unreviewed findings into reviewed findings.
- Sidecar references mark `authoritative`/`reviewState` so reviewers can distinguish evidence.

## Versioning and Compatibility

- Existing handover Markdown section parsing remains compatible.
- The provenance sidecar is additive and ignored by consumers that do not understand it.
- Sidecar absence is tolerated.
- Consumers that do understand the sidecar can display availability/provenance.
- No existing endpoint response field is removed or renamed.
- `noc-handover`/Copilot-specific provenance is optional compatibility metadata, not a requirement
  for the new format.
