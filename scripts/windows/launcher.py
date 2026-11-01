import argparse
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit


_SERVICE = "noc-web.service"
_EXIT_CODES = {
    "service_unavailable": 3,
    "health_timeout": 4,
    "browser_unavailable": 5,
    "runtime_configuration_invalid": 6,
}
_WINDOWS_LAUNCH_EXECUTION_FAILED_EXIT_CODE = 7


class LauncherError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _validate_local_url(url: str, port: int) -> None:
    try:
        parsed = urlsplit(url)
        valid = (
            parsed.scheme == "http"
            and parsed.hostname in {"127.0.0.1", "localhost"}
            and parsed.port == port
            and parsed.username is None
            and parsed.password is None
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        valid = False
    if not valid:
        raise LauncherError("runtime_configuration_invalid")


def render_hidden_launcher(configuration, runtime_config_path: Path) -> str:
    template_path = Path(__file__).with_name("launch-hidden.vbs.in")
    template = template_path.read_text(encoding="utf-8")
    values = {
        "DISTRIBUTION": configuration.wsl_distribution,
        "LINUX_USER": configuration.linux_user,
        "PYTHON": str(configuration.virtual_environment / "bin" / "python"),
        "LAUNCHER": str(configuration.repository_root / "scripts" / "windows" / "launch.py"),
        "RUNTIME_CONFIG": str(Path(runtime_config_path)),
        "APPLICATION_URL": configuration.application_url,
        "HEALTH_TIMEOUT": str(configuration.health_timeout_seconds),
        "WINDOWS_EXECUTION_FAILURE_EXIT_CODE": str(
            _WINDOWS_LAUNCH_EXECUTION_FAILED_EXIT_CODE
        ),
    }
    escaped_values = {}
    for key, value in values.items():
        if not value or any(character in value for character in "\x00\r\n"):
            raise LauncherError("runtime_configuration_invalid")
        escaped_values[key] = value.replace('"', '""')
    template = re.sub(
        r"@@([A-Z_]+)@@",
        lambda match: escaped_values.get(match.group(1), match.group(0)),
        template,
    )
    if "@@" in template:
        raise LauncherError("runtime_configuration_invalid")
    _validate_local_url(configuration.application_url, configuration.port)
    return template


def ensure_user_service(runner=None) -> str:
    runner = subprocess.run if runner is None else runner
    try:
        active = runner(
            ["systemctl", "--user", "is-active", "--quiet", _SERVICE],
            shell=False,
            timeout=10,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if active.returncode == 0:
            return "reused"
        started = runner(
            ["systemctl", "--user", "start", _SERVICE],
            shell=False,
            timeout=15,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise LauncherError("service_unavailable") from None
    if started.returncode != 0:
        raise LauncherError("service_unavailable")
    return "started"


def _healthy(url: str, timeout: float) -> bool:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError, TimeoutError):
        return False


def _open_windows_browser(url: str) -> None:
    try:
        result = subprocess.run(
            ["cmd.exe", "/c", "start", "", url],
            shell=False,
            timeout=10,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise LauncherError("browser_unavailable") from None
    if result.returncode != 0:
        raise LauncherError("browser_unavailable")


def launch(
    configuration,
    *,
    runner=None,
    health_check=None,
    browser_opener=None,
    monotonic=None,
    sleep=None,
) -> str:
    _validate_local_url(configuration.application_url, configuration.port)
    ensure_running = ensure_user_service(runner)
    health_check = _healthy if health_check is None else health_check
    browser_opener = (
        _open_windows_browser if browser_opener is None else browser_opener
    )
    monotonic = time.monotonic if monotonic is None else monotonic
    sleep = time.sleep if sleep is None else sleep
    health_url = configuration.application_url.rstrip("/") + "/api/health"
    deadline = monotonic() + configuration.health_timeout_seconds
    while True:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise LauncherError("health_timeout")
        if health_check(health_url, min(2.0, remaining)):
            break
        sleep(min(0.5, remaining))
    try:
        browser_opener(configuration.application_url)
    except LauncherError:
        raise
    except Exception:
        raise LauncherError("browser_unavailable") from None
    return ensure_running


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--runtime-config", required=True)
    parser.add_argument("--application-url", required=True)
    parser.add_argument("--health-timeout", type=int, required=True)
    arguments = parser.parse_args(argv)
    try:
        repository_root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(repository_root))
        from backend.config import load_runtime_configuration

        configuration = load_runtime_configuration(Path(arguments.runtime_config))
        if (
            configuration.application_url != arguments.application_url
            or configuration.health_timeout_seconds != arguments.health_timeout
        ):
            raise LauncherError("runtime_configuration_invalid")
        launch(configuration)
    except LauncherError as error:
        return _EXIT_CODES.get(error.code, 6)
    except (OSError, ValueError):
        return 6
    return 0
