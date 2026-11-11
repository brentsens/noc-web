# Contract: Investigation Evidence Package

**Feature**: `016-ai-investigation-generation`
**Scope**: Internal bounded package passed to the configured AI provider

## Source

The package MUST be built exclusively from
`backend.services.datadog_evidence.get_incident_evidence(incident_id)`.

The package builder MUST NOT:
- call Datadog directly;
- invoke `noc-inv`, Copilot CLI, or Datadog MCP;
- read raw Datadog provider responses;
- include Authorization headers, Datadog access tokens, provider credentials, or unrelated process
  environment values;
- include unsupported or unvalidated evidence fields.

## Package Shape

```json
{
  "packageVersion": "1",
  "incident": {
    "id": "incident:aadf7955-1945-4ce6-b6ca-41e7fa734a78",
    "kind": "incident",
    "sourceUrl": "https://app.datadoghq.com/incidents/aadf7955-1945-4ce6-b6ca-41e7fa734a78",
    "availability": "available",
    "title": "Checkout latency elevated",
    "state": "ACTIVE",
    "severity": "SEV-2",
    "createdAt": "2026-11-10T22:40:00Z",
    "updatedAt": "2026-11-10T22:45:00Z",
    "detectedAt": "2026-11-10T22:39:00Z",
    "resolvedAt": null,
    "impactScope": "Elevated checkout errors in us-east-1.",
    "customerImpacted": true,
    "fields": {
      "service": "checkout"
    }
  },
  "notebooks": [
    {
      "id": "notebook:16295624",
      "kind": "notebook",
      "sourceUrl": "https://app.datadoghq.com/notebook/16295624",
      "source": "incident_field",
      "availability": "available",
      "title": "Checkout latency runbook",
      "markdown": "Monitor: monitor:150243517 ...",
      "queries": ["avg:checkout.latency{*}"],
      "timeRanges": [],
      "metadata": {
        "created": "2026-11-10T22:00:00Z",
        "modified": "2026-11-10T22:30:00Z"
      }
    }
  ],
  "monitors": [
    {
      "id": "monitor:150243517",
      "kind": "monitor",
      "sourceUrl": "https://app.datadoghq.com/monitors/150243517",
      "source": "notebook",
      "availability": "available",
      "name": "Checkout error rate",
      "type": "metric alert",
      "query": "avg(last_5m):sum:checkout.errors{*}.as_count() > 10",
      "thresholds": {
        "critical": 10
      },
      "tags": ["service:checkout"],
      "state": "Alert",
      "message": "Checkout errors are elevated."
    }
  ],
  "references": {
    "incident:aadf7955-1945-4ce6-b6ca-41e7fa734a78": {
      "id": "incident:aadf7955-1945-4ce6-b6ca-41e7fa734a78",
      "kind": "incident",
      "sourceUrl": "https://app.datadoghq.com/incidents/aadf7955-1945-4ce6-b6ca-41e7fa734a78",
      "source": "incident_field",
      "availability": "available"
    },
    "notebook:16295624": {
      "id": "notebook:16295624",
      "kind": "notebook",
      "sourceUrl": "https://app.datadoghq.com/notebook/16295624",
      "source": "incident_field",
      "availability": "available"
    },
    "monitor:150243517": {
      "id": "monitor:150243517",
      "kind": "monitor",
      "sourceUrl": "https://app.datadoghq.com/monitors/150243517",
      "source": "notebook",
      "availability": "available"
    }
  },
  "unavailable": [],
  "availability": "complete",
  "sizeBytes": 4096,
  "digest": "sha256:..."
}
```

## Stable Identifiers

Only these stable identifier forms are valid citations:

- `incident:<Datadog incident ID>`
- `notebook:<numeric notebook ID>`
- `monitor:<numeric monitor ID>`

Identifiers are canonical, case-sensitive, and must exactly match a key in `references`. URLs,
display titles, bare IDs, and other forms are not valid citations.

## Availability

- `incident` is `available` only when Feature 015 returns validated incident detail for an ACTIVE or
  STABLE incident.
- A referenced notebook/monitor is `available` when Feature 015 retrieved and normalized it.
- A referenced notebook/monitor that cannot be retrieved is included in `unavailable` with its
  stable ID, source URL when available, and a controlled error code.
- `availability` is `complete` when no supplied reference is unavailable; otherwise `partial`.
- Validated incident detail is the minimum required evidence. Missing or unavailable notebooks and
  monitors are labeled partial and do not alone block generation.
- Invalid or unavailable incident detail fails closed.

## Bounds and Minimization

| Bound | Limit |
|-------|-------|
| Total package | ≤256 KiB |
| Notebooks | ≤10 |
| Monitors | ≤10 |
| Per-notebook Markdown | ≤16 KiB |
| Total notebook Markdown | ≤64 KiB |
| Monitor query/message | ≤2 KiB each |
| Incident fields | ≤Feature 015 incident field bounds |
| Tags/thresholds/assets | Feature 015 bounds |

No field is silently truncated. Over-bound evidence fails closed with `evidence-too-large`.

## Secret and Environment Exclusion

The package builder MUST reject or redact:

- values matching configured DeepSeek or Datadog credential sentinels;
- keys or values resembling `Authorization`, `Bearer `, `api_key`, `access_token`, `token`,
  `secret`, or `password`;
- environment dumps or unrelated process settings;
- provider request/response payloads.

A detected credential-like value fails closed with `evidence-credential-detected`. The package is
never logged, persisted, or returned raw to the client.

## Digest

`digest` is a canonical SHA-256 digest over the bounded package excluding the digest field itself.
It is used by the preview store and create revalidation to detect changed evidence. Digest
generation must be deterministic and must not include credentials or non-deterministic timestamps
introduced by the server.

## Validation Checklist

- [ ] Built only from Feature 015 `get_incident_evidence`.
- [ ] Incident valid and ACTIVE/STABLE.
- [ ] All supplied references have stable IDs, source URLs, and availability.
- [ ] Unavailable references are explicit and bounded.
- [ ] Package size and item counts are within bounds.
- [ ] No credential-like content or unrelated environment values.
- [ ] Digest is canonical.
- [ ] Package is suitable for citation validation and system-authored availability disclosure.
