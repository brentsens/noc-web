import json
import subprocess

import pytest

from backend.services import dependency_readiness


def _atlas_status(*, session_usable=True, signed_in=True, site_usable=True):
    return json.dumps(
        {
            "session_usable": session_usable,
            "signed_in": signed_in,
            "sites": [{"alias": "sesamiio", "usable": site_usable}],
            "workspaces": [],
        }
    )


def test_external_capabilities_are_reported_independently_and_redacted(
    tmp_path, monkeypatch
):
    noc_bin = tmp_path / "bin"
    noc_bin.mkdir()
    secret = "sensitive-output-fixture"
    commands = {
        "atlas",
        "copilot",
        "m365",
        "tix",
        "noc-start",
        "noc-status",
        "noc-inv",
        "noc-handover",
    }
    for command in commands:
        executable = noc_bin / command
        executable.touch()
        executable.chmod(0o700)

    calls = []

    def run(arguments, **kwargs):
        calls.append((arguments, kwargs))
        class Result:
            returncode = 0
            stdout = (
                "noc-inv-contract=1"
                if arguments[0].endswith("/noc-inv")
                else _atlas_status()
                if arguments[0].endswith("/atlas")
                else secret
            )
            stderr = secret

        return Result()

    monkeypatch.setattr(dependency_readiness.subprocess, "run", run)
    results = dependency_readiness.assess_external_capabilities(
        noc_bin,
        timeout_seconds=2,
    )
    by_id = {result["id"]: result for result in results}

    assert set(by_id) == {
        "external.aiProvider",
        "external.atlas",
        "external.copilot",
        "external.datadog",
        "external.microsoft365",
        "external.nocTools",
    }
    assert by_id["external.atlas"]["status"] == "ready"
    assert by_id["external.atlas"]["installationStatus"] == "ready"
    assert by_id["external.nocTools"]["status"] == "ready"
    assert by_id["external.nocTools"]["installationStatus"] == "ready"
    assert by_id["external.copilot"]["status"] == "ready"
    assert by_id["external.datadog"]["status"] == "setup_required"
    assert by_id["external.datadog"]["providerReadiness"] == "notConfigured"
    assert by_id["external.microsoft365"]["status"] == "ready"
    assert secret not in str(results)
    assert all(call[1]["shell"] is False for call in calls)
    atlas_call = next(call for call in calls if call[0][0].endswith("/atlas"))
    assert atlas_call[0][1:] == ["auth", "status", "--json"]
    assert all(
        call[1]["stdout"] is (
            subprocess.PIPE
            if (
                call[0][0].endswith(("/noc-inv", "/atlas"))
            )
            else subprocess.DEVNULL
        )
        for call in calls
    )
    assert all(call[1]["stderr"] is subprocess.DEVNULL for call in calls)
    assert all(call[1]["timeout"] == 2 for call in calls)
    assert all(call[0][1:] != ["mcp", "list"] for call in calls)


