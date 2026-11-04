import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from backend.config import (
    DEFAULT_RUNTIME_PORT,
    FEATURE005_RUNTIME_SETTINGS,
    RuntimeConfigurationError,
    WorkstationRuntimeConfiguration,
    load_runtime_configuration,
    resolve_readiness_profile,
    runtime_configuration_path,
    save_runtime_configuration,
    validate_runtime_configuration,
)
from backend.services.dependency_readiness import assess_external_capabilities
from scripts.run_service import render_systemd_unit
from scripts.windows.launcher import render_hidden_launcher


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_REQUIREMENTS = REPOSITORY_ROOT / "requirements.txt"
MINIMUM_PYTHON = (3, 10)
HEALTH_REQUEST_TIMEOUT_SECONDS = 2
HEALTH_POLL_INTERVAL_SECONDS = 0.5
SHORTCUT_FAILURE_REASONS = frozenset(
    {
        "desktop_unavailable",
        "destination_invalid",
        "destination_unsafe",
        "install_path_unsafe",
        "launcher_source_invalid",
        "local_app_data_unavailable",
        "shortcut_write_failed",
    }
)


class InstallerError(RuntimeError):
    def __init__(self, code: str, *, reason: str | None = None):
        super().__init__(code)
        self.code = code
        self.reason = reason


@dataclass(frozen=True)
class InstallResult:
    configuration: WorkstationRuntimeConfiguration
    configuration_path: Path
    capability_results: tuple[dict, ...]


def _validate_source(repository_root: Path) -> Path:
    try:
        root = Path(repository_root).resolve(strict=True)
    except (OSError, RuntimeError):
        raise InstallerError("source_invalid") from None
    required = (
        root / "backend" / "app.py",
        root / "requirements.txt",
        root / "scripts" / "run_service.py",
        root / "scripts" / "windows" / "install-shortcut.ps1",
        root / "scripts" / "windows" / "launch-hidden.vbs.in",
        root / "systemd" / "noc-web.service.in",
    )
    if not root.is_dir() or any(not item.is_file() for item in required):
        raise InstallerError("source_invalid")
    try:
        requirements = [
            line.strip()
            for line in (root / "requirements.txt").read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    except OSError:
        raise InstallerError("source_invalid") from None
    if not requirements or any("==" not in requirement for requirement in requirements):
        raise InstallerError("requirements_unpinned")
    return root


def _runtime_configuration(
    root: Path,
    config_path: Path,
    environment: dict[str, str],
    user: str,
    uid: int,
) -> WorkstationRuntimeConfiguration:
    if config_path.exists():
        try:
            configuration = load_runtime_configuration(
                config_path, current_user=user, current_uid=uid
            )
        except RuntimeConfigurationError:
            raise InstallerError("configuration_invalid") from None
        if configuration.repository_root != root:
            raise InstallerError("repository_mismatch")
        distribution = environment.get("WSL_DISTRO_NAME")
        if distribution and configuration.wsl_distribution != distribution:
            raise InstallerError("distribution_mismatch")
        return configuration

    distribution = environment.get("WSL_DISTRO_NAME")
    if not distribution:
        raise InstallerError("wsl_distribution_unavailable")
    raw_port = environment.get("NOC_WEB_PORT", str(DEFAULT_RUNTIME_PORT))
    try:
        if not raw_port.isascii() or not raw_port.isdecimal():
            raise ValueError
        port = int(raw_port)
    except (AttributeError, ValueError):
        raise InstallerError("port_invalid") from None
    feature_settings = {
        key: environment[key]
        for key in FEATURE005_RUNTIME_SETTINGS
        if key in environment
    }
    payload = {
        "schemaVersion": 1,
        "repositoryRoot": str(root),
        "virtualEnvironment": str(root / ".venv"),
        "wslDistribution": distribution,
        "linuxUser": user,
        "linuxUid": uid,
        "port": port,
        "applicationUrl": f"http://127.0.0.1:{port}",
        "healthTimeoutSeconds": 60,
        "shortcutDirectory": None,
        "feature005Settings": feature_settings,
    }
    try:
        return validate_runtime_configuration(
            payload, current_user=user, current_uid=uid
        )
    except RuntimeConfigurationError:
        raise InstallerError("configuration_invalid") from None


def _run(
    arguments: list[str],
    *,
    runner,
    step: str,
    timeout: int = 30,
    capture: bool = False,
    require_success: bool = True,
):
    try:
        result = runner(
            arguments,
            shell=False,
            timeout=timeout,
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise InstallerError(step) from None
    if require_success and result.returncode != 0:
        raise InstallerError(step)
    return result


def _ensure_directory(path: Path) -> None:
    path = Path(path)
    if path.exists():
        if not path.is_dir() or path.is_symlink():
            raise InstallerError("runtime_directory_invalid")
        return
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError:
        raise InstallerError("runtime_directory_unavailable") from None
    if path.is_symlink() or not path.is_dir():
        raise InstallerError("runtime_directory_invalid")


def _write_managed_file(path: Path, content: str) -> None:
    _ensure_directory(path.parent)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise InstallerError("managed_file_invalid")
    temporary = path.with_name(f".{path.name}.new")
    backup = path.with_suffix(path.suffix + ".bak")
    try:
        if temporary.exists() or temporary.is_symlink():
            if temporary.is_dir() or temporary.is_symlink():
                raise OSError
            temporary.unlink()
        if path.exists():
            if backup.is_symlink() or (backup.exists() and not backup.is_file()):
                raise OSError
            shutil.copyfile(path, backup)
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise InstallerError("managed_file_write_failed") from None


def _create_runtime_directories(configuration: WorkstationRuntimeConfiguration):
    try:
        profile = resolve_readiness_profile(
            dict(configuration.feature005_settings)
        )
    except ValueError:
        raise InstallerError("workspace_configuration_invalid") from None
    for path in (profile.noc_root, profile.noc_bin, profile.probe_directory):
        _ensure_directory(path)
    return profile


def _install_virtual_environment(
    root: Path,
    configuration: WorkstationRuntimeConfiguration,
    *,
    runner,
):
    python = configuration.virtual_environment / "bin" / "python"
    if not python.is_file():
        _run(
            [
                sys.executable,
                "-m",
                "venv",
                str(configuration.virtual_environment),
            ],
            runner=runner,
            step="virtual_environment_create_failed",
            timeout=120,
        )
    if not python.is_file():
        raise InstallerError("virtual_environment_unavailable")
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--upgrade",
            "--requirement",
            str(root / "requirements.txt"),
        ],
        runner=runner,
        step="application_dependencies_install_failed",
        timeout=600,
    )


