# Data Model: Operator-Controlled Investigation Lifecycle

## Investigation Source Record

An investigation remains stored under its creation shift and normalized name.
That source location is the stable identity used for detail and mutation
requests; later shifts refer to it rather than copying the record.

| Field | Type | Meaning and validation |
|---|---|---|
| `creationShiftDate` | `YYYY-MM-DD` | Shift that created the record; derived from the validated source directory. |
| `investigationName` | Safe normalized identifier | Existing investigation identifier rules apply; never use an unchecked value as a path component. |
| `generationStatus` | Existing generation status | Retained from `generation-status.json`; lifecycle actions do not modify it. |
| `validationStatus` | Existing validation status | Retained as generation/validation metadata; never used as the current lifecycle badge. |
| `reviewState` | Existing review-state value | Separate from lifecycle; new records start `unreviewed`; confirmed escalation/cure records `reviewed`. Existing review/reject semantics remain distinct. |

Generated Markdown, evidence, and validation metadata remain at the source
location and are not rewritten to represent operator lifecycle.

## Operator Lifecycle

The current operator lifecycle is stored with the existing operator-reviewed
context and exposed as `lifecycleStatus`. It is independent of generation,
validation, and `reviewState`.

| Value | Display label | Rules |
|---|---|---|
| `ready_for_review` | Ready for Review | Default for new investigations and conservative migration fallback. Remains visible and blocks handover until explicitly reviewed. |
| `escalated_to_incident` | Escalated to Incident | Requires a non-empty reviewed finding; remains active across shifts. A Datadog attachment is optional. |
| `cured` | Cured | Requires a non-empty reviewed finding; is locally resolved, excluded from later active lists, and remains in history. Terminal. |

The transition graph is forward-only: `ready_for_review` may transition to
`escalated_to_incident` or `cured`; `escalated_to_incident` may transition to
`cured`; `cured` has no outgoing transition. Every transition requires explicit
confirmation. Selecting a dropdown option alone changes no persisted data.

The operator context stores:

| Field | Type | Meaning and validation |
|---|---|---|
| `lifecycleStatus` | Lifecycle enum | Sole source for the current lifecycle label and operational gating. |
| `finding` | String | Existing concise operator-reviewed finding field; trim, require non-empty for escalation/cure, retain its existing length limit, and reject line breaks in the single-line editor. |
| `reviewState` | Existing review-state value | Set to `reviewed` when escalation/cure is confirmed; remains independently represented. |
| `lastLifecycleChangedAt` | UTC timestamp | Set by the backend on confirmed lifecycle change. |
| `lastLifecycleChangedShiftDate` | `YYYY-MM-DD` | Selected shift supplied to the confirmed action; used to classify a cure as occurring this shift. |
| `state` (legacy) | String, optional | Preserve the old free-form state unchanged as migration/history evidence; never use it as the current lifecycle after migration. |

Lifecycle writes update the operator context atomically using the existing
temporary-file-and-replace pattern. A failed write must leave the complete
prior context and lifecycle intact.

### Legacy Migration

For records without `lifecycleStatus`:

1. If review metadata is not explicitly `reviewed`, derive
   `ready_for_review`, regardless of generated Markdown `Status`.
2. For explicitly reviewed records, classify the old reviewed-context `state`
   using normalized exact full-match allowlists. Existing resolved values map
   to `cured`; existing active values map to `escalated_to_incident`.
3. Also recognize the exact legacy value `done (cured)` as cured, as called out
   by the Feature 010 requirement.
4. All unknown, conflicting, malformed, or ambiguous records map to
   `ready_for_review`; no substring or fuzzy matching is allowed.
5. Preserve source evidence, generation metadata, review fields, and the
   original legacy state. Persist migration with an atomic local write; if that
   write fails, preserve the old record and surface the failure.

The exact existing state allowlists and repository evidence are documented in
[research.md](research.md).

## Datadog Incident Reference

At most one bounded reference may be attached to an escalated investigation.
The backend validates the operator-selected incident against the shared
Feature 009 snapshot at confirmation time; no title matching or automatic
selection is permitted.

| Field | Type | Meaning and validation |
|---|---|---|
| `incidentId` | String | Exact ID from the selected snapshot. |
| `url` | Validated URL string | Exact Datadog URL from the selected incident; opened only with `target="_blank"` and `rel="noopener noreferrer"`. |
| `title` | String | Exact incident title from the selected snapshot. |
| `lastKnownState` | `ACTIVE` or `STABLE` | Exact state returned by Feature 009; never inferred or rewritten. |
| `attachedAt` | UTC timestamp | Backend attachment time. |

Severity and cache freshness are shown from the shared snapshot during
selection but are not copied into the persisted reference. Raw Datadog evidence
is never stored in the investigation. Existing references remain visible when
cache freshness is stale or unavailable. A missing ID in a successful CURRENT
snapshot produces the specified resolution warning only; it does not change
`lifecycleStatus` or the last-known state.

## Cross-Shift Projection

The projection is derived from source records and contains no generated
Markdown or raw evidence.

| Field | Type | Meaning |
|---|---|---|
| `selectedShiftDate` | `YYYY-MM-DD` | Shift currently selected in the UI and response. |
| `creationShiftDate` | `YYYY-MM-DD` | Source shift. |
| `sourceReference` | Safe source identity | Creation shift plus validated normalized investigation name; no absolute filesystem path. |
| `lifecycleStatus` | Lifecycle enum | Same current value used by detail, Dashboard, Status, End Shift, and handover. |
| `reviewedFinding` | String or null | Concise operator-owned finding only. |
| `lastLifecycleChangedAt` | UTC timestamp or null | Last confirmed lifecycle change. |
| `lastLifecycleChangedShiftDate` | `YYYY-MM-DD` or null | Selected shift at the last confirmed change. |
| `datadogIncidentReference` | Bounded reference or null | Navigation and lifecycle context only. |
| `visibility` | `created_this_shift`, `carried`, `cured_this_shift`, `historical` | Classification relative to selected shift and requested view. |

The default active view includes new/active records created this shift, carried
ready/escalated records, and cured outcomes from the selected cure shift.
History includes cured records from any shift. Cured records do not appear in
later default active views.

## Handover Projection

Handover consumes the same lifecycle projection:

- `ready_for_review`: blocker and excluded from handover content.
- `escalated_to_incident`: eligible only with reviewed finding; emit concise
  operator-reviewed context in the existing Investigation Updates / Next Shift
  Actions sections.
- `cured`: no future action; optionally emit a concise reviewed outcome only
  when `lastLifecycleChangedShiftDate` equals the selected shift.

Raw generation content, review records, incident evidence, storage metadata,
and absolute source paths are not handover content.