def test_optional_capabilities_report_ready_independently(tmp_path, monkeypatch):
    monkeypatch.delenv("NOC_WEB_AI_PROVIDER", raising=False)
    monkeypatch.delenv("NOC_WEB_DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("NOC_WEB_DATADOG_ACCESS_TOKEN", "test-sentinel-datadog-token")
    noc_bin = tmp_path / "bin"
    noc_bin.mkdir()
    for command in (
        "atlas", "copilot", "m365", "tix", "noc-start", "noc-status",
        "noc-inv", "noc-handover",
    ):
        executable = noc_bin / command
        executable.touch()
        executable.chmod(0o700)

    def run(arguments, **_kwargs):
        class Result:
            returncode = 0
            stdout = (
                _atlas_status() if arguments[0].endswith("/atlas")
                else "noc-inv-contract=1" if arguments[0].endswith("/noc-inv")
                else ""
            )

        return Result()

    monkeypatch.setattr(dependency_readiness.subprocess, "run", run)

    results = dependency_readiness.assess_external_capabilities(noc_bin, timeout_seconds=1)

    assert {item["id"]: item["status"] for item in results} == {
        "external.aiProvider": "notConfigured",
        "external.atlas": "ready",
        "external.copilot": "ready",
        "external.datadog": "ready",
        "external.microsoft365": "ready",
        "external.nocTools": "ready",
    }


def test_optional_capabilities_classify_auth_setup_and_command_failure(
    tmp_path, monkeypatch
):
    noc_bin = tmp_path / "bin"
    noc_bin.mkdir()
    for command in (
        "atlas", "copilot", "m365", "tix", "noc-start", "noc-status",
        "noc-inv", "noc-handover",
    ):
        executable = noc_bin / command
        executable.touch()
        executable.chmod(0o700)

    def run(arguments, **_kwargs):
        class Result:
            returncode = 1 if (
                (
                    arguments[1:] in (["auth", "status"], ["status"])
                    and not arguments[0].endswith("/atlas")
                )
                or arguments[0].endswith("/tix")
            ) else 0
            stdout = _atlas_status() if arguments[0].endswith("/atlas") else ""

        return Result()

    monkeypatch.setattr(dependency_readiness.subprocess, "run", run)

    results = dependency_readiness.assess_external_capabilities(noc_bin, timeout_seconds=1)
    by_id = {item["id"]: item["status"] for item in results}

    assert by_id["external.atlas"] == "ready"
    assert by_id["external.copilot"] == "setup_required"
    assert by_id["external.datadog"] == "setup_required"
    assert by_id["external.microsoft365"] == "setup_required"
    assert by_id["external.nocTools"] == "unavailable"


def test_installed_but_unauthenticated_tools_have_safe_installation_status(
    tmp_path, monkeypatch
):
    noc_bin = tmp_path / "bin"
    noc_bin.mkdir()
    for command in ("atlas", "copilot", "m365"):
        executable = noc_bin / command
        executable.touch()
        executable.chmod(0o700)

    def run(arguments, **_kwargs):
        class Result:
            returncode = 1 if arguments[1:] in (
                ["auth", "status"], ["status"]
            ) else 0
            stdout = _atlas_status(session_usable=False, signed_in=False)

        return Result()

    monkeypatch.setattr(dependency_readiness.subprocess, "run", run)
    by_id = {
        item["id"]: item
        for item in dependency_readiness.assess_external_capabilities(
            noc_bin, timeout_seconds=1
        )
    }

    assert by_id["external.atlas"]["installationStatus"] == "installed"
    assert by_id["external.copilot"]["installationStatus"] == "installed"
    assert by_id["external.microsoft365"]["installationStatus"] == "installed"


def test_missing_and_failed_capability_probes_are_explicit(tmp_path, monkeypatch):
    noc_bin = tmp_path / "bin"
    noc_bin.mkdir()
    atlas = noc_bin / "atlas"
    atlas.touch()
    atlas.chmod(0o700)

    class Result:
        returncode = 7
        stdout = "not-for-response"
        stderr = "not-for-response"

    monkeypatch.setattr(
        dependency_readiness.subprocess,
        "run",
        lambda *args, **kwargs: Result(),
    )
    results = dependency_readiness.assess_external_capabilities(
        noc_bin,
        timeout_seconds=1,
    )
    by_id = {result["id"]: result for result in results}

    assert by_id["external.atlas"]["status"] == "unavailable"
    assert by_id["external.nocTools"]["status"] == "setup_required"
    assert "not-for-response" not in str(results)


def test_probe_timeout_is_unavailable_without_exposing_exception(monkeypatch, tmp_path):
    noc_bin = tmp_path / "bin"
    noc_bin.mkdir()
    atlas = noc_bin / "atlas"
    atlas.touch()
    atlas.chmod(0o700)

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"], output="token")

    monkeypatch.setattr(dependency_readiness.subprocess, "run", timeout)
    results = dependency_readiness.assess_external_capabilities(
        noc_bin,
        timeout_seconds=1,
    )

    atlas = next(item for item in results if item["id"] == "external.atlas")
    assert atlas["status"] == "unavailable"
    assert "token" not in str(results)


def test_atlas_is_discovered_only_from_trusted_linuxbrew_path(monkeypatch, tmp_path):
    trusted_linuxbrew_bin = tmp_path / "trusted-linuxbrew" / "bin"
    trusted_linuxbrew_bin.mkdir(parents=True)
    atlas = trusted_linuxbrew_bin / "atlas"
    atlas.write_text(
        "#!/bin/sh\n"
        'printf \'%s\\n\' \'{"session_usable":true,"signed_in":true,"sites":[{"alias":"sesamiio","usable":true}],"workspaces":[]}\'\n',
        encoding="utf-8",
    )
    atlas.chmod(0o700)

    unallowlisted_bin = tmp_path / "interactive-bin"
    unallowlisted_bin.mkdir()
    unallowlisted_atlas = unallowlisted_bin / "atlas"
    unallowlisted_atlas.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    unallowlisted_atlas.chmod(0o700)

    monkeypatch.setattr(
        dependency_readiness,
        "TRUSTED_LINUXBREW_BIN",
        trusted_linuxbrew_bin,
    )
    monkeypatch.setenv("PATH", str(unallowlisted_bin))

    results = dependency_readiness.assess_external_capabilities(
        tmp_path / "noc-bin",
        timeout_seconds=1,
    )

    atlas_result = next(item for item in results if item["id"] == "external.atlas")
    assert atlas_result["status"] == "ready"


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        (_atlas_status(session_usable=False, signed_in=False), "setup_required"),
        (_atlas_status(site_usable=False), "setup_required"),
    ],
)
def test_atlas_auth_status_reports_unusable_authentication_or_site(
    monkeypatch, tmp_path, payload, expected_status
):
    noc_bin = tmp_path / "bin"
    noc_bin.mkdir()
    atlas = noc_bin / "atlas"
    atlas.touch()
    atlas.chmod(0o700)

    class Result:
        returncode = 0
        stdout = payload

    monkeypatch.setattr(
        dependency_readiness.subprocess,
        "run",
        lambda *args, **kwargs: Result(),
    )

    results = dependency_readiness.assess_external_capabilities(
        noc_bin,
        timeout_seconds=1,
    )

    atlas_result = next(item for item in results if item["id"] == "external.atlas")
    assert atlas_result["status"] == expected_status


