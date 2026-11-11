# Data Model: Ollama Local AI Provider

**Feature**: `018-ollama-local-provider`
**Date**: 2026-11-11

## Scope

This model extends the existing provider-independent AI configuration, readiness, selection, retry,
and provenance structures. It does not replace Assistant, AI Actions, Feature 016 investigation, or
Feature 017 handover contracts.

## Entity Relationships

```text
ProviderConfiguration
  ├── primary DeepSeek configuration (existing)
  └── optional Ollama configuration
        ├── endpoint/model/static readiness
        └── explicit probe result

ProviderSelection
  ├── configured default provider
  ├── explicit per-request selection
  └── explicit Retry with Local AI confirmation

LocalRetrySnapshot
  ├── exact failed-request evidence/envelope
  ├── workflow + shift + request identity
  ├── failed primary provider identity
  └── opaque single-use retry token (10-minute TTL, memory only)

LocalRetryResult
  ├── existing workflow validated output
  ├── provider provenance: ollama + configured model
  └── existing persistence/lifecycle/delivery behavior

ProviderFailure
  ├── primary provider failure -> retry snapshot + optional localRetry metadata
  └── local provider failure -> fail closed; no replacement record
```

## Entity: ProviderConfiguration (extended)

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `identifier` | enum | yes | `deepseek-api`, `github-copilot-cli`, or `ollama` |
| `model` | string | for DeepSeek/Ollama | Existing DeepSeek model rules or configured Ollama model |
| `baseUrl` | string or null | for DeepSeek/Ollama | Validated provider base URL |
| `timeoutSeconds` | integer | yes | Bounded existing provider timeout or Ollama read/inference deadline (default 120, max 300) |
| `ollamaConnectTimeoutSeconds` | integer | when Ollama | Connection deadline (default 5, max 10) |
| `credentialPresent` | boolean | yes | DeepSeek only; Ollama has no auth secret |

**Ollama configuration rules**:
- `NOC_WEB_OLLAMA_BASE_URL` required when Ollama is selected; no hard-coded default.
- `NOC_WEB_OLLAMA_MODEL` defaults to recommended `qwen3:8b` when omitted.
- Base URL: HTTP or HTTPS, host required, no username/password, no query, no fragment, empty/root
  path only. Reverse-proxy subpaths are out of scope for the initial deployment.
- No Ollama authentication secret is required, invented, or persisted.
- Existing installations remain on DeepSeek unless explicitly reconfigured.

## Entity: ProviderReadiness (extended)

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `configuredProvider` | string or null | yes | Active configured provider |
| `readiness` | enum | yes | `ready`, `notReady`, `notConfigured` |
| `label` | string or null | yes | Human-readable provider label |
| `model` | string or null | yes | Configured model |
| `primaryProvider` | object | yes | Static DeepSeek/primary state, no probe |
| `localProvider` | object | yes | Static Ollama state, configured/unconfigured, model |
| `localProbe` | object or null | no | Last explicit probe result only; not part of static readiness |

**Local provider static state**:
- `configured`: endpoint and model configuration present.
- `unconfigured`: missing endpoint/model.
- `invalid`: configuration rejected.
- Static readiness never performs a network call or inference.
- Local unavailability does not fail core readiness while DeepSeek remains usable.

## Entity: OllamaProbeResult

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `provider` | string | yes | Always `ollama` |
| `endpointConfigured` | boolean | yes | Base URL present and valid |
| `model` | string or null | yes | Configured model |
| `available` | boolean | yes | Endpoint reachable and model present |
| `reason` | enum or null | no | `unconfigured`, `invalid-endpoint`, `unreachable`, `refused`, `timeout`, `model-missing`, `malformed` |
| `probedAt` | timestamp | yes | Explicit probe time |

**Rules**:
- Probe checks endpoint reachability and configured model presence in Ollama's model list.
- Probe performs no inference, token generation, or model loading.
- Probe result is sanitized and contains no credentials or response metadata.

## Entity: OllamaResponse

**Purpose**: Bounded provider output derived only from Ollama's `response` field.

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `response` | string | yes | Non-empty string; bounded bytes |
| `parsedOutput` | object | yes | Parsed JSON object passed to existing workflow validators |
| ignored fields | any | no | `thinking`, context arrays, durations, model-loading/model metadata; never consumed |

**Rules**:
- Missing, empty, non-string, malformed, unsupported, or oversized `response` fails closed.
- Thinking-only output has no usable response and fails closed.
- All ignored metadata is discarded and never enters prompts, client responses, records, or validators.
- No Authorization/credential header is sent to Ollama.

