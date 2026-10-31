import json

from fastapi.testclient import TestClient

from backend.app import app
from backend.services import investigations


SELECTED_SHIFT = "2099-12-31"
PREVIOUS_SHIFT = "2099-12-30"
OLDER_SHIFT = "2099-12-29"


def _reviewed_context(status, *, finding="Operator finding", changed_shift=None):
    return {
        "reviewState": "reviewed" if status != "ready_for_review" else "unreviewed",
        "lifecycleStatus": status,
        "finding": finding if status != "ready_for_review" else "",
        "state": "legacy state must remain unchanged",
        "lastLifecycleChangedAt": "2099-12-30T12:00:00+00:00" if changed_shift else None,
        "lastLifecycleChangedShiftDate": changed_shift,
    }


def test_cross_shift_projection_classifies_active_and_cured_work(
    investigation_factory,
):
    investigation_factory(
        shift_date=SELECTED_SHIFT,
        name="created-ready",
        reviewed_context=_reviewed_context("ready_for_review"),
    )
    investigation_factory(
        shift_date=PREVIOUS_SHIFT,
        name="carried-escalation",
        reviewed_context=_reviewed_context(
            "escalated_to_incident", changed_shift=PREVIOUS_SHIFT
        ),
    )
    investigation_factory(
        shift_date=PREVIOUS_SHIFT,
        name="cured-this-shift",
        reviewed_context=_reviewed_context(
            "cured", changed_shift=SELECTED_SHIFT
        ),
    )
    investigation_factory(
        shift_date=OLDER_SHIFT,
        name="cured-earlier",
        reviewed_context=_reviewed_context(
            "cured", changed_shift=PREVIOUS_SHIFT
        ),
    )

    client = TestClient(app)
    active = client.get(
        f"/api/shifts/{SELECTED_SHIFT}/investigations?view=active"
    ).json()
    history = client.get(
        f"/api/shifts/{SELECTED_SHIFT}/investigations?view=history"
    ).json()
    active_by_name = {
        item["name"]: item for item in active["investigations"]
    }
    history_by_name = {
        item["name"]: item for item in history["investigations"]
    }

    assert active["selectedShiftDate"] == SELECTED_SHIFT
    assert active["view"] == "active"
    assert active_by_name["created-ready"]["visibility"] == "created_this_shift"
    assert active_by_name["carried-escalation"]["visibility"] == "carried"
    assert active_by_name["cured-this-shift"]["visibility"] == "cured_this_shift"
    assert "cured-earlier" not in active_by_name
    assert history_by_name["cured-earlier"]["visibility"] == "historical"
    assert history_by_name["cured-earlier"]["creationShiftDate"] == OLDER_SHIFT
    assert history_by_name["cured-earlier"]["sourceReference"] == {
        "creationShiftDate": OLDER_SHIFT,
        "investigationName": "cured-earlier",
    }


def test_carried_projection_excludes_source_evidence_and_preserves_legacy_state(
    investigation_factory,
):
    directory = investigation_factory(
        shift_date=PREVIOUS_SHIFT,
        name="carried",
        generation={
            "generationStatus": "completed",
            "validationStatus": "ready_for_review",
        },
        reviewed_context=_reviewed_context(
            "escalated_to_incident", changed_shift=PREVIOUS_SHIFT
        ),
    )
    raw_evidence = "raw generated evidence must remain at source only"
    (directory / "investigation.md").write_text(
        "# Investigation: Carried work\n"
        "- Status: active\n"
        "- Source of truth: noc-inv\n"
        "\n## Summary\n"
        f"{raw_evidence}\n",
        encoding="utf-8",
    )

    result = investigations.get_investigations(SELECTED_SHIFT)
    carried = next(item for item in result if item["name"] == "carried")

    assert carried["visibility"] == "carried"
    assert carried["lifecycleStatus"] == "escalated_to_incident"
    assert carried["reviewedFinding"]["finding"] == "Operator finding"
    assert "advisory" not in carried
    assert raw_evidence not in json.dumps(carried)
    assert json.loads(
        (directory / "reviewed-context.json").read_text(encoding="utf-8")
    )["state"] == "legacy state must remain unchanged"


def test_cross_shift_detail_rejects_unsafe_source_identifiers(
    investigation_factory,
):
    investigation_factory(name="safe-record")

    assert investigations.get_investigation(SELECTED_SHIFT, "../safe-record") is None
    assert investigations.get_investigation(SELECTED_SHIFT, "safe-record/../safe-record") is None
    assert investigations.get_investigation("../2099-12-31", "safe-record") is None


def test_cross_shift_projection_ignores_symlinked_source_records(
    investigation_factory, noc_root
):
    outside = investigation_factory(shift_date=OLDER_SHIFT, name="outside")
    investigations_directory = noc_root / SELECTED_SHIFT / "investigations"
    investigations_directory.mkdir(parents=True)
    (investigations_directory / "linked").symlink_to(outside, target_is_directory=True)

    assert [
        item["name"] for item in investigations.get_investigations(SELECTED_SHIFT)
    ] == ["outside"]
