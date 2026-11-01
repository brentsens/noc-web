import hashlib
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from scripts import install_runtime


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("from_repository_root", [True, False])
def test_supported_installer_entrypoint_imports_backend_without_pythonpath(
    tmp_path, from_repository_root
):
    installer = REPOSITORY_ROOT / "scripts" / "install.sh"
    command = (
        ["./scripts/install.sh"]
        if from_repository_root
        else [str(installer)]
    )
    environment = {
        "HOME": str(tmp_path / "home"),
        "PATH": os.environ.get("PATH", ""),
    }

    result = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT if from_repository_root else tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 1
    assert "NOC_WEB_INSTALL_ERROR=" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
    assert "No module named 'backend'" not in result.stderr
    assert any(
        code in result.stderr
        for code in (
            "NOC_WEB_INSTALL_ERROR=root_execution_forbidden",
            "NOC_WEB_INSTALL_ERROR=wsl_distribution_unavailable",
        )
    )


def _environment(tmp_path):
    noc_root = tmp_path / "noc"
    noc_bin = tmp_path / "bin"
    probe_dir = noc_root / "readiness"
    for path in (noc_root, noc_bin, probe_dir):
        path.mkdir(parents=True, exist_ok=True)
    return {
        "HOME": str(tmp_path / "home"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "WSL_DISTRO_NAME": "Configured WSL",
        "NOC_WEB_NOC_ROOT": str(noc_root),
        "NOC_WEB_NOC_BIN": str(noc_bin),
        "NOC_WEB_READINESS_PROBE_DIR": str(probe_dir),
    }


def _runner(calls):
    def run(arguments, **kwargs):
        calls.append((arguments, kwargs))
        return SimpleNamespace(returncode=0, stdout="yes\n")

    return run


def _shortcut_installer(_configuration, _config_path, source):
    assert 'QuotePowerShellLiteral(wslPath) & _' in source
    assert '" --distribution " & QuotePowerShellLiteral(distribution)' in source


def test_install_is_repeatable_and_preserves_config_and_noc_records(tmp_path):
    environment = _environment(tmp_path)
    config_path = tmp_path / "config" / "noc-web" / "runtime.json"
    systemd_directory = tmp_path / "systemd" / "user"
    noc_root = Path(environment["NOC_WEB_NOC_ROOT"])
    operational_files = (
        noc_root / "tickets" / "open" / "NOC-111.json",
        noc_root / "2099-12-31" / "handover" / "handover-2099-12-31.md",
        noc_root / "2099-12-31" / "ai-reports" / "report.json",
        noc_root / "investigations" / "NOC-111" / "investigation.json",
        noc_root / ".datadog-active-incidents.json",
        noc_root / ".jira-open-tickets.json",
    )
    for index, path in enumerate(operational_files):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"operator-owned-record-{index}", encoding="utf-8")
    original_hashes = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in operational_files
    }
    calls = []
    kwargs = {
        "repository_root": REPOSITORY_ROOT,
        "configuration_path": config_path,
        "environment": environment,
        "runner": _runner(calls),
        "health_check": lambda _url, _timeout: True,
        "shortcut_installer": _shortcut_installer,
        "systemd_directory": systemd_directory,
        "user": "operator",
        "uid": 1000,
        "capability_assessor": lambda *_args, **_kwargs: [],
    }

    first = install_runtime.install_runtime(**kwargs)
    original_config = config_path.read_bytes()
    second = install_runtime.install_runtime(**kwargs)

    assert first.configuration.wsl_distribution == "Configured WSL"
    assert second.configuration.port == 8000
    assert config_path.read_bytes() == original_config
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in operational_files
    } == original_hashes
    assert (systemd_directory / "noc-web.service").is_file()
    assert (systemd_directory / "noc-web.service.bak").is_file()
    assert any("pip" in arguments and "install" in arguments for arguments, _ in calls)
    commands = [arguments for arguments, _ in calls]
    assert ["systemctl", "--user", "reset-failed", "noc-web.service"] in commands
    assert commands.index(
        ["systemctl", "--user", "reset-failed", "noc-web.service"]
    ) < commands.index(["systemctl", "--user", "enable", "--now", "noc-web.service"])
    assert commands.index(
        ["systemctl", "--user", "enable", "--now", "noc-web.service"]
    ) < commands.index(["systemctl", "--user", "restart", "noc-web.service"])
    assert not any(
        any(name in str(arguments).lower() for name in ("atlas", "copilot", "m365"))
        for arguments, _ in calls
    )


