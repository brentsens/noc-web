"""Fail-closed verified NOC Web release staging."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from urllib.request import urlopen


class BootstrapError(RuntimeError):
    """A safe bootstrap failure category."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class VerificationRecord:
    release_id: str
    asset_name: str
    manifest_sha256: str
    archive_sha256: str
    signature_verified: bool
    archive_validated: bool


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_install_root(path: Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute() or candidate == Path(candidate.anchor) or ".." in candidate.parts:
        raise BootstrapError("SOURCE_VERIFICATION_FAILED")
    try:
        resolved = candidate.resolve(strict=False)
    except OSError:
        raise BootstrapError("SOURCE_VERIFICATION_FAILED") from None
    if any(parent.is_symlink() for parent in (resolved, *resolved.parents)):
        raise BootstrapError("SOURCE_VERIFICATION_FAILED")
    return resolved


def validate_archive(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if not names:
                raise ValueError
            for name in names:
                member = PurePosixPath(name)
                if member.is_absolute() or ".." in member.parts:
                    raise ValueError
            required = {
                "requirements.txt",
                "backend/app.py",
                "scripts/install_runtime.py",
                "scripts/windows/install-shortcut.ps1",
                "scripts/windows/launch-hidden.vbs.in",
                "systemd/noc-web.service.in",
            }
            normalized = {name.lstrip("./") for name in names}
            if not required.issubset(normalized):
                raise ValueError
    except (OSError, ValueError, zipfile.BadZipFile):
        raise BootstrapError("SOURCE_VERIFICATION_FAILED") from None


def verify_signature(checksums: Path, signature: Path, public_key: Path, *, verifier="gpgv") -> None:
    try:
        result = subprocess.run(
            [verifier, "--keyring", str(public_key), str(signature), str(checksums)],
            shell=False, timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise BootstrapError("SOURCE_VERIFICATION_FAILED") from None
    if result.returncode != 0:
        raise BootstrapError("SOURCE_VERIFICATION_FAILED")


def stage_verified_release(
    archive: Path,
    *,
    expected_sha256: str,
    install_root: Path,
    record_path: Path,
    release_id: str,
    checksums: Path,
    signature_verified: bool,
) -> VerificationRecord:
    if not signature_verified or sha256_file(archive) != expected_sha256:
        raise BootstrapError("SOURCE_VERIFICATION_FAILED")
    validate_archive(archive)
    root = safe_install_root(install_root)
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="noc-web-stage-", dir=root.parent) as directory:
        staging = Path(directory) / "release"
        with zipfile.ZipFile(archive) as source:
            source.extractall(staging)
        if root.exists():
            backup = root.with_name(f"{root.name}.previous")
            if backup.exists():
                shutil.rmtree(backup)
            os.replace(root, backup)
            try:
                os.replace(staging, root)
            except OSError:
                os.replace(backup, root)
                raise BootstrapError("SOURCE_VERIFICATION_FAILED") from None
        else:
            os.replace(staging, root)
    record = VerificationRecord(
        release_id=release_id, asset_name=Path(archive).name,
        manifest_sha256=sha256_file(checksums), archive_sha256=expected_sha256,
        signature_verified=True, archive_validated=True,
    )
    record_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = record_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(record), sort_keys=True), encoding="utf-8")
    os.replace(temporary, record_path)
    return record
