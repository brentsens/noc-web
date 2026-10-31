# Quickstart: Investigation Lifecycle

## Prerequisites

- Python dependencies are installed as described by the repository.
- Tests use temporary NOC roots and mocked Feature 009 snapshots; they do not
  require live Datadog, Jira, credentials, or operator data.
- For manual UI verification, run the existing noc-web backend and frontend
  against a temporary NOC root.

## Validation Scenarios

### 1. Create, review, and transition lifecycle

1. Create an investigation through the existing confirmed generation flow.
2. Verify list and detail show `Ready for Review`, with generation,
   validation, and review metadata still separate.
3. Select `Escalated to Incident` but cancel its confirmation; verify no request
   is sent and no operator context changes.
4. Confirm with a concise finding; verify list, detail, Dashboard, Status, End
   Shift, and handover readiness show the same lifecycle.
5. Confirm the transition graph: Ready may move to Escalated or Cured;
   Escalated may move to Cured; Cured cannot transition.

### 2. Carry work across shifts and preserve history

1. Create Ready and Escalated source investigations on one shift.
2. Select a later shift and verify both appear as carried with their creation
   shift and safe source reference.
3. Cure one with a reviewed finding on a selected shift. Verify it appears as
   `Cured this shift`, is absent from later active views, and remains in
   history.
4. Confirm later-shift projections contain no copied Markdown or raw evidence.

### 3. Attach a Datadog incident

1. Provide a mocked CURRENT Feature 009 snapshot with an ACTIVE or STABLE
   incident.
2. Verify the selection dialog shows ID, title, available severity, exact
   state, URL, and cache freshness.
3. Cancel confirmation and verify no attachment write. Confirm selection and
   verify only the bounded reference is stored.
4. Verify stale, refreshing, unavailable, absent, RESOLVED, or already-attached
   incidents are rejected for a new attachment.
5. Remove an existing attachment from a successful current test snapshot and
   verify the resolution warning while local lifecycle remains escalated.
6. Verify the Datadog link opens the exact URL with `noopener noreferrer`.

### 4. Verify readiness and handover

1. Verify Ready blocks handover and is excluded from handover content.
2. Verify reviewed Escalated context is concise and appears only in the
   existing investigation update/action sections.
3. Verify Cured does not block End Shift or create future actions; a
   cure-shift outcome may be included without raw content.

## Automated Checks

Run focused tests for lifecycle, cross-shift, attachment, assistant, handover,
readiness, generation, and frontend behavior:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_investigation_lifecycle.py \
  tests/test_investigation_projection.py \
  tests/test_investigation_attachments.py \
  tests/test_investigations.py \
  tests/test_assistant.py \
  tests/test_handover.py \
  tests/test_status.py \
  tests/test_end_shift.py \
  tests/test_dashboard.py \
  tests/test_investigation_generation.py \
  tests/test_frontend_modules.py
```

Run the full repository suite and static checks before completion:

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/python -m compileall -q backend
node --input-type=module --check < frontend/js/api.js
git diff --check
```

The frontend regression suite parses and exercises the changed ES-module entry
points. The direct Node check validates `frontend/js/api.js`. Tests must cover
atomic-write failure, conservative migration, explicit confirmation,
cross-shift paths, attachment state/freshness, and unchanged external-system
state.
