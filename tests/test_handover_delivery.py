import subprocess

import pytest

from backend.services import handover, handover_delivery
from backend.services.handover_evidence import build_handover_evidence
from tests.support.handover_ai import (
    SHIFT_DATE,
    fake_loader,
    fake_runtime,
    loaders,
)


def _package():
    return build_handover_evidence(SHIFT_DATE, **loaders())


def _generate(noc_root):
    package = _package()
    runtime = fake_runtime()
    handover.generate_handover(
        SHIFT_DATE,
        evidence_loader=fake_loader(package),
        provider_runtime=runtime,
    )
    return runtime


def _mock_delivery(monkeypatch, *, returncode=0, stdout="preview output"):
    captured = []

    def fake_run(args, **kwargs):
        captured.append((args, kwargs))
        return subprocess.CompletedProcess(
            args=args,
            returncode=returncode,
            stdout=stdout,
            stderr="",
        )

    monkeypatch.setattr(handover_delivery.shutil, "which", lambda command: "/mock/m365")
    monkeypatch.setattr(handover_delivery.subprocess, "run", fake_run)
    return captured


def test_delivery_preview_and_send_use_markdown_only(noc_root, monkeypatch):
    runtime = _generate(noc_root)
    captured = _mock_delivery(monkeypatch)

    preview = handover_delivery.preview_handover_email(
        SHIFT_DATE,
        "operator@example.com",
    )
    sent = handover_delivery.send_handover_email(
        SHIFT_DATE,
        "operator@example.com",
    )

    assert preview["sent"] is False
    assert preview["preview"] == "preview output"
    assert sent["sent"] is True
    handover_file = noc_root / SHIFT_DATE / "handover" / f"handover-{SHIFT_DATE}.md"
    sidecar_file = noc_root / SHIFT_DATE / "handover" / "handover-provenance.json"
    for args, _kwargs in captured:
        assert "--body-file" in args
        assert str(handover_file) in args
        assert str(sidecar_file) not in args
    assert len(runtime.calls) == 1


def test_delivery_rejects_invalid_recipient(noc_root, monkeypatch):
    _generate(noc_root)
    _mock_delivery(monkeypatch)

    with pytest.raises(ValueError):
        handover_delivery.preview_handover_email(SHIFT_DATE, "not-an-email")


def test_delivery_failure_does_not_change_local_record(noc_root, monkeypatch):
    _generate(noc_root)
    handover_file = noc_root / SHIFT_DATE / "handover" / f"handover-{SHIFT_DATE}.md"
    original = handover_file.read_text(encoding="utf-8")
    _mock_delivery(monkeypatch, returncode=1)

    with pytest.raises(handover_delivery.ExternalOperationFailed):
        handover_delivery.send_handover_email(SHIFT_DATE, "operator@example.com")

    assert handover_file.read_text(encoding="utf-8") == original
