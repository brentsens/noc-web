# Phase 0 Research: Ollama Local AI Provider

**Feature**: `018-ollama-local-provider`
**Date**: 2026-11-11
**Status**: Complete — technical unknowns resolved

## Decision 1: Extend the existing provider architecture rather than build a parallel AI path

**Decision**: Extend `backend/services/ai_provider.py` with `ollama` as a supported provider identifier,
configuration, static readiness, and runtime resolution. Preserve DeepSeek as the default for existing
installations and add explicit configuration/per-request selection for Ollama.

Configuration:
- `NOC_WEB_AI_PROVIDER` may explicitly select `ollama` as the configured default.
- `NOC_WEB_OLLAMA_BASE_URL` is required when Ollama is selected and has no hard-coded default.
- `NOC_WEB_OLLAMA_MODEL` defaults to documented recommended `qwen3:8b` when omitted.
- `NOC_WEB_OLLAMA_TIMEOUT_SECONDS` defaults to 120 seconds (max 300) for LAN read/inference; a
  separate connection deadline defaults to 5 seconds (max 10).
- Existing DeepSeek configuration and defaults remain unchanged.

**Rationale**: All workflows already use the provider-independent runtime and validator contracts.
Reusing them ensures local inference cannot bypass or duplicate safety rules.

**Alternatives considered**:
- Separate Ollama workflow/service — rejected: duplicates validators and risks divergent safety.
- Change the global default to Ollama — rejected: existing installations must remain on DeepSeek and
  no automatic migration may occur.
- Hard-code a localhost URL — rejected by the DHCP/LAN requirement.

## Decision 2: Implement a bounded Ollama adapter that consumes only `response`

**Decision**: Add `backend/services/ollama_provider.py` using Ollama's non-streaming generation
endpoint. The adapter:

- sends the provider-neutral envelope and system prompt;
- requests non-streaming JSON output;
- accepts only a non-empty string `response` field;
- parses that field into the expected provider object;
- ignores `thinking`, `context`, duration, model-loading, model identity, and every other response
  metadata field;
- rejects missing/non-string/empty response, malformed JSON, unsupported content, and oversized
  response/output;
- sends no Authorization header and no DeepSeek/Datadog/M365 credentials;
- refuses redirects and uses bounded connection/read deadlines.

**Rationale**: `response` is the only model-output field. Ignoring all metadata prevents thinking or
provider internals from entering prompts, client responses, persisted records, or downstream
validators.

**Alternatives considered**:
- Parse `thinking` as fallback output — rejected: thinking is not usable output/evidence.
- Accept arbitrary Ollama metadata — rejected: expands the contract and risks leaking internals.
- Streaming responses — rejected for the initial bounded request/response contract.

## Decision 3: Require explicit selection/retry; never automatically fall back

**Decision**: A DeepSeek failure remains fail-closed. Local inference requires one of:

- Ollama explicitly configured as the default provider;
- explicit per-request provider selection;
- explicit **Retry with Local AI** confirmation after a primary-provider failure.

No automatic fallback or automatic retry is permitted. Retry UI is shown only after the primary
failure and requires confirmation immediately before local inference.

**Rationale**: The operator must understand when a different provider is used. Automatic fallback
would hide provider failures and change the evidence/authority path invisibly.

**Alternatives considered**:
- Automatic DeepSeek-to-Ollama fallback — rejected by the feature description.
- Automatic retry after failure — rejected; requires explicit confirmation.
- Silent provider substitution — rejected; provenance and operator trust depend on explicit selection.

## Decision 4: Use a bounded, exact failed-request retry snapshot

**Decision**: Add `backend/services/local_retry.py` with a process-local retry store:

- 10-minute TTL;
- maximum 32 active snapshots;
- cryptographically random opaque retry token;
- single-use snapshots;
- in-memory only; no disk, log, or operational-data persistence;
- exact failed-request evidence/envelope, workflow kind, shift, request identity, provider identity
  that failed, and creation/expiry timestamps;
- no secrets, prompts returned to clients, or unrelated environment values.

Assistant/AI Actions capture the exact provider envelope. Investigation generation captures the exact
previewed evidence package and request. Handover generation captures the exact evidence package and
advisory envelope. A failed primary request exposes `localRetry` availability plus the opaque token;
successful primary requests discard the snapshot. Expired, missing, used, or mismatched tokens fail
closed.

**Rationale**: The local retry must use the evidence the operator reviewed, not a silently fresh
dataset. A bounded in-memory snapshot preserves exactness without persisting sensitive operational
evidence.

**Alternatives considered**:
- Re-fetch evidence on retry — rejected: could silently change evidence.
- Persist retry snapshots — rejected: unnecessary operational-data exposure.
- Long-lived retry tokens — rejected: bounded operator retry window.

## Decision 5: Reuse every existing workflow validator

**Decision**: Invoke Ollama through the same service-level validation path as DeepSeek:

- Assistant/AI Actions: existing schema, evidence IDs, stale rules, secret exclusion, and output
  bounds.