def _ensure_user_manager(user: str, *, runner):
    _run(
        ["systemctl", "--user", "show-environment"],
        runner=runner,
        step="user_service_manager_unavailable",
    )
    linger = _run(
        ["loginctl", "show-user", user, "--property=Linger", "--value"],
        runner=runner,
        step="user_linger_unavailable",
        capture=True,
        require_success=False,
    )
    if linger.returncode != 0:
        raise InstallerError("user_linger_unavailable")
    state = linger.stdout.strip().lower()
    if state == "yes":
        return
    if state != "no":
        raise InstallerError("user_linger_unavailable")
    _run(
        ["sudo", "loginctl", "enable-linger", user],
        runner=runner,
        step="user_linger_enable_failed",
        timeout=120,
    )
    verified = _run(
        ["loginctl", "show-user", user, "--property=Linger", "--value"],
        runner=runner,
        step="user_linger_enable_failed",
        capture=True,
    )
    if verified.stdout.strip().lower() != "yes":
        raise InstallerError("user_linger_enable_failed")


def _health_check(url: str, timeout: float) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError, TimeoutError):
        return False


def _wait_for_health(configuration, health_check, monotonic, sleep):
    health_url = configuration.application_url.rstrip("/") + "/api/health"
    deadline = monotonic() + configuration.health_timeout_seconds
    while True:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise InstallerError("health_timeout")
        if health_check(
            health_url,
            min(HEALTH_REQUEST_TIMEOUT_SECONDS, remaining),
        ):
            return
        sleep(min(HEALTH_POLL_INTERVAL_SECONDS, remaining))


def _windows_path(path: Path, *, runner) -> str:
    result = _run(
        ["wslpath", "-w", str(path)],
        runner=runner,
        step="windows_path_conversion_failed",
        capture=True,
    )
    value = result.stdout.strip()
    if not value or "\n" in value or "\r" in value:
        raise InstallerError("windows_path_conversion_failed")
    return value


def _install_windows_shortcut(
    configuration: WorkstationRuntimeConfiguration,
    config_path: Path,
    launcher_source: str,
    *,
    root: Path,
    runner,
):
    script = root / "scripts" / "windows" / "install-shortcut.ps1"
    with tempfile.TemporaryDirectory(prefix="noc-web-launcher-") as directory:
        source = Path(directory) / "launch-hidden.vbs"
        source.write_text(launcher_source, encoding="utf-8")
        script_win = _windows_path(script, runner=runner)
        source_win = _windows_path(source, runner=runner)
        arguments = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            script_win,
            "-LauncherSource",
            source_win,
            "-ShortcutDirectory",
            configuration.shortcut_directory or "",
        ]
        result = _run(
            arguments,
            runner=runner,
            step="shortcut_install_failed",
            timeout=60,
            capture=True,
            require_success=False,
        )
        if result.returncode != 0:
            output_lines = set(result.stdout.splitlines())
            reason = "shortcut_write_failed"
            if "SHORTCUT_INSTALL_FAILED" in output_lines:
                for line in output_lines:
                    prefix = "SHORTCUT_INSTALL_REASON="
                    if line.startswith(prefix):
                        candidate = line[len(prefix) :]
                        if candidate in SHORTCUT_FAILURE_REASONS:
                            reason = candidate
                        break
            raise InstallerError("shortcut_install_failed", reason=reason)