def test_atlas_auth_status_malformed_output_is_unavailable_and_redacted(
    monkeypatch, tmp_path
):
    noc_bin = tmp_path / "bin"
    noc_bin.mkdir()
    atlas = noc_bin / "atlas"
    atlas.touch()
    atlas.chmod(0o700)
    secret = "sensitive-malformed-atlas-output"

    class Result:
        returncode = 0
        stdout = secret

    monkeypatch.setattr(
        dependency_readiness.subprocess,
        "run",
        lambda *args, **kwargs: Result(),
    )

    results = dependency_readiness.assess_external_capabilities(
        noc_bin,
        timeout_seconds=1,
    )

    atlas_result = next(item for item in results if item["id"] == "external.atlas")
    assert atlas_result["status"] == "unavailable"
    assert secret not in str(results)


def test_atlas_auth_status_timeout_is_unavailable_and_redacted(monkeypatch, tmp_path):
    noc_bin = tmp_path / "bin"
    noc_bin.mkdir()
    atlas = noc_bin / "atlas"
    atlas.touch()
    atlas.chmod(0o700)
    secret = "sensitive-atlas-timeout-output"

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"], output=secret)

    monkeypatch.setattr(dependency_readiness.subprocess, "run", timeout)

    results = dependency_readiness.assess_external_capabilities(
        noc_bin,
        timeout_seconds=1,
    )

    atlas_result = next(item for item in results if item["id"] == "external.atlas")
    assert atlas_result["status"] == "unavailable"
    assert secret not in str(results)


def test_missing_atlas_reports_setup_required(monkeypatch, tmp_path):
    monkeypatch.setattr(dependency_readiness.shutil, "which", lambda *_args, **_kwargs: None)

    results = dependency_readiness.assess_external_capabilities(
        tmp_path / "bin",
        timeout_seconds=1,
    )

    atlas_result = next(item for item in results if item["id"] == "external.atlas")
    assert atlas_result["status"] == "setup_required"


def test_ai_provider_capability_is_static_optional_and_non_secret(
    tmp_path,
    monkeypatch,
):
    sentinel = "test-sentinel-deepseek-key"
    noc_bin = tmp_path / "bin"
    noc_bin.mkdir()
    monkeypatch.setenv("NOC_WEB_AI_PROVIDER", "deepseek-api")
    monkeypatch.setenv("NOC_WEB_DEEPSEEK_API_KEY", sentinel)
    monkeypatch.setenv("NOC_WEB_DEEPSEEK_MODEL", "deepseek-flash")
    monkeypatch.setattr(
        dependency_readiness,
        "_executable",
        lambda *args, **kwargs: None,
    )

    results = dependency_readiness.assess_external_capabilities(
        noc_bin,
        timeout_seconds=1,
    )
    provider = next(
        item for item in results if item["id"] == "external.aiProvider"
    )

    assert provider["required"] is False
    assert provider["status"] == "ready"
    assert provider["providerReadiness"] == "ready"
    assert provider["configuredProvider"] == "deepseek-api"
    assert provider["model"] == "deepseek-flash"
    assert "credential" not in provider
    assert sentinel not in str(results)