## Entity: ProviderSelection

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `mode` | enum | yes | `configured-default`, `per-request`, or `retry-confirmed` |
| `provider` | enum | yes | `deepseek-api`, `github-copilot-cli`, or `ollama` |
| `confirmed` | boolean | for retry | Must be exactly true |
| `retryToken` | string or null | for retry | Opaque, single-use, 10-minute token |

**Rules**:
- DeepSeek remains configured default for existing installations.
- Ollama may be explicitly configured default or explicitly selected.
- No provider is selected automatically after failure.
- Retry with Local AI requires explicit confirmation.

## Entity: LocalRetrySnapshot

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `token` | opaque string | yes | Cryptographically random, single-use |
| `workflow` | enum | yes | `assistant`, `ai-actions`, `investigation`, `handover` |
| `shiftDate` | date string | yes | Existing selected-shift validation |
| `requestIdentity` | object | yes | Workflow request identity and target fields |
| `evidenceSnapshot` | object | yes | Exact validated evidence/envelope used by failed primary request |
| `failedProvider` | string | yes | Primary provider that failed |
| `createdAt` | timestamp | yes | Server time |
| `expiresAt` | timestamp | yes | Created + 10 minutes |
| `status` | enum | yes | `active`, `consumed`, or `expired` |

**Rules**:
- Maximum 32 active snapshots; process memory only.
- No evidence is persisted to disk for retry.
- Snapshot is single-use and expires after 10 minutes.
- Missing/expired/used/mismatched tokens fail closed.
- Snapshot never contains credentials, Authorization headers, environment values, or unrelated data.
- The snapshot is exposed to the client only as an opaque token and availability metadata.

## Entity: ProviderFailure

| Code | Meaning |
|------|---------|
| `provider-not-configured` | Selected provider lacks configuration |
| `provider-not-ready` | Static configuration invalid/incomplete |
| `provider-unavailable` | Endpoint unreachable/refused/auth failure |
| `provider-timeout` | Connect/read/inference deadline elapsed |
| `provider-invalid-response` | Malformed/missing/non-string/oversized/unsupported response |
| `ollama-model-missing` | Configured model not present in explicit probe/invocation |
| `retry-snapshot-expired` | Retry token expired |
| `retry-snapshot-used` | Retry token already consumed |
| `retry-snapshot-unavailable` | Exact evidence snapshot unavailable |

**Rules**: failures are sanitized; no secrets, response metadata, or generated content are exposed.

## Entity: ProviderProvenance (extended)

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `configuredProvider` | string | yes | `ollama` for local output |
| `model` | string or null | yes | Configured Ollama model |
| `providerMode` | enum | yes | `primary`, `local-selected`, or `local-retry` |
| existing investigation/handover provenance fields | unchanged | yes | Existing contracts remain authoritative |

**Rules**:
- Local output MUST be identified as `ollama`, never DeepSeek/Copilot/reviewed/deterministic.
- Existing investigation/handover provenance files remain compatible; provider fields are additive.
- No credentials or Ollama metadata are persisted in provenance.

## Existing Workflow Outputs

The following remain authoritative and provider-independent:

- Assistant/AI Actions schema, evidence IDs, stale rules, credential exclusion, response bounds.
- Feature 016 exact citations, partial/stale handling, lifecycle, review boundaries, persistence.
- Feature 017 bracketed citations, stale/partial qualification, count-claim rejection, deterministic
  mandatory sections, all-open-ticket inclusion, final handover format, provenance, delivery.
- Preview/store/digest rules for investigations and handover.
- Microsoft 365 delivery and Datadog read-only behavior.

## State Transitions

### Provider selection/primary request

```text
configured/selected provider -> primary request
  -> success (discard retry snapshot)
  -> failure (fail closed; create bounded retry snapshot if local provider configured)
```

### Local retry

```text
retry offered -> operator confirmation -> consume snapshot
  -> local inference -> existing validators
      -> success: existing workflow persistence/provenance
      -> failure: fail closed, no replacement record, prior records unchanged
```

### Retry snapshot lifecycle

```text
created -> active
active -> consumed (single local retry attempt)
active -> expired (10 minutes)
```

### Local probe

```text
static readiness (no network) -> explicit probe
  -> endpoint reachable + model present -> available
  -> unconfigured/invalid/unreachable/refused/timeout/model-missing -> unavailable
```

## Compatibility Rules

- Existing DeepSeek/Copilot provider behavior and existing installations remain unchanged.
- Existing workflows remain usable when Ollama is absent/unavailable.
- Local provider selection/retry is additive and does not remove existing fields.
- Existing investigation/handover records remain readable, reviewable, and deliverable.
- No local inference may mutate Datadog, Jira, tickets, investigations, shift notes, handover state,
  Microsoft 365 objects, recipients, or other external systems.
