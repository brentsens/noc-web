import copy

import pytest

from backend.services.handover_evidence import (
    HandoverEvidenceError,
    build_handover_evidence,
)
from tests.support.handover_ai import (
    SHIFT_DATE,
    dashboard_summary,
    incident,
    investigation,
    loaders,
    readiness,
    reviewed_finding,
    shift_notes,
    snapshot,
    status_summary,
    ticket,
)


def _package(**overrides):
    return build_handover_evidence(SHIFT_DATE, **loaders(**overrides))


def test_ticket_union_includes_local_remote_duplicate_and_stale_entries():
    local = ticket("NOC-1", summary="Local only")
    duplicate = ticket("NOC-2", summary="Tracked locally", next_action="Call vendor.")
    remote_duplicate = ticket(
        "NOC-2",
        summary="Remote summary",
        next_action="",
        tracked=False,
        tracking_state="jira-only",
    )
    remote_only = ticket(
        "NOC-3",
        summary="Remote only",
        tracked=False,
        tracking_state="jira-only",
    )
    package = build_handover_evidence(
        SHIFT_DATE,
        **loaders(
            local_tickets=[local, duplicate],
            remote_queue={
                "tickets": [remote_duplicate, remote_only],
                "cacheAvailable": True,
                "count": 2,
            },
            remote_health={"available": True, "freshness": "stale"},
        ),
    )

    merged = package["tickets"]["merged"]
    assert [item["jiraKey"] for item in merged] == ["NOC-1", "NOC-2", "NOC-3"]
    assert package["tickets"]["count"] == 3
    assert package["tickets"]["freshness"]["remote"] == "stale"
    assert all(item["freshness"] in {"current", "stale", "partial"} for item in merged)
    assert package["availability"] == "partial"
    assert "notes" not in merged[0]


def test_ticket_union_rejects_unestablishable_and_over_bound_sets():
    with pytest.raises(HandoverEvidenceError) as error:
        build_handover_evidence(
            SHIFT_DATE,
            **loaders(
                local_summary={"available": False},
                remote_queue={"tickets": [], "cacheAvailable": False},
                remote_health={"available": False, "freshness": "unavailable"},
            ),
        )
    assert error.value.code == "tickets-unavailable"

    many = [ticket(f"NOC-{index}") for index in range(501)]
    with pytest.raises(HandoverEvidenceError) as error:
        build_handover_evidence(
            SHIFT_DATE,
            **loaders(local_tickets=many, local_summary={
                "available": True, "count": len(many), "items": [],
            }),
        )
    assert error.value.code == "tickets-over-bound"


def test_zero_tickets_is_explicit_and_complete_when_sources_are_available():
    package = _package(
        local_tickets=[],
        local_summary={"available": True, "count": 0, "items": []},
        remote_queue={"tickets": [], "cacheAvailable": True, "count": 0},
        remote_health={"available": True, "freshness": "current"},
    )

    assert package["tickets"]["count"] == 0
    assert package["tickets"]["complete"] is True
    assert package["availability"] in {"complete", "partial"}


def test_stable_ids_and_review_authority_flags():
    reviewed = investigation("reviewed-one", reviewed=True)
    unreviewed = investigation("unreviewed-one", reviewed=False, finding="")
    package = _package(
        investigations=[reviewed, unreviewed],
        reviewed_findings=[reviewed_finding("reviewed-one")],
    )

    references = package["references"]
    assert "ticket:NOC-556" in references
    assert "investigation:reviewed-one" in references
    assert "investigation:unreviewed-one" in references
    assert references["investigation:reviewed-one"]["authoritative"] is True
    assert references["investigation:unreviewed-one"]["authoritative"] is False
    assert any(item["id"].startswith("shift-note:") for item in package["shiftNotes"])
    assert "status:" in " ".join(references)
    assert "dashboard:" in " ".join(references)
    assert "readiness:" in " ".join(references)
    assert "datadog-context:" not in " ".join(references)


def test_datadog_context_freshness_and_unavailable_reference():
    package = _package(
        datadog_snapshot=snapshot(incidents=[incident()], freshness="stale"),
    )
    assert package["datadogIncidents"][0]["id"].startswith("incident:")
    assert package["datadogIncidents"][0]["freshness"] == "stale"
    assert package["availability"] == "partial"

    unavailable = _package(datadog_snapshot=snapshot(incidents=[], freshness="unavailable"))
    assert "datadog-context:2099-12-31" in unavailable["references"]
    assert unavailable["references"]["datadog-context:2099-12-31"]["availability"] == "unavailable"


def test_package_digest_is_deterministic_and_no_credentials():
    first = _package()
    second = _package()
    assert first["digest"] == second["digest"]
    assert first["sizeBytes"] <= 1024 * 1024
    assert "Authorization" not in str(first)

    with pytest.raises(HandoverEvidenceError) as error:
        _package(
            local_tickets=[ticket("NOC-9", summary="Authorization: Bearer secret-value")],
        )
    assert error.value.code == "evidence-credential-detected"


def test_package_size_over_bound_fails_closed():
    entries = [
        {"section": "Operational Events", "time": None, "text": "x" * 4000}
        for _ in range(300)
    ]
    with pytest.raises(HandoverEvidenceError) as error:
        _package(notes=shift_notes(entries=entries))
    assert error.value.code == "evidence-too-large"


def test_mandatory_evidence_item_bounds_fail_closed():
    entries = [
        {"section": "Operational Events", "time": None, "text": "Small note"}
        for _ in range(2001)
    ]
    with pytest.raises(HandoverEvidenceError) as error:
        _package(notes=shift_notes(entries=entries))
    assert error.value.code == "evidence-too-large"
