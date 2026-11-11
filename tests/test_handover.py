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
    assert "NOC-3" in ticket_content
    assert "[stale ticket evidence]" not in ticket_content
    assert "[evidence:" not in ticket_content
    summary_content = next(
        section["content"] for section in result["sections"] if section["name"] == "Summary"
    )
    assert "Some source data was stale, partial, or unavailable" in summary_content
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
    assert "- Open tickets: 3." in content
    assert "NOC-1" in content and "NOC-2" in content and "NOC-3" in content
    assert "Assignee: NOC Engineer" in content
    assert "Environment: uspri-prod" in content
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


def test_partial_evidence_is_disclosed_in_markdown_and_sidecar(noc_root):
    package = _package(
        datadog_snapshot=snapshot(incidents=[incident()], freshness="stale"),
        remote_health={"available": True, "freshness": "stale"},
    )

    _generate(package)

    content = _paths(noc_root)[0].read_text(encoding="utf-8")
    sidecar = json.loads(_paths(noc_root)[1].read_text(encoding="utf-8"))
    assert "Evidence availability: PARTIAL." in content
    assert sidecar["availability"] == "partial"
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
