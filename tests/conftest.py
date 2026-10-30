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
        jira_cache,
        investigations,
        ticket_sync,
        tickets,
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
        jira_cache,
        investigations,
        ticket_sync,
        tickets,
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

    monkeypatch.setattr(
        jira_cache,
        "CACHE_FILE",
        test_root / ".jira-open-tickets.json",
    )

    return test_root