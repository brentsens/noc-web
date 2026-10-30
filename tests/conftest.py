import pytest


@pytest.fixture
def fake_assistant_provider(monkeypatch):
    """Inject a deterministic provider and capture its bounded request envelopes."""
    from backend.app import app, configure_assistant_provider

    calls = []

    def install(response):
        def provider(envelope):
            calls.append(envelope)
            if isinstance(response, Exception):
                raise response
            return response

        monkeypatch.setattr(app.state, "assistant_provider", None)
        configure_assistant_provider(provider)
        return calls

    return install


@pytest.fixture
def readiness_workspace(tmp_path):
    """Create isolated, non-sensitive readiness inputs."""
    from datetime import datetime, timezone
    import stat

    from backend.config import CacheSourcePolicy, ConfigurationProfile
    from backend.services.readiness import COMMAND_CATALOG

    root = tmp_path / "readiness-noc"
    records = root / "tickets" / "open"
    command_directory = root / "bin"
    probe_directory = root / "probe"
    records.mkdir(parents=True)
    command_directory.mkdir()
    probe_directory.mkdir()
    (records / "NOC-1.json").write_text(
        '{"id":"NOC-1","jira":{},"noc":{},"metadata":{}}',
        encoding="utf-8",
    )
    (root / ".jira-open-tickets.json").write_text(
        '{"refreshedAt":"' + datetime.now(timezone.utc).isoformat() + '","tickets":[]}',
        encoding="utf-8",
    )
    for command, _ in COMMAND_CATALOG:
        executable = command_directory / command
        output = "printf 'noc-inv-contract=1\\n'\n" if command == "noc-inv" else ""
        executable.write_text(f"#!/bin/sh\n{output}exit 0\n", encoding="utf-8")
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    return ConfigurationProfile(
        noc_root=root,
        noc_bin=command_directory,
        probe_directory=probe_directory,
        cache_sources=(CacheSourcePolicy("jiraOpenTickets", 1800),),
        command_timeout_seconds=1,
        settings=(),
    )


@pytest.fixture
def investigation_workspace(readiness_workspace, monkeypatch):
    """Provide configured paths and fake local commands for generation tests."""
    monkeypatch.setenv("NOC_WEB_NOC_ROOT", str(readiness_workspace.noc_root))
    monkeypatch.setenv("NOC_WEB_NOC_BIN", str(readiness_workspace.noc_bin))
    monkeypatch.setenv(
        "NOC_WEB_READINESS_PROBE_DIR",
        str(readiness_workspace.probe_directory),
    )
    monkeypatch.setenv("NOC_WEB_INVESTIGATION_TIMEOUT_SECONDS", "3")
    return readiness_workspace


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
        ai_reports,
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
        ai_reports,
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