# Contract: Handover Evidence Package

**Feature**: `017-ai-handover-generation`
**Scope**: Internal bounded evidence package used for deterministic assembly and advisory citations

## Source Boundary

The package MUST be built only from validated NOC Web services:

- shift notes: `backend/services/shift_notes.py`;
- local open tickets: `backend/services/tickets.py`;
- remote open-ticket cache: `backend/services/jira_ticket_queue.py` and
  `backend/services/jira_cache.py`;
- reviewed findings/lifecycle: `backend/services/investigations.py`;
- already-available Datadog incident snapshot: `backend/services/datadog_incidents.py`;
- status/dashboard projections: `backend/services/status.py` and
  `backend/services/dashboard.py`;
- readiness/preflight: `backend/services/end_shift.py` and `backend/services/readiness.py`.

It MUST NOT:
- invoke `noc-handover`, Copilot CLI, or Datadog MCP;
- call raw Datadog mutation endpoints;
- fetch new Datadog incident context beyond what is already available;
- include raw provider payloads, credentials, Authorization headers, unrelated environment values, or
  unsupported fields;
- omit, truncate, or AI-summarize any open ticket.

## Package Shape

```json
{
  "shiftDate": "2026-11-10",
  "packageVersion": "1",
  "shiftNotes": [
    {
      "id": "shift-note:2026-11-10:4f2a9c1d3e7b",
      "section": "Operational Events",
      "time": "14:20",
      "text": "Checkout latency recovered.",
      "source": "shift-notes",
      "availability": "available"
    }
  ],
  "tickets": {
    "localOpen": [],
    "remoteOpen": [],
    "merged": [
      {
        "id": "ticket:NOC-556",
        "jiraKey": "NOC-556",
        "summary": "Superior US deposits shown in SES but not received",
        "status": "In Progress",
        "priority": "High",
        "nextAction": "Confirm response from dispatch.",
        "tracked": true,
        "trackingState": "active",
        "source": "merged",
        "freshness": "current",
        "needsReview": false
      }
    ],
    "sourcesAvailable": {
      "local": true,
      "remote": true
    },
    "freshness": {
      "local": "current",
      "remote": "stale"
    },
    "complete": true,
    "count": 1
  },
  "investigations": [
    {
      "id": "investigation:checkout-latency",
      "name": "checkout-latency",
      "displayTitle": "Checkout latency",
      "lifecycleStatus": "escalated_to_incident",
      "reviewState": "reviewed",
      "authoritative": true,
      "reviewedFinding": {
        "finding": "Limiter misconfiguration confirmed.",
        "state": "Monitoring"
      },
      "availability": "available",
      "sourceReference": {
        "creationShiftDate": "2026-11-09",
        "investigationName": "checkout-latency"
      }
    }
  ],
  "datadogIncidents": [],
  "status": {
    "id": "status:2026-11-10",
    "available": true,
    "summary": {},
    "freshness": "current"
  },
  "dashboard": {
    "id": "dashboard:2026-11-10",
    "available": true,
    "summary": {},
    "freshness": "current"
  },
  "readiness": {
    "id": "readiness:2026-11-10",
    "available": true,
    "summary": {},
    "freshness": "current",
    "blockers": [],
    "warnings": []
  },
  "references": {
    "ticket:NOC-556": {
      "id": "ticket:NOC-556",
      "kind": "ticket",
      "source": "merged",
      "availability": "available",
      "authoritative": true,
      "freshness": "current"
    }
  },
  "unavailable": [],
  "availability": "partial",
  "sizeBytes": 4096,
  "digest": "sha256:..."
}
```

## Stable Evidence IDs

Only these forms are valid citation IDs:

- `shift-note:<shift-date>:<deterministic-hash>`
- `ticket:<ticket-key>`
- `investigation:<safe-investigation-name>`
- `incident:<Datadog-incident-id>`
- `status:<shift-date>`
- `dashboard:<shift-date>`
- `readiness:<shift-date>`
- `datadog-context:<shift-date>` (context availability/provenance; not a citable fact)

IDs are canonical, case-sensitive, and must exactly match a key in `references` with
`availability: available`. AI citations must use the exact bracketed form
`[evidence:<stable-id>]`; sentence punctuation belongs after the closing `]`. URLs, display names,
aliases, bare/unbracketed IDs, unavailable IDs, shortened IDs, altered punctuation, whitespace
inside brackets, and nested brackets are invalid citations.

## Ticket Completeness

- `merged` is the deterministic union of locally tracked open tickets and all remote cached open
  tickets, deduplicated by canonical ticket key.
- Local-only open tickets are included.
- Remote-only open tickets are included.
- Stale/partial remote entries are included with qualification; the list is never silently reduced.
- If neither source can establish the open set, `complete` is false and generation fails closed.
- If the ticket count exceeds the bound, generation fails closed with `tickets-over-bound`.
- The mandatory Open Tickets section contains every `merged` ticket in deterministic order.
- AI cannot add, remove, reorder, or summarize tickets in the mandatory section.
- Private local NOC notes and local-work notes are excluded from the handover and AI evidence
  package; only bounded operational counts/flags are included from status/dashboard summaries.

## Investigation Review Boundary

- Reviewed findings and lifecycle state are supplied with `reviewState: reviewed` and
  `authoritative: true`.
- Unreviewed/rejected investigations may be supplied with `authoritative: false` for advisory
  synthesis only.
- Deterministic Investigation Updates MUST contain only reviewed findings.
- AI MUST NOT describe unreviewed or advisory content as reviewed or authoritative.

## Availability

- `availability` is `complete`, `partial`, or `unavailable` based on source health and missing
  evidence.
- Stale, partial, missing, and unavailable sources are listed in `unavailable` with controlled
  reason codes.
- The handover MUST include system-authored availability disclosure.
- AI output MUST NOT describe stale/partial/missing/unavailable evidence as current or complete.

## Bounds and Minimization

| Bound | Limit |
|-------|-------|
| Total package | ≤1 MiB |
| Open tickets | ≤500 |
| Shift-note entries | ≤2,000 |
| Investigations | ≤200 |
| Datadog incident context items | ≤100 |
| Per-entry text | Follows existing source bounds |

No ticket or mandatory evidence item may be silently truncated or dropped. Over-bound content fails
closed.

## Secret and Environment Exclusion

The package builder MUST reject or redact:

- configured DeepSeek or Datadog credential sentinels;
- keys/values resembling `Authorization`, `Bearer `, `api_key`, `access_token`, `token`, `secret`,
  or `password`;
- environment dumps or unrelated process settings;
- provider request/response payloads.

A detected credential-like value fails closed with `evidence-credential-detected`. The package is
never logged, persisted raw, or returned to the client.

## Digest

`digest` is a canonical SHA-256 over the bounded package excluding the digest and size fields. It is
returned by deterministic preview and used to reject stale previews at generation time.

## Validation Checklist

- [ ] Built only from validated NOC Web services and already-available Datadog context.
- [ ] Ticket list is the complete union, deduplicated, sorted, and all entries included.
- [ ] Source availability and freshness are explicit.
- [ ] Reviewed findings are separated from unreviewed/advisory evidence.
- [ ] Stable IDs are unique and match the allowed forms.
- [ ] Package bounds are enforced without truncation.
- [ ] No credential-like content or unrelated environment values.
- [ ] Canonical digest is deterministic.
- [ ] No Datadog mutation is possible through the package.
