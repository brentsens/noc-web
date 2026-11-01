import subprocess
from types import SimpleNamespace

import pytest

from scripts.windows import launcher


def _configuration(tmp_path):
    return SimpleNamespace(
        wsl_distribution="NOC Workstation",
        linux_user="operator",
        repository_root=tmp_path / "noc-web",
        virtual_environment=tmp_path / "noc-web" / ".venv",
        application_url="http://127.0.0.1:8123",
        health_timeout_seconds=3,
        port=8123,
    )


def test_active_service_is_reused_and_browser_waits_for_health(tmp_path):
    configuration = _configuration(tmp_path)
    calls = []
    health_results = iter((False, True))

    def run(arguments, **kwargs):
        calls.append(arguments)
        return SimpleNamespace(returncode=0)

    opened = []
    launch_result = launcher.launch(
        configuration,
        runner=run,
        health_check=lambda url, timeout: next(health_results),
        browser_opener=opened.append,
        sleep=lambda _delay: None,
    )

    assert launch_result == "reused"
    assert calls == [["systemctl", "--user", "is-active", "--quiet", "noc-web.service"]]
    assert opened == ["http://127.0.0.1:8123"]


def test_stopped_service_is_started_without_running_a_second_server(tmp_path):
    configuration = _configuration(tmp_path)
    calls = []

    def run(arguments, **kwargs):
        calls.append(arguments)
        return SimpleNamespace(returncode=3 if "is-active" in arguments else 0)

    opened = []
    result = launcher.launch(
        configuration,
        runner=run,
        health_check=lambda _url, _timeout: True,
        browser_opener=opened.append,
    )

    assert result == "started"
    assert calls == [
        ["systemctl", "--user", "is-active", "--quiet", "noc-web.service"],
        ["systemctl", "--user", "start", "noc-web.service"],
    ]
    assert opened == ["http://127.0.0.1:8123"]


def test_health_wait_is_bounded_and_failure_does_not_open_browser(tmp_path):
    configuration = _configuration(tmp_path)
    times = iter((0.0, 1.0, 2.0, 3.0))
    opened = []

    with pytest.raises(launcher.LauncherError) as error:
        launcher.launch(
            configuration,
            runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=0),
            health_check=lambda _url, _timeout: False,
            browser_opener=opened.append,
            monotonic=lambda: next(times),
            sleep=lambda _delay: None,
        )

    assert error.value.code == "health_timeout"
    assert opened == []


@pytest.mark.parametrize(
    ("service_result", "expected_code"),
    ((3, "service_unavailable"),),
)
def test_service_start_failure_is_explicit_and_never_opens_browser(
    tmp_path, service_result, expected_code
):
    configuration = _configuration(tmp_path)
    opened = []

    def run(arguments, **kwargs):
        return SimpleNamespace(
            returncode=3 if "is-active" in arguments else service_result
        )

    with pytest.raises(launcher.LauncherError) as error:
        launcher.launch(
            configuration,
            runner=run,
            browser_opener=opened.append,
        )

    assert error.value.code == expected_code
    assert opened == []


def test_browser_failure_is_explicit_after_health(tmp_path):
    configuration = _configuration(tmp_path)

    def fail_browser(_url):
        raise OSError("sensitive process output")

    with pytest.raises(launcher.LauncherError) as error:
        launcher.launch(
            configuration,
            runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=0),
            health_check=lambda _url, _timeout: True,
            browser_opener=fail_browser,
        )

    assert error.value.code == "browser_unavailable"
    assert "sensitive process output" not in str(error.value)


def test_generated_hidden_launcher_targets_configured_runtime_without_secrets(tmp_path):
    configuration = _configuration(tmp_path)
    runtime_config = tmp_path / "config" / "runtime.json"
    source = launcher.render_hidden_launcher(configuration, runtime_config)

    assert "NOC Workstation" in source
    assert "operator" in source
    assert str(configuration.repository_root) in source
    assert str(configuration.virtual_environment) in source
    assert str(runtime_config) in source
    assert "http://127.0.0.1:8123" in source
    assert "0.0.0.0" not in source
    assert "token" not in source.lower()
    assert "password" not in source.lower()
    assert "shell.Run(command, 0, True)" in source
    assert 'wslPath = shell.ExpandEnvironmentStrings("%SystemRoot%\\System32\\wsl.exe")' in source
    assert 'powerShellPath = shell.ExpandEnvironmentStrings( _' in source
    assert "%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" in source
    assert 'powerShellCommand = "& " & QuotePowerShellLiteral(wslPath)' in source
    assert '" -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command " & _' in source
    assert 'ShowFailure "WINDOWS_LAUNCH_EXECUTION_FAILED"' in source
    assert "WScript.Quit 7" in source
    assert "WSL or the configured distribution is unavailable" not in source


def test_generated_hidden_launcher_preserves_argument_boundaries(tmp_path):
    configuration = _configuration(tmp_path)
    configuration.wsl_distribution = 'NOC "Primary"'
    configuration.linux_user = 'operator "one"'
    configuration.repository_root = tmp_path / 'noc web "primary"'
    configuration.virtual_environment = configuration.repository_root / ".venv"
    configuration.application_url = "http://localhost:8123"
    runtime_config = tmp_path / 'config "one"' / "runtime.json"

    source = launcher.render_hidden_launcher(configuration, runtime_config)

    assert 'distribution = "NOC ""Primary"""' in source
    assert 'linuxUser = "operator ""one"""' in source
    assert 'pythonPath = "' + str(configuration.virtual_environment).replace('"', '""') in source
    assert 'launcherPath = "' + str(configuration.repository_root).replace('"', '""') in source
    assert 'runtimeConfig = "' + str(runtime_config).replace('"', '""') in source
    assert 'QuotePowerShellLiteral(wslPath)' in source
    for argument in (
        "distribution",
        "linuxUser",
        "pythonPath",
        "launcherPath",
        "runtimeConfig",
        "applicationUrl",
        "healthTimeout",
    ):
        assert f"QuotePowerShellLiteral({argument})" in source


def test_non_local_application_target_fails_before_service_or_browser(tmp_path):
    configuration = _configuration(tmp_path)
    configuration.application_url = "https://example.invalid"
    calls = []

    with pytest.raises(launcher.LauncherError) as error:
        launcher.launch(
            configuration,
            runner=lambda args, **kwargs: calls.append(args),
            browser_opener=lambda _url: pytest.fail("browser must not open"),
        )

    assert error.value.code == "runtime_configuration_invalid"
    assert calls == []


def test_probe_arguments_never_use_shell_or_capture_subprocess_output():
    arguments = []

    def run(command, **kwargs):
        arguments.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    launcher.ensure_user_service(run)

    assert all(call[1]["shell"] is False for call in arguments)
    assert all(call[1]["stdout"] is subprocess.DEVNULL for call in arguments)
    assert all(call[1]["stderr"] is subprocess.DEVNULL for call in arguments)
