"""Confirmed, credential-free provisioning for release-manifest tools."""

from __future__ import annotations

import hashlib
import argparse
import json
import os
import re
import shutil
import subprocess
import tarfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from scripts.bootstrap.release_manifest import ToolEntry, load_manifest


REQUIRED_NOC_TOOLS = (
    ("tix", ("--help",), None),
    ("noc-start", ("--help",), None),
    ("noc-status", ("--help",), None),
    ("noc-inv", ("--contract-version",), "noc-inv-contract=1"),
    ("noc-handover", ("--help",), None),
)
_SENSITIVE_PATH_PART = frozenset(
    {"auth", "authentication", "credential", "credentials", "cookie", "cookies",
     "secret", "secrets", "session", "sessions", "token", "tokens"}
)


class ProvisionError(RuntimeError):
    """A redacted provisioning failure."""


@dataclass(frozen=True)
class ProvisioningResult:
    tool: str
    status: str
    guidance: str


def write_provisioning_record(path: Path, result: ProvisioningResult, *, confirmed: bool) -> None:
    """Persist only bounded, credential-free provisioning status."""
    if result.tool not in {"atlas", "copilot", "m365", "datadogMcp", "nocTools"}:
        raise ProvisionError("invalid-tool")
    if result.status not in {"ready", "setup_required", "unavailable"}:
        raise ProvisionError("invalid-status")
    if _contains_sensitive_path_part(str(path)):
        raise ProvisionError("unsafe-record")
    payload = {
        "tool": result.tool,
        "status": result.status,
        "confirmed": bool(confirmed),
        "sourceVerified": result.status == "ready",
    }
    target = Path(path)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    os.replace(temporary, target)


class _SafeArgumentParser(argparse.ArgumentParser):
    """Do not echo operator-supplied argument values on an invocation error."""

    def error(self, message: str) -> None:
        raise ProvisionError("invalid-arguments")


def _contains_sensitive_path_part(value: str) -> bool:
    return any(
        word in _SENSITIVE_PATH_PART
        for part in Path(value).parts
        for word in re.split(r"[^a-z0-9]+", part.casefold())
        if word
    )


