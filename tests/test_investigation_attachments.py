import json

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.services import datadog_incidents


CREATION_SHIFT = "2099-12-30"
SELECTED_SHIFT = "2099-12-31"


def _incident(state="ACTIVE", *, incident_id="IR-24"):
    return {
        "id": incident_id,
        "title": "Memory pressure",
        "state": state,
        "severity": "SEV-3",
        "url": f"https://app.datadoghq.com/incidents/{incident_id}",
        "summary": "Raw incident evidence must not be copied",
    }


def _escalated_context():
    return {
        "reviewState": "reviewed",
        "lifecycleStatus": "escalated_to_incident",
        "finding": "Operator-reviewed finding",
        "state": "legacy state",
        "reviewedAt": "2099-12-30T12:00:00+00:00",
        "reviewedBy": "operator",
        "lastLifecycleChangedAt": "2099-12-30T12:00:00+00:00",
        "lastLifecycleChangedShiftDate": CREATION_SHIFT,
    }


def _attach_request(incident_id="IR-24", *, confirmed=True):
    return {
        "confirmed": confirmed,
        "incidentId": incident_id,
        "selectedShiftDate": SELECTED_SHIFT,
    }


def _install_snapshot(monkeypatch, *, freshness="current", incidents=None):
    calls = []

    def snapshot(*args, **kwargs):
        calls.append(kwargs)
        return {
            "incidents": [_incident()] if incidents is None else incidents,
            "count": len([_incident()] if incidents is None else incidents),
            "freshness": freshness,
            "lastSuccessfulAt": "2099-12-31T12:00:00Z",
            "error": None,
        }

    monkeypatch.setattr(datadog_incidents, "get_incident_snapshot", snapshot)
    return calls


@pytest.mark.parametrize("state", ["ACTIVE", "STABLE"])
def test_current_active_or_stable_incident_can_be_explicitly_attached(
    investigation_factory, monkeypatch, state
):
    directory = investigation_factory(
        shift_date=CREATION_SHIFT,
        name="memory",
        title="Memory pressure",
        reviewed_context=_escalated_context(),
    )
    calls = _install_snapshot(monkeypatch, incidents=[_incident(state)])

    response = TestClient(app).post(
        f"/api/shifts/{CREATION_SHIFT}/investigations/memory/datadog-incident",
        json=_attach_request(),
    )

    assert response.status_code == 200
    body = response.json()
    reference = body["datadogIncidentReference"]
    assert set(reference) == {
        "incidentId",
        "url",
        "title",
        "lastKnownState",
        "attachedAt",
    }
    assert reference["incidentId"] == "IR-24"
    assert reference["url"] == "https://app.datadoghq.com/incidents/IR-24"
    assert reference["title"] == "Memory pressure"
    assert reference["lastKnownState"] == state
    assert reference["attachedAt"]
    assert body["datadogIncidentCacheFreshness"] == "current"
    assert body["lifecycleStatus"] == "escalated_to_incident"
    assert calls == [{"schedule_refresh": False}]

    persisted = json.loads(
        (directory / "reviewed-context.json").read_text(encoding="utf-8")
    )
    assert persisted["datadogIncidentReference"] == reference
    assert "summary" not in reference
    assert "evidence" not in persisted
    assert "Raw incident evidence must not be copied" not in json.dumps(persisted)


@pytest.mark.parametrize("freshness", ["stale", "refreshing", "unavailable"])
def test_attachment_rejects_noncurrent_cache_without_writing(
    investigation_factory, monkeypatch, freshness
):
    directory = investigation_factory(
        shift_date=CREATION_SHIFT,
        reviewed_context=_escalated_context(),
    )
    before = (directory / "reviewed-context.json").read_bytes()
    _install_snapshot(monkeypatch, freshness=freshness)

    response = TestClient(app).post(
        f"/api/shifts/{CREATION_SHIFT}/investigations/memory/datadog-incident",
        json=_attach_request(),
    )

    assert response.status_code == 422
    assert (directory / "reviewed-context.json").read_bytes() == before


