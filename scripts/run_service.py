import argparse
import os
import socket
import sys
from pathlib import Path

from backend.config import (
    RuntimeConfigurationError,
    WorkstationRuntimeConfiguration,
    load_runtime_configuration,
    runtime_configuration_path,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
UNIT_TEMPLATE = REPOSITORY_ROOT / "systemd" / "noc-web.service.in"
UNIT_NAME = "noc-web.service"
START_LIMIT_INTERVAL_SECONDS = 60
START_LIMIT_BURST = 5
RESTART_DELAY_SECONDS = 5
TRUSTED_LINUXBREW_BIN = Path("/home/linuxbrew/.linuxbrew/Homebrew/bin")
PROVIDER_ENVIRONMENT_ALLOWLIST = (
    "NOC_WEB_AI_PROVIDER",
    "NOC_WEB_DEEPSEEK_API_KEY",
    "NOC_WEB_DEEPSEEK_MODEL",
    "NOC_WEB_DEEPSEEK_BASE_URL",
    "NOC_WEB_AI_TIMEOUT_SECONDS",
    "NOC_WEB_DATADOG_ACCESS_TOKEN",
    "NOC_WEB_DATADOG_BASE_URL",
    "NOC_WEB_DATADOG_TIMEOUT_SECONDS",
)


class PortConflictError(RuntimeError):
    """The configured localhost listener is already occupied."""


def _systemd_command_argument(value: str) -> str:
    escaped = value.replace("%", "%%").replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _systemd_environment_assignment(name: str, value: str) -> str:
    return _systemd_command_argument(f"{name}={value}")


def _systemd_path(value: str) -> str:
    return value.replace("%", "%%")


def render_systemd_unit(
    configuration: WorkstationRuntimeConfiguration,
    config_path: Path | None = None,
) -> str:
    config_path = runtime_configuration_path() if config_path is None else Path(config_path)
    template = UNIT_TEMPLATE.read_text(encoding="utf-8")
    substitutions = {
        "@REPOSITORY_ROOT@": _systemd_path(str(configuration.repository_root)),
        "@PYTHON@": _systemd_command_argument(
            str(configuration.virtual_environment / "bin" / "python")
        ),
        "@CONFIG_PATH@": _systemd_command_argument(str(config_path)),
        "@AI_PROVIDER_ENV_FILE@": str(config_path.parent / "ai-provider.env"),
        "@DATADOG_PROVIDER_ENV_FILE@": str(config_path.parent / "datadog-provider.env"),
        "@XDG_CONFIG_HOME_ENV@": _systemd_environment_assignment(
            "XDG_CONFIG_HOME", str(config_path.parent.parent)
        ),
        "@RUNTIME_CONFIG_ENV@": _systemd_environment_assignment(
            "NOC_WEB_RUNTIME_CONFIG", str(config_path)
        ),
        "@PORT@": str(configuration.port),
        "@START_LIMIT_INTERVAL@": str(START_LIMIT_INTERVAL_SECONDS),
        "@START_LIMIT_BURST@": str(START_LIMIT_BURST),
        "@RESTART_DELAY@": f"{RESTART_DELAY_SECONDS}s",
    }
    for token, replacement in substitutions.items():
        template = template.replace(token, replacement)
    return template


def build_service_environment(
    configuration: WorkstationRuntimeConfiguration,
    *,
    home: Path | None = None,
    config_path: Path | None = None,
    inherited: dict[str, str] | None = None,
) -> dict[str, str]:
    if inherited is None:
        inherited = os.environ
    home = Path.home() if home is None else Path(home)
    config_path = runtime_configuration_path() if config_path is None else Path(config_path)
    environment = {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(config_path.parent.parent),
        "PATH": os.pathsep.join((
            str(home / ".local" / "bin"),
            str(TRUSTED_LINUXBREW_BIN),
            "/usr/local/sbin",
            "/usr/local/bin",
            "/usr/sbin",
            "/usr/bin",
            "/sbin",
            "/bin",
        )),
        "NOC_WEB_PORT": str(configuration.port),
        "PYTHONUNBUFFERED": "1",
    }
    environment.update(dict(configuration.feature005_settings))
    for name in PROVIDER_ENVIRONMENT_ALLOWLIST:
        value = inherited.get(name)
        if value:
            environment[name] = value
    return environment


def build_uvicorn_command(
    configuration: WorkstationRuntimeConfiguration,
) -> list[str]:
    return [
        str(configuration.virtual_environment / "bin" / "python"),
        "-m",
        "uvicorn",
        "backend.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(configuration.port),
        "--no-access-log",
    ]


def assert_listener_available(port: int) -> None:
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("invalid-port")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", port))
    except OSError:
        raise PortConflictError("configured localhost port is already in use") from None


def _start(config_path: Path) -> int:
    configuration = load_runtime_configuration(config_path)
    assert_listener_available(configuration.port)
    python = configuration.virtual_environment / "bin" / "python"
    if not python.is_file():
        print("NOC_WEB_STARTUP_ERROR=virtual-environment-unavailable", file=sys.stderr)
        return 78
    command = build_uvicorn_command(configuration)
    environment = build_service_environment(
        configuration,
        home=Path.home(),
        config_path=config_path,
    )
    try:
        os.execvpe(command[0], command, environment)
    except OSError:
        print("NOC_WEB_STARTUP_ERROR=runtime-launch-failed", file=sys.stderr)
        return 70
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--config", type=Path, default=runtime_configuration_path())
    arguments = parser.parse_args(argv)
    try:
        return _start(arguments.config)
    except RuntimeConfigurationError as error:
        print(f"NOC_WEB_STARTUP_ERROR=configuration-{error.setting}", file=sys.stderr)
        return 78
    except PortConflictError:
        print("NOC_WEB_STARTUP_ERROR=port-in-use", file=sys.stderr)
        return 98


if __name__ == "__main__":
    raise SystemExit(main())
