import json

import pytest

from fastapi.testclient import TestClient

from backend.app import app
from backend.services import dashboard, handover, investigations, shift_notes, status


SHIFT_DATE = "2099-12-31"


def _investigation(noc_root, source="noc-inv"):
    directory = noc_root / SHIFT_DATE / "investigations" / "memory"
    directory.mkdir(parents=True)
    (directory / "investigation.md").write_text(
        f"""# Investigation: Memory pressure
- Status: active
- Source of truth: {source}
- Datadog Notebook: https://example.test/notebook/123

## Summary
raw Datadog log body must never become an API field
""",
        encoding="utf-8",
    )
    if source == "noc-inv":
        (directory / "noc-inv.log").write_text(
            "raw secret-like source output", encoding="utf-8"
        )
    return directory


def test_investigation_projection_is_read_only_and_excludes_raw_evidence(noc_root):
    _investigation(noc_root)

    result = investigations.get_investigation(SHIFT_DATE, "memory")

    assert result["evidence"] == {
        "provenance": "noc-inv",
        "availability": "available",
        "access": "read-only",
        "reference": "https://example.test/notebook/123",
    }
    assert result["advisory"]["available"] is True
    assert "summary" not in result
    assert "raw Datadog" not in str(result)


def test_review_requires_confirmation_and_only_publishes_concise_context(noc_root):
    directory = _investigation(noc_root)
    client = TestClient(app)

    response = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/memory/review",
        json={
            "confirmed": False,
            "lifecycleStatus": "escalated_to_incident",
            "finding": "Memory is high",
            "selectedShiftDate": SHIFT_DATE,
        },
    )

    assert response.status_code == 422
    assert not (directory / "reviewed-context.json").exists()

    response = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/memory/review",
        json={
            "confirmed": True,
            "lifecycleStatus": "escalated_to_incident",
            "finding": "Memory is high",
            "selectedShiftDate": SHIFT_DATE,
        },
    )

    assert response.status_code == 200
    assert response.json()["reviewedFinding"]["finding"] == "Memory is high"
    assert investigations.get_reviewed_findings(SHIFT_DATE) == [{
        "investigation": "memory",
        "finding": "Memory is high",
        "state": "Escalated to Incident",
        "reviewedAt": response.json()["reviewedFinding"]["reviewedAt"],
        "reviewedBy": "operator",
        "lifecycleStatus": "escalated_to_incident",
    }]


def test_non_noc_inv_or_copilot_source_cannot_be_reviewed(noc_root):
    _investigation(noc_root, source="Jira ticket")

    try:
        investigations.review_investigation(
            SHIFT_DATE, "memory", "Should not publish", "blocked"
        )
    except ValueError as error:
        assert "noc-inv or Copilot MCP" in str(error)
    else:
        raise AssertionError("Unsupported evidence provenance was accepted")


def test_rejected_advisory_is_not_propagated(noc_root):
    _investigation(noc_root)
    client = TestClient(app)

    response = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/memory/reject",
        json={"confirmed": True},
    )

    assert response.status_code == 200
    assert response.json()["lifecycle"]["reviewState"] == "rejected"
    assert investigations.get_reviewed_findings(SHIFT_DATE) == []


@pytest.mark.parametrize(
    "lifecycle_status",
    ["escalated_to_incident", "cured"],
)
def test_reject_cannot_reset_lifecycle_or_discard_operator_context(
    noc_root,
    lifecycle_status,
):
    directory = _investigation(noc_root)
    original_context = {
        "reviewState": "reviewed",
        "lifecycleStatus": lifecycle_status,
        "finding": "Operator-reviewed finding",
        "state": "legacy state",
        "reviewedAt": "2026-10-31T12:00:00+00:00",
        "reviewedBy": "operator",
        "lastLifecycleChangedAt": "2026-10-31T12:00:00+00:00",
        "lastLifecycleChangedShiftDate": SHIFT_DATE,
        "datadogIncidentReference": {
            "incidentId": "IR-24",
            "url": "https://app.datadoghq.com/incidents/24",
            "title": "API latency",
            "lastKnownState": "STABLE",
            "attachedAt": "2026-10-31T12:01:00+00:00",
        },
    }
    context_file = directory / "reviewed-context.json"
    context_file.write_text(json.dumps(original_context), encoding="utf-8")
    client = TestClient(app)

    response = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/memory/reject",
        json={"confirmed": True},
    )

    assert response.status_code == 422
    assert json.loads(context_file.read_text(encoding="utf-8")) == original_context
    assert investigations.get_investigation(SHIFT_DATE, "memory")["lifecycleStatus"] == lifecycle_status


