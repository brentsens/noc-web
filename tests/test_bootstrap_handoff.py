from pathlib import Path

import pytest

from scripts.bootstrap.handoff import (
    HandoffError,
    LinuxIdentity,
    create_verified_venv_and_install,
    discover_linux_identity,
    install_location,
    handoff_feature011,
)
from scripts.bootstrap.windows_preflight import (
    WSL_RESOLUTION_MISSING,
    WSL_RESOLUTION_NATIVE_SYSTEM32,
    WSL_RESOLUTION_SYSNATIVE,
    WindowsContext,
    assess,
    parse_and_validate_account,
    resolve_wsl_executable,
)


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


def test_windows_preflight_categorizes_wsl2_capability_and_redirected_desktop():
    context = WindowsContext(
        wsl_available=True, distributions=("Ubuntu",), requested_distribution="Ubuntu",
        windows_user="different-user", profile_path=r"C:\Users\different-user",
        desktop_path=r"C:\Users\different-user\OneDrive\Desktop", linux_user="operator", linux_uid=1000,
        systemd_available=True, permission_available=True, confirmed=True, source_verified=True,
    )
    assert assess(context) == "READY"
    assert assess(WindowsContext(**{**context.__dict__, "wsl_available": False})) == "WSL_SETUP_REQUIRED"
    assert assess(WindowsContext(**{**context.__dict__, "distributions": ("Debian",)})) == "DISTRIBUTION_SETUP_REQUIRED"
    assert assess(WindowsContext(**{**context.__dict__, "requested_distribution": "Debian", "distributions": ("Debian",)})) == "READY"
    assert assess(WindowsContext(**{**context.__dict__, "wsl2_available": False})) == "DISTRIBUTION_SETUP_REQUIRED"
    assert assess(WindowsContext(**{**context.__dict__, "systemd_available": False})) == "RUNTIME_SETUP_REQUIRED"
    assert assess(WindowsContext(**{**context.__dict__, "permission_available": False})) == "PERMISSION_REQUIRED"
    assert assess(WindowsContext(**{**context.__dict__, "confirmed": False})) == "CONFIRMATION_DECLINED"
    assert assess(WindowsContext(**{**context.__dict__, "source_verified": False})) == "SOURCE_VERIFICATION_FAILED"


def test_wsl_executable_64bit_process_selects_system32():
    system_root = r"C:\Windows"
    native = r"C:\Windows\System32\wsl.exe"
    result = resolve_wsl_executable(
        system_root=system_root,
        is_64bit_os=True,
        is_64bit_process=True,
        path_exists={native: True, r"C:\Windows\Sysnative\wsl.exe": True},
        path_entries=(r"C:\evil",),
    )
    assert result.path == native
    assert result.resolution == WSL_RESOLUTION_NATIVE_SYSTEM32
    assert result.category is None


def test_wsl_executable_32bit_process_on_64bit_os_selects_sysnative():
    system_root = r"C:\Windows"
    sysnative = r"C:\Windows\Sysnative\wsl.exe"
    redirected_system32 = r"C:\Windows\System32\wsl.exe"
    result = resolve_wsl_executable(
        system_root=system_root,
        is_64bit_os=True,
        is_64bit_process=False,
        # Wow64: System32 view is redirected; real wsl.exe is only via Sysnative.
        path_exists={sysnative: True, redirected_system32: False},
        path_entries=(r"C:\Users\operator\evil-bin",),
    )
    assert result.path == sysnative
    assert result.resolution == WSL_RESOLUTION_SYSNATIVE
    assert result.category is None


def test_wsl_executable_genuinely_missing_returns_wsl_setup_required():
    result = resolve_wsl_executable(
        system_root=r"C:\Windows",
        is_64bit_os=True,
        is_64bit_process=True,
        path_exists={
            r"C:\Windows\System32\wsl.exe": False,
            r"C:\Windows\Sysnative\wsl.exe": False,
        },
        path_entries=(r"C:\fake\with\wsl.exe",),
    )
    assert result.path is None
    assert result.resolution == WSL_RESOLUTION_MISSING
    assert result.category == "WSL_SETUP_REQUIRED"
    assert result.reason == "wsl-not-found"
    assert result.stage == "platform-check"


