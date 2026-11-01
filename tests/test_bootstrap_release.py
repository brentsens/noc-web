import hashlib
import json
import zipfile

import pytest

from scripts.bootstrap.acquire_release import (
    BootstrapError,
    safe_install_root,
    stage_verified_release,
    validate_archive,
)
from scripts.bootstrap.release_manifest import ManifestError, validate_manifest


def _manifest(**changes):
    value = {
        "schemaVersion": 1,
        "applicationRepository": "brentsens/noc-web",
        "releasePublicKey": "release-public-key.txt",
        "targetDistribution": "Ubuntu",
        "releaseAssets": {"archive": "noc-web.zip", "checksums": "SHA256SUMS", "signature": "SHA256SUMS.asc"},
        "brandingAsset": "assets/windows/sesami-noc-operations.png",
        "toolEntries": [],
    }
    value.update(changes)
    return value


def _archive(path, unsafe=False):
    required = (
        "requirements.txt", "backend/app.py", "scripts/install_runtime.py",
        "scripts/windows/install-shortcut.ps1", "scripts/windows/launch-hidden.vbs.in",
        "systemd/noc-web.service.in",
    )
    with zipfile.ZipFile(path, "w") as archive:
        for name in required:
            archive.writestr(name, "fixture")
        if unsafe:
            archive.writestr("../outside", "unsafe")


def test_manifest_rejects_untrusted_schema_source_and_tool_entries():
    assert validate_manifest(_manifest()).application_repository == "brentsens/noc-web"
    with pytest.raises(ManifestError):
        validate_manifest(_manifest(schemaVersion=2))
    with pytest.raises(ManifestError):
        validate_manifest(_manifest(applicationRepository="https://invalid"))
    invalid = _manifest(toolEntries=[{
        "tool": "nocTools", "version": "1", "source": "http://invalid",
        "sha256": "0" * 64, "target": "code/noc-tools", "compatibility": "*",
        "requiresConfirmation": True, "readinessId": "external.nocTools",
    }])
    with pytest.raises(ManifestError):
        validate_manifest(invalid)


def test_archive_validation_and_staging_preserve_prior_release(tmp_path):
    archive = tmp_path / "release.zip"
    checksums = tmp_path / "SHA256SUMS"
    _archive(archive)
    checksums.write_text("fixture", encoding="utf-8")
    root = tmp_path / "installed"
    root.mkdir()
    (root / "prior").write_text("preserved", encoding="utf-8")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    record = stage_verified_release(
        archive, expected_sha256=digest, install_root=root,
        record_path=tmp_path / "state" / "record.json", release_id="v1",
        checksums=checksums, signature_verified=True,
    )
    assert record.archive_validated
    assert (root / "backend" / "app.py").is_file()
    assert (tmp_path / "installed.previous" / "prior").read_text() == "preserved"
    assert json.loads((tmp_path / "state" / "record.json").read_text())["release_id"] == "v1"


def test_unsafe_release_paths_and_hashes_fail_closed(tmp_path):
    archive = tmp_path / "unsafe.zip"
    _archive(archive, unsafe=True)
    with pytest.raises(BootstrapError):
        validate_archive(archive)
    with pytest.raises(BootstrapError):
        safe_install_root(tmp_path / ".." / "..")
    checksums = tmp_path / "checksums"
    checksums.write_text("x")
    with pytest.raises(BootstrapError):
        stage_verified_release(
            archive, expected_sha256="0" * 64, install_root=tmp_path / "install",
            record_path=tmp_path / "record", release_id="v1", checksums=checksums,
            signature_verified=True,
        )
