import hashlib
import zipfile
from pathlib import Path

from scripts.bootstrap.provision_dependencies import (
    REQUIRED_NOC_TOOLS,
    compatible_noc_tools,
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


def test_missing_noc_tools_installs_verified_compatible_release(tmp_path):
    artifact = tmp_path / "noc-tools.zip"
    _archive(artifact)
    result = provision_noc_tools(
        _entry(artifact), install_root=tmp_path, noc_bin=tmp_path / "bin", confirmed=True,
    )
    assert result.status == "ready"
    assert compatible_noc_tools(tmp_path / "bin")


def test_partial_or_bad_checksum_noc_tools_is_unavailable(tmp_path):
    artifact = tmp_path / "noc-tools.zip"
    _archive(artifact, complete=False)
    assert provision_noc_tools(
        _entry(artifact), install_root=tmp_path, noc_bin=tmp_path / "bin", confirmed=True,
    ).status == "unavailable"
    bad = _entry(artifact)
    object.__setattr__(bad, "sha256", "0" * 64)
    assert provision_noc_tools(
        bad, install_root=tmp_path, noc_bin=tmp_path / "other-bin", confirmed=True,
    ).status == "unavailable"
