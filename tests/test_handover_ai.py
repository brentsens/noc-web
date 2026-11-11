import json

import pytest

from backend.services.handover_ai import (
    HANDOVER_SYSTEM_PROMPT,
    HandoverAIError,
    build_handover_envelope,
    validate_advisory_output,
)
from backend.services.handover_evidence import build_handover_evidence
from tests.support.handover_ai import (
    SHIFT_DATE,
    incident,
    investigation,
    loaders,
    reviewed_finding,
    snapshot,
    ticket,
    valid_advisory,
)


def _package(**overrides):
    return build_handover_evidence(SHIFT_DATE, **loaders(**overrides))


def test_envelope_exposes_exact_allowed_unavailable_and_non_authoritative_ids():
    package = _package(
        investigations=[
            investigation("reviewed-one", reviewed=True),
            investigation("unreviewed-one", reviewed=False, finding=""),
        ],
        reviewed_findings=[reviewed_finding("reviewed-one")],
        datadog_snapshot=snapshot(incidents=[], freshness="unavailable"),
    )
    envelope = build_handover_envelope(package, shift_date=SHIFT_DATE)
    contract = envelope["citationContract"]

    assert contract["citationFormat"] == "[evidence:<stable-id>]"
    assert contract["example"].startswith("Use the exact bracketed form")
    assert "unbracketed IDs" in contract["forbiddenCitationForms"]
    assert "nested brackets" in contract["forbiddenCitationForms"]
    assert "ticket:NOC-556" in contract["availableEvidenceIds"]
    assert "ticket:NOC-556" in contract["allowedEvidenceIds"]
    assert "investigation:reviewed-one" in contract["allowedEvidenceIds"]
    assert "investigation:unreviewed-one" not in contract["allowedEvidenceIds"]
    assert "investigation:unreviewed-one" in contract["nonAuthoritativeEvidenceIds"]
    assert "datadog-context:2099-12-31" in contract["unavailableEvidenceIds"]
    assert "byte-for-byte" in contract["rule"]
    assert "source URLs" in contract["forbiddenCitationForms"]
    assert "ticket names" in contract["forbiddenCitationForms"]
    assert envelope["requiredSections"] == [
        "advisorySummary",
        "operationalRisks",
        "recommendedFocus",
        "watchItems",
    ]


def test_prompt_is_explicit_about_citation_and_authority_rules():
    prompt = HANDOVER_SYSTEM_PROMPT
    assert "citationContract.allowedEvidenceIds" in prompt
    assert "byte-for-byte" in prompt
    assert "shortened IDs" in prompt
    assert "source URLs" in prompt
    assert "nonAuthoritativeEvidenceIds" in prompt
    assert "reviewed finding" in prompt
    assert "omit the claim" in prompt
    assert "staleEvidenceIds" in prompt
    assert "partialEvidenceIds" in prompt
    assert 'MUST contain the literal word "stale"' in prompt
    assert "citationContract.availableEvidenceIds" in prompt
    assert "[evidence:<stable-id>]" in prompt
    assert "unbracketed IDs" in prompt
    assert "numeric counts" in prompt


def test_valid_advisory_output_passes_with_exact_ids():
    package = _package()
    output = valid_advisory(package)
    assert validate_advisory_output(output, package) == output


@pytest.mark.parametrize(
    "bad_citation",
    [
        "[evidence:ticket:999999]",
        "[evidence:ticket: noc-556]",
        "[evidence:ticket:NOC-556:]",
        "https://jira.example/browse/NOC-556",
        "NOC-556",
        "[evidence:investigation:unreviewed-one]",
        "[evidence:monitor:150243517]",
        "[evidence:readiness:2099-12-31",
    ],
)
def test_invalid_or_nonauthoritative_citations_are_rejected(bad_citation):
    package = _package(
        investigations=[
            investigation("reviewed-one", reviewed=True),
            investigation("unreviewed-one", reviewed=False, finding=""),
        ],
        reviewed_findings=[reviewed_finding("reviewed-one")],
    )
    output = valid_advisory(package)
    output["operationalRisks"] = [f"Risk ({bad_citation})."]

    with pytest.raises(HandoverAIError) as error:
        validate_advisory_output(output, package)

    assert error.value.code == "evidence-reference-invalid"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.pop("watchItems"),
        lambda value: value.__setitem__("extra", ["[evidence:ticket:NOC-556]"]),
        lambda value: value.__setitem__("advisorySummary", "not a list"),
        lambda value: value.__setitem__("advisorySummary", []),
        lambda value: value.__setitem__("advisorySummary", ["TBD"]),
        lambda value: value.__setitem__("advisorySummary", ["No citation."]),
        lambda value: value.__setitem__("advisorySummary", ["x" * 2049]),
        lambda value: value.__setitem__(
            "advisorySummary",
            ["[evidence:ticket:NOC-556] " + ("x" * 2040)],
        ),
        lambda value: value.__setitem__(
            "advisorySummary",
            ["Authorization: Bearer secret-token-value [evidence:ticket:NOC-556]"],
        ),
    ],
)
def test_malformed_or_over_bound_advisory_is_rejected(mutate):
    package = _package()
    output = valid_advisory(package)
    mutate(output)

    with pytest.raises(HandoverAIError):
        validate_advisory_output(output, package)


