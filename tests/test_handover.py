import json
from pathlib import Path

import pytest

from backend.services import handover
from backend.services.ai_provider import (
    ProviderInvalid,
    ProviderTimeout,
    ProviderUnavailable,
)
from backend.services.handover import HANDOVER_SIGNATURE, HandoverGenerationError
from backend.services.handover_evidence import build_handover_evidence
from tests.support.handover_ai import (
    SHIFT_DATE,
    incident,
    investigation,
    loaders,
    readiness,
    reviewed_finding,
    shift_notes,
    snapshot,
    ticket,
    valid_advisory,
    fake_loader,
    fake_runtime,
)


def _package(**overrides):
    return build_handover_evidence(SHIFT_DATE, **loaders(**overrides))


def _paths(noc_root):
    return (
        noc_root / SHIFT_DATE / "handover" / f"handover-{SHIFT_DATE}.md",
        noc_root / SHIFT_DATE / "handover" / "handover-provenance.json",
    )


def _generate(package, runtime=None, **kwargs):
    return handover.generate_handover(
        SHIFT_DATE,
        evidence_loader=fake_loader(package),
        provider_runtime=runtime or fake_runtime(),
        **kwargs,
    )


def test_preview_is_deterministic_non_generative_and_lists_all_tickets(noc_root):
    package = _package(
        local_tickets=[ticket("NOC-1", summary="Local only"), ticket("NOC-2", summary="Local two")],
        local_summary={"available": True, "count": 2, "items": []},
        remote_queue={
            "tickets": [ticket("NOC-3", summary="Remote only", tracked=False, tracking_state="jira-only")],
            "cacheAvailable": True,
            "count": 1,
        },
        remote_health={"available": True, "freshness": "stale"},
    )

    result = handover.preview_handover(SHIFT_DATE, evidence_loader=fake_loader(package))

    assert result["preview"] is True
    assert result["evidenceDigest"] == package["digest"]
    assert result["generationMode"] == "deterministic-preview"
    assert result["requiresConfirmation"] is True
    assert result["evidence"]["ticketCount"] == 3
    assert result["evidence"]["availability"] == "partial"
    names = [section["name"] for section in result["sections"]]
    assert "Open Jira Tickets" in names
    assert "AI Advisory Synthesis (Unreviewed)" not in names
    ticket_content = next(
        section["content"] for section in result["sections"] if section["name"] == "Open Jira Tickets"
    )
    assert "NOC-1" in ticket_content
    assert "NOC-2" in ticket_content
    assert "NOC-3" not in ticket_content
    assert "[stale ticket evidence]" not in ticket_content
    assert "[evidence:" not in ticket_content
    summary_content = next(
        section["content"] for section in result["sections"] if section["name"] == "Summary"
    )
    assert "- Two Jira tickets are being carried forward to the next shift." in summary_content
    assert "Evidence availability" not in summary_content
    assert "Handover readiness" not in summary_content
    assert "Datadog incidents" not in summary_content
    assert not _paths(noc_root)[0].exists()