@pytest.mark.parametrize(
    ("initial_status", "snapshot_incidents", "incident_id", "expected_status"),
    [
        ("ready_for_review", [_incident()], "IR-24", 422),
        ("escalated_to_incident", [], "IR-24", 422),
        ("escalated_to_incident", [_incident("RESOLVED")], "IR-24", 422),
        ("escalated_to_incident", [_incident()], "IR-25", 422),
        ("escalated_to_incident", [_incident()], "IR-24", 409),
    ],
)
def test_attachment_rejects_ineligible_or_duplicate_selection(
    investigation_factory,
    monkeypatch,
    initial_status,
    snapshot_incidents,
    incident_id,
    expected_status,
):
    directory = investigation_factory(
        shift_date=CREATION_SHIFT,
        reviewed_context={
            **_escalated_context(),
            "lifecycleStatus": initial_status,
            **(
                {"datadogIncidentReference": {
                    "incidentId": "IR-24",
                    "url": "https://app.datadoghq.com/incidents/IR-24",
                    "title": "Memory pressure",
                    "lastKnownState": "ACTIVE",
                    "attachedAt": "2099-12-30T12:00:00+00:00",
                }}
                if initial_status == "escalated_to_incident"
                and snapshot_incidents == [_incident()]
                and incident_id == "IR-24"
                else {}
            ),
        },
    )
    _install_snapshot(monkeypatch, incidents=snapshot_incidents)
    before = (directory / "reviewed-context.json").read_bytes()

    response = TestClient(app).post(
        f"/api/shifts/{CREATION_SHIFT}/investigations/memory/datadog-incident",
        json=_attach_request(incident_id),
    )

    assert response.status_code == expected_status
    if expected_status != 200:
        assert (directory / "reviewed-context.json").read_bytes() == before


def test_attachment_requires_explicit_confirmation_and_selection(
    investigation_factory, monkeypatch
):
    directory = investigation_factory(
        shift_date=CREATION_SHIFT,
        reviewed_context=_escalated_context(),
    )
    before = (directory / "reviewed-context.json").read_bytes()
    calls = _install_snapshot(monkeypatch)
    client = TestClient(app)

    unconfirmed = client.post(
        f"/api/shifts/{CREATION_SHIFT}/investigations/memory/datadog-incident",
        json=_attach_request(confirmed=False),
    )
    no_selection = client.post(
        f"/api/shifts/{CREATION_SHIFT}/investigations/memory/datadog-incident",
        json={"confirmed": True, "selectedShiftDate": SELECTED_SHIFT},
    )

    assert unconfirmed.status_code == 422
    assert no_selection.status_code == 422
    assert calls == []
    assert (directory / "reviewed-context.json").read_bytes() == before


def test_attachment_write_failure_preserves_previous_reference(
    investigation_factory, monkeypatch
):
    directory = investigation_factory(
        shift_date=CREATION_SHIFT,
        reviewed_context=_escalated_context(),
    )
    context_file = directory / "reviewed-context.json"
    before = context_file.read_bytes()
    original_replace = type(context_file).replace
    _install_snapshot(monkeypatch)

    def fail_context_replace(path, target):
        if target == context_file:
            raise OSError("simulated atomic replace failure")
        return original_replace(path, target)

    monkeypatch.setattr(type(context_file), "replace", fail_context_replace)

    response = TestClient(app).post(
        f"/api/shifts/{CREATION_SHIFT}/investigations/memory/datadog-incident",
        json=_attach_request(),
    )

    assert response.status_code == 500
    assert context_file.read_bytes() == before


def test_ai_evidence_investigation_can_attach_current_incident(
    investigation_factory, monkeypatch,
):
    directory = investigation_factory(
        shift_date=CREATION_SHIFT,
        name="memory",
        title="Memory pressure",
        reviewed_context=_escalated_context(),
    )
    (directory / "evidence-provenance.json").write_text(json.dumps({
        "provenance": "ai-evidence",
        "availability": "complete",
        "references": {},
    }), encoding="utf-8")
    _install_snapshot(monkeypatch)

    response = TestClient(app).post(
        f"/api/shifts/{CREATION_SHIFT}/investigations/memory/datadog-incident",
        json=_attach_request(),
    )

    assert response.status_code == 200
    assert response.json()["datadogIncidentReference"]["incidentId"] == "IR-24"
