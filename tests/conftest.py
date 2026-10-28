import pytest


@pytest.fixture
def noc_root(
    tmp_path,
    monkeypatch,
):

    test_root = (
        tmp_path / "noc"
    )

    test_root.mkdir()

    from backend import config

    from backend.services import (
        end_shift,
        handover,
        handover_delivery,
        shift_notes,
        start_shift,
        status,
        health,
        ticket_sync,
    )

    modules = (
        config,
        end_shift,
        handover,
        handover_delivery,
        shift_notes,
        start_shift,
        status,
        health,
        ticket_sync,
    )

    for module in modules:

        monkeypatch.setattr(
            module,
            "NOC_ROOT",
            test_root,
        )

        monkeypatch.setattr(
    ticket_sync,
    "SYNC_STATE_FILE",
    test_root / ".ticket-sync-state.json",
)

    return test_root