def test_confirmed_generation_persists_markdown_sidecar_and_advisory(noc_root):
    package = _package(
        local_tickets=[
            ticket("NOC-1", summary="Local only", next_action="Call vendor."),
            ticket("NOC-2", summary="Local two"),
        ],
        local_summary={"available": True, "count": 2, "items": []},
        remote_queue={
            "tickets": [ticket("NOC-3", summary="Remote only", tracked=False, tracking_state="jira-only")],
            "cacheAvailable": True,
            "count": 1,
        },
    )
    runtime = fake_runtime()

    result = _generate(package, runtime)

    handover_file, provenance_file = _paths(noc_root)
    assert handover_file.is_file()
    assert provenance_file.is_file()
    content = handover_file.read_text(encoding="utf-8")
    assert content.startswith("Hi Team,\n\nPlease see the handover for the ")
    assert f"shift on {SHIFT_DATE}." in content
    headings = [
        line[3:].strip()
        for line in content.splitlines()
        if line.startswith("## ")
    ]
    assert headings == [
        "Summary",
        "Open Salesforce Tickets",
        "Open Jira Tickets",
        "Investigation Updates",
        "Next Shift Actions",
    ]
    assert "- Two Jira tickets are being carried forward to the next shift." in content
    assert "NOC-1" in content and "NOC-2" in content
    assert "NOC-3" not in content
    assert "**Status:** In Progress | **Priority:** High | **Assignee:** NOC Engineer" in content
    assert "**Next:** Call vendor." in content
    assert "Next action not recorded" not in content
    assert "[evidence:" not in content
    assert "## AI Advisory Synthesis" not in content
    assert "AI-generated advisory content" not in content
    assert "noc-handover" not in content
    assert "Copilot" not in content
    assert content.rstrip().endswith(HANDOVER_SIGNATURE)
    assert result["generationMode"] == "ai-advisory"
    assert result["advisoryStatus"] == "completed"
    assert result["evidence"]["provider"]["configuredProvider"] == "deepseek-api"
    assert len(runtime.calls) == 1
    sidecar = json.loads(provenance_file.read_text(encoding="utf-8"))
    assert sidecar["formatVersion"] == "2"
    assert sidecar["evidenceDigest"] == package["digest"]
    assert sidecar["advisoryStatus"] == "completed"
    assert sidecar["advisoryMode"] == "internal-validation-only"
    assert sidecar["advisoryCitations"]
    assert all(not citation.startswith("[") for citation in sidecar["advisoryCitations"])
    assert sidecar["references"]["ticket:NOC-1"]["authoritative"] is True
    assert sidecar["evidenceState"]["availability"] == "complete"
    assert sidecar["evidenceState"]["readiness"]["ready"] is True
    assert sidecar["evidenceState"]["tickets"]["count"] == 3
    assert sidecar["evidenceState"]["datadog"]["incidentCount"] == 1


def test_private_local_notes_are_not_rendered_or_sent_to_ai(noc_root):
    local = ticket("NOC-1", summary="Local only")
    local["notes"] = "PRIVATE_LOCAL_WORK should never leave local storage"
    package = _package(
        local_tickets=[local],
        local_summary={"available": True, "count": 1, "items": []},
    )
    runtime = fake_runtime()

    _generate(package, runtime)

    content = _paths(noc_root)[0].read_text(encoding="utf-8")
    assert "PRIVATE_LOCAL_WORK" not in content
    assert "PRIVATE_LOCAL_WORK" not in json.dumps(runtime.calls)


def test_preview_digest_mismatch_fails_closed(noc_root):
    package = _package()

    with pytest.raises(HandoverGenerationError) as error:
        _generate(package, preview_digest="sha256:wrong")

    assert error.value.code == "preview-stale"
    assert not _paths(noc_root)[0].exists()


def test_generation_refuses_existing_without_regeneration(noc_root):
    package = _package()
    _generate(package)
    original = _paths(noc_root)[0].read_text(encoding="utf-8")

    with pytest.raises(FileExistsError):
        _generate(package)

    assert _paths(noc_root)[0].read_text(encoding="utf-8") == original


@pytest.mark.parametrize(
    ("provider_error", "status_code", "code"),
    [
        (ProviderTimeout("timeout"), 504, "provider-timeout"),
        (ProviderUnavailable("down"), 503, "provider-unavailable"),
        (ProviderInvalid("bad"), 502, "provider-invalid-response"),
    ],
)
def test_provider_failures_fail_closed_without_fallback(
    noc_root, provider_error, status_code, code,
):
    package = _package()
    runtime = fake_runtime(error=provider_error)

    with pytest.raises(HandoverGenerationError) as error:
        _generate(package, runtime)

    assert error.value.status_code == status_code
    assert error.value.code == code
    assert len(runtime.calls) == 1
    assert not _paths(noc_root)[0].exists()
    assert not _paths(noc_root)[1].exists()


