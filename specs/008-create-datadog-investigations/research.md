# Research: Confirmation-Gated Datadog Investigation Creation

**Feature**: [spec.md](spec.md)
**Date**: 2026-10-30

## Existing investigation and propagation boundaries

**Decision**: Extend the existing shift-scoped investigation API and service rather than introducing a parallel record system. Keep inspection read-only and preserve the explicit Review/Reject workflow. Use the existing reviewed-finding projection as the only propagation gate.

**Rationale**: `backend/api/investigations.py` owns list/detail/review/reject routes, while `backend/services/investigations.py` projects shift-scoped records and exposes `get_reviewed_findings()` for downstream consumers. Dashboard, Status, Shift Notes, End Shift, handover, and Assistant context already consume that review boundary. The existing record path is `{NOC_ROOT}/{YYYY-MM-DD}/investigations/{name}/investigation.md`.

**Alternatives considered**:
- Create a separate investigation subsystem: rejected because it would duplicate storage, review state, and downstream gating.
- Treat successful generation as review: rejected because generation must remain advisory and operator review is the authority boundary.

## Command orchestration boundary

**Decision**: Add a backend generation service/adapter around configured `noc-inv`. Invoke only a fixed, non-interactive command contract using an argument array and `shell=False`; pass validated values only as data. Apply a dedicated bounded investigation timeout from the approved configuration profile, separate from short readiness probes. Never fall back to a TTY, prompt automation, or direct Datadog retrieval.

**Rationale**: Readiness currently checks whether `noc-inv` is present, but no invocation adapter or non-interactive contract is implemented in NOC Web. An explicit contract preserves `noc-inv` as the generation authority while isolating the frontend and API from its current executable form. If the deployed command does not implement the contract, return a controlled unavailable result rather than attempting an interactive run.

**Alternatives considered**:
- Reimplement the Datadog/Copilot workflow in FastAPI: rejected because `noc-inv` is authoritative and direct evidence retrieval is out of scope.
- Drive an interactive process or inject terminal input: rejected because it is unsafe, brittle, and not a non-interactive invocation contract.
- Pass arbitrary operator-provided command text or options: rejected because input must not alter command behavior.

## Preview and confirmation

**Decision**: Make preview a stateless, local validation operation with no subprocess, filesystem write, or Notebook fetch. Put the shift date in the shift-scoped route, return normalized values and the logical destination, and require `confirmed: true` on the separate create request. Revalidate all values and duplicate state during creation.

**Rationale**: Existing API routes are shift-scoped, and frontend workflow context already preserves/validates selected shift. Revalidation prevents a stale preview from bypassing current conflict or input checks. The final request is the only path that can invoke generation.

**Alternatives considered**:
- Let preview launch a dry-run of `noc-inv`: rejected because preview must not execute the generator.
- Trust the browser's prior validation: rejected because API boundaries must independently validate untrusted input.
- Add preview tokens or persistent preview records: rejected because stateless validation is sufficient and avoids writes/state before confirmation.

## Validation and publication

**Decision**: Validate generated records for required metadata, exact Notebook URL, shift/name, provenance, required headings, and non-placeholder required sections before exposing them as ready. Use a server-generated staging location and exclusive conflict reservation; publish without overwriting. Keep safe malformed output as a needs-review record; clean temporary files and suppress unsafe/raw diagnostics.

**Rationale**: The current projection validates the title and metadata and handles provenance, but does not enforce the complete generated-output contract. Staging separates temporary command output from durable records and permits validation before publication. Reservation plus final duplicate recheck prevents races and overwrite. A retained malformed record remains inspectable without becoming propagation-eligible.

**Alternatives considered**:
- Write directly into the final record path during generation: rejected because incomplete output could be observed as a completed investigation.
- Delete every malformed result: rejected because safe malformed output must remain available for controlled review.
- Publish malformed content into reviewed-finding consumers: rejected because only explicitly reviewed, validated concise findings may propagate.

## Readiness and configuration

**Decision**: Reuse Feature 005's configuration profile, command catalog, and safe local-storage capability probes. Extend readiness to report `noc-inv`, GitHub Copilot CLI, and investigation-storage availability without invoking the generation workflow or exposing command output.

**Rationale**: `backend/config.py` supplies approved workstation locations and timeout configuration. Generation may outlast the existing short command probe timeout, so use a separate bounded `NOC_WEB_INVESTIGATION_TIMEOUT_SECONDS` setting (default 300, maximum 900). `backend/services/readiness.py` checks configured commands and writable storage safely. It includes `noc-inv` but not Copilot CLI, although health and Start Shift checks already detect `copilot`; readiness must add the missing explicit capability. Do not probe Datadog MCP or authentication directly.

**Alternatives considered**:
- Hard-code a user-home directory or executable: rejected by Feature 005 and the constitution.
- Probe Datadog or run a real investigation during readiness: rejected because readiness must be read-only and must not access external services or credentials.

## Downstream review gates

**Decision**: Keep existing downstream use of reviewed findings; add pending/needs-review visibility to End Shift readiness, but do not append generated output or raw evidence to handover. Refresh/select the created record through the existing Investigations list.

**Rationale**: Current consumers already gate propagation through the service's reviewed-finding projection; End Shift already surfaces review blockers. Creation itself must not modify Shift Notes or generate/deliver handover.

**Alternatives considered**:
- Copy generated text into operational views immediately: rejected because generated output is advisory.
- Add a new handover source or bypass current review state: rejected because it would weaken existing safety boundaries.

## Resolved design questions

- **Notebook URL allowlist**: Use only `https://app.datadoghq.com/notebook/<numeric-id>/<slug>` with one slug segment and no query, fragment, credentials, or extra path.
- **Name normalization**: Trim and lowercase, collapse whitespace and repeated hyphens, then require a leading ASCII letter/digit and an identifier of at most 80 ASCII letters, digits, or hyphens.
- **Failure with partial output**: Preserve only when it can be safely represented as a shift-scoped needs-review record; otherwise remove staging data and return a sanitized failure.
- **List refresh failure**: Report creation and refresh separately; never imply that successful generation failed solely because the subsequent list refresh failed.

## Repository evidence

- Existing investigation routes and explicit confirmation: `backend/api/investigations.py:53-167`.
- Existing inspection, metadata projection, storage path, and reviewed-finding gate: `backend/services/investigations.py:9-26,110-158,225-233`.
- Safe path and atomic review persistence: `backend/services/investigations.py:161-222`.
- Feature 005 configuration and timeout: `backend/config.py:44-51,59-77,100-147`.
- Readiness command catalog and storage probes: `backend/services/readiness.py:13-19,160-225`.
- `noc-inv` is readiness-probed; Copilot is checked in health/Start Shift but not the readiness command catalog: `backend/services/readiness.py:13-19`, `backend/services/health.py:9-18,62-77`.
- Selected-shift context and confirmation helper: `frontend/js/workflow-context.js:1-66,68-143`.
- Central frontend API request/error handling: `frontend/js/api.js:1-35`.
- Test configuration: `pytest.ini:1-3`; run `pytest` from repository root. No Python runtime version is pinned in the repository manifests.
- Existing API errors use FastAPI's `detail` field; frontend `apiRequest()` reads `error.detail`.
