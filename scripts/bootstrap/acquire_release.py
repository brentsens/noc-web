"""Fail-closed acquisition and staging of an approved NOC Web release."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable
from urllib.request import urlopen

from scripts.bootstrap.handoff import (
    HandoffError,
    LinuxIdentity,
    create_verified_venv_and_install,
)
from scripts.bootstrap.release_manifest import ReleaseEntry


class BootstrapError(RuntimeError):
    """A safe bootstrap failure category."""

    def __init__(self, code: str = "SOURCE_VERIFICATION_FAILED"):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class VerificationRecord:
    release_id: str
    asset_name: str
    manifest_sha256: str
    archive_sha256: str
    provenance_verified: bool
    archive_validated: bool


STATE_SCHEMA_VERSION = 1
_SAFE_RESULT = re.compile(r"^[A-Z][A-Z_]{1,63}$")
_VERSION = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
_ACTIVE_STATES = frozenset({"preflight", "awaiting_confirmation", "staging", "handoff"})
_TERMINAL_STATES = frozenset({"ready", "failed"})
_CONTROLLED_PATH = "/usr/local/bin:/usr/bin:/bin"


@dataclass(frozen=True)
class BootstrapStateRecord:
    """Credential-free installation state used to make reruns safe."""

    schema_version: int
    release_id: str
    release_version: str
    repository: str
    install_root: str
    archive_sha256: str
    state: str
    last_result: str
    updated_at: str


@dataclass(frozen=True)
class StateResolution:
    classification: str
    record: BootstrapStateRecord | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _state_path(record_path: Path) -> Path:
    return Path(record_path).with_name("installation-state.json")


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _release_version(tag: str) -> str:
    if not _VERSION.fullmatch(tag):
        raise BootstrapError()
    return tag[1:]


def _state_record(
    release: ReleaseEntry, root: Path, *, state: str, last_result: str,
) -> BootstrapStateRecord:
    if state not in _ACTIVE_STATES | _TERMINAL_STATES or not _SAFE_RESULT.fullmatch(last_result):
        raise BootstrapError()
    return BootstrapStateRecord(
        schema_version=STATE_SCHEMA_VERSION,
        release_id=release.tag,
        release_version=_release_version(release.tag),
        repository=release.repository,
        install_root=str(root),
        archive_sha256=release.sha256,
        state=state,
        last_result=last_result,
        updated_at=_timestamp(),
    )


def write_state_record(path: Path, record: BootstrapStateRecord) -> None:
    """Atomically persist only validated, credential-free state."""
    root = safe_install_root(Path(record.install_root))
    expected = BootstrapStateRecord(
        schema_version=record.schema_version,
        release_id=record.release_id,
        release_version=record.release_version,
        repository=record.repository,
        install_root=str(root),
        archive_sha256=record.archive_sha256,
        state=record.state,
        last_result=record.last_result,
        updated_at=record.updated_at,
    )
    if _parse_state_record(asdict(expected)) != expected:
        raise BootstrapError()
    destination = Path(path)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(expected), sort_keys=True), encoding="utf-8")
    os.replace(temporary, destination)


def _parse_state_record(value: object) -> BootstrapStateRecord:
    fields = {
        "schema_version", "release_id", "release_version", "repository", "install_root",
        "archive_sha256", "state", "last_result", "updated_at",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise BootstrapError()
    record = BootstrapStateRecord(**value)
    if (
        record.schema_version != STATE_SCHEMA_VERSION
        or not isinstance(record.release_id, str)
        or _release_version(record.release_id) != record.release_version
        or not isinstance(record.repository, str)
        or not isinstance(record.archive_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", record.archive_sha256)
        or record.state not in _ACTIVE_STATES | _TERMINAL_STATES
        or not isinstance(record.last_result, str)
        or not _SAFE_RESULT.fullmatch(record.last_result)
        or not isinstance(record.updated_at, str)
    ):
        raise BootstrapError()
    try:
        datetime.fromisoformat(record.updated_at.replace("Z", "+00:00"))
        safe_install_root(Path(record.install_root))
    except (TypeError, ValueError, BootstrapError):
        raise BootstrapError() from None
    return record


def read_state_record(path: Path) -> BootstrapStateRecord:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise BootstrapError() from None
    return _parse_state_record(value)


def _version_key(tag: str) -> tuple[int, int, int]:
    match = _VERSION.fullmatch(tag)
    if not match:
        raise BootstrapError()
    return tuple(int(part) for part in match.groups())


def resolve_installation_state(
    state_path: Path, release: ReleaseEntry, *, install_root: Path,
) -> StateResolution:
    """Classify an existing record without changing its release or operator data."""
    try:
        record = read_state_record(state_path)
    except BootstrapError:
        return StateResolution("corrupt")
    root = safe_install_root(install_root)
    if Path(record.install_root) != root or record.repository != release.repository:
        return StateResolution("incompatible", record)
    if record.state in _ACTIVE_STATES:
        return StateResolution("interrupted", record)
    if record.state == "failed":
        return StateResolution("failed", record)
    if not _valid_installed_release(root):
        return StateResolution("corrupt", record)
    if record.release_id == release.tag and record.archive_sha256 == release.sha256:
        return StateResolution("current", record)
    if _version_key(record.release_id) < _version_key(release.tag):
        return StateResolution("older", record)
    return StateResolution("incompatible", record)


def _valid_installed_release(root: Path) -> bool:
    required = (
        "requirements.txt", "backend/app.py", "scripts/install_runtime.py",
        "scripts/windows/install-shortcut.ps1", "scripts/windows/launch-hidden.vbs.in",
        "systemd/noc-web.service.in",
    )
    return root.is_dir() and not root.is_symlink() and all((root / item).is_file() for item in required)


_PRESERVED_FEATURE011_CONTENT = ("data", "runtime.json", ".venv")


def _copy_preserved_feature011_content(previous: Path, replacement: Path) -> None:
    """Keep content owned by Feature 011 or the operator out of app replacement."""
    for name in _PRESERVED_FEATURE011_CONTENT:
        source = previous / name
        if not source.exists():
            continue
        if source.is_symlink():
            raise BootstrapError()
        destination = replacement / name
        if destination.exists():
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()
        if source.is_dir():
            shutil.copytree(source, destination, symlinks=True)
        else:
            shutil.copy2(source, destination, follow_symlinks=False)


def safe_install_root(path: Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute() or candidate == Path(candidate.anchor) or ".." in candidate.parts:
        raise BootstrapError()
    if any(parent.is_symlink() for parent in (candidate, *candidate.parents)):
        raise BootstrapError()
    try:
        resolved = candidate.resolve(strict=False)
    except OSError:
        raise BootstrapError() from None
    if any(parent.is_symlink() for parent in (resolved, *resolved.parents)):
        raise BootstrapError()
    return resolved


def _safe_member(name: str) -> PurePosixPath:
    member = PurePosixPath(name)
    if not name or member.is_absolute() or ".." in member.parts or member == PurePosixPath("."):
        raise BootstrapError()
    return member


def _archive_members(path: Path) -> tuple[list[tarfile.TarInfo], str]:
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = archive.getmembers()
            if not members:
                raise BootstrapError()
            names = [_safe_member(member.name) for member in members]
            if any(not member.isfile() and not member.isdir() for member in members):
                raise BootstrapError()
            first_parts = {name.parts[0] for name in names}
            prefix = f"{next(iter(first_parts))}/" if len(first_parts) == 1 else ""
            normalized = {str(name)[len(prefix):] for name in names}
            required = {
                "requirements.txt", "backend/app.py", "scripts/install_runtime.py",
                "scripts/windows/install-shortcut.ps1", "scripts/windows/launch-hidden.vbs.in",
                "systemd/noc-web.service.in",
            }
            if not required.issubset(normalized):
                raise BootstrapError()
            return members, prefix
    except (OSError, tarfile.TarError):
        raise BootstrapError() from None


def validate_archive(path: Path) -> None:
    _archive_members(path)


def _checksum_digest(checksums: Path, asset_name: str) -> str:
    try:
        lines = checksums.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        raise BootstrapError() from None
    matches = []
    for line in lines:
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        digest, name = parts
        if name.lstrip("*") == asset_name:
            matches.append(digest.lower())
    if len(matches) != 1 or len(matches[0]) != 64 or any(char not in "0123456789abcdef" for char in matches[0]):
        raise BootstrapError()
    return matches[0]


def download_release_assets(release: ReleaseEntry, destination: Path, *, opener: Callable = urlopen) -> tuple[Path, Path]:
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    archive, checksums = destination / release.archive, destination / release.checksum
    try:
        for url, target in ((release.archive_url, archive), (release.checksum_url, checksums)):
            with opener(url, timeout=30) as response, target.open("wb") as stream:
                shutil.copyfileobj(response, stream)
    except (OSError, ValueError):
        raise BootstrapError() from None
    return archive, checksums


def _controlled_subprocess(
    command: list[str], *, timeout: int,
) -> subprocess.CompletedProcess[bytes]:
    """Run a bounded verifier without an interactive shell or inherited PATH."""
    if not command or timeout <= 0:
        raise BootstrapError()
    try:
        return subprocess.run(
            command,
            shell=False,
            timeout=timeout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={"PATH": _CONTROLLED_PATH, "HOME": str(Path.home())},
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise BootstrapError() from None


def verify_provenance(archive: Path, release: ReleaseEntry, *, verifier: str = "gh") -> None:
    if verifier != "gh":
        raise BootstrapError()
    command = [
        verifier, "attestation", "verify", str(archive), "--repo", release.repository,
        "--signer-workflow", release.signer_workflow, "--source-ref", f"refs/tags/{release.tag}",
    ]
    result = _controlled_subprocess(command, timeout=60)
    if result.returncode != 0:
        raise BootstrapError()


def _extract_verified_archive(archive_path: Path, destination: Path) -> None:
    members, prefix = _archive_members(archive_path)
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in members:
                name = member.name[len(prefix):]
                if not name:
                    continue
                target = destination.joinpath(*PurePosixPath(name).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                if member.isdir():
                    target.mkdir(exist_ok=True)
                else:
                    source = archive.extractfile(member)
                    if source is None:
                        raise BootstrapError()
                    with source, target.open("xb") as output:
                        shutil.copyfileobj(source, output)
    except (OSError, tarfile.TarError):
        raise BootstrapError() from None


def _write_verification_record(path: Path, record: VerificationRecord) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(record), sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def stage_verified_release(
    archive: Path,
    *,
    release: ReleaseEntry,
    install_root: Path,
    record_path: Path,
    checksums: Path,
    provenance_verified: bool,
    state_path: Path | None = None,
) -> VerificationRecord:
    archive_digest = sha256_file(archive)
    if (
        not provenance_verified
        or archive.name != release.archive
        or archive_digest != release.sha256
        or _checksum_digest(checksums, release.archive) != release.sha256
    ):
        raise BootstrapError()
    validate_archive(archive)
    root = safe_install_root(install_root)
    root.parent.mkdir(parents=True, exist_ok=True)
    state_destination = Path(state_path) if state_path is not None else _state_path(record_path)
    verified_record = VerificationRecord(
        release_id=release.tag, asset_name=release.archive,
        manifest_sha256=sha256_file(checksums), archive_sha256=archive_digest,
        provenance_verified=True, archive_validated=True,
    )
    if state_destination.exists():
        existing = resolve_installation_state(state_destination, release, install_root=root)
        if existing.classification == "current":
            _write_verification_record(record_path, verified_record)
            return verified_record
        if (
            existing.classification == "interrupted"
            and existing.record is not None
            and existing.record.release_id == release.tag
            and existing.record.archive_sha256 == release.sha256
            and _valid_installed_release(root)
        ):
            write_state_record(
                state_destination, _state_record(release, root, state="ready", last_result="READY"),
            )
            _write_verification_record(record_path, verified_record)
            return verified_record
    write_state_record(
        state_destination, _state_record(release, root, state="staging", last_result="STAGING"),
    )
    with tempfile.TemporaryDirectory(prefix="noc-web-stage-", dir=root.parent) as directory:
        staging = Path(directory) / "release"
        staging.mkdir()
        _extract_verified_archive(archive, staging)
        if root.exists():
            backup = root.with_name(f"{root.name}.previous")
            if backup.exists():
                if backup.is_symlink():
                    raise BootstrapError()
                shutil.rmtree(backup)
            os.replace(root, backup)
            try:
                _copy_preserved_feature011_content(backup, staging)
                os.replace(staging, root)
            except OSError:
                os.replace(backup, root)
                raise BootstrapError() from None
            except BootstrapError:
                os.replace(backup, root)
                raise
        else:
            os.replace(staging, root)
    _write_verification_record(record_path, verified_record)
    write_state_record(
        state_destination, _state_record(release, root, state="ready", last_result="READY"),
    )
    return verified_record


def acquire_verified_release(
    release: ReleaseEntry, *, install_root: Path, record_path: Path,
    opener: Callable = urlopen, verifier: str = "gh",
    state_path: Path | None = None,
) -> VerificationRecord:
    root = safe_install_root(install_root)
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="noc-web-download-", dir=root.parent) as directory:
        archive, checksums = download_release_assets(release, Path(directory), opener=opener)
        if sha256_file(archive) != release.sha256 or _checksum_digest(checksums, release.archive) != release.sha256:
            raise BootstrapError()
        verify_provenance(archive, release, verifier=verifier)
        return stage_verified_release(
            archive, release=release, install_root=root, record_path=record_path,
            checksums=checksums, provenance_verified=True, state_path=state_path,
        )


def handoff_verified_release(release_root: Path, *, distribution: str) -> None:
    """Delegate a verified staged release to Feature 011 exactly once."""
    root = Path(release_root)
    try:
        identity = LinuxIdentity(
            distribution=distribution,
            user=os.environ.get("USER", ""),
            uid=os.getuid(),
            home=Path.home(),
        )
        create_verified_venv_and_install(root, identity)
    except (HandoffError, OSError):
        previous = root.with_name(f"{root.name}.previous")
        if previous.is_dir() and not previous.is_symlink():
            failed = root.with_name(f"{root.name}.failed")
            try:
                if failed.exists():
                    shutil.rmtree(failed)
                os.replace(root, failed)
                os.replace(previous, root)
                shutil.rmtree(failed)
            except OSError:
                # Do not destroy either verified release if rollback itself fails.
                pass
        raise BootstrapError("FEATURE011_HANDOFF_FAILED") from None


def main(argv: list[str] | None = None) -> int:
    """Acquire one manifest-pinned release and hand it to Feature 011."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--install-root", required=True)
    parser.add_argument("--record-path", required=True)
    parser.add_argument("--distribution", required=True)
    try:
        from scripts.bootstrap.release_manifest import load_manifest

        arguments = parser.parse_args(argv)
        manifest = load_manifest(Path(arguments.manifest))
        acquire_verified_release(
            manifest.application,
            install_root=Path(arguments.install_root),
            record_path=Path(arguments.record_path),
        )
        handoff_verified_release(Path(arguments.install_root), distribution=arguments.distribution)
    except BootstrapError as error:
        print(error.code if error.code == "FEATURE011_HANDOFF_FAILED" else "SOURCE_VERIFICATION_FAILED")
        return 1
    except (OSError, ValueError):
        print("SOURCE_VERIFICATION_FAILED")
        return 1
    print("BOOTSTRAP_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