def test_reject_preserves_ready_context_and_does_not_block_operator_transition(noc_root):
    directory = _investigation(noc_root)
    original_context = {
        "reviewState": "unreviewed",
        "lifecycleStatus": "ready_for_review",
        "finding": "",
        "state": "legacy state",
        "reviewedBy": "previous operator",
        "lastLifecycleChangedAt": None,
        "lastLifecycleChangedShiftDate": None,
        "operatorMetadata": {"source": "retained"},
    }
    context_file = directory / "reviewed-context.json"
    context_file.write_text(json.dumps(original_context), encoding="utf-8")
    client = TestClient(app)

    rejected = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/memory/reject",
        json={"confirmed": True},
    )

    assert rejected.status_code == 200
    rejected_context = json.loads(context_file.read_text(encoding="utf-8"))
    assert rejected_context["reviewState"] == "rejected"
    assert rejected_context["lifecycleStatus"] == "ready_for_review"
    for key, value in original_context.items():
        if key != "reviewState":
            assert rejected_context[key] == value

    transitioned = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/memory/review",
        json={
            "confirmed": True,
            "lifecycleStatus": "escalated_to_incident",
            "finding": "Operator-reviewed finding",
            "selectedShiftDate": SHIFT_DATE,
        },
    )

    assert transitioned.status_code == 200
    assert transitioned.json()["lifecycleStatus"] == "escalated_to_incident"


def test_generated_needs_review_cannot_be_reviewed_but_can_be_explicitly_rejected(
    noc_root,
):
    directory = noc_root / SHIFT_DATE / "investigations" / "generated"
    directory.mkdir(parents=True)
    (directory / "investigation.md").write_text(
        "# Investigation: Generated record\n"
        "- Status: active\n"
        "- Source of truth: noc-inv\n"
        "- Evidence Provenance: noc-inv\n"
        "- FINAL Datadog Notebook: https://app.datadoghq.com/notebook/123/example\n"
        "\n## Summary\nTBD\n",
        encoding="utf-8",
    )
    (directory / "generation-status.json").write_text(
        '{"generationStatus":"completed","validationStatus":"needs_review",'
        '"shiftDate":"2099-12-31","name":"generated",'
        '"notebookUrl":"https://app.datadoghq.com/notebook/123/example",'
        '"provenance":"noc-inv"}',
        encoding="utf-8",
    )
    client = TestClient(app)

    review = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/generated/review",
        json={
            "confirmed": True,
            "lifecycleStatus": "escalated_to_incident",
            "finding": "Queue high",
            "selectedShiftDate": SHIFT_DATE,
        },
    )
    assert review.status_code == 422
    assert not (directory / "reviewed-context.json").exists()
    assert investigations.get_reviewed_findings(SHIFT_DATE) == []

    rejected = client.post(
        f"/api/shifts/{SHIFT_DATE}/investigations/generated/reject",
        json={"confirmed": True},
    )
    assert rejected.status_code == 200
    assert rejected.json()["lifecycle"]["reviewState"] == "rejected"


def test_corrupt_investigations_return_unavailable_projections_without_changing_files(noc_root):
    _investigation(noc_root)
    corrupt_context = noc_root / SHIFT_DATE / "investigations" / "corrupt-context"
    corrupt_context.mkdir()
    (corrupt_context / "investigation.md").write_text(
        "# Investigation: Context validation\n- Status: active\n",
        encoding="utf-8",
    )
    context_file = corrupt_context / "reviewed-context.json"
    context_file.write_text("{not json", encoding="utf-8")
    corrupt_investigation = noc_root / SHIFT_DATE / "investigations" / "corrupt-investigation"
    corrupt_investigation.mkdir()
    (corrupt_investigation / "investigation.md").write_text(
        "- Status: active\n", encoding="utf-8"
    )

    results = {result["name"]: result for result in investigations.get_investigations(SHIFT_DATE)}

    assert results["memory"]["evidence"]["availability"] == "available"
    assert results["corrupt-context"]["lifecycle"]["reviewState"] == "unavailable"
    assert results["corrupt-context"]["lifecycleStatus"] == "ready_for_review"
    assert results["corrupt-context"]["error"]["code"] == "reviewed-context-unavailable"
    assert results["corrupt-context"]["reviewedFinding"] is None
    assert "advisory" not in results["corrupt-context"]
    assert results["corrupt-investigation"]["evidence"]["availability"] == "unavailable"
    assert results["corrupt-investigation"]["lifecycleStatus"] == "ready_for_review"
    assert results["corrupt-investigation"]["error"]["code"] == "investigation-unavailable"
    assert context_file.read_text(encoding="utf-8") == "{not json"

    detail = investigations.get_investigation(SHIFT_DATE, "corrupt-investigation")
    assert detail["error"]["code"] == "investigation-unavailable"


