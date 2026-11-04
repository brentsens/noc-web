"""WSL-side Feature 012 handoff to the Feature 011 runtime installer."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


INSTALL_SUBPATH = Path(".local/share/sesami-noc-operations/noc-web")
_REQUIRED = (
    "requirements.txt",
    "backend/app.py",
    "scripts/install_runtime.py",
    "scripts/windows/install-shortcut.ps1",
    "scripts/windows/launch-hidden.vbs.in",
    "systemd/noc-web.service.in",
)
_CONTROLLED_PATH = "/usr/local/bin:/usr/bin:/bin"
_HANDOFF_TIMEOUT_SECONDS = 600


class HandoffError(RuntimeError):
    """A safe Feature 012 handoff failure."""


@dataclass(frozen=True)
class LinuxIdentity:
    distribution: str
    user: str
    uid: int
    home: Path


def install_location(identity: LinuxIdentity) -> Path:
    if identity.distribution != "Ubuntu" or identity.user == "root" or identity.uid <= 0:
        raise HandoffError("identity")
    home = Path(identity.home)
    if not home.is_absolute() or ".." in home.parts:
        raise HandoffError("identity")
    return home / INSTALL_SUBPATH


def discover_linux_identity(
    distribution: str = "Ubuntu",
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> LinuxIdentity:
    """Discover and validate Linux identity using authoritative passwd record.

    Determines username via `id -un`, UID via `id -u`, parses authoritative
    home from `getent passwd`, validates account/UID relationship and home
    existence. Tolerates inconsistent inherited HOME when passwd record is valid.
    """
    exec_run = runner if runner is not None else subprocess.run

    try:
        user_res = exec_run(
            ["id", "-un"],
            capture_output=True,
            text=True,
            check=False,
            env={"PATH": _CONTROLLED_PATH},
        )
    except OSError:
        raise HandoffError("identity") from None
    if getattr(user_res, "returncode", 1) != 0:
        raise HandoffError("identity")
    username = user_res.stdout.strip()
    if not username or username == "root" or not re.match(r"^[a-z_][a-z0-9_-]{0,63}$", username):
        raise HandoffError("identity")

    try:
        uid_res = exec_run(
            ["id", "-u"],
            capture_output=True,
            text=True,
            check=False,
            env={"PATH": _CONTROLLED_PATH},
        )
    except OSError:
        raise HandoffError("identity") from None
    if getattr(uid_res, "returncode", 1) != 0:
        raise HandoffError("identity")
    uid_str = uid_res.stdout.strip()
    if not re.match(r"^[1-9][0-9]*$", uid_str):
        raise HandoffError("identity")
    uid = int(uid_str)

    try:
        passwd_res = exec_run(
            ["getent", "passwd", username],
            capture_output=True,
            text=True,
            check=False,
            env={"PATH": _CONTROLLED_PATH},
        )
    except OSError:
        raise HandoffError("identity") from None
    if getattr(passwd_res, "returncode", 1) != 0:
        raise HandoffError("identity")
    lines = [line.strip() for line in passwd_res.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise HandoffError("identity")
    parts = lines[0].split(":")
    if len(parts) != 7:
        raise HandoffError("identity")
    rec_user, _, rec_uid_str, _, _, rec_home, _ = parts
    if rec_user != username or rec_uid_str != uid_str:
        raise HandoffError("identity")

    try:
        uid_passwd_res = exec_run(
            ["getent", "passwd", uid_str],
            capture_output=True,
            text=True,
            check=False,
            env={"PATH": _CONTROLLED_PATH},
        )
    except OSError:
        raise HandoffError("identity") from None
    if getattr(uid_passwd_res, "returncode", 1) != 0:
        raise HandoffError("identity")
    uid_lines = [line.strip() for line in uid_passwd_res.stdout.splitlines() if line.strip()]
    if len(uid_lines) != 1:
        raise HandoffError("identity")
    uid_parts = uid_lines[0].split(":")
    if len(uid_parts) != 7 or uid_parts[0] != username or uid_parts[2] != uid_str or uid_parts[5] != rec_home:
        raise HandoffError("identity")

    home = Path(rec_home)
    if (
        not home.is_absolute()
        or ".." in home.parts
        or len(rec_home) > 240
        or not re.match(r"^/[A-Za-z0-9._/-]{1,240}$", rec_home)
        or rec_home in {"/", "/root"}
    ):
        raise HandoffError("identity")
    if not home.is_dir():
        raise HandoffError("identity")

    return LinuxIdentity(distribution=distribution, user=username, uid=uid, home=home)


def _valid_release(root: Path) -> bool:
    return root.is_dir() and not root.is_symlink() and all((root / item).is_file() for item in _REQUIRED)


def _copy_release(source: Path, target: Path) -> None:
    if not _valid_release(source):
        raise HandoffError("source")
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="noc-web-handoff-", dir=target.parent) as directory:
        staged = Path(directory) / "release"
        shutil.copytree(source, staged, symlinks=False)
        if not _valid_release(staged):
            raise HandoffError("source")
        if target.exists():
            raise HandoffError("partial_installation")
        os.replace(staged, target)


def handoff_feature011(
    verified_release: Path,
    identity: LinuxIdentity,
    *,
    installer: Callable[[Path, LinuxIdentity], object],
) -> Path:
    """Install only a verified release and invoke Feature 011 exactly once."""
    target = install_location(identity)
    if target.exists() and not _valid_release(target):
        raise HandoffError("partial_installation")
    if not target.exists():
        _copy_release(Path(verified_release), target)
    try:
        installer(target, identity)
    except Exception:
        raise HandoffError("feature011") from None
    return target


def create_verified_venv_and_install(
    release_root: Path,
    identity: LinuxIdentity,
    *,
    runner: Callable[..., object] = subprocess.run,
) -> None:
    """Create the release-owned virtual environment and invoke Feature 011.

    The release is already verified and staged by Feature 012.  This function
    deliberately delegates service, shortcut, and health ownership to the
    existing Feature 011 installer rather than reproducing any of it.
    """
    root = Path(release_root)
    if not _valid_release(root):
        raise HandoffError("source")
    python = shutil.which("python3", path=_CONTROLLED_PATH)
    if python is None:
        raise HandoffError("runtime")
    venv_python = root / ".venv" / "bin" / "python"
    environment = {
        "HOME": str(identity.home),
        "PATH": _CONTROLLED_PATH,
        "WSL_DISTRO_NAME": identity.distribution,
    }
    shortcut_mode = os.environ.get("NOC_WEB_SHORTCUT_MODE")
    if shortcut_mode in {"hidden-vbs", "wsl-native"}:
        environment["NOC_WEB_SHORTCUT_MODE"] = shortcut_mode

    def invoke(command: list[str]) -> None:
        try:
            result = runner(
                command,
                shell=False,
                timeout=_HANDOFF_TIMEOUT_SECONDS,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=environment,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise HandoffError("runtime") from None
        if getattr(result, "returncode", 1) != 0:
            raise HandoffError("runtime")

    if not venv_python.is_file():
        invoke([python, "-m", "venv", str(root / ".venv")])
    invoke([
        str(venv_python), "-m", "pip", "install", "--disable-pip-version-check",
        "--requirement", str(root / "requirements.txt"),
    ])
    invoke([str(venv_python), str(root / "scripts" / "install_runtime.py")])
