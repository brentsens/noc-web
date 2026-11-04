"""Regression coverage for the WSL-native SESAMI bootstrap frontend."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.bootstrap.wsl_native import (
    LAUNCHER_NAME,
    WslNativeError,
    assess_prerequisites,
    build_wsl_shortcut_arguments,
    create_windows_shortcut,
    detect_wsl2,
    install_linux_launcher,
    parse_prerequisite_output,
    read_distro_family,
    resolve_operator_identity,
    ubuntu_package_install_command,
)


ROOT = Path(__file__).resolve().parents[1]


def test_detect_wsl2_requires_distro_name_and_wsl2_kernel():
    release = detect_wsl2(
        uname_release="6.6.87.2-microsoft-standard-WSL2",
        environ={"WSL_DISTRO_NAME": "Ubuntu"},
    )
    assert "WSL2" in release

    with pytest.raises(WslNativeError) as missing:
        detect_wsl2(uname_release="6.6.87.2-microsoft-standard-WSL2", environ={})
    assert missing.value.category == "WSL_SETUP_REQUIRED"
    assert missing.value.reason == "not-wsl"

    with pytest.raises(WslNativeError) as wsl1:
        detect_wsl2(
            uname_release="4.4.0-19041-Microsoft",
            environ={"WSL_DISTRO_NAME": "Ubuntu"},
        )
    assert wsl1.value.reason == "wsl1-unsupported"


def test_read_distro_family_from_os_release(tmp_path):
    path = tmp_path / "os-release"
    path.write_text('NAME="Ubuntu"\nID=ubuntu\nVERSION_ID="26.04"\n', encoding="utf-8")
    assert read_distro_family(path) == "ubuntu"

    path.write_text("ID=fedora\n", encoding="utf-8")
    assert read_distro_family(path) == "fedora"


def test_ubuntu_remediation_command_is_allowlisted_only():
    command = ubuntu_package_install_command(("python3", "ca-certificates"))
    assert command == (
        "sudo apt-get update && sudo apt-get install --yes python3 ca-certificates"
    )
    with pytest.raises(WslNativeError) as error:
        ubuntu_package_install_command(("python3", "curl"))
    assert error.value.reason == "packages-unapproved"


def test_non_ubuntu_capability_gap_is_reported_without_apt_guidance():
    snapshot = parse_prerequisite_output(
        [
            "DISTRO_FAMILY=fedora",
            "GH_ATTESTATION=missing",
            "GH_ATTESTATION_EXIT=127",
            "MISSING_CAPABILITIES=python3 gh-attestation",
        ]
    )
    assert snapshot.distro_family == "fedora"
    assert snapshot.ready is False
    assert "python3" in snapshot.capabilities
    # Apt remediation remains available as a helper, but run_wsl_native_bootstrap
    # only invokes it when distro_family == ubuntu.


def test_authoritative_passwd_home_and_stale_inherited_home(tmp_path, monkeypatch):
    real_home = tmp_path / "home" / "brent"
    real_home.mkdir(parents=True)
    monkeypatch.setenv("HOME", "/home/brentn")

    class FakeRun:
        def __init__(self, stdout, returncode=0):
            self.stdout = stdout
            self.returncode = returncode

    def fake_run(cmd, *args, **kwargs):
        if cmd == ["id", "-un"]:
            return FakeRun("brent\n")
        if cmd == ["id", "-u"]:
            return FakeRun("1000\n")
        if cmd in (["getent", "passwd", "brent"], ["getent", "passwd", "1000"]):
            return FakeRun(f"brent:x:1000:1000::{real_home}:/bin/bash\n")
        raise AssertionError(cmd)

    user, uid, home = resolve_operator_identity(distribution="Ubuntu", runner=fake_run)
    assert user == "brent"
    assert uid == 1000
    assert home == real_home


def test_root_operator_is_rejected(tmp_path):
    class FakeRun:
        def __init__(self, stdout, returncode=0):
            self.stdout = stdout
            self.returncode = returncode

    def fake_run(cmd, *args, **kwargs):
        if cmd == ["id", "-un"]:
            return FakeRun("root\n")
        if cmd == ["id", "-u"]:
            return FakeRun("0\n")
        if cmd in (["getent", "passwd", "root"], ["getent", "passwd", "0"]):
            return FakeRun("root:x:0:0::/root:/bin/bash\n")
        raise AssertionError(cmd)

    with pytest.raises(WslNativeError) as error:
        resolve_operator_identity(distribution="Ubuntu", runner=fake_run)
    assert error.value.category == "DISTRIBUTION_SETUP_REQUIRED"


def test_parse_prerequisite_ready_and_gh_states():
    ready = parse_prerequisite_output(
        [
            "DISTRO_FAMILY=ubuntu",
            "GH_ATTESTATION=ready",
            "GH_ATTESTATION_EXIT=0",
            "PREREQUISITES_READY",
        ]
    )
    assert ready.ready is True
    assert ready.gh_attestation == "ready"

    missing_gh = parse_prerequisite_output(
        [
            "DISTRO_FAMILY=ubuntu",
            "GH_ATTESTATION=missing",
            "GH_ATTESTATION_EXIT=127",
            "MISSING_CAPABILITIES=gh-attestation",
        ]
    )
    assert missing_gh.ready is False
    assert missing_gh.gh_attestation == "missing"


def test_install_linux_launcher_points_at_release_venv(tmp_path):
    home = tmp_path / "home" / "operator"
    release = home / ".local" / "share" / "sesami-noc-operations" / "noc-web"
    launch_module = release / "scripts" / "windows" / "sesami_noc_launch.py"
    launch_module.parent.mkdir(parents=True)
    launch_module.write_text("# fixture\n", encoding="utf-8")
    (release / ".venv" / "bin").mkdir(parents=True)
    (release / ".venv" / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")

    path = install_linux_launcher(home=home, release_root=release)
    assert path == home / ".local" / "bin" / LAUNCHER_NAME
    assert path.stat().st_mode & stat.S_IXUSR
    text = path.read_text(encoding="utf-8")
    assert "scripts.windows.sesami_noc_launch" in text
    assert str(release) in text
    assert "credential" not in text
    assert "token" not in text


def test_shortcut_arguments_target_distribution_and_linux_launcher():
    arguments = build_wsl_shortcut_arguments(
        distribution="Ubuntu",
        linux_launcher="/home/operator/.local/bin/sesami-noc-launch",
    )
    assert arguments == (
        "--distribution Ubuntu --exec /home/operator/.local/bin/sesami-noc-launch"
    )
    with pytest.raises(WslNativeError):
        build_wsl_shortcut_arguments(
            distribution="Ubuntu; rm -rf /",
            linux_launcher="/home/operator/.local/bin/sesami-noc-launch",
        )
    with pytest.raises(WslNativeError):
        build_wsl_shortcut_arguments(
            distribution="Ubuntu",
            linux_launcher="/tmp/../home/operator/.local/bin/sesami-noc-launch",
        )


def test_wsl_native_entry_and_shortcut_scripts_are_present():
    install = (ROOT / "scripts" / "install-sesami.sh").read_text(encoding="utf-8")
    verify = (ROOT / "scripts" / "bootstrap" / "verify_bootstrap_bundle.sh").read_text(
        encoding="utf-8"
    )
    shortcut = (ROOT / "scripts" / "bootstrap" / "install_wsl_shortcut.ps1").read_text(
        encoding="utf-8"
    )
    launch = (ROOT / "scripts" / "windows" / "sesami_noc_launch.py").read_text(
        encoding="utf-8"
    )
    native = (ROOT / "scripts" / "bootstrap" / "wsl_native.py").read_text(encoding="utf-8")

    assert "curl | bash" not in install
    assert "python3 -m scripts.bootstrap.wsl_native" in install
    assert "id -u" in install
    assert "ab55b3d776d760db3ea758d80b9fc7218ef3bd33a0723589d73b7f0a2171370f" in verify
    assert "noc-web-v1.0.3.tar.gz" in verify
    assert "--signer-workflow" in verify
    assert "System32\\wsl.exe" in shortcut
    assert "Sysnative\\wsl.exe" in shortcut
    assert "SESAMI NOC Operations.lnk" in shortcut
    assert "SHORTCUT_TARGET=wsl.exe" in shortcut
    assert "Get-Command wsl" not in shortcut
    assert "launch(" in launch
    assert "NOC_WEB_SHORTCUT_MODE" in native
    assert "noc-inv-contract=1" in native
    assert "v1.0.3" in native
    assert "v1.0.1" not in native or "noc-tools" in native.lower()


def test_install_runtime_skips_vbs_shortcut_for_wsl_native_mode():
    source = (ROOT / "scripts" / "install_runtime.py").read_text(encoding="utf-8")
    assert 'shortcut_mode == "wsl-native"' in source
    assert 'environment.get("NOC_WEB_SHORTCUT_MODE", "hidden-vbs")' in source


def test_handoff_forwards_wsl_native_shortcut_mode():
    source = (ROOT / "scripts" / "bootstrap" / "handoff.py").read_text(encoding="utf-8")
    assert 'NOC_WEB_SHORTCUT_MODE' in source
    assert "wsl-native" in source


def test_assess_prerequisites_invokes_existing_checker(tmp_path, monkeypatch):
    package_root = ROOT
    os_release = tmp_path / "os-release"
    os_release.write_text("ID=ubuntu\n", encoding="utf-8")

    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(
            returncode=0,
            stdout="\n".join(
                [
                    "DISTRO_FAMILY=ubuntu",
                    "GH_ATTESTATION=ready",
                    "GH_ATTESTATION_EXIT=0",
                    "PREREQUISITES_READY",
                ]
            ),
        )

    snapshot = assess_prerequisites(
        package_root, runner=fake_run, os_release=os_release
    )
    assert snapshot.ready is True
    assert calls
    assert calls[0][0] == "/bin/sh"
    assert calls[0][1].endswith("check_runtime_prerequisites.sh")


def test_no_bundled_credentials_in_wsl_native_artifacts():
    for relative in (
        "scripts/install-sesami.sh",
        "scripts/bootstrap/wsl_native.py",
        "scripts/bootstrap/install_wsl_shortcut.ps1",
        "scripts/bootstrap/verify_bootstrap_bundle.sh",
        "scripts/windows/sesami_noc_launch.py",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8").lower()
        for banned in ("password=", "api_key", "authorization:", "cookie:", "begin rsa"):
            assert banned not in text


def test_daily_launch_does_not_require_custom_windows_exe():
    shortcut = (ROOT / "scripts" / "bootstrap" / "install_wsl_shortcut.ps1").read_text(
        encoding="utf-8"
    )
    assert "TargetPath = $wslPath" in shortcut
    assert "SESAMI-NOC-Operations-Setup.exe" not in shortcut
    assert "wscript.exe" not in shortcut

def test_windows_shortcut_uses_explicit_powershell_with_controlled_path(tmp_path):
    package_root = tmp_path / "package"
    shortcut_script = (
        package_root / "scripts" / "bootstrap" / "install_wsl_shortcut.ps1"
    )
    shortcut_script.parent.mkdir(parents=True)
    shortcut_script.write_text("# fixture\n", encoding="utf-8")

    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))

        if command[0] == "wslpath":
            return SimpleNamespace(
                returncode=0,
                stdout="C:\\bootstrap\\install_wsl_shortcut.ps1\n",
            )

        assert command[0] == (
            "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
        )
        assert kwargs["env"]["PATH"] == "/usr/local/bin:/usr/bin:/bin"

        return SimpleNamespace(
            returncode=0,
            stdout="SHORTCUT_INSTALLED\nSHORTCUT_TARGET=wsl.exe\n",
        )

    create_windows_shortcut(
        package_root=package_root,
        distribution="Ubuntu",
        linux_launcher=Path("/home/operator/.local/bin/sesami-noc-launch"),
        runner=fake_run,
    )

    powershell_calls = [
        command for command, _ in calls
        if command[0].endswith("/powershell.exe")
    ]
    assert len(powershell_calls) == 1