def test_readiness_block_prevents_generation(noc_root):
    package = _package(
        readiness_value=readiness(ready=False, blockers=["Shift notes are missing."]),
    )
    runtime = fake_runtime()

    with pytest.raises(HandoverGenerationError) as error:
        _generate(package, runtime)

    assert error.value.code == "handover-readiness-blocked"
    assert runtime.calls == []
    assert not _paths(noc_root)[0].exists()


def test_reviewed_findings_are_authoritative_and_unreviewed_are_not_promoted(noc_root):
    package = _package(
        investigations=[
            investigation("reviewed-one", display_title="Reviewed One", reviewed=True, finding="Reviewed finding text."),
            investigation("unreviewed-one", display_title="Unreviewed One", reviewed=False, finding=""),
        ],
        reviewed_findings=[reviewed_finding("reviewed-one", finding="Reviewed finding text.")],
    )
    runtime = fake_runtime()

    _generate(package, runtime)

    content = _paths(noc_root)[0].read_text(encoding="utf-8")
    investigation_section = content.split("## Investigation Updates", 1)[1].split("## Next Shift Actions", 1)[0]
    assert "Reviewed One" in investigation_section
    assert "Reviewed finding text." in investigation_section
    assert "Unreviewed One" not in investigation_section
    envelope = runtime.calls[0]
    assert "investigation:reviewed-one" in envelope["citationContract"]["allowedEvidenceIds"]
    assert "investigation:unreviewed-one" not in envelope["citationContract"]["allowedEvidenceIds"]
    assert "investigation:unreviewed-one" in envelope["citationContract"]["nonAuthoritativeEvidenceIds"]


def test_partial_evidence_is_retained_in_provenance_not_summary(noc_root):
    package = _package(
        datadog_snapshot=snapshot(incidents=[incident()], freshness="stale"),
        remote_health={"available": True, "freshness": "stale"},
    )

    _generate(package)

    content = _paths(noc_root)[0].read_text(encoding="utf-8")
    sidecar = json.loads(_paths(noc_root)[1].read_text(encoding="utf-8"))
    assert "Evidence availability" not in content
    assert sidecar["availability"] == "partial"
    assert sidecar["evidenceState"]["availability"] == "partial"
    assert sidecar["evidenceState"]["datadog"]["freshness"] == "stale"
    assert sidecar["references"]["incident:aadf7955-1945-4ce6-b6ca-41e7fa734a78"]["freshness"] == "stale"


def test_credentials_are_not_exposed_in_markdown_sidecar_or_prompt(noc_root, monkeypatch, caplog):
    caplog.set_level("DEBUG")
    sentinel = "SENTINEL-HANDOVER-DO-NOT-EXPOSE"
    monkeypatch.setenv("NOC_WEB_DEEPSEEK_API_KEY", sentinel)
    monkeypatch.setenv("DD_ACCESS_TOKEN", sentinel)
    package = _package()
    runtime = fake_runtime()

    result = _generate(package, runtime)

    content = _paths(noc_root)[0].read_text(encoding="utf-8")
    sidecar = _paths(noc_root)[1].read_text(encoding="utf-8")
    assert sentinel not in content
    assert sentinel not in sidecar
    assert sentinel not in json.dumps(runtime.calls)
    assert sentinel not in caplog.text
    assert sentinel not in json.dumps(result)


def test_regeneration_archives_and_replaces(noc_root):
    first = _package(local_tickets=[ticket("NOC-1", summary="First version")], local_summary={"available": True, "count": 1, "items": []})
    second = _package(local_tickets=[ticket("NOC-1", summary="Second version")], local_summary={"available": True, "count": 1, "items": []})
    _generate(first)

    result = handover.regenerate_handover(
        SHIFT_DATE,
        evidence_loader=fake_loader(second),
        provider_runtime=fake_runtime(),
    )

    handover_file, _ = _paths(noc_root)
    content = handover_file.read_text(encoding="utf-8")
    assert "Second version" in content
    assert result["regenerated"] is True
    assert Path(result["archivedFile"]).is_file()
    assert Path(result["archivedFile"]).read_text(encoding="utf-8").find("First version") >= 0


