import hashlib
import json
import zipfile
from pathlib import Path

import pytest

import scripts.bootstrap.provision_dependencies as provisioning
from scripts.bootstrap.provision_dependencies import (
    ProvisionError,
    REQUIRED_NOC_TOOLS,
    compatible_noc_tools,
    provision_tool,
    provision_noc_tools,
)
from scripts.bootstrap.release_manifest import ToolEntry


def _entry(artifact: Path) -> ToolEntry:
    return ToolEntry(
        tool="nocTools", version="1.0.0", source=artifact.as_uri(),
        sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
        target=".local/lib/noc-tools/1.0.0", compatibility="noc-web>=1",
        readiness_id="external.nocTools", requires_confirmation=True,
    )


def _archive(path: Path, *, complete=True, compatible=True) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for command, _, _ in REQUIRED_NOC_TOOLS[: None if complete else -1]:
            output = "noc-inv-contract=1" if command == "noc-inv" and compatible else ""
            archive.writestr(command, f"#!/bin/sh\nprintf '%s\\n' '{output}'\n")


def _commands(directory: Path, *, complete=True, compatible=True) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for command, _, _ in REQUIRED_NOC_TOOLS[: None if complete else -1]:
        output = "noc-inv-contract=1" if command == "noc-inv" and compatible else ""
        path = directory / command
        path.write_text(f"#!/bin/sh\nprintf '%s\\n' '{output}'\n")
        path.chmod(0o700)


def test_absent_noc_tools_installs_verified_compatible_release(tmp_path):
    artifact = tmp_path / "noc-tools.zip"
    _archive(artifact)
    result = provision_noc_tools(
        _entry(artifact), install_root=tmp_path, noc_bin=tmp_path / "bin", confirmed=True,
    )
    assert result.status == "ready"
    assert compatible_noc_tools(tmp_path / "bin")


def test_compatible_noc_tools_is_preserved_without_replacement(tmp_path):
    bin_path = tmp_path / "bin"
    _commands(bin_path)
    (bin_path / "operator-script").write_text("preserved")
    artifact = tmp_path / "artifact.zip"
    _archive(artifact)
    invalid = _entry(artifact)
    artifact.unlink()

    result = provision_noc_tools(
        invalid, install_root=tmp_path, noc_bin=bin_path, confirmed=True,
    )

    assert result.status == "ready"
    assert (bin_path / "operator-script").read_text() == "preserved"


def test_partial_archive_is_unavailable_without_installing_commands(tmp_path):
    artifact = tmp_path / "noc-tools.zip"
    _archive(artifact, complete=False)
    result = provision_noc_tools(
        _entry(artifact), install_root=tmp_path, noc_bin=tmp_path / "bin", confirmed=True,
    )
    assert result.status == "unavailable"
    assert not (tmp_path / "bin").exists()


def test_bad_checksum_noc_tools_is_unavailable(tmp_path):
    artifact = tmp_path / "noc-tools.zip"
    _archive(artifact)
    bad = _entry(artifact)
    object.__setattr__(bad, "sha256", "0" * 64)
    assert provision_noc_tools(
        bad, install_root=tmp_path, noc_bin=tmp_path / "other-bin", confirmed=True,
    ).status == "unavailable"


def test_incompatible_existing_commands_are_replaced_without_losing_other_user_files(tmp_path):
    artifact = tmp_path / "noc-tools.zip"
    _archive(artifact)
    bin_path = tmp_path / "bin"
    _commands(bin_path, compatible=False)
    (bin_path / "operator-script").write_text("preserved")

    result = provision_noc_tools(
        _entry(artifact), install_root=tmp_path, noc_bin=bin_path, confirmed=True,
    )

    assert result.status == "ready"
    assert compatible_noc_tools(bin_path)
    assert (bin_path / "operator-script").read_text() == "preserved"


def test_missing_required_command_is_unavailable(tmp_path):
    artifact = tmp_path / "noc-tools.zip"
    _archive(artifact, complete=False)
    bin_path = tmp_path / "bin"
    _commands(bin_path, compatible=False)
    (bin_path / "operator-script").write_text("preserved")

    assert provision_noc_tools(
        _entry(artifact), install_root=tmp_path, noc_bin=bin_path, confirmed=True,
    ).status == "unavailable"
    assert (bin_path / "operator-script").read_text() == "preserved"


def test_incompatible_noc_inv_contract_is_unavailable(tmp_path):
    artifact = tmp_path / "noc-tools.zip"
    _archive(artifact, compatible=False)
    assert provision_noc_tools(
        _entry(artifact), install_root=tmp_path, noc_bin=tmp_path / "bin", confirmed=True,
    ).status == "unavailable"


def test_credential_bearing_artifact_source_is_rejected_without_downloading(
    tmp_path, monkeypatch
):
    artifact = tmp_path / "noc-tools.zip"
    _archive(artifact)
    entry = _entry(artifact)
    object.__setattr__(
        entry, "source", "https://example.test/noc-tools.zip?access_token=secret"
    )
    monkeypatch.setattr(
        provisioning,
        "_download",
        lambda *_: pytest.fail("credential-bearing source must not be downloaded"),
    )

    result = provision_noc_tools(
        entry, install_root=tmp_path, noc_bin=tmp_path / "bin", confirmed=True,
    )

    assert result.status == "unavailable"
    assert "secret" not in str(result)


