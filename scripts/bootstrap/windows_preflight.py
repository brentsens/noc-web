"""Pure Windows bootstrap preflight policy for regression tests."""

from __future__ import annotations

import re
from dataclasses import dataclass


WSL_RESOLUTION_NATIVE_SYSTEM32 = "native-system32"
WSL_RESOLUTION_SYSNATIVE = "sysnative"
WSL_RESOLUTION_MISSING = "missing"


@dataclass(frozen=True)
class WslExecutableResolution:
    """Deterministic Windows-owned wsl.exe discovery result."""

    path: str | None
    resolution: str
    category: str | None = None
    reason: str | None = None
    stage: str | None = None


def resolve_wsl_executable(
    *,
    system_root: str,
    is_64bit_os: bool,
    is_64bit_process: bool,
    path_exists: dict[str, bool],
    path_entries: tuple[str, ...] = (),
) -> WslExecutableResolution:
    """Resolve wsl.exe from Windows-owned locations only.

    Never consults PATH. A 32-bit process on 64-bit Windows must use Sysnative
    to bypass Wow64 filesystem redirection of System32.
    """
    del path_entries  # Explicitly ignored: never resolve wsl.exe from PATH.
    root = (system_root or "").rstrip("\\/")
    if not root:
        return WslExecutableResolution(
            path=None,
            resolution=WSL_RESOLUTION_MISSING,
            category="WSL_SETUP_REQUIRED",
            reason="wsl-not-found",
            stage="platform-check",
        )

    def win_join(*parts: str) -> str:
        return "\\".join(part.strip("\\/") for part in parts if part)

    def normalize(path: str) -> str:
        return path.replace("/", "\\").rstrip("\\").lower()

    native = win_join(root, "System32", "wsl.exe")
    sysnative = win_join(root, "Sysnative", "wsl.exe")
    existence = {normalize(key): value for key, value in path_exists.items()}

    def exists(candidate: str) -> bool:
        return bool(existence.get(normalize(candidate), False))

    if is_64bit_process:
        if exists(native):
            return WslExecutableResolution(
                path=native,
                resolution=WSL_RESOLUTION_NATIVE_SYSTEM32,
            )
        return WslExecutableResolution(
            path=None,
            resolution=WSL_RESOLUTION_MISSING,
            category="WSL_SETUP_REQUIRED",
            reason="wsl-not-found",
            stage="platform-check",
        )

    if is_64bit_os:
        # Wow64: System32 is redirected; only Sysnative reaches the real binary.
        if exists(sysnative):
            return WslExecutableResolution(
                path=sysnative,
                resolution=WSL_RESOLUTION_SYSNATIVE,
            )
        return WslExecutableResolution(
            path=None,
            resolution=WSL_RESOLUTION_MISSING,
            category="WSL_SETUP_REQUIRED",
            reason="wsl-not-found",
            stage="platform-check",
        )

    # 32-bit Windows: System32 is the native system directory.
    if exists(native):
        return WslExecutableResolution(
            path=native,
            resolution=WSL_RESOLUTION_NATIVE_SYSTEM32,
        )
    return WslExecutableResolution(
        path=None,
        resolution=WSL_RESOLUTION_MISSING,
        category="WSL_SETUP_REQUIRED",
        reason="wsl-not-found",
        stage="platform-check",
    )


@dataclass(frozen=True)
class WindowsContext:
    wsl_available: bool
    distributions: tuple[str, ...]
    requested_distribution: str
    windows_user: str
    profile_path: str
    desktop_path: str
    linux_user: str
    linux_uid: int
    systemd_available: bool
    permission_available: bool
    confirmed: bool
    source_verified: bool
    wsl2_available: bool = True
    passwd_home: str | None = None
    inherited_home: str | None = None
    home_exists: bool = True
    account_valid: bool = True
    record_valid: bool = True


def parse_and_validate_account(
    *,
    username: str,
    uid: int,
    passwd_record: str | None,
    inherited_home: str | None = None,
    home_exists: bool = True,
) -> str:
    """Parse authoritative home from passwd record and validate account/UID relationship.

    Tolerates inconsistent inherited HOME when passwd record is valid.
    Fails safely (raises ValueError) if record is missing, malformed, ambiguous,
    or resolved home is unusable / does not exist.
    """
    if not username or username == "root" or not re.match(r"^[a-z_][a-z0-9_-]{0,63}$", username):
        raise ValueError("invalid-username")
    if uid <= 0:
        raise ValueError("invalid-uid")
    if not passwd_record:
        raise ValueError("missing-passwd-record")
    parts = passwd_record.strip().split(":")
    if len(parts) != 7:
        raise ValueError("malformed-passwd-record")
    rec_user, _, rec_uid, _, _, rec_home, _ = parts
    if rec_user != username or rec_uid != str(uid):
        raise ValueError("ambiguous-account-relationship")
    if (
        not rec_home.startswith("/")
        or ".." in rec_home
        or len(rec_home) > 240
        or not re.match(r"^/[A-Za-z0-9._/-]{1,240}$", rec_home)
        or rec_home in {"/", "/root"}
    ):
        raise ValueError("malformed-home-directory")
    if not home_exists:
        raise ValueError("home-directory-unusable")
    return rec_home


def assess(context: WindowsContext) -> str:
    if not context.wsl_available:
        return "WSL_SETUP_REQUIRED"
    if not context.wsl2_available or context.requested_distribution not in context.distributions:
        return "DISTRIBUTION_SETUP_REQUIRED"
    if not context.account_valid or not context.record_valid or not context.home_exists:
        return "DISTRIBUTION_SETUP_REQUIRED"
    if context.passwd_home is not None:
        if (
            not context.passwd_home.startswith("/")
            or ".." in context.passwd_home
            or context.passwd_home in {"", "/", "/root"}
            or len(context.passwd_home) > 240
        ):
            return "DISTRIBUTION_SETUP_REQUIRED"
    if (
        not context.windows_user
        or not context.profile_path
        or not context.desktop_path
        or context.linux_user in {"", "root"}
        or context.linux_uid <= 0
    ):
        return "RUNTIME_SETUP_REQUIRED"
    if not context.systemd_available:
        return "RUNTIME_SETUP_REQUIRED"
    if not context.permission_available:
        return "PERMISSION_REQUIRED"
    if not context.confirmed:
        return "CONFIRMATION_DECLINED"
    if not context.source_verified:
        return "SOURCE_VERIFICATION_FAILED"
    return "READY"