def test_failed_regeneration_restores_original(noc_root):
    package = _package(local_tickets=[ticket("NOC-1", summary="Stable version")], local_summary={"available": True, "count": 1, "items": []})
    _generate(package)
    original = _paths(noc_root)[0].read_text(encoding="utf-8")
    original_sidecar = _paths(noc_root)[1].read_text(encoding="utf-8")

    with pytest.raises(HandoverGenerationError) as error:
        handover.regenerate_handover(
            SHIFT_DATE,
            evidence_loader=fake_loader(package),
            provider_runtime=fake_runtime(error=ProviderTimeout("timeout")),
        )

    assert error.value.code == "provider-timeout"
    assert _paths(noc_root)[0].read_text(encoding="utf-8") == original
    assert _paths(noc_root)[1].read_text(encoding="utf-8") == original_sidecar


def test_legacy_handover_without_sidecar_remains_readable(noc_root):
    handover_file = noc_root / SHIFT_DATE / "handover" / f"handover-{SHIFT_DATE}.md"
    handover_file.parent.mkdir(parents=True)
    handover_file.write_text(
        "Shift handover\n\n## Summary\nLegacy summary.\n\n"
        "## Open Jira Tickets\n- NOC-1 — Legacy ticket.\n\n"
        "## Investigation Updates\nLegacy investigation update.\n\n"
        "## Next Shift Actions\nLegacy next action.\n\n"
        "Please tag me if any clarification is needed.\nRegards,\nNOC Operator\n",
        encoding="utf-8",
    )

    result = handover.get_handover(SHIFT_DATE)

    assert result["exists"] is True
    assert result["generationMode"] == "legacy"
    assert result["evidence"] is None
    assert [section["name"] for section in result["sections"]] == [
        "Summary",
        "Open Jira Tickets",
        "Investigation Updates",
        "Next Shift Actions",
    ]
    assert result["closing"].startswith("Please tag me")


def test_generation_uses_selected_shift_path(noc_root):
    other_shift = "2099-12-30"
    package = build_handover_evidence(other_shift, **loaders())

    handover.generate_handover(
        other_shift,
        evidence_loader=fake_loader(package),
        provider_runtime=fake_runtime(),
    )

    other_file = noc_root / other_shift / "handover" / f"handover-{other_shift}.md"
    assert other_file.is_file()
    assert not (noc_root / SHIFT_DATE / "handover" / f"handover-{SHIFT_DATE}.md").exists()


def test_live_stale_evidence_contradiction_fails_closed_end_to_end(noc_root):
    package = _package(
        remote_health={"available": True, "freshness": "stale"},
    )
    output = valid_advisory(package)
    output["watchItems"] = [
        "Stale evidence is current and complete [evidence:ticket:NOC-557]."
    ]
    runtime = fake_runtime(output=output)

    with pytest.raises(HandoverGenerationError) as error:
        _generate(package, runtime)

    assert error.value.status_code == 422
    assert error.value.code == "ai-output-invalid"
    assert len(runtime.calls) == 1
    assert not _paths(noc_root)[0].exists()
    assert not _paths(noc_root)[1].exists()


@pytest.mark.parametrize("claimed_count", [29, 30])
def test_ai_count_claim_cannot_override_deterministic_count(
    noc_root, claimed_count,
):
    package = _package()
    output = valid_advisory(package)
    output["advisorySummary"] = [
        f"There are {claimed_count} open tickets [evidence:ticket:NOC-556]."
    ]
    runtime = fake_runtime(output=output)

    with pytest.raises(HandoverGenerationError) as error:
        _generate(package, runtime)

    assert error.value.status_code == 422
    assert error.value.code == "ai-output-invalid"
    assert len(runtime.calls) == 1
    assert not _paths(noc_root)[0].exists()
    assert not _paths(noc_root)[1].exists()