- Feature 016 investigation generation: existing exact citation, partial/stale, lifecycle,
  provenance, and persistence rules.
- Feature 017 handover advisory generation: existing bracketed citations, stale/partial
  qualification, count-claim rejection, deterministic mandatory sections/all tickets, and provenance.
- Local output receives no extra authority and cannot mark itself reviewed or deterministic.

**Rationale**: Provider choice must never determine validation strength. Reusing the same validators
prevents a weaker local path.

**Alternatives considered**:
- Local-specific validators — rejected: duplicate and drift from authoritative contracts.
- Skip AI validation for local models — rejected: unsafe and violates feature requirements.

## Decision 6: Separate static readiness from explicit local probing

**Decision**: Add static primary/local provider readiness and an explicit probe:

- Static readiness reads configuration only: endpoint configured/unconfigured, model, local provider
  static readiness. It never calls Ollama.
- An explicit probe performs a bounded `/api/tags` request, checks endpoint reachability and whether
  the configured model appears in Ollama's model list, and returns a sanitized availability result.
  It performs no inference/model loading.
- Local provider unavailability is warning/optional and does not fail core readiness while DeepSeek
  remains usable.
- UI exposes primary provider, optional local provider, endpoint/model, probe result, and retry
  availability distinctly.

**Rationale**: Static pages must stay fast and safe when the gaming PC is asleep. Operators still need
an intentional way to check local availability.

**Alternatives considered**:
- Probe automatically from health/status — rejected by the no-inference/static-readiness requirement.
- Minimal inference probe — rejected: loads the model and is unnecessarily expensive.
- Endpoint-only probe — rejected: would report available without the configured model.

## Decision 7: Validate endpoints, bound networking, and exclude secrets

**Decision**: The Ollama base URL validator accepts only HTTP/HTTPS base origins with a host, no
embedded credentials, no query, no fragment, and an empty/root path. Reverse-proxy subpaths are out of
scope for the initial deployment. The adapter rejects redirects and never follows a different host.
Connect/read deadlines are explicit and bounded. No Ollama authentication secret is used, invented,
or persisted. Only content-type/accept headers are sent; no Authorization or process secrets.

**Rationale**: The host address may change via DHCP, so it must be configurable, but the request
destination must always remain the validated configured origin. Bounded deadlines prevent indefinite
waits on sleeping hosts.

**Alternatives considered**:
- Allow arbitrary paths/redirects — rejected: expands SSRF/credential-forwarding risk.
- Reuse DeepSeek Authorization handling — rejected: Ollama needs no auth and must not receive secrets.
- Unbounded inference waits — rejected by LAN timeout requirements.

## Decision 8: Record explicit Ollama provenance

**Decision**: Provider provenance records `ollama` and the configured model in existing response and
persisted metadata. Local output is never labeled DeepSeek, Copilot, reviewed operator content, or
deterministic system-authored evidence. Investigation/handover provenance remains additive and
backward compatible.

**Rationale**: Operators and reviewers must know which provider produced advisory content.

**Alternatives considered**:
- Reuse DeepSeek identifier for local output — rejected: misleading.
- Hide provider identity — rejected: defeats auditability.

## Decision 9: Add provider selection/retry to the existing API/UI contracts

**Decision**: Add optional provider selection and workflow-specific retry fields without breaking
existing success contracts:

- Assistant/AI Actions: optional explicit provider selection; failure responses may include
  `localRetry` metadata; retry endpoint accepts the opaque token and confirmation.
- Investigation generation: explicit configured/selected provider or retry token; exact preview
  evidence and existing create confirmation rules remain.
- Handover generation: explicit configured/selected provider or retry token; exact evidence snapshot,
  preview digest, generation/regeneration confirmation, and archive behavior remain.
- Shared frontend provider status/probe and Retry with Local AI confirmation UI.

**Rationale**: Provider selection and retry must be visible and deliberate in the existing workflows,
not hidden in a parallel UI.

**Alternatives considered**:
- API-only retry with no UI — rejected: operators need explicit confirmation/visibility.
- New workflow pages — rejected: duplicates existing UX and contracts.

## Decision 10: Test with fake Ollama servers and deterministic snapshots

**Decision**: Add tests using fake HTTP transports/Ollama responses for:

- endpoint/model configuration, `qwen3:8b`, invalid endpoints, redirects, unexpected hosts;
- unreachable/sleeping/refused/timeout/missing-model/malformed/missing/non-string/oversized response;
- thinking/context/duration/model metadata exclusion;
- retry snapshot TTL/bounds/single-use/exact evidence;
- explicit selection and retry confirmation/no automatic fallback;
- Assistant, AI Actions, investigation, and handover validator compatibility;
- provenance, secrets, zero external mutations, static readiness/probe separation;
- DeepSeek default/no automatic migration.

**Rationale**: Real LAN inference is non-deterministic and may be unavailable. Injected transports
prove fail-closed behavior and metadata/secret boundaries without live hosts.

**Alternatives considered**:
- Live Ollama integration tests in the default suite — rejected: environment-dependent and slow.
  Optional manual quickstart coverage may exercise a real host.
