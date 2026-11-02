from pathlib import Path

import pytest

from scripts.bootstrap.handoff import (
    HandoffError,
    LinuxIdentity,
    create_verified_venv_and_install,
    install_location,
    handoff_feature011,
)
from scripts.bootstrap.windows_preflight import WindowsContext, assess


def _identity(tmp_path: Path) -> LinuxIdentity:
    return LinuxIdentity("Ubuntu", "operator", 1000, tmp_path / "home" / "operator")


def _release(root: Path, *, partial=False) -> Path:
    for name in (
        "requirements.txt",
        "backend/app.py",
        "scripts/install_runtime.py",
        "scripts/windows/install-shortcut.ps1",
        "scripts/windows/launch-hidden.vbs.in",
        "systemd/noc-web.service.in",
    ):
        if partial and name == "backend/app.py":
            continue
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    return root


def test_fresh_handoff_installs_to_the_deterministic_per_user_location(tmp_path):
    source = _release(tmp_path / "verified")
    identity = _identity(tmp_path)
    calls = []

    target = handoff_feature011(
        source, identity, installer=lambda root, identity: calls.append((root, identity))
    )

    assert target == install_location(identity)
    assert (target / "backend/app.py").is_file()
    assert calls == [(target, identity)]


def test_existing_valid_installation_is_reused_and_repeated_runs_are_safe(tmp_path):
    source = _release(tmp_path / "verified")
    identity = _identity(tmp_path)
    target = install_location(identity)
    _release(target)
    (target / "operator-data").write_text("preserved")
    calls = []

    assert handoff_feature011(source, identity, installer=lambda *args: calls.append(args)) == target
    assert handoff_feature011(source, identity, installer=lambda *args: calls.append(args)) == target
    assert (target / "operator-data").read_text() == "preserved"
    assert len(calls) == 2


def test_repeat_handoff_preserves_feature011_and_operator_data_created_on_first_run(tmp_path):
    source = _release(tmp_path / "verified")
    identity = _identity(tmp_path)

    def installer(target, _identity):
        (target / "data").mkdir(exist_ok=True)
        (target / "data" / "noc.json").write_text("operator state")
        (target / "runtime.json").write_text("Feature 011 state")

    target = handoff_feature011(source, identity, installer=installer)
    handoff_feature011(source, identity, installer=lambda *_: None)

    assert (target / "data" / "noc.json").read_text() == "operator state"
    assert (target / "runtime.json").read_text() == "Feature 011 state"


def test_partial_installation_and_feature011_failure_fail_closed_without_data_loss(tmp_path):
    source = _release(tmp_path / "verified")
    identity = _identity(tmp_path)
    target = install_location(identity)
    _release(target, partial=True)
    (target / "operator-data").write_text("preserved")

    with pytest.raises(HandoffError):
        handoff_feature011(source, identity, installer=lambda *_: None)
    assert (target / "operator-data").read_text() == "preserved"

    _release(target)
    with pytest.raises(HandoffError):
        handoff_feature011(source, identity, installer=lambda *_: (_ for _ in ()).throw(RuntimeError()))
    assert (target / "operator-data").read_text() == "preserved"


def test_wrong_distribution_or_linux_identity_is_rejected(tmp_path):
    source = _release(tmp_path / "verified")
    with pytest.raises(HandoffError):
        handoff_feature011(source, LinuxIdentity("Debian", "operator", 1000, Path("/home/operator")), installer=lambda *_: None)
    with pytest.raises(HandoffError):
        handoff_feature011(source, LinuxIdentity("Ubuntu", "root", 0, Path("/root")), installer=lambda *_: None)


def test_feature011_handoff_creates_pinned_venv_and_runs_existing_installer(tmp_path):
    root = _release(tmp_path / "verified")
    identity = _identity(tmp_path)
    calls = []

    class Result:
        returncode = 0

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        if command[1:3] == ["-m", "venv"]:
            python = root / ".venv" / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_text("#!/bin/sh\n")
        return Result()

    create_verified_venv_and_install(root, identity, runner=runner)

    assert calls[0][0][1:3] == ["-m", "venv"]
    assert calls[1][0][1:4] == ["-m", "pip", "install"]
    assert calls[1][0][-1] == str(root / "requirements.txt")
    assert calls[2][0] == [str(root / ".venv" / "bin" / "python"), str(root / "scripts/install_runtime.py")]
    assert calls[2][1]["env"]["PATH"] == "/usr/local/bin:/usr/bin:/bin"
    assert calls[2][1]["env"]["WSL_DISTRO_NAME"] == "Ubuntu"


def test_feature011_handoff_reports_safe_failure_without_raw_subprocess_output(tmp_path):
    root = _release(tmp_path / "verified")

    class Failed:
        returncode = 1

    with pytest.raises(HandoffError, match="runtime"):
        create_verified_venv_and_install(
            root, _identity(tmp_path), runner=lambda *_args, **_kwargs: Failed()
        )


def test_windows_preflight_categorizes_wsl_distribution_and_redirected_desktop():
    context = WindowsContext(
        wsl_available=True, distributions=("Ubuntu",), requested_distribution="Ubuntu",
        windows_user="different-user", profile_path=r"C:\Users\different-user",
        desktop_path=r"C:\Users\different-user\OneDrive\Desktop", linux_user="operator", linux_uid=1000,
        systemd_available=True, permission_available=True, confirmed=True, source_verified=True,
    )
    assert assess(context) == "READY"
    assert assess(WindowsContext(**{**context.__dict__, "wsl_available": False})) == "WSL_SETUP_REQUIRED"
    assert assess(WindowsContext(**{**context.__dict__, "distributions": ("Debian",)})) == "DISTRIBUTION_SETUP_REQUIRED"
    assert assess(WindowsContext(**{**context.__dict__, "requested_distribution": "Debian"})) == "DISTRIBUTION_SETUP_REQUIRED"
    assert assess(WindowsContext(**{**context.__dict__, "systemd_available": False})) == "RUNTIME_SETUP_REQUIRED"
    assert assess(WindowsContext(**{**context.__dict__, "permission_available": False})) == "PERMISSION_REQUIRED"
    assert assess(WindowsContext(**{**context.__dict__, "confirmed": False})) == "CONFIRMATION_DECLINED"
    assert assess(WindowsContext(**{**context.__dict__, "source_verified": False})) == "SOURCE_VERIFICATION_FAILED"