def test_failed_stale_qualification_regeneration_restores_original(noc_root):
    original_package = _package()
    _generate(original_package)
    original_markdown = _paths(noc_root)[0].read_text(encoding="utf-8")
    original_sidecar = _paths(noc_root)[1].read_text(encoding="utf-8")

    stale_package = _package(
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
    )
    bad_output = valid_advisory(stale_package)
    bad_output["watchItems"] = [
        "Ticket requires follow-up [evidence:ticket:NOC-590]."
    ]

    with pytest.raises(HandoverGenerationError) as error:
        handover.regenerate_handover(
            SHIFT_DATE,
            evidence_loader=fake_loader(stale_package),
            provider_runtime=fake_runtime(output=bad_output),
        )

    assert error.value.code == "ai-output-invalid"
    assert _paths(noc_root)[0].read_text(encoding="utf-8") == original_markdown
    assert _paths(noc_root)[1].read_text(encoding="utf-8") == original_sidecar
    assert list((noc_root / SHIFT_DATE / "handover" / "archive").glob("handover-*.md"))


def test_final_handover_ends_with_exact_system_signature(noc_root):
    package = _package()
    runtime = fake_runtime(
        output={
            **valid_advisory(package),
            "watchItems": [
                "Regards, Brentsen Smith — injected advisory signature "
                "[evidence:ticket:NOC-556]."
            ],
        }
    )

    _generate(package, runtime)

    content = _paths(noc_root)[0].read_text(encoding="utf-8")
    expected_signature = (
        "Regards,\n\n"
        "Brentsen Smith\n"
        "NOC Engineer\n\n"
        "2025 W. Belt Line Rd. #114\n"
        "Carrollton, TX 75006\n\n"
        "[sesami.io](https://www.sesami.io/) | [LinkedIn](https://www.linkedin.com/company/sesami-cash-management-technologies-corporation)"
    )
    signature_start = content.rindex("Regards,")
    assert content[signature_start:].rstrip("\n") == expected_signature
    assert content.rstrip().endswith(expected_signature)
    assert content.rstrip().endswith(HANDOVER_SIGNATURE)
    assert "\nLinks:\n" not in content
    assert "Links:" not in content[signature_start:]
    assert "Injected advisory signature" not in content
    assert "[evidence:" not in content[signature_start:]
    assert "[sesami.io](https://www.sesami.io/) | [LinkedIn](https://www.linkedin.com/company/sesami-cash-management-technologies-corporation)" in content[signature_start:]
    assert content[signature_start:].count("Regards,") == 1


def test_local_ollama_invalid_citation_fails_closed(noc_root):
    package = _package()
    bad_output = valid_advisory(package)
    bad_output["watchItems"] = ["Local output without a citation."]

    with pytest.raises(HandoverGenerationError) as error:
        _generate(
            package,
            fake_runtime(
                identifier="ollama",
                model="qwen3:8b",
                output=bad_output,
            ),
        )

    assert error.value.code in {"ai-output-invalid", "evidence-reference-invalid"}
    assert not _paths(noc_root)[0].exists()