def test_invalid_existing_configuration_is_not_replaced(tmp_path):
    environment = _environment(tmp_path)
    config_path = tmp_path / "config" / "noc-web" / "runtime.json"
    config_path.parent.mkdir(parents=True)
    invalid = b'{"schemaVersion": 99}'
    config_path.write_bytes(invalid)
    calls = []

    with pytest.raises(install_runtime.InstallerError):
        install_runtime.install_runtime(
            repository_root=REPOSITORY_ROOT,
            configuration_path=config_path,
            environment=environment,
            runner=_runner(calls),
            health_check=lambda *_args: True,
            shortcut_installer=_shortcut_installer,
            systemd_directory=tmp_path / "systemd",
            user="operator",
            uid=1000,
            capability_assessor=lambda *_args, **_kwargs: [],
        )

    assert config_path.read_bytes() == invalid
    assert calls == []


def test_wrong_source_and_root_execution_fail_before_runtime_changes(tmp_path):
    with pytest.raises(install_runtime.InstallerError):
        install_runtime.install_runtime(
            repository_root=tmp_path,
            environment={"WSL_DISTRO_NAME": "Test"},
            runner=lambda *_args, **_kwargs: pytest.fail("must not run"),
            user="operator",
            uid=1000,
        )

    with pytest.raises(install_runtime.InstallerError):
        install_runtime.install_runtime(
            repository_root=REPOSITORY_ROOT,
            environment={"WSL_DISTRO_NAME": "Test"},
            runner=lambda *_args, **_kwargs: pytest.fail("must not run"),
            user="root",
            uid=0,
        )


def test_shortcut_failure_is_not_reported_as_success(tmp_path):
    environment = _environment(tmp_path)

    def shortcut_failure(*_args):
        raise install_runtime.InstallerError("shortcut_install_failed")

    with pytest.raises(install_runtime.InstallerError) as error:
        install_runtime.install_runtime(
            repository_root=REPOSITORY_ROOT,
            configuration_path=tmp_path / "runtime.json",
            environment=environment,
            runner=_runner([]),
            health_check=lambda *_args: True,
            shortcut_installer=shortcut_failure,
            systemd_directory=tmp_path / "systemd",
            user="operator",
            uid=1000,
            capability_assessor=lambda *_args, **_kwargs: [],
        )

    assert error.value.code == "shortcut_install_failed"


def test_shortcut_install_failure_preserves_safe_reason_without_raw_output(
    tmp_path, monkeypatch, capsys
):
    calls = []

    def runner(arguments, **kwargs):
        calls.append((arguments, kwargs))
        if arguments[0] == "wslpath":
            return SimpleNamespace(returncode=0, stdout="C:\\test\\path\n")
        return SimpleNamespace(
            returncode=1,
            stdout=(
                "SHORTCUT_INSTALL_FAILED\n"
                "SHORTCUT_INSTALL_REASON=destination_unsafe\n"
                "Sensitive exception detail: C:\\Users\\operator\\private\n"
            ),
        )

    with pytest.raises(install_runtime.InstallerError) as error:
        install_runtime._install_windows_shortcut(
            SimpleNamespace(shortcut_directory=None),
            tmp_path / "runtime.json",
            "launcher source",
            root=REPOSITORY_ROOT,
            runner=runner,
        )

    assert error.value.code == "shortcut_install_failed"
    assert error.value.reason == "destination_unsafe"
    assert "private" not in str(error.value)
    assert calls[-1][1]["stdout"] == subprocess.PIPE
    assert calls[-1][1]["stderr"] == subprocess.DEVNULL

    def fail_install():
        raise error.value

    monkeypatch.setattr(install_runtime, "install_runtime", fail_install)
    assert install_runtime.main() == 1
    captured = capsys.readouterr()
    assert captured.err == (
        "NOC_WEB_INSTALL_ERROR=shortcut_install_failed\n"
        "NOC_WEB_INSTALL_REASON=destination_unsafe\n"
    )
    assert "private" not in captured.err
