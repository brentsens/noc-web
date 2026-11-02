import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "bootstrap" / "check_runtime_prerequisites.sh"
INSTALLER = ROOT / "scripts" / "windows" / "bootstrap-install.ps1"

_SUPPORTED_PYTHON = """#!/bin/sh
case "$*" in
  *sys.version_info*) exit 0 ;;
  *'-m venv'*) /bin/mkdir -p "$3/bin"; /bin/cp "$0" "$3/bin/python"; /bin/chmod +x "$3/bin/python"; exit 0 ;;
  *) exit 0 ;;
esac
"""


def _executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


def _run(
    directory: Path,
    *,
    python: str | None = _SUPPORTED_PYTHON,
    gh: str | None = "#!/bin/sh\nexit 0\n",
    os_release: str = "ID=ubuntu\n",
    include_noc_tools: bool = False,
) -> list[str]:
    directory.mkdir(parents=True, exist_ok=True)
    release = directory / "os-release"
    release.write_text(os_release)
    if python is not None:
        _executable(directory / "python3", python)
    if gh is not None:
        _executable(directory / "gh", gh)
    if include_noc_tools:
        _executable(directory / "bash", "#!/bin/sh\nexit 0\n")
        _executable(directory / "timeout", "#!/bin/sh\nexit 0\n")
        _executable(directory / "mktemp", "#!/bin/sh\nexit 0\n")
    result = subprocess.run(
        ["/bin/sh", str(SCRIPT), *(["--include-noc-tools"] if include_noc_tools else [])],
        text=True,
        capture_output=True,
        check=False,
        env={
            "PATH": str(directory),
            "HOME": str(directory),
            "NOC_BOOTSTRAP_OS_RELEASE": str(release),
        },
    )
    assert result.returncode == 0
    return result.stdout.splitlines()


def test_ubuntu_with_all_core_capabilities_is_ready(tmp_path):
    if not Path("/etc/ssl/certs/ca-certificates.crt").is_file():
        return

    assert _run(tmp_path) == [
        "DISTRO_FAMILY=ubuntu",
        "GH_ATTESTATION=ready",
        "PREREQUISITES_READY",
    ]


def test_python_missing_is_an_ubuntu_installable_capability(tmp_path):
    lines = _run(tmp_path, python=None)

    assert lines[:2] == ["DISTRO_FAMILY=ubuntu", "GH_ATTESTATION=ready"]
    assert "MISSING_UBUNTU_PACKAGES=python3" in lines
    assert any(line.startswith("MISSING_CAPABILITIES=python3") for line in lines)


def test_unsupported_python_is_not_misclassified_as_an_apt_package(tmp_path):
    lines = _run(
        tmp_path,
        python="""#!/bin/sh
case "$*" in
  *sys.version_info*) exit 1 ;;
  *) exit 0 ;;
esac
""",
    )

    assert lines == [
        "DISTRO_FAMILY=ubuntu",
        "GH_ATTESTATION=ready",
        "MISSING_CAPABILITIES=python3.10+",
    ]


def test_venv_creation_failure_requests_only_python3_venv(tmp_path):
    lines = _run(
        tmp_path,
        python="""#!/bin/sh
case "$*" in
  *sys.version_info*) exit 0 ;;
  *'-m venv'*) exit 1 ;;
  *) exit 0 ;;
esac
""",
    )

    assert lines == [
        "DISTRO_FAMILY=ubuntu",
        "GH_ATTESTATION=ready",
        "MISSING_UBUNTU_PACKAGES=python3-venv",
        "MISSING_CAPABILITIES=venv-pip",
    ]


def test_ssl_failure_requests_ca_certificates(tmp_path):
    lines = _run(
        tmp_path,
        python="""#!/bin/sh
case "$*" in
  *sys.version_info*) exit 0 ;;
  *'-m venv'*) /bin/mkdir -p "$3/bin"; /bin/cp "$0" "$3/bin/python"; /bin/chmod +x "$3/bin/python"; exit 0 ;;
  *'import ssl'*) exit 1 ;;
  *) exit 0 ;;
esac
""",
    )

    assert lines == [
        "DISTRO_FAMILY=ubuntu",
        "GH_ATTESTATION=ready",
        "MISSING_UBUNTU_PACKAGES=ca-certificates",
        "MISSING_CAPABILITIES=python-ssl",
    ]


def test_os_release_identifies_non_ubuntu_without_using_the_wsl_display_name(tmp_path):
    lines = _run(tmp_path, os_release='NAME="Debian"\nID=debian\n')

    assert lines == [
        "DISTRO_FAMILY=debian",
        "GH_ATTESTATION=ready",
        "PREREQUISITES_READY",
    ]


