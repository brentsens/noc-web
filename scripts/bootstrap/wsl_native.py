"""WSL-native Feature 012 bootstrap frontend.

Reuses trusted release acquisition, prerequisites, provisioning, repair, and
Feature 011 handoff without requiring a Windows EXE for first-time install.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


_CONTROLLED_PATH = "/usr/local/bin:/usr/bin:/bin"
_WSL2_KERNEL = re.compile(r"microsoft-standard-WSL2", re.IGNORECASE)
_SAFE_DISTRO = re.compile(r"^[A-Za-z0-9._-]{1,63}$")
_SAFE_HOME = re.compile(r"^/[A-Za-z0-9._/-]{1,240}$")
INSTALL_SUBPATH = Path(".local/share/sesami-noc-operations/noc-web")
RECORD_SUBPATH = Path(".local/state/sesami-noc-operations/release-record.json")
LAUNCHER_NAME = "sesami-noc-launch"
LAUNCHER_RELATIVE = Path(".local/bin") / LAUNCHER_NAME


class WslNativeError(RuntimeError):
    """Categorized, non-secret WSL-native bootstrap failure."""

    def __init__(self, category: str, *, stage: str = "", reason: str = ""):
        super().__init__(category)
        self.category = category
        self.stage = stage
        self.reason = reason


@dataclass(frozen=True)
class WslNativeContext:
    distribution: str
    distro_family: str
    username: str
    uid: int
    home: Path
    kernel: str


@dataclass(frozen=True)
class PrerequisiteSnapshot:
    distro_family: str
    gh_attestation: str
    packages: tuple[str, ...]
    capabilities: tuple[str, ...]
    ready: bool


def detect_wsl2(
    *,
    uname_release: str | None = None,
    environ: dict[str, str] | None = None,
) -> str:
    """Return the kernel release when WSL2 is verified; otherwise raise."""
    environment = os.environ if environ is None else environ
    if not environment.get("WSL_DISTRO_NAME"):
        raise WslNativeError("WSL_SETUP_REQUIRED", stage="platform-check", reason="not-wsl")
    release = uname_release
    if release is None:
        try:
            release = os.uname().release
        except OSError as error:
            raise WslNativeError(
                "WSL_SETUP_REQUIRED", stage="platform-check", reason="kernel-unavailable"
            ) from error
    if not release or not _WSL2_KERNEL.search(release):
        raise WslNativeError("WSL_SETUP_REQUIRED", stage="kernel-check", reason="wsl1-unsupported")
    return release


def read_distro_family(os_release_path: Path) -> str:
    if not os_release_path.is_file():
        return "unknown"
    try:
        for line in os_release_path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("ID="):
                continue
            value = line.split("=", 1)[1].strip().strip('"')
            if re.fullmatch(r"[a-z0-9._-]+", value or ""):
                return value
            return "unknown"
    except OSError:
        return "unknown"
    return "unknown"


def resolve_operator_identity(
    *,
    distribution: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> tuple[str, int, Path]:
    """Resolve non-root operator identity from id/getent passwd."""
    from scripts.bootstrap.handoff import HandoffError, discover_linux_identity

    if not _SAFE_DISTRO.fullmatch(distribution or ""):
        raise WslNativeError(
            "DISTRIBUTION_SETUP_REQUIRED",
            stage="distribution-validation",
            reason="unsafe-distribution-name",
        )
    try:
        identity = discover_linux_identity(distribution, runner=runner)
    except HandoffError as error:
        raise WslNativeError(
            "DISTRIBUTION_SETUP_REQUIRED",
            stage="linux-identity",
            reason="account-record-invalid",
        ) from error
    if identity.user == "root" or identity.uid <= 0:
        raise WslNativeError(
            "RUNTIME_SETUP_REQUIRED",
            stage="linux-identity",
            reason="root-forbidden",
        )
    home = Path(identity.home)
    if (
        not home.is_absolute()
        or ".." in home.parts
        or not _SAFE_HOME.fullmatch(str(home))
        or not home.is_dir()
    ):
        raise WslNativeError(
            "DISTRIBUTION_SETUP_REQUIRED",
            stage="linux-identity",
            reason="home-unusable",
        )
    return identity.user, identity.uid, home


def require_systemd_user(
    *,
    uid: int,
    home: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> None:
    exec_run = runner if runner is not None else subprocess.run
    try:
        result = exec_run(
            ["systemctl", "--user", "is-system-running"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
            env={
                "PATH": _CONTROLLED_PATH,
                "HOME": str(home),
                "XDG_RUNTIME_DIR": f"/run/user/{uid}",
                "DBUS_SESSION_BUS_ADDRESS": f"unix:path=/run/user/{uid}/bus",
            },
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise WslNativeError(
            "RUNTIME_SETUP_REQUIRED",
            stage="systemd-user",
            reason="systemd-user-inactive",
        ) from error
    status = (result.stdout or "").strip()
    if result.returncode != 0 or status not in {"running", "degraded"}:
        raise WslNativeError(
            "RUNTIME_SETUP_REQUIRED",
            stage="systemd-user",
            reason="systemd-user-inactive",
        )


def parse_prerequisite_output(lines: list[str]) -> PrerequisiteSnapshot:
    family = "unknown"
    gh = "missing"
    packages: list[str] = []
    capabilities: list[str] = []
    ready = False
    for line in lines:
        if line.startswith("DISTRO_FAMILY="):
            family = line.split("=", 1)[1].strip() or "unknown"
        elif line.startswith("GH_ATTESTATION="):
            gh = line.split("=", 1)[1].strip() or "missing"
        elif line.startswith("MISSING_UBUNTU_PACKAGES="):
            packages = [item for item in line.split("=", 1)[1].split() if item]
        elif line.startswith("MISSING_CAPABILITIES="):
            capabilities = [item for item in line.split("=", 1)[1].split() if item]
        elif line == "PREREQUISITES_READY":
            ready = True
    return PrerequisiteSnapshot(
        distro_family=family,
        gh_attestation=gh,
        packages=tuple(packages),
        capabilities=tuple(capabilities),
        ready=ready and not packages and not capabilities and gh == "ready",
    )


def assess_prerequisites(
    package_root: Path,
    *,
    include_noc_tools: bool = False,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    os_release: Path | None = None,
) -> PrerequisiteSnapshot:
    script = package_root / "scripts" / "bootstrap" / "check_runtime_prerequisites.sh"
    if not script.is_file():
        raise WslNativeError(
            "RUNTIME_SETUP_REQUIRED",
            stage="prerequisites",
            reason="checker-missing",
        )
    exec_run = runner if runner is not None else subprocess.run
    command = ["/bin/sh", str(script)]
    if include_noc_tools:
        command.append("--include-noc-tools")
    environment = {
        "PATH": _CONTROLLED_PATH,
        "HOME": os.environ.get("HOME", ""),
    }
    if os_release is not None:
        environment["NOC_BOOTSTRAP_OS_RELEASE"] = str(os_release)
    try:
        result = exec_run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise WslNativeError(
            "RUNTIME_SETUP_REQUIRED",
            stage="prerequisites",
            reason="checker-failed",
        ) from error
    if result.returncode != 0:
        raise WslNativeError(
            "RUNTIME_SETUP_REQUIRED",
            stage="prerequisites",
            reason="checker-failed",
        )
    return parse_prerequisite_output((result.stdout or "").splitlines())


def ubuntu_package_install_command(packages: tuple[str, ...]) -> str:
    approved = {"python3", "python3-venv", "ca-certificates"}
    ordered = [package for package in ("python3", "python3-venv", "ca-certificates") if package in packages]
    extras = [package for package in packages if package not in approved]
    if extras or not ordered:
        raise WslNativeError(
            "RUNTIME_SETUP_REQUIRED",
            stage="runtime-packages",
            reason="packages-unapproved",
        )
    return "sudo apt-get update && sudo apt-get install --yes " + " ".join(ordered)


def install_linux_launcher(*, home: Path, release_root: Path) -> Path:
    """Install ~/.local/bin/sesami-noc-launch that reuses Feature 011 launch logic."""
    if not (release_root / "scripts" / "windows" / "sesami_noc_launch.py").is_file():
        raise WslNativeError(
            "FEATURE011_HANDOFF_FAILED",
            stage="launcher",
            reason="release-missing-launcher",
        )
    bin_dir = home / ".local" / "bin"
    bin_dir.mkdir(mode=0o755, parents=True, exist_ok=True)
    target = bin_dir / LAUNCHER_NAME
    temporary = bin_dir / (LAUNCHER_NAME + ".new")
    script = f"""#!/bin/sh