def test_wsl_executable_ignores_malicious_path_entries():
    planted = r"C:\Users\attacker\bin\wsl.exe"
    result = resolve_wsl_executable(
        system_root=r"C:\Windows",
        is_64bit_os=True,
        is_64bit_process=True,
        path_exists={planted: True, r"C:\Windows\System32\wsl.exe": False},
        path_entries=(r"C:\Users\attacker\bin", planted),
    )
    assert result.path is None
    assert result.resolution == WSL_RESOLUTION_MISSING
    assert result.category == "WSL_SETUP_REQUIRED"
    assert result.reason == "wsl-not-found"


def test_wsl_executable_t050_inno_setup_32bit_context_with_existing_ubuntu():
    """T050: WSL2 Ubuntu is present, but bootstrap runs under Inno's 32-bit process.

    Wow64 redirection makes System32\\wsl.exe appear missing while Sysnative works.
    Discovery must select Sysnative rather than emitting a false wsl-not-found.
    """
    system_root = r"C:\WINDOWS"
    sysnative = r"C:\WINDOWS\Sysnative\wsl.exe"
    result = resolve_wsl_executable(
        system_root=system_root,
        is_64bit_os=True,
        is_64bit_process=False,
        path_exists={
            sysnative: True,
            # Redirected System32 check fails even though real WSL exists.
            r"C:\WINDOWS\System32\wsl.exe": False,
            r"C:\WINDOWS\SysWOW64\wsl.exe": False,
            r"C:\evil\wsl.exe": True,
        },
        path_entries=(r"C:\evil",),
    )
    assert result.path == sysnative
    assert result.resolution == WSL_RESOLUTION_SYSNATIVE
    assert result.category is None
    assert result.reason is None


def test_wsl_executable_32bit_windows_uses_native_system32():
    native = r"C:\Windows\System32\wsl.exe"
    result = resolve_wsl_executable(
        system_root=r"C:\Windows",
        is_64bit_os=False,
        is_64bit_process=False,
        path_exists={native: True, r"C:\Windows\Sysnative\wsl.exe": False},
    )
    assert result.path == native
    assert result.resolution == WSL_RESOLUTION_NATIVE_SYSTEM32


def test_wsl_executable_wow64_does_not_trust_redirected_system32():
    redirected = r"C:\Windows\System32\wsl.exe"
    result = resolve_wsl_executable(
        system_root=r"C:\Windows",
        is_64bit_os=True,
        is_64bit_process=False,
        # A planted SysWOW64 binary must not be accepted via redirected System32.
        path_exists={redirected: True, r"C:\Windows\Sysnative\wsl.exe": False},
    )
    assert result.path is None
    assert result.resolution == WSL_RESOLUTION_MISSING
    assert result.category == "WSL_SETUP_REQUIRED"
    assert result.reason == "wsl-not-found"