def install_runtime(
    *,
    repository_root: Path = REPOSITORY_ROOT,
    configuration_path: Path | None = None,
    environment: dict[str, str] | None = None,
    runner=None,
    health_check=None,
    shortcut_installer=None,
    systemd_directory: Path | None = None,
    user: str | None = None,
    uid: int | None = None,
    python_version=None,
    capability_assessor=None,
    monotonic=None,
    sleep=None,
) -> InstallResult:
    environment = dict(os.environ if environment is None else environment)
    runner = subprocess.run if runner is None else runner
    health_check = _health_check if health_check is None else health_check
    monotonic = time.monotonic if monotonic is None else monotonic
    sleep = time.sleep if sleep is None else sleep
    current_user = os.getuid() if hasattr(os, "getuid") else 0
    current_uid = current_user if uid is None else uid
    current_username = user
    if current_username is None:
        try:
            import getpass

            current_username = getpass.getuser()
        except OSError:
            raise InstallerError("user_identity_unavailable") from None
    version = sys.version_info if python_version is None else python_version

    if current_uid == 0 or current_username == "root":
        raise InstallerError("root_execution_forbidden")
    if tuple(version[:2]) < MINIMUM_PYTHON:
        raise InstallerError("python_version_unsupported")
    if not environment.get("WSL_DISTRO_NAME"):
        raise InstallerError("wsl_distribution_unavailable")

    root = _validate_source(repository_root)
    config_path = (
        runtime_configuration_path(
            environment,
            home=Path(environment.get("HOME", str(Path.home()))),
        )
        if configuration_path is None
        else Path(configuration_path)
    )
    configuration = _runtime_configuration(
        root, config_path, environment, current_username, current_uid
    )
    profile = _create_runtime_directories(configuration)
    _ensure_user_manager(current_username, runner=runner)
    _install_virtual_environment(root, configuration, runner=runner)

    if not config_path.exists():
        try:
            save_runtime_configuration(
                config_path,
                configuration.serialize(),
                current_user=current_username,
                current_uid=current_uid,
            )
        except RuntimeConfigurationError:
            raise InstallerError("configuration_write_failed") from None
    else:
        try:
            load_runtime_configuration(
                config_path, current_user=current_username, current_uid=current_uid
            )
        except RuntimeConfigurationError:
            raise InstallerError("configuration_invalid") from None

    if systemd_directory is None:
        config_home = Path(
            environment.get(
                "XDG_CONFIG_HOME",
                str(Path(environment.get("HOME", str(Path.home()))) / ".config"),
            )
        )
        systemd_directory = config_home / "systemd" / "user"
    unit_path = Path(systemd_directory) / "noc-web.service"
    _write_managed_file(unit_path, render_systemd_unit(configuration, config_path))

    _run(
        ["systemctl", "--user", "daemon-reload"],
        runner=runner,
        step="user_service_reload_failed",
    )
    _run(
        ["systemctl", "--user", "reset-failed", "noc-web.service"],
        runner=runner,
        step="user_service_reset_failed",
    )
    _run(
        ["systemctl", "--user", "enable", "--now", "noc-web.service"],
        runner=runner,
        step="user_service_start_failed",
        timeout=60,
    )
    _run(
        ["systemctl", "--user", "restart", "noc-web.service"],
        runner=runner,
        step="user_service_restart_failed",
        timeout=60,
    )
    _wait_for_health(configuration, health_check, monotonic, sleep)

    shortcut_mode = environment.get("NOC_WEB_SHORTCUT_MODE", "hidden-vbs")
    if shortcut_mode == "wsl-native":
        # WSL-native bootstrap owns the Desktop shortcut (wsl.exe -> sesami-noc-launch).
        # Feature 011 still owns the managed service, runtime.json, and health gate.
        pass
    else:
        launcher_source = render_hidden_launcher(configuration, config_path)
        if shortcut_installer is None:
            _install_windows_shortcut(
                configuration,
                config_path,
                launcher_source,
                root=root,
                runner=runner,
            )
        else:
            try:
                shortcut_installer(configuration, config_path, launcher_source)
            except InstallerError:
                raise
            except Exception:
                raise InstallerError("shortcut_install_failed") from None

    assessor = (
        assess_external_capabilities
        if capability_assessor is None
        else capability_assessor
    )
    capabilities = tuple(
        assessor(profile.noc_bin, timeout_seconds=profile.command_timeout_seconds)
    )
    return InstallResult(configuration, config_path, capabilities)


def main(argv=None) -> int:
    del argv
    try:
        result = install_runtime()
    except InstallerError as error:
        print(f"NOC_WEB_INSTALL_ERROR={error.code}", file=sys.stderr)
        if error.reason:
            print(f"NOC_WEB_INSTALL_REASON={error.reason}", file=sys.stderr)
        return 1
    print("Core noc-web: READY")
    for capability in result.capability_results:
        print(f'{capability["capability"]}: {capability["status"].upper()}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