def test_partial_evidence_claims_are_rejected():
    package = _package(
        datadog_snapshot=snapshot(incidents=[], freshness="unavailable"),
    )
    output = valid_advisory(package)
    output["advisorySummary"] = ["All evidence is complete and current [evidence:ticket:NOC-556]."]

    with pytest.raises(HandoverAIError) as error:
        validate_advisory_output(output, package)

    assert error.value.code == "ai-output-invalid"


def test_total_advisory_size_bound_is_enforced():
    package = _package()
    output = valid_advisory(package)
    for section in output:
        output[section] = [f"[evidence:ticket:NOC-556] " + ("x" * 2020) for _ in range(8)]

    with pytest.raises(HandoverAIError) as error:
        validate_advisory_output(output, package)

    assert error.value.code == "ai-output-too-large"


def test_envelope_includes_incident_uuid_and_date_scoped_ids():
    package = _package()
    envelope = build_handover_envelope(package, shift_date=SHIFT_DATE)
    allowed = envelope["citationContract"]["allowedEvidenceIds"]

    assert "incident:aadf7955-1945-4ce6-b6ca-41e7fa734a78" in allowed
    assert "ticket:NOC-556" in allowed
    assert "investigation:checkout-latency" in allowed
    assert "status:2099-12-31" in allowed
    assert "dashboard:2099-12-31" in allowed
    assert "readiness:2099-12-31" in allowed


def test_unavailable_evidence_citation_is_rejected():
    package = _package(
        datadog_snapshot=snapshot(incidents=[], freshness="unavailable"),
    )
    output = valid_advisory(package)
    output["watchItems"] = ["Context (datadog-context:2099-12-31)."]

    with pytest.raises(HandoverAIError) as error:
        validate_advisory_output(output, package)

    assert error.value.code == "evidence-reference-invalid"


def test_stale_ticket_described_as_current_is_rejected():
    package = _package(
        remote_health={"available": True, "freshness": "stale"},
    )
    output = valid_advisory(package)
    output["watchItems"] = ["Remote ticket is current [evidence:ticket:NOC-557]."]

    with pytest.raises(HandoverAIError) as error:
        validate_advisory_output(output, package)

    assert error.value.code == "ai-output-invalid"


def test_stale_evidence_must_be_labeled_in_the_same_item():
    package = _package(remote_health={"available": True, "freshness": "stale"})
    output = valid_advisory(package)
    output["watchItems"] = ["Remote ticket context [evidence:ticket:NOC-557]."]

    with pytest.raises(HandoverAIError) as error:
        validate_advisory_output(output, package)
    assert error.value.code == "ai-output-invalid"

    output["watchItems"] = ["Stale remote ticket context [evidence:ticket:NOC-557]."]
    assert validate_advisory_output(output, package)["watchItems"] == [
        "Stale remote ticket context [evidence:ticket:NOC-557]."
    ]


def test_partial_evidence_must_be_labeled_in_the_same_item():
    package = _package(
        local_summary={"available": False},
        local_tickets=[ticket("NOC-1", summary="Partially sourced ticket")],
    )
    output = valid_advisory(package)
    output["watchItems"] = ["Partially sourced ticket [evidence:ticket:NOC-1]."]

    with pytest.raises(HandoverAIError) as error:
        validate_advisory_output(output, package)
    assert error.value.code == "ai-output-invalid"

    output["watchItems"] = ["Partial evidence for ticket NOC-1 [evidence:ticket:NOC-1]."]
    assert validate_advisory_output(output, package)["watchItems"] == [
        "Partial evidence for ticket NOC-1 [evidence:ticket:NOC-1]."
    ]


def test_stale_or_partial_evidence_described_as_current_complete_fails():
    package = _package(remote_health={"available": True, "freshness": "stale"})
    output = valid_advisory(package)
    output["watchItems"] = [
        "Stale evidence is current and complete [evidence:ticket:NOC-557].",
    ]

    with pytest.raises(HandoverAIError) as error:
        validate_advisory_output(output, package)

    assert error.value.code == "ai-output-invalid"


