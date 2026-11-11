# Contract: Ollama Provider

**Feature**: `018-ollama-local-provider`
**Scope**: Ollama configuration, generation adapter, probe, and security boundaries

## Configuration

| Setting | Required | Default | Secret |
|---------|----------|---------|--------|
| `NOC_WEB_OLLAMA_BASE_URL` | when Ollama is selected/probed | none | No |
| `NOC_WEB_OLLAMA_MODEL` | No | `qwen3:8b` (documented recommendation) | No |
| `NOC_WEB_OLLAMA_TIMEOUT_SECONDS` | No | 120 seconds (max 300) LAN read/inference deadline | No |
| `NOC_WEB_OLLAMA_CONNECT_TIMEOUT_SECONDS` | No | 5 seconds (max 10) connection deadline | No |

`NOC_WEB_AI_PROVIDER=ollama` explicitly selects Ollama as the configured default. Existing
installations remain on DeepSeek unless explicitly reconfigured. Ollama may also be selected per
request or through explicit local retry.

## Endpoint Validation

The configured base URL MUST:

- be `http` or `https`;
- contain a host;
- contain no username/password;
- contain no query string;
- contain no fragment;
- contain an empty or root path only;
- not include a reverse-proxy subpath in the initial deployment;
- resolve the request only to the configured origin; redirects are rejected.

Invalid configuration reports the local provider unavailable/not-ready without failing core readiness
when the primary provider remains usable.

## Generation Request

The adapter sends one bounded non-streaming generation request to the configured Ollama origin. It
uses no Authorization header, no provider credentials, and no unrelated environment values.

It forwards only:

- the selected model;
- the provider-neutral system prompt;
- the bounded workflow envelope;
- non-streaming JSON output instructions;
- bounded inference options.

No DeepSeek, Datadog, Microsoft 365, or other process secrets are forwarded.

## Generation Response

The adapter accepts only Ollama's `response` field as model output.

- `response` MUST be a non-empty string.
- `response` MUST parse as the JSON object expected by the workflow.
- Missing, empty, non-string, malformed, unsupported, or oversized output fails closed.
- `thinking`, `context`, duration metadata, model-loading metadata, model identity, and all other
  response metadata are ignored completely.
- Thinking-only output has no usable response and fails closed.
- Ignored metadata MUST NOT enter prompts, client responses, investigation content, handover content,
  persisted data, or downstream validators.

### Safe Failure Diagnostics

Ollama generation failures log one fixed stage and the request format, for example:

`Ollama provider rejected response: stage=response-json-invalid format=json-schema`

Allowed stages are `response-envelope-invalid`, `response-field-missing`,
`response-field-empty`, `response-json-invalid`, `response-object-required`,
`response-over-bound`, `http-status-invalid`, and `structured-format-rejected`.
Logs MUST NOT include generated text, prompts, envelopes, evidence, thinking, context, model output,
credentials, environment values, or complete provider payloads. The public invalid-response error
remains `The local AI provider returned an invalid response.`

### Assistant Output Contract

The local Assistant request also supplies a strict JSON Schema through Ollama's generate `format`
field. The schema requires exactly one object with exactly two top-level keys: `aiObservations`
and `recommendations`, both JSON arrays. Wrapper objects and all additional
top-level metadata are forbidden. NOC Web, not the model, owns evidence availability, freshness,
status, and provenance; model-generated `evidence_status`, `evidenceStatus`, `evidence`, `status`,
`freshness`, `availability`, `provenance`, `confidence`, `limitations`, and `metadata` fields are
invalid. Evidence status may appear only naturally inside an observation or recommendation `text`
when the stale-evidence qualifier rule requires it. The model must return an exact two-key object;
no post-generation unwrapping, normalization, key deletion, repair, or retry occurs. The schema
also sets `additionalProperties: false`, requires `text` and `evidenceIds` on every item, requires
at least one evidence ID, and permits the recommendation `route` object only with its exact
`label`, `href`, and `requiresConfirmation` fields.

Valid: `{"aiObservations":[],"recommendations":[]}`

Invalid: `{"aiObservations":[],"evidence_status":"stale","recommendations":[]}`

## Explicit Probe

An explicit probe is the only readiness operation that contacts Ollama before inference.

- It checks endpoint reachability.
- It verifies the configured model is present in Ollama's model list.
- It performs no inference, token generation, or model loading.
- Static health/readiness never invokes the probe.

Probe result fields:

```json
{
  "provider": "ollama",
  "endpointConfigured": true,
  "model": "qwen3:8b",
  "available": true,
  "reason": null,
  "probedAt": "2026-11-11T16:20:00Z"
}
```

Failures use sanitized reasons: `unconfigured`, `invalid-endpoint`, `unreachable`, `refused`,
`timeout`, `model-missing`, or `malformed`.

## Timeouts and Bounds

- Connection deadlines are short and bounded for LAN reachability.
- Read/inference deadlines are bounded and configurable.
- No operation may wait indefinitely on a sleeping or unreachable host.
- Response and output sizes are bounded; oversized content fails closed.
- Redirects are rejected and are not followed to another host.

## Security

- No Ollama authentication secret is required, invented, or persisted.
- Never send Authorization headers, DeepSeek keys, Datadog tokens, Microsoft 365 credentials,
  environment values, or unrelated process secrets.
- Never expose those values or Ollama metadata in client responses, logs, errors, prompts, persisted
  operational files, investigations, handovers, or provenance.
- Local inference remains advisory and cannot modify any external system.
