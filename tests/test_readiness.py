import os
import stat
from datetime import datetime, timedelta, timezone

import pytest

from backend import config
from backend.config import (
    CacheSourcePolicy,
    ConfigurationError,
    ConfigurationProfile,
    DEFAULT_INVESTIGATION_TIMEOUT_SECONDS,
    resolve_readiness_profile,
)
from backend.services import readiness


def _profile(root):
    return ConfigurationProfile(
        noc_root=root,
        noc_bin=root / "bin",
        probe_directory=root / "probe",
        cache_sources=(CacheSourcePolicy("jiraOpenTickets", 1800),),
        command_timeout_seconds=1,
        settings=(),
    )


def _prepared_profile(tmp_path):
    root = tmp_path / "noc"
    records = root / "tickets" / "open"
    binary = root / "bin"
    probe = root / "probe"
    records.mkdir(parents=True)
    binary.mkdir()
    probe.mkdir()
    (records / "NOC-1.json").write_text(
        '{"id":"NOC-1","jira":{},"noc":{},"metadata":{}}',
        encoding="utf-8",
    )
    (root / ".jira-open-tickets.json").write_text(
        '{"refreshedAt":"' + datetime.now(timezone.utc).isoformat() + '","tickets":[]}',
        encoding="utf-8",
    )
    for command, _ in readiness.COMMAND_CATALOG:
        executable = binary / command
        output = "printf 'noc-inv-contract=1\\n'\n" if command == "noc-inv" else ""
        executable.write_text(f"#!/bin/sh\n{output}exit 0\n", encoding="utf-8")
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    return _profile(root)


def test_absent_overrides_preserve_historical_defaults(monkeypatch):
    monkeypatch.delenv("NOC_WEB_NOC_ROOT", raising=False)
    monkeypatch.delenv("NOC_WEB_NOC_BIN", raising=False)
    monkeypatch.delenv("NOC_WEB_READINESS_PROBE_DIR", raising=False)
    profile = resolve_readiness_profile({})

    assert profile.noc_root == config.HOME / "noc"
    assert profile.noc_bin == config.HOME / ".local" / "bin"
    assert profile.investigation_timeout_seconds == DEFAULT_INVESTIGATION_TIMEOUT_SECONDS
    assert {setting.source for setting in profile.settings} == {"default"}


def test_valid_explicit_overrides_are_redacted_and_normalized(tmp_path):
    root = tmp_path / "noc"
    binary = root / "bin"
    probe = root / "probe"
    binary.mkdir(parents=True)
    probe.mkdir()
    profile = resolve_readiness_profile({
        "NOC_WEB_NOC_ROOT": str(root),
        "NOC_WEB_NOC_BIN": str(binary),
        "NOC_WEB_READINESS_PROBE_DIR": str(probe),
        "NOC_WEB_JIRA_CACHE_MAX_AGE_SECONDS": "60",
        "NOC_WEB_COMMAND_TIMEOUT_SECONDS": "5",
        "NOC_WEB_INVESTIGATION_TIMEOUT_SECONDS": "300",
    })

    assert profile.noc_root == root.resolve()
    assert profile.cache_sources[0].maximum_age_seconds == 60
    assert profile.command_timeout_seconds == 5
    assert profile.investigation_timeout_seconds == 300
    assert {setting.source for setting in profile.settings} == {"explicit"}
    assert str(root) not in str(profile.settings)


@pytest.mark.parametrize("name,value", [
    ("NOC_WEB_NOC_ROOT", ""),
    ("NOC_WEB_NOC_ROOT", "relative"),
    ("NOC_WEB_NOC_BIN", ""),
    ("NOC_WEB_READINESS_PROBE_DIR", "/not/a/valid/probe"),
    ("NOC_WEB_JIRA_CACHE_MAX_AGE_SECONDS", "0"),
    ("NOC_WEB_JIRA_CACHE_MAX_AGE_SECONDS", "nope"),
    ("NOC_WEB_COMMAND_TIMEOUT_SECONDS", "61"),
    ("NOC_WEB_INVESTIGATION_TIMEOUT_SECONDS", "0"),
    ("NOC_WEB_INVESTIGATION_TIMEOUT_SECONDS", "901"),
    ("NOC_WEB_INVESTIGATION_TIMEOUT_SECONDS", "unbounded"),
])
def test_invalid_explicit_override_never_falls_back(name, value):
    with pytest.raises(ConfigurationError) as error:
        resolve_readiness_profile({name: value})
    assert error.value.setting == name
    assert error.value.explicit is True
    if value:
        assert value not in str(error.value)


def test_assessment_is_ready_with_compatible_records_and_safe_probes(readiness_workspace):
    result = readiness.assess_readiness(readiness_workspace, "2099-12-31")

    assert result["overallStatus"] == "ready"
    assert result["readOnly"] is True
    assert result["liveness"][0]["status"] == "notConfigured"
    assert not list(readiness_workspace.probe_directory.iterdir())
    assert not list(readiness_workspace.noc_root.glob(".readiness-*"))


