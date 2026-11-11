import copy

import pytest

from backend.services.investigation_evidence import (
    InvestigationEvidenceError,
    build_evidence_package,
)
from tests.support.investigation_ai import (
    INCIDENT_ID,
    MONITOR_ID,
    NOTEBOOK_ID,
    evidence_bundle,
    fake_loader,
)


def _package(bundle=None):
    return build_evidence_package(
        INCIDENT_ID,
        evidence_loader=fake_loader(bundle or evidence_bundle()),
    )


def test_complete_package_has_stable_ids_bounds_and_digest():
    first = _package()
    second = _package()

    assert first["packageVersion"] == "1"
    assert first["availability"] == "complete"
    assert first["incident"]["id"] == f"incident:{INCIDENT_ID}"
    assert first["notebooks"][0]["id"] == f"notebook:{NOTEBOOK_ID}"
    assert first["monitors"][0]["id"] == f"monitor:{MONITOR_ID}"
    assert first["references"][f"incident:{INCIDENT_ID}"]["sourceUrl"]
    assert first["references"][f"notebook:{NOTEBOOK_ID}"]["source"] == "incident_field"
    assert first["references"][f"monitor:{MONITOR_ID}"]["source"] == "notebook"
    assert first["sizeBytes"] <= 256 * 1024
    assert first["digest"].startswith("sha256:")
    assert first["digest"] == second["digest"]
    assert "cells" not in str(first)
    assert "omittedCellTypes" not in str(first)
    assert "Authorization" not in str(first)


def test_package_digest_changes_with_evidence_content():
    first = _package()
    second = _package(
        evidence_bundle(
            monitor_query="avg(last_5m):sum:checkout.errors{*}.as_count() > 50",
        )
    )

    assert first["digest"] != second["digest"]


def test_unavailable_references_are_partial_and_explicit():
    package = _package(evidence_bundle(unavailable_monitor=True))

    assert package["availability"] == "partial"
    assert package["unavailable"]
    identifier = f"monitor:{MONITOR_ID}"
    assert package["references"][identifier]["availability"] == "unavailable"
    assert package["references"][identifier]["error"] == "timeout"
    assert package["monitors"] == []


def test_notebook_markdown_over_bound_fails_closed():
    bundle = evidence_bundle(notebook_markdown="x" * (16 * 1024 + 1))

    with pytest.raises(InvestigationEvidenceError) as error:
        _package(bundle)

    assert error.value.code == "evidence-too-large"


def test_too_many_notebooks_fails_closed():
    bundle = evidence_bundle()
    template = bundle["notebooks"][0]
    entries = []
    for index in range(11):
        entry = copy.deepcopy(template)
        entry["reference"]["id"] = str(1000 + index)
        entry["evidence"]["id"] = str(1000 + index)
        entries.append(entry)
    bundle["notebooks"] = entries

    with pytest.raises(InvestigationEvidenceError) as error:
        _package(bundle)

    assert error.value.code == "evidence-too-large"


def test_credential_like_evidence_fails_closed():
    bundle = evidence_bundle()
    bundle["incident"]["fields"] = {"authorization": "Bearer secret"}

    with pytest.raises(InvestigationEvidenceError) as error:
        _package(bundle)

    assert error.value.code == "evidence-credential-detected"


def test_non_current_incident_fails_closed():
    with pytest.raises(InvestigationEvidenceError) as error:
        _package(evidence_bundle(state="RESOLVED"))

    assert error.value.code == "incident-not-current"


@pytest.mark.parametrize(
    ("failure_code", "expected"),
    [
        ("timeout", "evidence-timeout"),
        ("invalid-response", "evidence-invalid"),
        ("provider-unavailable", "evidence-unavailable"),
    ],
)
def test_evidence_retrieval_failures_are_controlled(failure_code, expected):
    from backend.services.datadog_evidence import DatadogEvidenceFailure

    def loader(_incident_id):
        raise DatadogEvidenceFailure(failure_code)

    with pytest.raises(InvestigationEvidenceError) as error:
        build_evidence_package(INCIDENT_ID, evidence_loader=loader)

    assert error.value.code == expected


def test_package_total_size_over_bound_fails_closed():
    bundle = evidence_bundle()
    bundle["notebooks"][0]["evidence"]["cells"] = [
        {
            "type": "timeseries",
            "queries": ["avg:" + ("x" * 1990) for _ in range(20)],
            "timeRange": None,
        }
        for _ in range(200)
    ]

    with pytest.raises(InvestigationEvidenceError) as error:
        _package(bundle)

    assert error.value.code == "evidence-too-large"