def _safe_artifact_source(source: str) -> bool:
    parsed = urlparse(source)
    return (
        parsed.scheme in {"file", "https"}
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
        and not _contains_sensitive_path_part(parsed.path)
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_target(root: Path, target: str) -> Path:
    root = Path(root).resolve()
    candidate = (root / target).resolve(strict=False)
    if candidate == root or root not in candidate.parents or candidate.is_symlink():
        raise ProvisionError("unsafe-target")
    return candidate


def _probe(command: Path, arguments: tuple[str, ...], expected: str | None) -> bool:
    if not command.is_file() or not os.access(command, os.X_OK):
        return False
    try:
        result = subprocess.run(
            [str(command), *arguments], shell=False, timeout=15,
            stdout=subprocess.PIPE if expected else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, text=True, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and (expected is None or result.stdout.strip() == expected)


def compatible_noc_tools(noc_bin: Path) -> bool:
    return all(_probe(Path(noc_bin) / command, arguments, expected)
               for command, arguments, expected in REQUIRED_NOC_TOOLS)


def _download(source: str, destination: Path) -> None:
    try:
        with urlopen(source, timeout=60) as response, destination.open("wb") as stream:
            shutil.copyfileobj(response, stream)
    except OSError:
        raise ProvisionError("download-failed") from None


def _extract(archive: Path, destination: Path) -> None:
    try:
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as source:
                names = source.namelist()
                if any(
                    Path(name).is_absolute()
                    or ".." in Path(name).parts
                    or _contains_sensitive_path_part(name)
                    for name in names
                ):
                    raise ValueError
                source.extractall(destination)
        elif tarfile.is_tarfile(archive):
            with tarfile.open(archive) as source:
                members = source.getmembers()
                if any(
                    Path(member.name).is_absolute()
                    or ".." in Path(member.name).parts
                    or _contains_sensitive_path_part(member.name)
                    for member in members
                ):
                    raise ValueError
                source.extractall(destination, filter="data")
        else:
            raise ValueError
    except (OSError, tarfile.TarError, ValueError, zipfile.BadZipFile):
        raise ProvisionError("extract-failed") from None


def _stage_directory(parent: Path, label: str) -> Path:
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory = parent / f".{label}-{uuid.uuid4().hex}"
    directory.mkdir(mode=0o700)
    return directory


def _atomic_replace_directory(staged: Path, target: Path) -> Path | None:
    """Replace a managed directory, retaining its predecessor for rollback."""
    backup = target.parent / f".{target.name}.previous-{uuid.uuid4().hex}"
    try:
        if target.exists():
            os.replace(target, backup)
        os.replace(staged, target)
    except OSError:
        if backup.exists() and not target.exists():
            try:
                os.replace(backup, target)
            except OSError:
                pass
        raise ProvisionError("replacement-failed") from None
    return backup if backup.exists() else None


def _restore_directory(target: Path, backup: Path | None) -> None:
    if not backup:
        shutil.rmtree(target, ignore_errors=True)
        return
    failed = target.parent / f".{target.name}.failed-{uuid.uuid4().hex}"
    try:
        if target.exists():
            os.replace(target, failed)
        os.replace(backup, target)
    except OSError:
        raise ProvisionError("replacement-failed") from None
    finally:
        shutil.rmtree(failed, ignore_errors=True)


def _replace_commands(staged: Path, noc_bin: Path) -> Path:
    """Replace only managed commands, leaving unrelated user executables intact."""
    noc_bin.mkdir(mode=0o700, parents=True, exist_ok=True)
    prepared = _stage_directory(noc_bin.parent, "noc-tools-pending")
    backup = _stage_directory(noc_bin.parent, "noc-tools-command-backup")
    installed: list[Path] = []
    try:
        _install_commands(staged, prepared)
        for command, _, _ in REQUIRED_NOC_TOOLS:
            current = noc_bin / command
            if current.exists() or current.is_symlink():
                os.replace(current, backup / command)
        for command, _, _ in REQUIRED_NOC_TOOLS:
            destination = noc_bin / command
            os.replace(prepared / command, destination)
            installed.append(destination)
        return backup
    except OSError:
        for destination in installed:
            destination.unlink(missing_ok=True)
        for command, _, _ in REQUIRED_NOC_TOOLS:
            original = backup / command
            if original.exists() or original.is_symlink():
                try:
                    os.replace(original, noc_bin / command)
                except OSError:
                    pass
        shutil.rmtree(backup, ignore_errors=True)
        raise ProvisionError("replacement-failed") from None
    finally:
        shutil.rmtree(prepared, ignore_errors=True)


def _restore_commands(noc_bin: Path, backup: Path) -> None:
    failed = _stage_directory(noc_bin.parent, "noc-tools-failed")
    try:
        for command, _, _ in REQUIRED_NOC_TOOLS:
            current = noc_bin / command
            if current.exists() or current.is_symlink():
                os.replace(current, failed / command)
            original = backup / command
            if original.exists() or original.is_symlink():
                os.replace(original, noc_bin / command)
    except OSError:
        raise ProvisionError("replacement-failed") from None
    finally:
        shutil.rmtree(failed, ignore_errors=True)


def _install_commands(source: Path | dict[str, Path], destination: Path) -> None:
    destination.mkdir(mode=0o700, exist_ok=True)
    for command, _, _ in REQUIRED_NOC_TOOLS:
        installed = destination / command
        original = source[command] if isinstance(source, dict) else source / command
        shutil.copy2(original, installed)
        installed.chmod(installed.stat().st_mode | 0o500)


def provision_noc_tools(
    entry: ToolEntry | None,
    *,
    install_root: Path,
    noc_bin: Path,
    confirmed: bool,
) -> ProvisioningResult:
    """Install a compatible approved noc-tools release without a checkout."""
    noc_bin = Path(noc_bin)
    if compatible_noc_tools(noc_bin):
        return ProvisioningResult("nocTools", "ready", "Compatible noc-tools is already installed.")
    if entry is None:
        return ProvisioningResult(
            "nocTools", "setup_required",
            "No approved compatible noc-tools release is available in this package.",
        )
    if not confirmed:
        return ProvisioningResult("nocTools", "setup_required", "Operator confirmation is required.")
    if not _safe_artifact_source(entry.source):
        return ProvisioningResult(
            "nocTools", "unavailable", "Approved noc-tools source is invalid."
        )
    if any(
        _contains_sensitive_path_part(str(value))
        for value in (install_root, noc_bin, entry.target)
    ):
        return ProvisioningResult(
            "nocTools", "unavailable", "Approved noc-tools target is invalid."
        )
    target = _safe_target(install_root, entry.target)
    # Checkout paths are never valid provisioning targets.
    if Path(entry.target).parts[0] == "code":
        raise ProvisionError("unsafe-target")
    staging = _stage_directory(Path(install_root), "noc-tools-stage")
    target_backup: Path | None = None
    bin_backup: Path | None = None
    try:
        archive = staging / "artifact"
        _download(entry.source, archive)
        if _sha256(archive) != entry.sha256:
            return ProvisioningResult("nocTools", "unavailable", "Approved noc-tools verification failed.")
        extracted = staging / "release"
        extracted.mkdir()
        _extract(archive, extracted)
        commands = {path.name: path for path in extracted.rglob("*") if path.is_file()
                    and path.name in {item[0] for item in REQUIRED_NOC_TOOLS}}
        if len(commands) != len(REQUIRED_NOC_TOOLS):
            return ProvisioningResult("nocTools", "unavailable", "Approved noc-tools release is incomplete.")
        staged_target = staging / "managed"
        _install_commands(commands, staged_target)
        if not compatible_noc_tools(staged_target):
            return ProvisioningResult("nocTools", "unavailable", "Installed noc-tools commands are incompatible.")
        staged_bin = staging / "bin"
        _install_commands(staged_target, staged_bin)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target_backup = _atomic_replace_directory(staged_target, target)
        try:
            bin_backup = _replace_commands(staged_bin, noc_bin)
        except ProvisionError:
            _restore_directory(target, target_backup)
            raise
        if not compatible_noc_tools(noc_bin):
            _restore_commands(noc_bin, bin_backup)
            _restore_directory(target, target_backup)
            return ProvisioningResult("nocTools", "unavailable", "Installed noc-tools commands are incompatible.")
        if target_backup:
            shutil.rmtree(target_backup, ignore_errors=True)
        if bin_backup:
            shutil.rmtree(bin_backup, ignore_errors=True)
        return ProvisioningResult("nocTools", "ready", "Approved compatible noc-tools is installed.")
    except ProvisionError:
        return ProvisioningResult("nocTools", "unavailable", "Approved noc-tools replacement failed.")
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def provision_tool(
    identifier: str,
    entry: ToolEntry | None,
    *,
    install_root: Path,
    noc_bin: Path,
    confirmed: bool,
    record_path: Path | None = None,
) -> ProvisioningResult:
    """Provision exactly one approved tool without selecting alternate sources."""
    if identifier not in {"atlas", "copilot", "m365", "datadogMcp", "nocTools"}:
        raise ProvisionError("invalid-tool")
    if identifier != "nocTools":
        result = ProvisioningResult(
            identifier,
            "setup_required",
            "No approved compatible release is available in this package.",
        )
    elif entry is not None and entry.tool != "nocTools":
        raise ProvisionError("invalid-entry")
    else:
        result = provision_noc_tools(
            entry, install_root=install_root, noc_bin=noc_bin, confirmed=confirmed
        )
    if record_path is not None:
        write_provisioning_record(record_path, result, confirmed=confirmed)
    return result


def main(argv: list[str] | None = None) -> int:
    """Provision only the manifest-pinned noc-tools artifact after confirmation."""
    parser = _SafeArgumentParser(add_help=False)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--install-root", required=True)
    parser.add_argument("--noc-bin", required=True)
    parser.add_argument("--confirmed", action="store_true")
    try:
        arguments = parser.parse_args(argv)
        if any(
            _contains_sensitive_path_part(value)
            for value in (arguments.manifest, arguments.install_root, arguments.noc_bin)
        ):
            raise ProvisionError("invalid-arguments")
        manifest = load_manifest(Path(arguments.manifest))
        result = provision_tool(
            "nocTools", manifest.tool("nocTools"),
            install_root=Path(arguments.install_root),
            noc_bin=Path(arguments.noc_bin),
            confirmed=arguments.confirmed,
        )
    except (OSError, ValueError, ProvisionError):
        print("DEPENDENCY_SETUP_REQUIRED")
        return 1
    print(result.status.upper())
    return 0 if result.status == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
