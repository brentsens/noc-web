"""Pure Windows bootstrap preflight policy for regression tests."""

from __future__ import annotations

from dataclasses import dataclass


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


def assess(context: WindowsContext) -> str:
    if not context.wsl_available:
        return "WSL_SETUP_REQUIRED"
    if not context.wsl2_available or context.requested_distribution not in context.distributions:
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