def test_only_reviewed_context_reaches_operational_projections(noc_root, monkeypatch):
    _investigation(noc_root)
    monkeypatch.setattr(dashboard, "get_jira_ticket_queue", lambda: {"tickets": []})
    monkeypatch.setattr(status, "get_jira_ticket_queue", lambda: {"tickets": []})

    pending = [
        dashboard.get_dashboard(SHIFT_DATE),
        status.get_status(SHIFT_DATE),
        shift_notes.get_shift_notes(SHIFT_DATE),
        handover.get_handover(SHIFT_DATE),
    ]
    assert all(result["reviewedFindings"] == [] for result in pending)
    assert all("raw secret-like source output" not in str(result) for result in pending)

    investigations.review_investigation(
        SHIFT_DATE, "memory", "Memory remains elevated", "monitoring"
    )
    dashboard_result = dashboard.get_dashboard(SHIFT_DATE)
    status_result = status.get_status(SHIFT_DATE)
    notes_result = shift_notes.get_shift_notes(SHIFT_DATE)

    for result in (dashboard_result, status_result, notes_result):
        assert result["reviewedFindings"][0]["finding"] == "Memory remains elevated"
        assert "raw secret-like source output" not in str(result)


@pytest.mark.parametrize(
    ("legacy_state", "expected_status"),
    [
        ("Cured", "cured"),
        ("Done (Cured)", "cured"),
        ("Active", "escalated_to_incident"),
        ("monitoring", "escalated_to_incident"),
        ("during monitoring", "ready_for_review"),
    ],
)
def test_legacy_review_migrates_only_exact_recognized_states(
    investigation_factory, legacy_state, expected_status
):
    directory = investigation_factory(
        name="legacy",
        reviewed_context={
            "reviewState": "reviewed",
            "finding": "Operator-reviewed finding",
            "state": legacy_state,
        },
    )

    projected = investigations.get_investigation(SHIFT_DATE, "legacy")

    assert projected["lifecycleStatus"] == expected_status
    persisted = json.loads(
        (directory / "reviewed-context.json").read_text(encoding="utf-8")
    )
    assert persisted["state"] == legacy_state
    assert persisted["lifecycleStatus"] == expected_status


def test_unreviewed_or_markdown_status_does_not_infer_lifecycle(
    investigation_factory,
):
    investigation_factory(
        name="unreviewed-cured",
        state="Cured",
        reviewed_context={
            "reviewState": "unreviewed",
            "finding": "",
            "state": "Cured",
        },
    )
    investigation_factory(name="markdown-cured", state="Cured")

    results = {
        item["name"]: item
        for item in investigations.get_investigations(SHIFT_DATE)
    }

    assert results["unreviewed-cured"]["lifecycleStatus"] == "ready_for_review"
    assert results["markdown-cured"]["lifecycleStatus"] == "ready_for_review"


def test_malformed_lifecycle_status_migrates_conservatively(investigation_factory):
    directory = investigation_factory(
        name="conflicting-lifecycle",
        reviewed_context={
            "reviewState": "reviewed",
            "lifecycleStatus": "active",
            "finding": "Operator-reviewed finding",
            "state": "Cured",
        },
    )

    projected = investigations.get_investigation(SHIFT_DATE, "conflicting-lifecycle")
    persisted = json.loads(
        (directory / "reviewed-context.json").read_text(encoding="utf-8")
    )

    assert projected["lifecycleStatus"] == "ready_for_review"
    assert persisted["legacyLifecycleStatus"] == "active"
    assert persisted["state"] == "Cured"


def test_legacy_migration_write_failure_preserves_previous_context(
    investigation_factory, monkeypatch
):
    directory = investigation_factory(
        name="migration-failure",
        reviewed_context={
            "reviewState": "reviewed",
            "finding": "Preserve this finding",
            "state": "Cured",
        },
    )
    context_file = directory / "reviewed-context.json"
    original = context_file.read_text(encoding="utf-8")
    original_replace = type(context_file).replace

    def fail_context_replace(path, target):
        if target == context_file:
            raise OSError("simulated atomic replace failure")
        return original_replace(path, target)

    monkeypatch.setattr(type(context_file), "replace", fail_context_replace)

    projected = investigations.get_investigation(SHIFT_DATE, "migration-failure")

    assert projected["error"]["code"] == "investigation-unavailable"
    assert context_file.read_text(encoding="utf-8") == original