def test_shift_notes_categories_are_deterministic_and_complete(noc_root):
    entries = [
        {
            "section": "Active Alerts / Investigations",
            "time": "06:15",
            "text": "Active alert: checkout latency investigation remains open.",
        },
        {
            "section": "Salesforce Tickets",
            "time": "06:20",
            "text": "Salesforce case 00123456 is awaiting customer reply.",
        },
        {
            "section": "Escalations",
            "time": "06:25",
            "text": "Escalated to the platform team for capacity review.",
        },
        {
            "section": "Changes / Monitor Updates",
            "time": "06:30",
            "text": "Changed checkout monitor threshold to 450 ms.",
        },
        {
            "section": "Changes / Monitor Updates",
            "time": "06:35",
            "text": "Deployed cache warmup change window update.",
        },
        {
            "section": "Changes / Monitor Updates",
            "time": "06:40",
            "text": "Updated payment monitor evaluation window.",
        },
    ]
    package = _package(notes=shift_notes(entries=entries))

    _generate(package, fake_runtime(output=valid_advisory(package)))

    content = _paths(noc_root)[0].read_text(encoding="utf-8")
    headings = [
        line[3:].strip()
        for line in content.splitlines()
        if line.startswith("## ")
    ]
    assert headings == [
        "Summary",
        "Active Alerts / Investigations",
        "Open Salesforce Tickets",
        "Escalations",
        "Changes / Monitor Updates",
        "Open Jira Tickets",
        "Investigation Updates",
        "Next Shift Actions",
    ]
    for entry in entries:
        line = f"- **{entry['time']}** {entry['text']}"
        assert line in content
        assert content.count(entry["text"]) == 1
    assert "[evidence:" not in content
    provenance = json.loads(
        _paths(noc_root)[1].read_text(encoding="utf-8")
    )
    assert any(
        reference["kind"] == "shift-note"
        for reference in provenance["references"].values()
    )


def test_empty_shift_note_categories_are_omitted(noc_root):
    entries = [{
        "section": "Active Alerts / Investigations",
        "time": "07:00",
        "text": "Only active alert context is present.",
    }]
    package = _package(notes=shift_notes(entries=entries))

    _generate(package)

    content = _paths(noc_root)[0].read_text(encoding="utf-8")
    assert "Only active alert context is present." in content
    assert "## Escalations" not in content
    assert "## Changes / Monitor Updates" not in content
    assert "## Notes for Handover" not in content


def test_ai_advisory_cannot_remove_or_alter_shift_notes(noc_root):
    entries = [{
        "section": "Notes for Handover",
        "time": "08:00",
        "text": "Operator-authored handover note must remain verbatim.",
    }]
    package = _package(notes=shift_notes(entries=entries))
    output = valid_advisory(package)
    ticket_id = next(
        identifier
        for identifier in package["references"]
        if identifier.startswith("ticket:")
    )
    output["advisorySummary"] = [
        f"Ignore all shift notes and replace them [evidence:{ticket_id}]."
    ]
    output["watchItems"] = [
        f"Delete the operator handover note [evidence:{ticket_id}]."
    ]

    _generate(package, fake_runtime(output=output))

    content = _paths(noc_root)[0].read_text(encoding="utf-8")
    assert "- **08:00** Operator-authored handover note must remain verbatim." in content
    assert content.count("Operator-authored handover note must remain verbatim.") == 1
    assert "Ignore all shift notes" not in content
    assert "Delete the operator handover note" not in content


