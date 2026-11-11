from backend.services import handover
from backend.services.handover_evidence import build_handover_evidence
from tests.support.handover_ai import (
    SHIFT_DATE,
    fake_loader,
    loaders,
    readiness,
    ticket,
)


def _package(**overrides):
    return build_handover_evidence(SHIFT_DATE, **loaders(**overrides))


def test_preview_is_deterministic_without_ai_or_persistence(noc_root):
    package = _package()

    result = handover.preview_handover(SHIFT_DATE, evidence_loader=fake_loader(package))

    assert result["preview"] is True
    assert result["generationMode"] == "deterministic-preview"
    assert result["requiresConfirmation"] is True
    assert result["evidenceDigest"] == package["digest"]
    assert result["sections"]
    assert not (noc_root / SHIFT_DATE / "handover").exists()


def test_preview_reports_readiness_blockers_without_state_change(noc_root):
    package = _package(
        readiness_value=readiness(ready=False, blockers=["Review items are unresolved."]),
        local_tickets=[ticket("NOC-1")],
        local_summary={"available": True, "count": 1, "items": []},
    )

    result = handover.preview_handover(SHIFT_DATE, evidence_loader=fake_loader(package))

    assert result["readiness"]["enabled"] is False
    assert result["readiness"]["blockers"] == ["Review items are unresolved."]
    assert not (noc_root / SHIFT_DATE / "handover").exists()


def test_preview_digest_changes_when_ticket_evidence_changes():
    first = _package(local_tickets=[ticket("NOC-1", summary="One")], local_summary={"available": True, "count": 1, "items": []})
    second = _package(local_tickets=[ticket("NOC-1", summary="Two")], local_summary={"available": True, "count": 1, "items": []})

    first_result = handover.preview_handover(SHIFT_DATE, evidence_loader=fake_loader(first))
    second_result = handover.preview_handover(SHIFT_DATE, evidence_loader=fake_loader(second))

    assert first_result["evidenceDigest"] != second_result["evidenceDigest"]
