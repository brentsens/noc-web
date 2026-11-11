from backend.services.investigation_generation import (
    InvestigationRequest,
    _validate_generated_record,
)


NOTEBOOK_URL = "https://app.datadoghq.com/notebook/123456/example-notebook"
REQUEST = InvestigationRequest(
    shift_date="2099-12-31",
    display_title="Checkout Latency",
    name="checkout-latency",
    notebook_url=NOTEBOOK_URL,
)


def _record(
    *,
    shift="2099-12-31",
    name="checkout-latency",
    notebook=NOTEBOOK_URL,
    provenance="noc-inv",
    summary="Latency increased after deployment.",
):
    return (
        "# Investigation: Checkout Latency\n"
        f"- Investigation Name: {name}\n"
        "- Display Title: Checkout Latency\n"
        f"- Shift Date: {shift}\n"
        f"- FINAL Datadog Notebook: {notebook}\n"
        f"- Evidence Provenance: {provenance}\n"
        f"\n## Summary\n{summary}\n"
        "\n## Confirmed Findings\nQueue depth is elevated.\n"
        "\n## Current Status\nService remains available.\n"
        "\n## Next Actions\nMonitor queue depth.\n"
        "\n## Handover Summary\nContinue monitoring queue depth.\n"
    )


def test_complete_generated_record_is_ready_for_review():
    provenance, errors = _validate_generated_record(_record(), REQUEST)

    assert provenance == "noc-inv"
    assert errors == []


def test_record_with_wrong_shift_name_url_or_provenance_needs_review():
    provenance, errors = _validate_generated_record(
        _record(
            shift="2099-12-30",
            name="other-investigation",
            notebook="https://app.datadoghq.com/notebook/123456/other",
            provenance="manual",
        ),
        REQUEST,
    )

    assert provenance == ""
    assert {"shift", "name", "notebook", "provenance"} <= set(errors)


def test_placeholder_only_required_sections_need_review():
    _, errors = _validate_generated_record(_record(summary="TBD"), REQUEST)

    assert "section:Summary" in errors


import copy

import pytest

from backend.services.investigation_ai import (
    INVESTIGATION_SYSTEM_PROMPT,
    InvestigationAIError,
    build_investigation_envelope,
    validate_ai_output,
)
from backend.services.investigation_evidence import build_evidence_package
from tests.support.investigation_ai import (
    INCIDENT_ID,
    MONITOR_ID,
    NOTEBOOK_ID,
    SECOND_MONITOR_ID,
    evidence_bundle,
    fake_loader,
    valid_output,
)


def _package(bundle=None):
    return build_evidence_package(
        INCIDENT_ID,
        evidence_loader=fake_loader(bundle or evidence_bundle()),
    )


def test_valid_ai_output_passes():
    package = _package()
    assert validate_ai_output(valid_output(package), package)


def test_missing_or_extra_ai_sections_are_rejected():
    package = _package()
    for mutate in (
        lambda value: value.pop("summary"),
        lambda value: value.__setitem__("extra", ["incident:" + INCIDENT_ID]),
    ):
        value = valid_output(package)
        mutate(value)
        with pytest.raises(InvestigationAIError) as error:
            validate_ai_output(value, package)
        assert error.value.code == "ai-output-invalid"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.__setitem__("summary", "not a list"),
        lambda value: value.__setitem__("summary", []),
        lambda value: value.__setitem__("summary", ["x" * (2048 + 1)]),
        lambda value: value.__setitem__(
            "summary",
            [f"incident:{INCIDENT_ID} " + ("x" * (2048 + 1))],
        ),
        lambda value: value.__setitem__("summary", ["TBD"]),
        lambda value: value.__setitem__("summary", ["No citation here."]),
        lambda value: value.__setitem__(
            "summary",
            ["Unsupported evidence monitor:999999."],
        ),
        lambda value: value.__setitem__(
            "summary",
            ["Authorization: Bearer secret-token-value incident:bad"],
        ),
    ],
)
def test_invalid_ai_output_is_rejected(mutate):
    package = _package()
    value = valid_output(package)
    mutate(value)

    with pytest.raises(InvestigationAIError):
        validate_ai_output(value, package)


def test_partial_evidence_claim_is_rejected():
    package = _package(evidence_bundle(unavailable_monitor=True))
    value = valid_output(package)
    value["summary"] = [f"All evidence is complete and current (incident:{INCIDENT_ID})."]

    with pytest.raises(InvestigationAIError) as error:
        validate_ai_output(value, package)

    assert error.value.code == "ai-output-invalid"