def test_non_ubuntu_missing_capability_is_detected_without_apt(tmp_path):
    lines = _run(tmp_path, python=None, os_release="ID=fedora\n")

    assert lines[:2] == ["DISTRO_FAMILY=fedora", "GH_ATTESTATION=ready"]
    assert "MISSING_UBUNTU_PACKAGES=python3" in lines
    assert any(line.startswith("MISSING_CAPABILITIES=python3") for line in lines)


def test_missing_gh_is_distinguished_from_an_unsupported_gh(tmp_path):
    missing = _run(tmp_path, gh=None)
    unsupported = _run(tmp_path / "unsupported", gh="#!/bin/sh\nexit 1\n")

    assert missing == [
        "DISTRO_FAMILY=ubuntu",
        "GH_ATTESTATION=missing",
        "MISSING_CAPABILITIES=gh-attestation",
    ]
    assert unsupported == [
        "DISTRO_FAMILY=ubuntu",
        "GH_ATTESTATION=unsupported",
        "MISSING_CAPABILITIES=gh-attestation",
    ]
    assert "gh attestation verify --help" in SCRIPT.read_text()


def test_jq_is_only_checked_when_optional_noc_tools_are_requested(tmp_path):
    core_lines = _run(tmp_path)
    noc_tools_lines = _run(tmp_path / "noc-tools", include_noc_tools=True)

    assert core_lines == [
        "DISTRO_FAMILY=ubuntu",
        "GH_ATTESTATION=ready",
        "PREREQUISITES_READY",
    ]
    assert noc_tools_lines == [
        "DISTRO_FAMILY=ubuntu",
        "GH_ATTESTATION=ready",
        "MISSING_CAPABILITIES=jq",
    ]


def test_external_acquisition_utilities_are_not_runtime_prerequisites():
    source = SCRIPT.read_text()

    assert "curl" not in source
    assert "tar " not in source
    assert "sha256sum" not in source


def test_systemd_and_wsl2_are_core_runtime_blockers_before_acquisition():
    source = INSTALLER.read_text()

    assert "systemctl --user show-environment" in source
    assert "microsoft-standard-WSL2" in source
    assert source.index("systemctl --user show-environment") < source.index(
        "Get-RuntimePrerequisiteAssessment $linuxPackageRoot"
    )


def test_ubuntu_packages_are_confirmed_rechecked_and_never_used_for_other_distros():
    source = INSTALLER.read_text()

    assert source.count("Get-RuntimePrerequisiteAssessment $linuxPackageRoot") >= 2
    assert "DistributionFamily -eq 'ubuntu'" in source
    assert source.index("Confirm-UbuntuPrerequisiteInstallation") < source.index(
        "Invoke-WslSafe $installCommand"
    )
    assert source.index("Invoke-WslSafe $installCommand") < source.index(
        "scripts.bootstrap.acquire_release"
    )
    assert "Write-BootstrapResult 'RUNTIME_SETUP_REQUIRED'" in source
    assert "MISSING_RUNTIME_CAPABILITIES=" in source


def test_github_cli_provisioning_is_confirmed_ubuntu_only_and_rechecked():
    source = INSTALLER.read_text()
    provisioner = ROOT / "scripts" / "bootstrap" / "provision_github_cli.sh"

    assert "[switch]$ConfirmGitHubCli" in source
    assert "GhAttestation -ne 'ready'" in source
    assert "DistributionFamily -ne 'ubuntu'" in source
    assert "Confirm-GitHubCliProvisioning" in source
    assert source.index("Confirm-GitHubCliProvisioning") < source.index(
        "Invoke-WslSafe $githubCliCommand"
    )
    assert source.count("Get-RuntimePrerequisiteAssessment $linuxPackageRoot") >= 3
    assert "https://cli.github.com/packages" in provisioner.read_text()
    assert "/usr/bin/apt-get install --yes gh" in provisioner.read_text()


def test_github_cli_provisioning_never_handles_operator_authentication_files():
    source = (ROOT / "scripts" / "bootstrap" / "provision_github_cli.sh").read_text()

    assert ".config/gh" not in source
    assert "gh auth" not in source
    assert "credential" not in source


def test_noc_tools_jq_is_reported_as_optional_readiness():
    source = (ROOT / "backend" / "services" / "dependency_readiness.py").read_text()

    assert 'noc-tools workflows require jq' in source
    assert '"setup_required"' in source


def test_installer_uses_supported_inno_wizard_api_for_distribution_selection():
    source = (ROOT / "packaging" / "windows" / "SESAMI-NOC-Operations-Setup.iss").read_text()

    assert re.search(r"\bInputQuery\b", source) is None
    assert "CreateInputQueryPage" in source
    assert "TInputQueryWizardPage" in source