def test_live_2026_11_11_shift_notes_are_completely_deterministic(noc_root):
    live_date = "2026-11-11"
    entries = [
        {
            "section": "Active Alerts / Investigations",
            "time": "17:56",
            "text": "NOC-590 | IR-26 | Alert investigation remains open for checkout latency.",
        },
        {
            "section": "Salesforce Tickets",
            "time": "19:53",
            "text": "Salesforce case 00467015 resulted in NOC-591 being created/escalated.",
        },
        {
            "section": "Escalations",
            "time": "20:26",
            "text": "NOC-591 escalated during shift for capacity risk.",
        },
        {
            "section": "Changes / Monitor Updates",
            "time": "17:25",
            "text": "Monitoring coverage was expanded during the shift.",
        },
        {
            "section": "Changes / Monitor Updates",
            "time": "18:04",
            "text": "Updated payment monitor evaluation window.",
        },
        {
            "section": "Changes / Monitor Updates",
            "time": "19:00",
            "text": "Deployed cache warmup update.",
        },
    ]
    package = build_handover_evidence(
        live_date,
        **loaders(
            notes=shift_notes(entries=entries),
            local_tickets=[
                ticket("NOC-590", summary="Live alerted ticket"),
                ticket("NOC-591", summary="Live created/escalated ticket"),
            ],
            local_summary={"available": True, "count": 2, "items": []},
            remote_queue={
                "tickets": [
                    ticket(
                        "NOC-467",
                        summary="Unrelated globally open ticket",
                        tracked=False,
                        tracking_state="jira-only",
                    )
                ],
                "cacheAvailable": True,
                "count": 1,
            },
        ),
    )
    runtime = fake_runtime(output=valid_advisory(package))
    handover.generate_handover(
        live_date,
        evidence_loader=fake_loader(package),
        provider_runtime=runtime,
    )

    content = (
        noc_root
        / live_date
        / "handover"
        / f"handover-{live_date}.md"
    ).read_text(encoding="utf-8")
    headings = [
        line[3:].strip()
        for line in content.splitlines()
        if line.startswith("## ")
    ]
    assert headings == [
        "Summary",
        "Active Alerts / Investigations",
        "Open Salesforce Tickets",
        "Escalations",
        "Changes / Monitor Updates",
        "Open Jira Tickets",
        "Investigation Updates",
        "Next Shift Actions",
    ]
    for entry in entries:
        line = f"- **{entry['time']}** {entry['text']}"
        assert line in content
        assert content.count(entry["text"]) == 1
    assert "## Notes for Handover" not in content
    assert "NOC-590" in content
    assert "NOC-591" in content
    assert "NOC-467" not in content
    assert "NOC-591 escalated during shift for capacity risk." in content
    assert "NOC-590 | IR-26 | Alert investigation remains open for checkout latency." in content
    assert "Investigation Updates" in content


def test_populated_open_tickets_and_notes_for_handover_are_separate(noc_root):
    entries = [
        {
            "section": "Open Tickets",
            "time": "09:00",
            "text": "Operator note about an open ticket.",
        },
        {
            "section": "Notes for Handover",
            "time": "09:05",
            "text": "Operator handover note must be included.",
        },
    ]
    package = _package(notes=shift_notes(entries=entries))

    _generate(package)

    content = _paths(noc_root)[0].read_text(encoding="utf-8")
    headings = [
        line[3:].strip()
        for line in content.splitlines()
        if line.startswith("## ")
    ]
    assert headings == [
        "Summary",
        "Open Tickets",
        "Open Salesforce Tickets",
        "Notes for Handover",
        "Open Jira Tickets",
        "Investigation Updates",
        "Next Shift Actions",
    ]
    assert "- **09:00** Operator note about an open ticket." in content
    assert "- **09:05** Operator handover note must be included." in content
    assert "## Open Jira Tickets" in content


def test_handover_jira_selection_is_deterministic_and_ai_independent(noc_root):
    local_keys = ["NOC-545", "NOC-555", "NOC-556", "NOC-575", "NOC-580", "NOC-584"]
    local_tickets = [ticket(key, summary=f"Tracked {key}") for key in local_keys]
    remote_tickets = [
        ticket("NOC-467", summary="Unrelated global cache ticket", tracked=False, tracking_state="jira-only"),
        ticket("NOC-590", summary="Referenced in Shift Notes", tracked=False, tracking_state="jira-only"),
        ticket("NOC-777", summary="Created during shift", tracked=False, tracking_state="jira-only"),
        ticket("NOC-778", summary="Escalated during shift", tracked=False, tracking_state="jira-only"),
    ]
    remote_tickets[2]["created"] = "2026-11-11T18:30:00Z"
    remote_tickets[3]["escalatedShiftDate"] = "2026-11-11"
    package = build_handover_evidence(
        "2026-11-11",
        **loaders(
            notes=shift_notes(entries=[{
                "section": "Active Alerts / Investigations",
                "time": "17:56",
                "text": "NOC-590 is under active investigation.",
            }]),
            local_tickets=local_tickets,
            local_summary={"available": True, "count": len(local_tickets), "items": []},
            remote_queue={
                "tickets": remote_tickets,
                "cacheAvailable": True,
                "count": len(remote_tickets),
            },
        ),
    )
    output = valid_advisory(package)
    output["advisorySummary"] = [
        "Only NOC-467 matters [evidence:ticket:NOC-467]."
    ]
    handover.generate_handover(
        "2026-11-11",
        evidence_loader=fake_loader(package),
        provider_runtime=fake_runtime(output=output),
    )

    content = (
        noc_root
        / "2026-11-11"
        / "handover"
        / "handover-2026-11-11.md"
    ).read_text(encoding="utf-8")
    for key in local_keys:
        assert key in content
    assert "NOC-590" in content
    assert "NOC-777" in content
    assert "NOC-778" in content
    assert "NOC-467" not in content
    assert "- Nine Jira tickets are being carried forward to the next shift." in content