def test_citation_failure_logs_only_ids_code_and_reason(caplog):
    package = _package()
    output = valid_advisory(package)
    output["watchItems"] = [
        "PRIVATE_ADVISORY_TEXT should never be logged [evidence:ticket:999999]."
    ]

    with pytest.raises(HandoverAIError) as error:
        validate_advisory_output(output, package)

    assert error.value.message == (
        "The AI provider cited unavailable or non-authoritative evidence."
    )
    assert "evidence-reference-invalid" in caplog.text
    assert "citation-not-supplied" in caplog.text
    assert "ticket:999999" in caplog.text
    assert "PRIVATE_ADVISORY_TEXT" not in caplog.text


def test_non_authoritative_citation_logs_reason_and_id(caplog):
    package = _package(
        investigations=[
            investigation("reviewed-one", reviewed=True),
            investigation("unreviewed-one", reviewed=False, finding=""),
        ],
        reviewed_findings=[reviewed_finding("reviewed-one")],
    )
    output = valid_advisory(package)
    output["watchItems"] = ["Unreviewed context [evidence:investigation:unreviewed-one]."]

    with pytest.raises(HandoverAIError):
        validate_advisory_output(output, package)

    assert "evidence-reference-invalid" in caplog.text
    assert "citation-not-allowed" in caplog.text
    assert "investigation:unreviewed-one" in caplog.text


def test_missing_citation_logs_reason_without_advisory_text(caplog):
    package = _package()
    output = valid_advisory(package)
    output["watchItems"] = ["PRIVATE_ADVISORY_TEXT without a citation."]

    with pytest.raises(HandoverAIError):
        validate_advisory_output(output, package)

    assert "evidence-reference-invalid" in caplog.text
    assert "citation-missing" in caplog.text
    assert "PRIVATE_ADVISORY_TEXT" not in caplog.text


def test_secret_like_citation_is_redacted_from_logs(caplog):
    package = _package()
    output = valid_advisory(package)
    output["watchItems"] = ["Invalid context [evidence:ticket:sk-abcdefghijklmnopqrstuvwx]."]

    with pytest.raises(HandoverAIError):
        validate_advisory_output(output, package)

    assert "evidence-reference-invalid" in caplog.text
    assert "sk-abcdefghijklmnopqrstuvwx" not in caplog.text
    assert "ticket:[redacted-citation]" in caplog.text


def test_exact_live_bracketed_readiness_citation_with_sentence_period_is_accepted():
    package = build_handover_evidence("2026-11-10", **loaders())
    output = valid_advisory(package)
    output["watchItems"] = ["Readiness context [evidence:readiness:2026-11-10]."]

    assert validate_advisory_output(output, package)["watchItems"] == [
        "Readiness context [evidence:readiness:2026-11-10]."
    ]


def test_exact_live_unbracketed_readiness_citation_with_period_is_rejected():
    package = build_handover_evidence("2026-11-10", **loaders())
    output = valid_advisory(package)
    output["watchItems"] = ["Readiness context readiness:2026-11-10."]

    with pytest.raises(HandoverAIError) as error:
        validate_advisory_output(output, package)

    assert error.value.code == "evidence-reference-invalid"


def test_bracketed_ticket_and_uuid_incident_citations_are_accepted():
    package = _package()
    output = valid_advisory(package)
    output["operationalRisks"] = [
        "Ticket context [evidence:ticket:NOC-556].",
        "Incident context [evidence:incident:aadf7955-1945-4ce6-b6ca-41e7fa734a78].",
    ]

    assert validate_advisory_output(output, package)["operationalRisks"] == [
        "Ticket context [evidence:ticket:NOC-556].",
        "Incident context [evidence:incident:aadf7955-1945-4ce6-b6ca-41e7fa734a78].",
    ]


def test_bracketed_stale_ticket_citation_requires_stale_label():
    package = _package(remote_health={"available": True, "freshness": "stale"})
    output = valid_advisory(package)
    output["watchItems"] = ["Stale ticket [evidence:ticket:NOC-557]."]

    assert validate_advisory_output(output, package)["watchItems"] == [
        "Stale ticket [evidence:ticket:NOC-557]."
    ]


