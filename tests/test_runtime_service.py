import getpass
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from backend.config import validate_runtime_configuration
from scripts.run_service import (
    PortConflictError,
    REPOSITORY_ROOT,
    TRUSTED_LINUXBREW_BIN,
    assert_listener_available,
    build_uvicorn_command,
    build_service_environment,
    render_systemd_unit,
)


def _config(tmp_path, repository_name="noc-web"):
    repository = tmp_path / repository_name
    (repository / "backend").mkdir(parents=True)
    (repository / "backend" / "app.py").write_text("app = object()\n", encoding="utf-8")
    (repository / "requirements.txt").write_text("fastapi==1\n", encoding="utf-8")
    return validate_runtime_configuration(
        {
            "schemaVersion": 1,
            "repositoryRoot": str(repository),
            "virtualEnvironment": str(repository / ".venv"),
            "wslDistribution": "Ubuntu-Local-Test",
            "linuxUser": "operator",
            "linuxUid": 1000,
            "port": 8123,
            "applicationUrl": "http://127.0.0.1:8123",
            "healthTimeoutSeconds": 60,
            "shortcutDirectory": None,
            "feature005Settings": {},
        },
        current_user="operator",
        current_uid=1000,
    )


def test_user_unit_uses_configured_worktree_venv_localhost_and_bounded_restart(
    tmp_path,
):
    config = _config(tmp_path)

    unit = render_systemd_unit(config)

    assert f"WorkingDirectory={config.repository_root}" in unit
    assert str(config.virtual_environment / "bin" / "python") in unit
    assert "NOC_WEB_PORT=8123" in unit
    assert "Restart=on-failure" in unit
    assert "StartLimitBurst=" in unit
    assert f"HOME={config.repository_root.parent}" not in unit
    assert "User=root" not in unit
    assert "0.0.0.0" not in unit

    command = build_uvicorn_command(config)
    assert command[command.index("--host") + 1] == "127.0.0.1"
    assert command[command.index("--port") + 1] == "8123"


def test_generated_user_unit_passes_systemd_user_verification(tmp_path):
    config = _config(tmp_path, repository_name="noc web%")
    python = config.virtual_environment / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.symlink_to(sys.executable)
    config_path = tmp_path / "config home%" / "noc-web" / "runtime.json"
    unit_path = tmp_path / "generated unit" / "noc-web.service"
    unit_path.parent.mkdir(parents=True)
    unit_path.write_text(
        render_systemd_unit(config, config_path),
        encoding="utf-8",
    )
    analyzer = shutil.which("systemd-analyze")
    assert analyzer is not None, "systemd-analyze is required for unit validation"

    result = subprocess.run(
        [analyzer, "--user", "verify", str(unit_path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_generated_execstart_starts_service_without_shell_python_environment(
    tmp_path,
):
    if os.getuid() == 0:
        pytest.skip("managed runtime must be exercised as an unprivileged user")

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    home = tmp_path / "service-home"
    home.mkdir()
    config_path = tmp_path / "config" / "noc-web" / "runtime.json"
    config_path.parent.mkdir(parents=True)
    configuration = validate_runtime_configuration(
        {
            "schemaVersion": 1,
            "repositoryRoot": str(REPOSITORY_ROOT),
            "virtualEnvironment": str(REPOSITORY_ROOT / ".venv"),
            "wslDistribution": "Service-Context-Test",
            "linuxUser": getpass.getuser(),
            "linuxUid": os.getuid(),
            "port": port,
            "applicationUrl": f"http://127.0.0.1:{port}",
            "healthTimeoutSeconds": 10,
            "shortcutDirectory": None,
            "feature005Settings": {},
        },
        current_user=getpass.getuser(),
        current_uid=os.getuid(),
    )
    config_path.write_text(
        json.dumps(configuration.serialize()),
        encoding="utf-8",
    )
    unit = render_systemd_unit(configuration, config_path)
    exec_start = next(
        line.removeprefix("ExecStart=")
        for line in unit.splitlines()
        if line.startswith("ExecStart=")
    )
    command = shlex.split(exec_start)
    expected_command = [
        str(configuration.virtual_environment / "bin" / "python"),
        "-m",
        "scripts.run_service",
        "--config",
        str(config_path),
    ]

    environment = {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(config_path.parent.parent),
        "PATH": os.pathsep.join((
            str(home / ".local" / "bin"),
            "/usr/local/sbin",
            "/usr/local/bin",
            "/usr/sbin",
            "/usr/bin",
            "/sbin",
            "/bin",
        )),
        "NOC_WEB_PORT": str(port),
        "NOC_WEB_RUNTIME_CONFIG": str(config_path),
    }
    assert "VIRTUAL_ENV" not in environment
    assert "PYTHONPATH" not in environment

    process = subprocess.Popen(
        command,
        cwd=configuration.repository_root,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    health_url = f"{configuration.application_url}/api/health"
    deadline = time.monotonic() + 15
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output, _ = process.communicate()
                pytest.fail(f"generated service command exited early: {output}")
            try:
                with urllib.request.urlopen(health_url, timeout=0.25) as response:
                    health = json.load(response)
                assert health["status"] == "healthy"
                assert health["service"] == "noc-web"
                assert command == expected_command
                return
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                time.sleep(0.05)
        output = process.communicate(timeout=1)[0]
        pytest.fail(f"generated service did not become healthy: {output}")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)


def test_service_environment_preserves_home_path_and_allowlisted_settings(tmp_path):
    config = _config(tmp_path)
    home = tmp_path / "operator"

    environment = build_service_environment(
        config,
        home=home,
        inherited={
            "COPILOT_TOKEN": "must-not-copy",
            "PATH": r"C:\Windows\System32:/interactive/bin",
        },
    )

    assert environment["HOME"] == str(home)
    assert environment["PATH"].split(os.pathsep) == [
        str(home / ".local" / "bin"),
        str(TRUSTED_LINUXBREW_BIN),
        "/usr/local/sbin",
        "/usr/local/bin",
        "/usr/sbin",
        "/usr/bin",
        "/sbin",
        "/bin",
    ]
    assert r"C:\Windows\System32" not in environment["PATH"]
    assert "/interactive/bin" not in environment["PATH"]
    assert "COPILOT_TOKEN" not in environment
    assert "NOC_WEB_PORT" in environment
    assert environment["NOC_WEB_PORT"] == "8123"


def test_generated_user_unit_includes_only_trusted_linuxbrew_path(tmp_path):
    unit = render_systemd_unit(_config(tmp_path))

    assert (
        "Environment=PATH=%h/.local/bin:"
        "/home/linuxbrew/.linuxbrew/Homebrew/bin:"
        "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    ) in unit
    assert "C:\\Windows" not in unit
    assert "/interactive/bin" not in unit


def test_listener_preflight_reports_existing_local_port(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]

        with pytest.raises(PortConflictError, match="already in use"):
            assert_listener_available(port)


def test_listener_preflight_does_not_bind_non_localhost_addresses():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

        with pytest.raises(PortConflictError):
            assert_listener_available(port)