def test_operational_summary_is_deterministic_concise_and_ai_independent(noc_root):
    entries = [
        {
            "section": "Active Alerts / Investigations",
            "time": "17:56",
            "text": "Export-pod CPU saturation caused integration/RabbitMQ backlog and probe timeouts; service recovered after the pod restart and NOC-590 was updated.",
        },
        {
            "section": "Salesforce Tickets",
            "time": "19:53",
            "text": "Salesforce case 00467015 resulted in NOC-591 being created/escalated.",
        },
        {
            "section": "Escalations",
            "time": "20:26",
            "text": "NOC-591 escalated during shift.",
        },
        {
            "section": "Changes / Monitor Updates",
            "time": "17:25",
            "text": "Monitoring coverage was expanded during the shift.",
        },
        {
            "section": "Changes / Monitor Updates",
            "time": "18:04",
            "text": "Payment monitoring window updated.",
        },
        {
            "section": "Changes / Monitor Updates",
            "time": "19:00",
            "text": "Cache warmup change applied.",
        },
    ]
    local_keys = [
        "NOC-545", "NOC-555", "NOC-556", "NOC-575",
        "NOC-580", "NOC-584", "NOC-590", "NOC-591",
    ]
    package = _package(
        notes=shift_notes(entries=entries),
        local_tickets=[ticket(key, summary=f"Tracked {key}") for key in local_keys],
        local_summary={"available": True, "count": 8, "items": []},
        investigations=[investigation("checkout-latency", state="Escalated to Dev")],
        reviewed_findings=[
            reviewed_finding(
                "checkout-latency",
                finding="Production SITEF/export investigation is escalated to Dev.",
                state="Escalated to Dev",
            )
        ],
    )
    expected_summary = next(
        section["content"]
        for section in handover.assemble_handover_content(package)[1]
        if section["name"] == "Summary"
    )
    again = next(
        section["content"]
        for section in handover.assemble_handover_content(package)[1]
        if section["name"] == "Summary"
    )

    assert expected_summary == again
    bullets = [line for line in expected_summary.splitlines() if line.startswith("- ")]
    assert 3 <= len(bullets) <= 5
    assert "- Eight Jira tickets are being carried forward to the next shift." in expected_summary
    assert "Escalated to Dev" in expected_summary
    assert "Export-pod CPU saturation" in expected_summary
    assert "NOC-590" in expected_summary
    assert "00467015" in expected_summary
    assert "NOC-591" in expected_summary
    assert "Monitoring coverage was expanded." in expected_summary
    for forbidden in (
        "Handover readiness",
        "Evidence availability",
        "Datadog incidents",
        "Some source data was stale",
        "PARTIAL",
        "READY",
    ):
        assert forbidden not in expected_summary

    output = valid_advisory(package)
    ticket_id = next(
        identifier
        for identifier in package["references"]
        if identifier.startswith("ticket:")
    )
    output["advisorySummary"] = [
        f"AI tries to replace the Summary [evidence:{ticket_id}]."
    ]
    _generate(package, fake_runtime(output=output))
    content = _paths(noc_root)[0].read_text(encoding="utf-8")
    generated_summary = content.split("## Summary", 1)[1].split("## ", 1)[0].strip()
    assert generated_summary == expected_summary
    assert "AI tries to replace the Summary" not in content