def test_preflight_accepts_authoritative_passwd_home_with_inconsistent_inherited_home():
    """Reproduces exact clean-workstation condition:
    username = brent
    uid = 1000
    passwd home = /home/brent
    inherited HOME = /home/brentn
    Expected behavior: accepted using /home/brent and proceeds to runtime prerequisite
    assessment rather than returning DISTRIBUTION_SETUP_REQUIRED.
    """
    context = WindowsContext(
        wsl_available=True,
        distributions=("Ubuntu",),
        requested_distribution="Ubuntu",
        windows_user="brent",
        profile_path=r"C:\Users\brent",
        desktop_path=r"C:\Users\brent\Desktop",
        linux_user="brent",
        linux_uid=1000,
        systemd_available=True,
        permission_available=True,
        confirmed=True,
        source_verified=True,
        passwd_home="/home/brent",
        inherited_home="/home/brentn",
        home_exists=True,
        account_valid=True,
        record_valid=True,
    )
    assert assess(context) == "READY"

    # Fails safely with DISTRIBUTION_SETUP_REQUIRED when account record is invalid, missing, or home unusable
    assert assess(WindowsContext(**{**context.__dict__, "account_valid": False})) == "DISTRIBUTION_SETUP_REQUIRED"
    assert assess(WindowsContext(**{**context.__dict__, "record_valid": False})) == "DISTRIBUTION_SETUP_REQUIRED"
    assert assess(WindowsContext(**{**context.__dict__, "home_exists": False})) == "DISTRIBUTION_SETUP_REQUIRED"
    assert assess(WindowsContext(**{**context.__dict__, "passwd_home": "/root"})) == "DISTRIBUTION_SETUP_REQUIRED"
    assert assess(WindowsContext(**{**context.__dict__, "passwd_home": ""})) == "DISTRIBUTION_SETUP_REQUIRED"
    assert assess(WindowsContext(**{**context.__dict__, "passwd_home": "relative/path"})) == "DISTRIBUTION_SETUP_REQUIRED"
    assert assess(WindowsContext(**{**context.__dict__, "passwd_home": "/home/brent/../other"})) == "DISTRIBUTION_SETUP_REQUIRED"


def test_parse_and_validate_account_tolerates_inconsistent_inherited_home():
    home = parse_and_validate_account(
        username="brent",
        uid=1000,
        passwd_record="brent:x:1000:1000::/home/brent:/bin/bash",
        inherited_home="/home/brentn",
        home_exists=True,
    )
    assert home == "/home/brent"

    # Does not assume /home/<username>
    custom_home = parse_and_validate_account(
        username="custom_operator",
        uid=1005,
        passwd_record="custom_operator:x:1005:1005::/var/data/custom_operator:/bin/bash",
        inherited_home="/tmp/bogus",
        home_exists=True,
    )
    assert custom_home == "/var/data/custom_operator"

    # Mismatched UID (ambiguous relationship) fails safely
    with pytest.raises(ValueError, match="ambiguous-account-relationship"):
        parse_and_validate_account(
            username="brent",
            uid=1000,
            passwd_record="brent:x:1001:1000::/home/brent:/bin/bash",
            home_exists=True,
        )

    # Malformed record fails safely
    with pytest.raises(ValueError, match="malformed-passwd-record"):
        parse_and_validate_account(
            username="brent",
            uid=1000,
            passwd_record="brent:x:1000",
            home_exists=True,
        )

    # Unusable home fails safely
    with pytest.raises(ValueError, match="home-directory-unusable"):
        parse_and_validate_account(
            username="brent",
            uid=1000,
            passwd_record="brent:x:1000:1000::/home/brent:/bin/bash",
            home_exists=False,
        )


def test_discover_linux_identity_reproduces_clean_workstation_evidence(monkeypatch, tmp_path):
    real_home = tmp_path / "home" / "brent"
    real_home.mkdir(parents=True)
    monkeypatch.setenv("HOME", "/home/brentn")

    class FakeRun:
        def __init__(self, stdout, returncode=0):
            self.stdout = stdout
            self.returncode = returncode

    def fake_subprocess_run(cmd, *args, **kwargs):
        if cmd == ["id", "-un"]:
            return FakeRun("brent\n")
        if cmd == ["id", "-u"]:
            return FakeRun("1000\n")
        if cmd == ["getent", "passwd", "brent"] or cmd == ["getent", "passwd", "1000"]:
            return FakeRun(f"brent:x:1000:1000::{real_home}:/bin/bash\n")
        raise AssertionError(f"unexpected command: {cmd}")

    identity = discover_linux_identity("Ubuntu", runner=fake_subprocess_run)
    assert identity.user == "brent"
    assert identity.uid == 1000
    assert identity.home == real_home
    assert identity.distribution == "Ubuntu"
    assert install_location(identity) == real_home / ".local/share/sesami-noc-operations/noc-web"