set -eu
ROOT={_shell_single_quote(str(release_root))}
export PATH={_shell_single_quote(_CONTROLLED_PATH)}
export HOME={_shell_single_quote(str(home))}
cd "$ROOT" || exit 1
exec "$ROOT/.venv/bin/python" -m scripts.windows.sesami_noc_launch
"""
    temporary.write_text(script, encoding="utf-8")
    temporary.chmod(temporary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    os.replace(temporary, target)
    return target


def build_wsl_shortcut_arguments(*, distribution: str, linux_launcher: str) -> str:
    if not _SAFE_DISTRO.fullmatch(distribution or ""):
        raise WslNativeError(
            "RUNTIME_SETUP_REQUIRED",
            stage="shortcut",
            reason="unsafe-distribution-name",
        )
    if (
        not linux_launcher.startswith("/")
        or ".." in linux_launcher
        or not _SAFE_HOME.fullmatch(linux_launcher)
        or any(ord(character) < 32 or character == '"' for character in linux_launcher)
    ):
        raise WslNativeError(
            "RUNTIME_SETUP_REQUIRED",
            stage="shortcut",
            reason="unsafe-launcher-path",
        )
    return f"--distribution {distribution} --exec {linux_launcher}"


def _shell_single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def create_windows_shortcut(
    *,
    package_root: Path,
    distribution: str,
    linux_launcher: Path,
    icon_linux_path: Path | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> None:
    script = package_root / "scripts" / "bootstrap" / "install_wsl_shortcut.ps1"
    if not script.is_file():
        raise WslNativeError(
            "RUNTIME_SETUP_REQUIRED",
            stage="shortcut",
            reason="shortcut-script-missing",
        )
    arguments = build_wsl_shortcut_arguments(
        distribution=distribution,
        linux_launcher=str(linux_launcher),
    )
    del arguments  # validated above; PowerShell receives discrete parameters
    exec_run = runner if runner is not None else subprocess.run

    def to_windows_path(linux_path: Path) -> str:
        try:
            converted = exec_run(
                ["wslpath", "-w", str(linux_path)],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
                env={"PATH": _CONTROLLED_PATH},
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise WslNativeError(
                "RUNTIME_SETUP_REQUIRED",
                stage="shortcut",
                reason="windows-path-conversion-failed",
            ) from error
        value = (converted.stdout or "").strip()
        if converted.returncode != 0 or not value or "\n" in value or "\r" in value:
            raise WslNativeError(
                "RUNTIME_SETUP_REQUIRED",
                stage="shortcut",
                reason="windows-path-conversion-failed",
            )
        return value

    script_win = to_windows_path(script)
    command = [
        "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        script_win,
        "-Distribution",
        distribution,
        "-LinuxLauncher",
        str(linux_launcher),
    ]
    if icon_linux_path is not None and icon_linux_path.is_file():
        try:
            command.extend(["-IconPath", to_windows_path(icon_linux_path)])
        except WslNativeError:
            # Icon is optional; keep the Microsoft wsl.exe shortcut without branding.
            pass
    try:
        result = exec_run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
            env={
                "PATH": _CONTROLLED_PATH,
                "HOME": os.environ.get("HOME", ""),
            },
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise WslNativeError(
            "RUNTIME_SETUP_REQUIRED",
            stage="shortcut",
            reason="shortcut-failed",
        ) from error
    lines = set((result.stdout or "").splitlines())
    if result.returncode != 0 or "SHORTCUT_INSTALLED" not in lines:
        raise WslNativeError(
            "RUNTIME_SETUP_REQUIRED",
            stage="shortcut",
            reason="shortcut-failed",
        )
    if "SHORTCUT_TARGET=wsl.exe" not in lines:
        raise WslNativeError(
            "RUNTIME_SETUP_REQUIRED",
            stage="shortcut",
            reason="shortcut-target-invalid",
        )


def run_confirmed_command(
    command: str,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> None:
    if not command or len(command) > 1024 or '"' in command:
        raise WslNativeError(
            "RUNTIME_SETUP_REQUIRED",
            stage="runtime-packages",
            reason="unsafe-command",
        )
    exec_run = runner if runner is not None else subprocess.run
    try:
        result = exec_run(
            ["/bin/sh", "-lc", command],
            capture_output=True,
            text=True,
            check=False,
            timeout=900,
            env={"PATH": _CONTROLLED_PATH, "HOME": os.environ.get("HOME", "")},
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise WslNativeError(
            "RUNTIME_SETUP_REQUIRED",
            stage="runtime-packages",
            reason="install-failed",
        ) from error
    if result.returncode != 0:
        raise WslNativeError(
            "RUNTIME_SETUP_REQUIRED",
            stage="runtime-packages",
            reason="install-failed",
        )


def acquire_and_handoff(
    *,
    package_root: Path,
    manifest_path: Path,
    home: Path,
    distribution: str,
    runner: Callable[..., object] | None = None,
) -> Path:
    from scripts.bootstrap.acquire_release import main as acquire_main

    install_root = home / INSTALL_SUBPATH
    record_path = home / RECORD_SUBPATH
    record_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    environment = {
        "HOME": str(home),
        "PATH": _CONTROLLED_PATH,
        "WSL_DISTRO_NAME": distribution,
        "NOC_WEB_SHORTCUT_MODE": "wsl-native",
    }
    previous = {key: os.environ.get(key) for key in environment}
    try:
        os.environ.update(environment)
        code = acquire_main(
            [
                "--manifest",
                str(manifest_path),
                "--install-root",
                str(install_root),
                "--record-path",
                str(record_path),
                "--distribution",
                distribution,
            ]
        )
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    del runner
    if code != 0:
        raise WslNativeError(
            "SOURCE_VERIFICATION_FAILED",
            stage="release-acquisition",
            reason="download-or-staging-failed",
        )
    if not install_root.is_dir():
        raise WslNativeError(
            "FEATURE011_HANDOFF_FAILED",
            stage="handoff",
            reason="install-root-missing",
        )
    return install_root


def provision_noc_tools(
    *,
    release_root: Path,
    manifest_path: Path,
    home: Path,
) -> None:
    from scripts.bootstrap.provision_dependencies import ProvisionError, main as provision_main

    previous_home = os.environ.get("HOME")
    previous_path = os.environ.get("PATH")
    try:
        os.environ["HOME"] = str(home)
        os.environ["PATH"] = f"{home / '.local' / 'bin'}:{_CONTROLLED_PATH}"
        code = provision_main(
            [
                "--manifest",
                str(manifest_path),
                "--install-root",
                str(home),
                "--noc-bin",
                str(home / ".local" / "bin"),
                "--confirmed",
            ]
        )
    except ProvisionError as error:
        raise WslNativeError(
            "DEPENDENCY_SETUP_REQUIRED",
            stage="noc-tools",
            reason="provisioning-failed",
        ) from error
    finally:
        if previous_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = previous_home
        if previous_path is None:
            os.environ.pop("PATH", None)
        else:
            os.environ["PATH"] = previous_path
    if code != 0:
        raise WslNativeError(
            "DEPENDENCY_SETUP_REQUIRED",
            stage="noc-tools",
            reason="provisioning-failed",
        )
    for command_name in ("tix", "noc-start", "noc-status", "noc-handover"):
        if shutil.which(command_name, path=f"{home / '.local' / 'bin'}:{_CONTROLLED_PATH}") is None:
            raise WslNativeError(
                "DEPENDENCY_SETUP_REQUIRED",
                stage="noc-tools",
                reason="command-missing",
            )
    try:
        result = subprocess.run(
            ["noc-inv", "--contract-version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            env={
                "PATH": f"{home / '.local' / 'bin'}:{_CONTROLLED_PATH}",
                "HOME": str(home),
            },
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise WslNativeError(
            "DEPENDENCY_SETUP_REQUIRED",
            stage="noc-tools",
            reason="contract-check-failed",
        ) from error
    if result.returncode != 0 or (result.stdout or "").strip() != "noc-inv-contract=1":
        raise WslNativeError(
            "DEPENDENCY_SETUP_REQUIRED",
            stage="noc-tools",
            reason="contract-mismatch",
        )
    del release_root


def collect_context(
    *,
    environ: dict[str, str] | None = None,
    os_release_path: Path = Path("/etc/os-release"),
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> WslNativeContext:
    environment = dict(os.environ if environ is None else environ)
    kernel = detect_wsl2(environ=environment)
    distribution = environment.get("WSL_DISTRO_NAME", "")
    if not _SAFE_DISTRO.fullmatch(distribution):
        raise WslNativeError(
            "DISTRIBUTION_SETUP_REQUIRED",
            stage="distribution-validation",
            reason="unsafe-distribution-name",
        )
    family = read_distro_family(os_release_path)
    username, uid, home = resolve_operator_identity(distribution=distribution, runner=runner)

    require_systemd_user(
        uid=uid,
        home=home,
        runner=runner,
    )

    return WslNativeContext(
        distribution=distribution,
        distro_family=family,
        username=username,
        uid=uid,
        home=home,
        kernel=kernel,
    )


def run_wsl_native_bootstrap(
    *,
    package_root: Path,
    confirm_prerequisites: bool = False,
    confirm_replacement: bool = False,
    confirm_noc_tools: bool = False,
    github_cli_approved: bool = False,
    environ: dict[str, str] | None = None,
    os_release_path: Path = Path("/etc/os-release"),
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    prompt: Callable[[str], bool] | None = None,
) -> str:
    """Execute the WSL-native bootstrap and return BOOTSTRAP_READY on success."""
    package_root = Path(package_root).resolve()
    manifest_path = package_root / "packaging" / "windows" / "bootstrap-manifest.json"
    if not manifest_path.is_file():
        raise WslNativeError(
            "SOURCE_VERIFICATION_FAILED",
            stage="source-verification",
            reason="manifest-missing",
        )

    context = collect_context(environ=environ, os_release_path=os_release_path, runner=runner)
    os.environ["HOME"] = str(context.home)

    prerequisites = assess_prerequisites(package_root, runner=runner, os_release=os_release_path)
    if prerequisites.packages:
        if prerequisites.distro_family != "ubuntu":
            raise WslNativeError(
                "RUNTIME_SETUP_REQUIRED",
                stage="runtime-capabilities",
                reason="missing-capabilities",
            )
        command = ubuntu_package_install_command(prerequisites.packages)
        print(f"APPROVED_UBUNTU_PREREQUISITE_INSTALL={command}")
        approved = confirm_prerequisites
        if prompt is not None:
            approved = prompt(command)
        if not approved:
            raise WslNativeError(
                "RUNTIME_SETUP_REQUIRED",
                stage="runtime-packages",
                reason="operator-declined",
            )
        run_confirmed_command(command, runner=runner)
        prerequisites = assess_prerequisites(
            package_root, runner=runner, os_release=os_release_path
        )

    non_gh = [item for item in prerequisites.capabilities if item != "gh-attestation"]
    if prerequisites.packages or non_gh:
        raise WslNativeError(
            "RUNTIME_SETUP_REQUIRED",
            stage="runtime-capabilities",
            reason="missing-capabilities",
        )

    if prerequisites.gh_attestation != "ready":
        if prerequisites.distro_family != "ubuntu":
            raise WslNativeError(
                "RUNTIME_SETUP_REQUIRED",
                stage="gh-attestation",
                reason="unsupported-distro-gh",
            )
        gh_script = package_root / "scripts" / "bootstrap" / "provision_github_cli.sh"
        gh_command = f"sudo /bin/sh {_shell_single_quote(str(gh_script))}"
        print("APPROVED_GITHUB_CLI_SOURCE=https://cli.github.com/packages")
        print(f"APPROVED_GITHUB_CLI_COMMAND={gh_command}")
        if not github_cli_approved:
            raise WslNativeError(
                "RUNTIME_SETUP_REQUIRED",
                stage="gh-attestation",
                reason="approval-pending",
            )
        run_confirmed_command(gh_command, runner=runner)
        prerequisites = assess_prerequisites(
            package_root, runner=runner, os_release=os_release_path
        )
        if prerequisites.gh_attestation != "ready":
            raise WslNativeError(
                "RUNTIME_SETUP_REQUIRED",
                stage="gh-attestation",
                reason="attestation-unavailable",
            )

    prerequisites = assess_prerequisites(
        package_root, runner=runner, os_release=os_release_path
    )
    if (
        prerequisites.gh_attestation != "ready"
        or prerequisites.packages
        or prerequisites.capabilities
    ):
        raise WslNativeError(
            "RUNTIME_SETUP_REQUIRED",
            stage="prerequisites",
            reason="not-ready",
        )

    if not confirm_replacement:
        raise WslNativeError(
            "CONFIRMATION_DECLINED",
            stage="release-confirmation",
            reason="operator-declined",
        )

    print("APPROVED_RELEASE=v1.0.4")
    release_root = acquire_and_handoff(
        package_root=package_root,
        manifest_path=manifest_path,
        home=context.home,
        distribution=context.distribution,
        runner=runner,
    )

    launcher = install_linux_launcher(home=context.home, release_root=release_root)
    icon = package_root / "packaging" / "windows" / "sesami-noc-operations.ico"
    create_windows_shortcut(
        package_root=package_root,
        distribution=context.distribution,
        linux_launcher=launcher,
        icon_linux_path=icon if icon.is_file() else None,
        runner=runner,
    )

    if confirm_noc_tools:
        noc_prereq = assess_prerequisites(
            package_root,
            include_noc_tools=True,
            runner=runner,
            os_release=os_release_path,
        )
        if not noc_prereq.ready and (
            noc_prereq.packages or [c for c in noc_prereq.capabilities if c != "gh-attestation"]
        ):
            raise WslNativeError(
                "DEPENDENCY_SETUP_REQUIRED",
                stage="noc-tools",
                reason="prerequisites-missing",
            )
        provision_noc_tools(
            release_root=release_root,
            manifest_path=manifest_path,
            home=context.home,
        )

    return "BOOTSTRAP_READY"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="install-sesami")
    parser.add_argument(
        "--package-root",
        default="",
        help="Verified package root containing packaging/windows/bootstrap-manifest.json",
    )
    parser.add_argument("--confirm-prerequisites", action="store_true")
    parser.add_argument("--confirm-replacement", action="store_true")
    parser.add_argument("--confirm-noc-tools", action="store_true")
    parser.add_argument("--github-cli-approved", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    package_root = Path(arguments.package_root) if arguments.package_root else Path.cwd()
    try:
        result = run_wsl_native_bootstrap(
            package_root=package_root,
            confirm_prerequisites=arguments.confirm_prerequisites,
            confirm_replacement=arguments.confirm_replacement,
            confirm_noc_tools=arguments.confirm_noc_tools,
            github_cli_approved=arguments.github_cli_approved,
        )
    except WslNativeError as error:
        print(error.category)
        if error.stage:
            print(f"STAGE={error.stage}")
        if error.reason:
            print(f"REASON={error.reason}")
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