@pytest.mark.parametrize(
    "malformed",
    [
        "[evidence:readiness:2099-12-31",
        "[[evidence:readiness:2099-12-31]]",
        "[evidence: readiness:2099-12-31]",
        "[evidence:readiness:2099-12-31.]",
        "[evidence:readiness:2099/12/31]",
        "[evidence:readiness:2099-12-31]]",
        "evidence:readiness:2099-12-31",
    ],
)
def test_malformed_or_unbracketed_citation_forms_are_not_accepted(malformed):
    package = _package()
    output = valid_advisory(package)
    output["watchItems"] = [f"Malformed citation {malformed}."]

    with pytest.raises(HandoverAIError) as error:
        validate_advisory_output(output, package)

    assert error.value.code == "evidence-reference-invalid"


@pytest.mark.parametrize(
    "claim",
    [
        "There are 29 open tickets [evidence:ticket:NOC-556].",
        "Open tickets: 30 [evidence:ticket:NOC-556].",
        "We have 1 investigation [evidence:investigation:checkout-latency].",
    ],
)
def test_ai_count_claims_are_rejected(claim):
    package = _package()
    output = valid_advisory(package)
    output["advisorySummary"] = [claim]

    with pytest.raises(HandoverAIError) as error:
        validate_advisory_output(output, package)

    assert error.value.code == "ai-output-invalid"


def _stale_package():
    return _package(
        local_tickets=[ticket("NOC-556", summary="Current ticket")],
        local_summary={"available": True, "count": 1, "items": []},
        remote_queue={
            "tickets": [
                ticket(
                    "NOC-590",
                    summary="Stale ticket",
                    tracked=False,
                    tracking_state="jira-only",
                )
            ],
            "cacheAvailable": True,
            "count": 1,
        },
        remote_health={"available": True, "freshness": "stale"},
        datadog_snapshot=snapshot(incidents=[incident()], freshness="stale"),
    )


def test_stale_qualification_examples_are_explicit_in_prompt_and_envelope():
    prompt = HANDOVER_SYSTEM_PROMPT
    assert "Stale ticket evidence indicates follow-up is still recorded" in prompt
    assert "Current status cannot be confirmed from this stale incident snapshot" in prompt
    assert "Ticket requires follow-up" in prompt
    assert "Incident is stable" in prompt

    package = _stale_package()
    contract = build_handover_envelope(package, shift_date=SHIFT_DATE)["citationContract"]
    assert "literal word" in contract["staleQualificationRule"]
    assert "wholly current" in contract["staleQualificationRule"]
    assert contract["staleQualificationExamples"]["valid"]
    assert contract["staleQualificationExamples"]["invalid"]


def test_good_stale_qualification_examples_are_accepted():
    package = _stale_package()
    output = valid_advisory(package)
    output["watchItems"] = [
        "Stale ticket evidence indicates follow-up is still recorded [evidence:ticket:NOC-590].",
        "Current status cannot be confirmed from this stale incident snapshot "
        "[evidence:incident:aadf7955-1945-4ce6-b6ca-41e7fa734a78].",
    ]

    assert validate_advisory_output(output, package)["watchItems"] == output["watchItems"]


@pytest.mark.parametrize(
    "text",
    [
        "Ticket requires follow-up [evidence:ticket:NOC-590].",
        "Incident is stable [evidence:incident:aadf7955-1945-4ce6-b6ca-41e7fa734a78].",
    ],
)
def test_live_stale_qualification_failures_are_rejected_and_logged(caplog, text):
    package = _stale_package()
    output = valid_advisory(package)
    output["watchItems"] = [text]

    with pytest.raises(HandoverAIError) as error:
        validate_advisory_output(output, package)

    assert error.value.code == "ai-output-invalid"
    assert "code=ai-output-invalid" in caplog.text
    assert "stale-evidence-unqualified" in caplog.text
    assert text not in caplog.text
    assert "Ticket requires follow-up" not in caplog.text
    assert "Incident is stable" not in caplog.text


def test_mixed_current_and_stale_items_must_identify_stale_evidence():
    package = _stale_package()
    output = valid_advisory(package)
    output["operationalRisks"] = [
        "Both tickets are current [evidence:ticket:NOC-556] [evidence:ticket:NOC-590]."
    ]

    with pytest.raises(HandoverAIError) as error:
        validate_advisory_output(output, package)
    assert error.value.code == "ai-output-invalid"

    output["operationalRisks"] = [
        "Stale ticket NOC-590 and current ticket NOC-556 are separate "
        "[evidence:ticket:NOC-590] [evidence:ticket:NOC-556]."
    ]
    assert validate_advisory_output(output, package)["operationalRisks"] == output["operationalRisks"]

    output["operationalRisks"] = [
        "Both tickets are current; stale evidence is included "
        "[evidence:ticket:NOC-556] [evidence:ticket:NOC-590]."
    ]
    with pytest.raises(HandoverAIError) as error:
        validate_advisory_output(output, package)
    assert error.value.code == "ai-output-invalid"
