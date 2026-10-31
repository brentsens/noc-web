# Investigation Lifecycle API Contract

This feature extends the existing FastAPI investigation routes. Route path
parameters identifying a source record always refer to its creation shift and
validated normalized name. The selected shift remains an explicit request or
response value; cross-shift projection does not change the source identity.

## List and Detail

### `GET /api/shifts/{selectedShiftDate}/investigations?view=active|history`

`view` defaults to `active`.

The response retains `shiftDate`, `count`, and `investigations`, and adds
`view`. Each investigation contains a bounded projection including:

- `creationShiftDate`, `sourceReference`, `lifecycleStatus`,
  `lifecycleLabel`, nested `lifecycle.reviewState`, `reviewedFinding`
- `lastLifecycleChangedAt`, `lastLifecycleChangedShiftDate`
- `visibility` (`created_this_shift`, `carried`, `cured_this_shift`, or
  `historical`)
- optional `datadogIncidentReference`
- generation/validation metadata in separate fields

`lifecycleStatus` is always one of `ready_for_review`,
`escalated_to_incident`, or `cured`; its label is derived only from that value.
If operator context cannot be read, the conservative lifecycle value is
`ready_for_review`, `lifecycle.reviewState` is `unavailable`, and an `error`
object explains the unavailable context. This fallback does not make the
investigation reviewable or writable.

The active view excludes cured records from later shifts but may include a
cured-this-shift outcome. The history view retains cured records. Neither view
returns raw generated evidence for carried records.

### `GET /api/shifts/{creationShiftDate}/investigations/{investigationName}?selectedShiftDate={date}`

`selectedShiftDate` is optional and defaults to the creation shift. The route
returns the source investigation and same lifecycle projection. A source record
can be opened from any selected-shift projection using its validated
`sourceReference`.

## Lifecycle Confirmation

### `POST /api/shifts/{creationShiftDate}/investigations/{investigationName}/review`

Request:

```json
{
  "confirmed": true,
  "lifecycleStatus": "escalated_to_incident",
  "finding": "Operator-reviewed finding",
  "selectedShiftDate": "2026-10-31",
  "reviewedBy": "optional operator label"
}
```

`lifecycleStatus` is one of `escalated_to_incident` or `cured` for a transition.
The target `cured` or `escalated_to_incident` requires a non-empty, concise
finding. The UI must ask for explicit confirmation after selection and before
submitting. Selection alone performs no request and no write.

Allowed transitions are `ready_for_review` to `escalated_to_incident` or
`cured`, and `escalated_to_incident` to `cured`. `cured` is terminal. Invalid
transitions, unsafe source identifiers, missing findings, or absent
confirmation fail without changing the prior record. Successful changes update
only local operator context and return the new projection. `generationStatus`,
`validationStatus`, generated content, Datadog, Jira, Shift Notes, Local NOC
Tracking, and email are not modified.

The existing reject action remains a distinct review operation and does not
create a fourth lifecycle state. `POST
`/api/shifts/{creationShiftDate}/investigations/{investigationName}/reject`
requires `confirmed: true` and applies only to unreviewed
`ready_for_review` advisories. It changes `reviewState` to `rejected` while
preserving `lifecycleStatus` and the rest of the operator context. Rejection
does not prevent a later explicitly confirmed lifecycle transition with a
reviewed finding. Reviewed, escalated, and cured records cannot be rejected;
rejected requests fail without writing.

## Datadog Attachment

### `POST /api/shifts/{creationShiftDate}/investigations/{investigationName}/datadog-incident`

Request:

```json
{
  "confirmed": true,
  "incidentId": "IR-24",
  "selectedShiftDate": "2026-10-31"
}
```

The backend reads the shared Feature 009 snapshot without initiating a second
Datadog retrieval. It accepts a new attachment only when cache freshness is
`current`, the investigation is `escalated_to_incident`, the selected incident
is present, and its exact Datadog state is `ACTIVE` or `STABLE`. It stores one
bounded incident reference and returns it. A second attachment is rejected
unless a separately confirmed replacement flow is specified.

The selection UI displays incident ID, title, optional severity, exact state,
URL, and cache freshness. It submits only after explicit incident selection and
confirmation. Existing attached references remain visible with freshness when
the cache is stale, refreshing, or unavailable.

The frontend displays the exact stored URL as “View Datadog Incident” and uses
`target="_blank"` with `rel="noopener noreferrer"`. When a successful current
snapshot omits the attached ID, the UI shows the resolution warning; it does
not update the stored state or local lifecycle.

## Errors and Failure Semantics

| Condition | Response behavior |
|---|---|
| Invalid shift date, unsafe name, invalid lifecycle, or invalid transition | Explicit `400`, `404`, or `422` client error; no write. |
| Missing investigation | `404`; no write. |
| Missing confirmation or required finding | `422` validation error; no write. |
| Snapshot stale, refreshing, unavailable, or incident absent/not ACTIVE or STABLE | Explicit attachment rejection with safe freshness/status metadata; no write. |
| Attachment already exists | `409` conflict; no write. |
| Atomic local write failure | Explicit server error; the previous complete record remains intact. |

Errors must not include raw investigation content, Datadog evidence, credentials,
or absolute filesystem paths.
