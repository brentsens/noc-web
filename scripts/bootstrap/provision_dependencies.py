"""Confirmed, credential-free provisioning for release-manifest tools."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen

from scripts.bootstrap.release_manifest import ToolEntry


REQUIRED_NOC_TOOLS = (
    ("tix", ("--help",), None),
    ("noc-start", ("--help",), None),
    ("noc-status", ("--help",), None),
    ("noc-inv", ("--contract-version",), "noc-inv-contract=1"),
    ("noc-handover", ("--help",), None),
)


class ProvisionError(RuntimeError):
    """A redacted provisioning failure."""


@dataclass(frozen=True)
class ProvisioningResult:
    tool: str
    status: str
    guidance: str


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
                if any(Path(name).is_absolute() or ".." in Path(name).parts for name in names):
                    raise ValueError
                source.extractall(destination)
        elif tarfile.is_tarfile(archive):
            with tarfile.open(archive) as source:
                members = source.getmembers()
                if any(Path(member.name).is_absolute() or ".." in Path(member.name).parts for member in members):
                    raise ValueError
                source.extractall(destination, filter="data")
        else:
            raise ValueError
    except (OSError, tarfile.TarError, ValueError, zipfile.BadZipFile):
        raise ProvisionError("extract-failed") from None


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
    target = _safe_target(install_root, entry.target)
    # Checkout paths are never valid provisioning targets.
    if Path(entry.target).parts[0] == "code":
        raise ProvisionError("unsafe-target")
    with tempfile.TemporaryDirectory(prefix="noc-tools-", dir=install_root) as directory:
        archive = Path(directory) / "artifact"
        _download(entry.source, archive)
        if _sha256(archive) != entry.sha256:
            return ProvisioningResult("nocTools", "unavailable", "Approved noc-tools verification failed.")
        extracted = Path(directory) / "release"
        extracted.mkdir()
        _extract(archive, extracted)
        commands = {path.name: path for path in extracted.rglob("*") if path.is_file()
                    and path.name in {item[0] for item in REQUIRED_NOC_TOOLS}}
        if len(commands) != len(REQUIRED_NOC_TOOLS):
            return ProvisioningResult("nocTools", "unavailable", "Approved noc-tools release is incomplete.")
        target.mkdir(mode=0o700, parents=True, exist_ok=True)
        for name, source in commands.items():
            destination = target / name
            shutil.copy2(source, destination)
            destination.chmod(destination.stat().st_mode | 0o500)
    if not compatible_noc_tools(target):
        return ProvisioningResult("nocTools", "unavailable", "Installed noc-tools commands are incompatible.")
    noc_bin.mkdir(mode=0o700, parents=True, exist_ok=True)
    for command, _, _ in REQUIRED_NOC_TOOLS:
        source, destination = target / command, noc_bin / command
        temporary = destination.with_suffix(".new")
        shutil.copy2(source, temporary)
        temporary.chmod(temporary.stat().st_mode | 0o500)
        os.replace(temporary, destination)
    return ProvisioningResult("nocTools", "ready", "Approved compatible noc-tools is installed.")
