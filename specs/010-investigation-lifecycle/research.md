# Research: Operator-Controlled Investigation Lifecycle

## Decision: Keep generation metadata and operator lifecycle separate

**Decision**: Preserve `generation-status.json` as generation and validation
metadata. Store the operator-controlled lifecycle, reviewed finding, change
timestamp, and bounded Datadog incident reference with the existing
operator-reviewed context for the source investigation. Use `lifecycleStatus`
as the only current lifecycle value; retain legacy free-form state only as
migration evidence, never as the current badge.

**Rationale**: Generation currently writes `generationStatus`,
`validationStatus`, and provenance independently (`backend/services/
investigation_generation.py:476-487`). The investigation projection already
reads review state and finding separately (`backend/services/investigations.py:
87-113`). Review context is written through a temporary sibling file and
replacement (`backend/services/investigations.py:258-312`), providing a local
atomic-write pattern that can preserve existing metadata.

**Alternatives considered**: Rewriting generated Markdown or generation status
to encode lifecycle was rejected because it conflates AI validation with
operator authority and risks changing original records. A second lifecycle
sidecar was rejected in favor of keeping the existing single operator-context
write boundary.

## Decision: Derive cross-shift views from source investigations

**Decision**: Build a bounded active/history projection from the original
shift-scoped investigation records. Keep each investigation at its creation
location; projections carry only source reference, creation shift, lifecycle,
reviewed finding, and bounded attachment reference. Do not replicate generated
Markdown or raw evidence into later shifts.

**Rationale**: Current list and detail reads are scoped to one selected shift
(`backend/services/investigations.py:225-257`). Generation stores each source
record below its creation shift (`backend/services/investigation_generation.py:
233-244`). Dashboard, Status, End Shift, and handover currently reconstruct
different investigation subsets (`backend/services/dashboard.py:55-68`,
`backend/services/status.py:143-233`, `backend/services/end_shift.py:47-73`,
`backend/services/handover.py:563-570`). A shared projection is needed to
prevent conflicting status and visibility.

**Alternatives considered**: Copying records into every shift was rejected
because it duplicates raw evidence and creates competing lifecycle values. A
second independently maintained cross-shift index was rejected because it can
drift from source records; derive the index from source metadata unless later
scale evidence requires a cache.

## Decision: Reuse the Feature 009 incident snapshot

**Decision**: Read incident options from the existing shared incident snapshot;
do not add another Datadog retrieval path. Require a current cache and exact
`ACTIVE` or `STABLE` incident state for new attachments. Preserve the exact
provided URL, state, title, and ID in a bounded reference. If a successful
current snapshot no longer contains an attached incident, show the specified
resolution warning without changing the local lifecycle.

**Rationale**: Feature 009 already exposes one bounded snapshot with `incidents`,
`count`, refresh timestamps, freshness, and controlled error values. It retains
`ACTIVE` and `STABLE`, excludes `RESOLVED` only after a successful refresh, and
preserves last-known incidents on failed refreshes
(`backend/services/datadog_incidents.py:429-464, 547-565`; API contract in
`specs/009-live-datadog-incident-awareness/contracts/incidents-api.md`).
Reusing it preserves the source-of-truth boundary and avoids a second external
call.

**Alternatives considered**: Direct Datadog access, an independent incident
cache, title matching, and attachment from stale data were rejected because
they bypass the approved shared snapshot or cannot establish a current,
operator-selected incident.

## Decision: Make lifecycle the common operational projection

**Decision**: Update the existing investigation projection and its consumers so
Dashboard, Status, End Shift, investigation list/detail, and handover all use
the same `lifecycleStatus`. Ready-for-review work remains a blocker and is
excluded from handover. Reviewed escalations may contribute concise operator
context; cured work is excluded from later active views and future actions,
with an optional concise outcome in its cure shift.

**Rationale**: Status currently creates investigation review blockers from
generation and validation metadata (`backend/services/status.py:196-233`),
End Shift aggregates `needsReview` (`backend/services/end_shift.py:47-73`),
and handover filters by review state, validation state, and free-form reviewed
state (`backend/services/handover.py:563-570`). Updating a common projection
and these consumers prevents the current list/detail/readiness contradictions.

**Alternatives considered**: Keeping independent status calculations in each
consumer was rejected because it would preserve inconsistent badges and
handover gates. Including raw generated content or review records in handover
was rejected because only bounded, reviewed operator context is authoritative.

## Decision: Migrate conservatively and only through local atomic writes

**Decision**: Derive legacy lifecycle from review metadata and the existing
exact reviewed-state classifications only. For reviewed records, map the
existing exact active-state allowlist to `escalated_to_incident` and the exact
resolved-state allowlist to `cured`; unreviewed, malformed, or otherwise
ambiguous records become `ready_for_review`. Never infer lifecycle from
Markdown `Status` alone. Preserve all generation and review history. Save
confirmed lifecycle changes as a complete local update; on failure, retain the
previous record and lifecycle.

**Rationale**: Legacy records may contain `investigation.md`,
`generation-status.json`, and `reviewed-context.json` independently
(`tests/test_investigations.py:9-28, 47-73, 107-125`). The existing handover
classifier already uses normalized, exact full-match allowlists for resolved
and active reviewed-state values (`backend/services/handover.py:43-52,
145-150`). It recognizes resolved values `cured`, `done`, `resolved`,
`complete`, `completed`, `closed`, `fixed`, `recovered`, `cleared`,
`remediated`, `fully cured`, `fully resolved`, and `self-recovered`; active
values are `active`, `open`, `ongoing`, `in progress`, `investigating`,
`monitoring`, `escalated`, `unresolved`, `follow-up required`, and `follow up
required`. The user-specified legacy literal `Done (Cured)` is not in this
existing list and will be added as one exact full-match cured value. Fixtures
demonstrate `Active`, `monitoring`, and `Cured`
(`tests/test_handover.py:376-422, 414-421, 731-735`;
`tests/test_investigations.py:53-70`). Markdown `Status` is parsed verbatim
without classification (`backend/services/investigations.py:22-33, 168-208`).
Reusing only the existing exact reviewed-context classifier preserves
demonstrated active/cured behavior without fuzzy matching; unknown values
remain `ready_for_review`.

**Alternatives considered**: Fuzzy text matching, using generated Markdown
status as lifecycle, or defaulting every reviewed record to cured were rejected
because they can silently hide active work or turn generated content into
operator authority. Overwriting source investigation files was rejected
because it would discard review history or generated evidence.