def test_readiness_reports_generation_commands_and_investigation_storage(
    readiness_workspace,
):
    result = readiness.assess_readiness(readiness_workspace, "2099-12-31")
    checks = {item["id"]: item for item in result["checks"]}

    assert checks["command.noc-inv"]["status"] == "ready"
    assert checks["command.copilot"]["status"] == "ready"
    assert checks["investigationStorage.path"]["status"] == "ready"


def test_readiness_rejects_incompatible_noc_inv_contract(readiness_workspace):
    executable = readiness_workspace.noc_bin / "noc-inv"
    executable.write_text("#!/bin/sh\nprintf 'legacy-contract\\n'\nexit 0\n", encoding="utf-8")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)

    result = readiness.assess_readiness(readiness_workspace, "2099-12-31")
    checks = {item["id"]: item for item in result["checks"]}

    assert checks["command.noc-inv"]["status"] == "notReady"
    assert "compatible noc-inv contract" in checks["command.noc-inv"]["correctiveAction"]


def test_readiness_reports_missing_copilot_command(readiness_workspace):
    (readiness_workspace.noc_bin / "copilot").unlink()

    result = readiness.assess_readiness(readiness_workspace, "2099-12-31")

    assert next(
        item for item in result["checks"] if item["id"] == "command.copilot"
    )["status"] == "notReady"


def test_missing_default_locations_are_configuration_not_ready(tmp_path):
    profile = _profile(tmp_path / "missing")

    result = readiness.assess_readiness(profile, "2099-12-31")

    assert result["configuration"]["status"] == "notReady"
    assert result["overallStatus"] == "notReady"


@pytest.mark.parametrize("record", [
    '{"id":"NOC-1","jira":[],"noc":{},"metadata":{}}',
    "not-json",
])
def test_incompatible_noc_records_are_not_converted(tmp_path, record):
    profile = _prepared_profile(tmp_path)
    record_file = profile.noc_root / "tickets" / "open" / "NOC-1.json"
    record_file.write_text(record, encoding="utf-8")

    result = readiness.assess_readiness(profile, "2099-12-31")

    noc_check = next(item for item in result["checks"] if item["id"] == "nocData.records")
    assert noc_check["status"] == "notReady"
    assert record_file.read_text(encoding="utf-8") == record


def test_cache_age_boundary_is_source_specific(tmp_path):
    profile = _prepared_profile(tmp_path)
    cache_file = profile.noc_root / ".jira-open-tickets.json"
    refreshed = datetime.now(timezone.utc) - timedelta(seconds=1800)
    cache_file.write_text(
        '{"refreshedAt":"' + refreshed.isoformat() + '","tickets":[]}', encoding="utf-8"
    )

    result = readiness.assess_readiness(profile, "2099-12-31")
    cache_check = next(item for item in result["checks"] if item["category"] == "cache")
    assert cache_check["status"] == "notReady"


def test_command_failure_and_liveness_are_separate(tmp_path, monkeypatch):
    profile = _prepared_profile(tmp_path)
    command = profile.noc_bin / "tix"
    command.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    monkeypatch.setattr(readiness, "LIVENESS_CATALOG", (("jira", ("true",)),))

    result = readiness.assess_readiness(profile, "2099-12-31")

    assert next(item for item in result["checks"] if item["id"] == "command.tix")["status"] == "notReady"
    assert result["liveness"][0]["status"] == "available"
    assert result["overallStatus"] == "notReady"


def test_write_probe_does_not_overwrite_existing_file_and_cleans_up(tmp_path, monkeypatch):
    profile = _prepared_profile(tmp_path)
    existing = profile.probe_directory / ".readiness-keep"
    existing.write_text("unchanged", encoding="utf-8")
    monkeypatch.setattr(readiness.uuid, "uuid4", lambda: type("Id", (), {"hex": "keep"})())

    check = readiness._write_check(profile)

    assert check.status == "notReady"
    assert existing.read_text(encoding="utf-8") == "unchanged"


def test_readiness_discards_sensitive_command_output(tmp_path, monkeypatch):
    profile = _prepared_profile(tmp_path)
    secret = "token-value-123"

    class Result:
        returncode = 0
        stdout = secret

    def failed_run(*args, **kwargs):
        assert kwargs["stderr"] is readiness.subprocess.DEVNULL
        command = args[0][0]
        if command.endswith("/noc-inv"):
            assert kwargs["stdout"] is readiness.subprocess.PIPE
        else:
            assert kwargs["stdout"] is readiness.subprocess.DEVNULL
        return Result()

    monkeypatch.setattr(readiness.subprocess, "run", failed_run)
    result = readiness.assess_readiness(profile, "2099-12-31")
    assert secret not in str(result)