def test_ai_output_over_total_bound_is_rejected():
    package = _package()
    value = valid_output(package)
    for section in value:
        value[section] = [
            f"incident:{INCIDENT_ID} " + ("x" * 1900)
            for _ in range(8)
        ]

    with pytest.raises(InvestigationAIError) as error:
        validate_ai_output(value, package)

    assert error.value.code == "ai-output-too-large"


def test_ai_evidence_generated_record_is_ready_for_review():
    provenance, errors = _validate_generated_record(
        _record(provenance="ai-evidence"),
        REQUEST,
    )

    assert provenance == "ai-evidence"
    assert errors == []


def test_unavailable_evidence_citation_is_rejected():
    package = _package(evidence_bundle(unavailable_monitor=True))
    value = valid_output(package)
    unavailable_id = package["unavailable"][0]["id"]
    value["summary"] = [f"Unavailable monitor looked healthy ({unavailable_id})."]

    with pytest.raises(InvestigationAIError) as error:
        validate_ai_output(value, package)

    assert error.value.code == "evidence-reference-invalid"


def test_envelope_exposes_exact_allowed_live_evidence_ids():
    bundle = evidence_bundle()
    second_monitor = copy.deepcopy(bundle["monitors"][0])
    second_monitor["reference"]["id"] = SECOND_MONITOR_ID
    second_monitor["evidence"]["id"] = SECOND_MONITOR_ID
    bundle["monitors"].append(second_monitor)
    package = _package(bundle)

    envelope = build_investigation_envelope(package, {
        "displayTitle": "Checkout latency",
        "name": "checkout-latency",
        "shiftDate": "2099-12-31",
        "notebookUrl": "https://app.datadoghq.com/notebook/16295624/runbook",
    })

    expected = sorted([
        f"incident:{INCIDENT_ID}",
        f"notebook:{NOTEBOOK_ID}",
        f"monitor:{MONITOR_ID}",
        f"monitor:{SECOND_MONITOR_ID}",
    ])
    assert envelope["citationContract"]["allowedEvidenceIds"] == expected
    assert envelope["evidenceIdentifiers"] == expected
    assert envelope["citationContract"]["unavailableEvidenceIds"] == []
    assert "byte-for-byte" in envelope["citationContract"]["rule"]
    assert "omit the claim" in envelope["citationContract"]["rule"]
    assert "monitor names" in envelope["citationContract"]["forbiddenCitationForms"]
    assert "source URLs" in envelope["citationContract"]["forbiddenCitationForms"]
    assert "bare numeric IDs" in envelope["citationContract"]["forbiddenCitationForms"]


def test_exact_live_evidence_ids_are_accepted_when_copied_verbatim():
    bundle = evidence_bundle()
    second_monitor = copy.deepcopy(bundle["monitors"][0])
    second_monitor["reference"]["id"] = SECOND_MONITOR_ID
    second_monitor["evidence"]["id"] = SECOND_MONITOR_ID
    bundle["monitors"].append(second_monitor)
    package = _package(bundle)

    value = {
        "summary": [f"Incident context ({package['incident']['id']})."],
        "confirmedFindings": [f"Notebook evidence (notebook:{NOTEBOOK_ID})."],
        "currentStatus": [f"Primary monitor (monitor:{MONITOR_ID})."],
        "nextActions": [f"Secondary monitor (monitor:{SECOND_MONITOR_ID})."],
        "handoverSummary": [f"Handover context ({package['incident']['id']})."],
    }

    assert validate_ai_output(value, package) == value


@pytest.mark.parametrize(
    "bad_citation",
    [
        "monitor:999999",
        "incident:aadf7955",
        "notebook:999999",
        "monitor:150243517:",
    ],
)
def test_unsupplied_or_altered_citation_ids_are_rejected(bad_citation):
    package = _package()
    value = valid_output(package)
    value["confirmedFindings"] = [f"Claim cites an invalid ID ({bad_citation})."]

    with pytest.raises(InvestigationAIError) as error:
        validate_ai_output(value, package)

    assert error.value.code == "evidence-reference-invalid"


def test_investigation_prompt_is_explicit_about_exact_citations():
    prompt = INVESTIGATION_SYSTEM_PROMPT

    assert "citationContract.allowedEvidenceIds" in prompt
    assert "byte-for-byte" in prompt
    assert "shortened IDs" in prompt
    assert "human-readable aliases" in prompt
    assert "source URLs" in prompt
    assert "monitor names" in prompt
    assert "omit the claim" in prompt
    assert "citationContract.unavailableEvidenceIds" in prompt
