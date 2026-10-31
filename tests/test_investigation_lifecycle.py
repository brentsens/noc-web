import json

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.services import investigations


SHIFT_DATE = "2099-12-31"


def _ready_context():
    return {
        "reviewState": "unreviewed",
        "lifecycleStatus": "ready_for_review",
        "finding": "",
        "state": "",
        "lastLifecycleChangedAt": None,
        "lastLifecycleChangedShiftDate": None,
    }


def _request(lifecycle_status, *, finding="Operator-reviewed finding", confirmed=True):
    return {
        "confirmed": confirmed,
        "lifecycleStatus": lifecycle_status,
        "finding": finding,
        "selectedShiftDate": SHIFT_DATE,
    }


def _context(directory):
    return json.loads(
        (directory / "reviewed-context.json").read_text(encoding="utf-8")
    )


def test_lifecycle_requires_confirmation_and_preserves_previous_context(
    investigation_factory,
):
    directory = investigation_factory(
        reviewed_context=_ready_context(),
    )
    before = _context(directory)

    response = TestClient(app).post(
        f"/api/shifts/{SHIFT_DATE}/investigations/memory/review",
        json=_request("escalated_to_incident", confirmed=False),
    )

    assert response.status_code == 422
    assert _context(directory) == before


def test_lifecycle_rejects_selected_shift_before_creation_shift(
    investigation_factory,
):
    creation_shift = "2099-12-30"
    directory = investigation_factory(
        shift_date=creation_shift,
        reviewed_context=_ready_context(),
    )
    before = _context(directory)
    request = _request("escalated_to_incident")
    request["selectedShiftDate"] = "2099-12-29"

    response = TestClient(app).post(
        f"/api/shifts/{creation_shift}/investigations/memory/review",
        json=request,
    )

    assert response.status_code == 422
    assert _context(directory) == before


@pytest.mark.parametrize(
    ("initial_status", "initial_review_state", "target_status", "expected_code"),
    [
        ("ready_for_review", "unreviewed", "escalated_to_incident", 200),
        ("ready_for_review", "unreviewed", "cured", 200),
        ("escalated_to_incident", "reviewed", "cured", 200),
        ("cured", "reviewed", "escalated_to_incident", 422),
    ],
)
def test_lifecycle_transitions_follow_the_forward_only_graph(
    investigation_factory,
    initial_status,
    initial_review_state,
    target_status,
    expected_code,
):
    directory = investigation_factory(
        reviewed_context={
            "reviewState": initial_review_state,
            "lifecycleStatus": initial_status,
            "finding": "Prior reviewed finding" if initial_review_state == "reviewed" else "",
            "state": "monitoring" if initial_review_state == "reviewed" else "",
            "lastLifecycleChangedAt": None,
            "lastLifecycleChangedShiftDate": None,
        },
    )

    response = TestClient(app).post(
        f"/api/shifts/{SHIFT_DATE}/investigations/memory/review",
        json=_request(target_status),
    )

    assert response.status_code == expected_code
    if expected_code == 200:
        body = response.json()
        assert body["lifecycleStatus"] == target_status
        assert body["lifecycle"]["reviewState"] == "reviewed"
        assert body["reviewedFinding"]["finding"] == "Operator-reviewed finding"
        persisted = _context(directory)
        assert persisted["lifecycleStatus"] == target_status
        assert persisted["lastLifecycleChangedShiftDate"] == SHIFT_DATE
        assert persisted["lastLifecycleChangedAt"]
    else:
        assert _context(directory)["lifecycleStatus"] == initial_status


@pytest.mark.parametrize(
    ("lifecycle_status", "finding"),
    [
        ("escalated_to_incident", ""),
        ("cured", " \t "),
    ],
)
def test_escalated_or_cured_lifecycle_requires_a_nonempty_finding(
    investigation_factory, lifecycle_status, finding
):
    directory = investigation_factory(reviewed_context=_ready_context())
    before = _context(directory)

    response = TestClient(app).post(
        f"/api/shifts/{SHIFT_DATE}/investigations/memory/review",
        json=_request(lifecycle_status, finding=finding),
    )

    assert response.status_code == 422
    assert _context(directory) == before


def test_validation_metadata_does_not_replace_lifecycle_status(investigation_factory):
    investigation_factory(
        generation={
            "generationStatus": "completed",
            "validationStatus": "ready_for_review",
        },
        reviewed_context={
            "reviewState": "reviewed",
            "lifecycleStatus": "escalated_to_incident",
            "finding": "Operator-reviewed finding",
            "state": "monitoring",
            "lastLifecycleChangedAt": None,
            "lastLifecycleChangedShiftDate": None,
        },
    )

    projection = investigations.get_investigation(SHIFT_DATE, "memory")

    assert projection["validationStatus"] == "ready_for_review"
    assert projection["lifecycleStatus"] == "escalated_to_incident"
    assert projection["lifecycleLabel"] == "Escalated to Incident"


def test_lifecycle_write_failure_preserves_previous_context(
    investigation_factory, monkeypatch
):
    directory = investigation_factory(reviewed_context=_ready_context())
    context_file = directory / "reviewed-context.json"
    before = context_file.read_bytes()
    original_replace = type(context_file).replace

    def fail_context_replace(path, target):
        if target == context_file:
            raise OSError("simulated atomic replace failure")
        return original_replace(path, target)

    monkeypatch.setattr(type(context_file), "replace", fail_context_replace)

    response = TestClient(app).post(
        f"/api/shifts/{SHIFT_DATE}/investigations/memory/review",
        json=_request("escalated_to_incident"),
    )

    assert response.status_code == 500
    assert context_file.read_bytes() == before


def test_lifecycle_update_does_not_modify_jira_or_shift_notes(
    investigation_factory, noc_root
):
    investigation_factory()
    unrelated_files = {
        noc_root / ".jira-open-tickets.json": b'{"tickets":[]}\n',
        noc_root / ".ticket-sync-state.json": b'{"sync":"unchanged"}\n',
        noc_root / SHIFT_DATE / "shift-notes.json": b'{"notes":"unchanged"}\n',
    }
    for path, content in unrelated_files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    response = TestClient(app).post(
        f"/api/shifts/{SHIFT_DATE}/investigations/memory/review",
        json=_request("escalated_to_incident"),
    )

    assert response.status_code == 200
    assert {path: path.read_bytes() for path in unrelated_files} == unrelated_files