def test_archive_with_authentication_file_is_rejected_without_installing(tmp_path):
    artifact = tmp_path / "noc-tools.zip"
    _archive(artifact)
    with zipfile.ZipFile(artifact, "a") as archive:
        archive.writestr("authentication-token.json", "secret")

    result = provision_noc_tools(
        _entry(artifact), install_root=tmp_path, noc_bin=tmp_path / "bin", confirmed=True,
    )

    assert result.status == "unavailable"
    assert not (tmp_path / "bin").exists()


def test_sensitive_cli_arguments_are_rejected_without_echoing_values(capsys, monkeypatch):
    monkeypatch.setattr(
        provisioning,
        "load_manifest",
        lambda *_: pytest.fail("sensitive argument must not be read"),
    )
    assert provisioning.main([
        "--manifest", "token-value", "--install-root", "install", "--noc-bin", "bin",
    ]) == 1
    output = capsys.readouterr()
    assert output.out == "DEPENDENCY_SETUP_REQUIRED\n"
    assert "token-value" not in output.err


def test_interrupted_replacement_restores_prior_managed_release_and_commands(tmp_path, monkeypatch):
    artifact = tmp_path / "noc-tools.zip"
    _archive(artifact)
    entry = _entry(artifact)
    target = tmp_path / entry.target
    _commands(target, compatible=False)
    (target / "managed-state").write_text("old")
    bin_path = tmp_path / "bin"
    _commands(bin_path, compatible=False)
    (bin_path / "operator-script").write_text("preserved")

    monkeypatch.setattr(
        provisioning, "_replace_commands",
        lambda *_: (_ for _ in ()).throw(ProvisionError("interrupted")),
    )
    result = provision_noc_tools(entry, install_root=tmp_path, noc_bin=bin_path, confirmed=True)

    assert result.status == "unavailable"
    assert (target / "managed-state").read_text() == "old"
    assert not compatible_noc_tools(bin_path)
    assert (bin_path / "operator-script").read_text() == "preserved"


def test_failed_replacement_preserves_prior_commands_and_managed_release(tmp_path, monkeypatch):
    artifact = tmp_path / "noc-tools.zip"
    _archive(artifact)
    entry = _entry(artifact)
    target = tmp_path / entry.target
    _commands(target, compatible=False)
    (target / "managed-state").write_text("old")
    bin_path = tmp_path / "bin"
    _commands(bin_path, compatible=False)
    (bin_path / "operator-script").write_text("preserved")

    original_replace = provisioning.os.replace
    calls = 0

    def fail_while_replacing_commands(source, destination):
        nonlocal calls
        calls += 1
        if calls == 4:
            raise OSError("replacement failed")
        return original_replace(source, destination)

    monkeypatch.setattr(provisioning.os, "replace", fail_while_replacing_commands)
    result = provision_noc_tools(entry, install_root=tmp_path, noc_bin=bin_path, confirmed=True)

    assert result.status == "unavailable"
    assert (target / "managed-state").read_text() == "old"
    assert not compatible_noc_tools(bin_path)
    assert (bin_path / "operator-script").read_text() == "preserved"


@pytest.mark.parametrize("tool", ("atlas", "copilot", "m365", "datadogMcp"))
def test_non_noc_tool_requires_an_approved_manifest_entry_and_never_authenticates(tmp_path, tool):
    result = provision_tool(
        tool, None, install_root=tmp_path, noc_bin=tmp_path / "bin", confirmed=True,
    )
    assert result.status == "setup_required"
    assert "authentication" not in result.guidance.casefold()


def test_noc_tools_requires_confirmation_and_records_only_safe_status(tmp_path):
    artifact = tmp_path / "noc-tools.zip"
    _archive(artifact)
    record = tmp_path / "records" / "noc-tools.json"
    result = provision_tool(
        "nocTools", _entry(artifact), install_root=tmp_path, noc_bin=tmp_path / "bin",
        confirmed=False, record_path=record,
    )

    assert result.status == "setup_required"
    assert json.loads(record.read_text()) == {
        "confirmed": False,
        "sourceVerified": False,
        "status": "setup_required",
        "tool": "nocTools",
    }


def test_unknown_tool_and_wrong_manifest_entry_fail_closed(tmp_path):
    artifact = tmp_path / "noc-tools.zip"
    _archive(artifact)
    with pytest.raises(ProvisionError):
        provision_tool("arbitrary", None, install_root=tmp_path, noc_bin=tmp_path / "bin", confirmed=True)
    wrong = _entry(artifact)
    object.__setattr__(wrong, "tool", "atlas")
    with pytest.raises(ProvisionError):
        provision_tool("nocTools", wrong, install_root=tmp_path, noc_bin=tmp_path / "bin", confirmed=True)
