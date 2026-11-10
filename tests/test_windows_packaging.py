from pathlib import Path

from scripts.bootstrap.release_manifest import load_manifest


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "packaging" / "windows"


def test_packaging_uses_only_approved_branding_and_allowlisted_inputs():
    icon_script = (PACKAGE / "generate-icon.ps1").read_text()
    project = (PACKAGE / "SESAMI-NOC-Operations-Setup.iss").read_text()
    assert "assets\\windows\\sesami-noc-operations.png" in icon_script
    assert "$PSScriptRoot" not in icon_script
    assert "$MyInvocation.MyCommand.Path" in icon_script
    assert "Copy-Item -LiteralPath $resolvedSource -Destination $temporarySource" in icon_script
    assert "Remove-Item -LiteralPath $temporarySource" in icon_script
    assert "if ($null -ne $image)" in icon_script
    for size in ("16", "24", "32", "48", "64", "128", "256"):
        assert size in icon_script
    assert "sesami-noc-operations.ico" in project
    assert "SetupIconFile=sesami-noc-operations.ico" in project
    assert "Source: \"..\\..\\scripts\\bootstrap\\*.py\"" in project
    assert "function BootstrapParameters" in project
    assert "MB_YESNO" in project
    assert "-ConfirmReplacement" in project
    assert "-ConfirmNocTools" in project
    assert "procedure RunBootstrap" in project
    assert "AddQuotes(ExpandConstant('{app}\\scripts\\windows\\bootstrap-install.ps1'))" in project
    assert "BootstrapParameters('')" in project
    assert "ewWaitUntilTerminated" in project
    assert "if ResultCode = 0 then" in project
    assert "FailBootstrap(" in project
    for excluded in (".git", ".venv", "cache", "credential", "token", "session"):
        assert excluded not in project.lower()


def test_packaging_manifest_and_build_contract_are_immutable():
    manifest = load_manifest(PACKAGE / "bootstrap-manifest.json")
    assert manifest.application.tag == "v1.0.4"
    assert manifest.application.archive == "noc-web-v1.0.4.tar.gz"
    tool = manifest.tool("nocTools")
    assert tool and tool.version == "v1.0.1"
    build = (PACKAGE / "build-installer.ps1").read_text()
    assert "Inno Setup 6" in build
    assert "$env:LOCALAPPDATA\\Programs\\Inno Setup 6\\ISCC.exe" in build
    assert "SESAMI-NOC-Operations-Setup.exe" in build
    assert "Expected installer was not produced" in build


def test_bootstrap_status_uses_redacted_feature011_readiness_results():
    status = (ROOT / "scripts" / "windows" / "bootstrap-status.ps1").read_text()

    assert "assess_external_capabilities" in status
    assert "TOOL_STATUS=$toolId=$state" in status
    assert "external.datadog" in status
    assert "external.datadogMcp" not in status
    assert "$ToolStates = @('installed', 'setup_required', 'ready', 'unavailable')" in status
    assert "ConvertFrom-Json" in status
    assert "2>$null" in status
    assert "bootstrap-manifest.json" in status


def test_bootstrap_install_uses_bounded_controlled_subprocesses_and_safe_categories():
    install = (ROOT / "scripts" / "windows" / "bootstrap-install.ps1").read_text()

    for category in (
        "BOOTSTRAP_READY", "WSL_SETUP_REQUIRED", "DISTRIBUTION_SETUP_REQUIRED",
        "RUNTIME_SETUP_REQUIRED", "SOURCE_VERIFICATION_FAILED",
        "CONFIRMATION_DECLINED", "PERMISSION_REQUIRED",
        "FEATURE011_HANDOFF_FAILED", "DEPENDENCY_SETUP_REQUIRED",
    ):
        assert category in install
    assert "$ControlledLinuxPath = '/usr/local/bin:/usr/bin:/bin'" in install
    assert "$WslTimeoutMilliseconds = 30000" in install
    assert "WaitForExit($WslTimeoutMilliseconds)" in install
    assert "PATH=$ControlledLinuxPath" in install
    assert "RedirectStandardError = $true" in install
    assert "PSObject.Properties['ArgumentList']" in install
    assert "Get-SafeWslValue" in install
    assert "function ConvertTo-PosixShellLiteral" in install
    assert "$Value.Replace($singleQuote, $escapedSingleQuote)" in install
    assert "$escapedSingleQuote = $singleQuote + '\\' + $singleQuote + $singleQuote" in install
    assert "ConvertTo-SafeWslPath $BootstrapManifest" in install
    assert "cd $(ConvertTo-PosixShellLiteral $linuxPackageRoot)" in install
    assert "$BootstrapManifest.Replace(\"'\", \"''\")" not in install
    assert 'APPROVED_RELEASE=$approvedRelease' in install
    assert "if (-not $ConfirmReplacement)" in install
    assert "& wsl.exe" not in install
    assert "function Resolve-WslExecutable" in install
    assert "[Environment]::Is64BitOperatingSystem" in install
    assert "[Environment]::Is64BitProcess" in install
    assert "Sysnative\\wsl.exe" in install
    assert "System32\\wsl.exe" in install
    assert "WSL_RESOLUTION=" in install
    assert "native-system32" in install
    assert "sysnative" in install
    assert "Get-Command wsl" not in install
    assert "where.exe" not in install
    resolve_block = install.split("function Resolve-WslExecutable", 1)[1].split(
        "function Write-BootstrapResult", 1
    )[0]
    assert "$env:Path" not in resolve_block
    assert "Get-Command wsl" not in resolve_block
    assert "Sysnative" in resolve_block
    assert "Never consult PATH" in resolve_block


def test_windows_pester_regression_suite_is_versioned_and_non_destructive():
    acceptance = (ROOT / "tests" / "windows" / "Feature012Bootstrap.Tests.ps1").read_text()
    readme = (PACKAGE / "README.md").read_text()
    runner = (PACKAGE / "run-pester-regression.ps1").read_text()

    assert "ModuleVersion = '6.2.0'" in acceptance
    assert "Describe 'Feature 012 Windows shortcut launch simulation' {\n    BeforeAll {\n        function Invoke-MockedShortcutLaunch" in acceptance
    assert not acceptance.startswith("# Requires -Modules @{ ModuleName = 'Pester'; ModuleVersion = '6.2.0' }\n# These tests inspect package contracts and simulate Windows integration points.\n# They never invoke bootstrap-install.ps1, WSL, a browser, or a real shortcut.\n\nfunction Invoke-MockedShortcutLaunch")
    assert "function Get-StagedResourcePath" in acceptance
    assert "$resourceRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)" in acceptance
    assert "Test-Path -LiteralPath $resourcePath -PathType Leaf" in acceptance
    assert "Required staged regression input is missing: $RelativePath" in acceptance
    assert "Get-Content -LiteralPath (Get-StagedResourcePath" in acceptance
    assert "Mock Start-Process" in acceptance
    assert "Mock Invoke-WebRequest" in acceptance
    assert "Mock New-Object" in acceptance
    assert "WSL_SETUP_REQUIRED" in acceptance
    assert "SOURCE_VERIFICATION_FAILED" in acceptance
    assert "DEPENDENCY_SETUP_REQUIRED" in acceptance
    assert "Should -Not -Match '(?im)\\b(login|signin|auth)\\b'" in acceptance
    assert '"compatibility"\\s*:\\s*"noc-inv-contract=1"' in acceptance
    assert "run-pester-regression.ps1" in readme
    assert "Import-Module Pester -RequiredVersion 6.2.0 -Force" in runner
    assert "$originalLocation = Get-Location" in runner
    assert "Set-Location -LiteralPath $stageRoot" in runner
    assert "$nativeTestPath = [System.IO.Path]::GetFullPath(" in runner
    assert "Invoke-Pester -Path $nativeTestPath" in runner
    assert "[System.IO.Path]::GetTempPath()" in runner
    assert "[Guid]::NewGuid()" in runner
    assert "$nativeTempRoot -match '^[\\\\]{2}'" in runner
    assert "finally {" in runner
    assert "Set-Location -LiteralPath $originalLocation.Path" in runner
    assert "Remove-Item -LiteralPath $stageRoot -Recurse -Force" in runner
    assert "$result.TotalCount -eq 0 -or $result.FailedCount -gt 0" in runner
    assert "Pester regression failed: Total={0}; Passed={1}; Failed={2}; Skipped={3}; NotRun={4}." in runner
    assert "bootstrap-install.ps1" in runner
    assert "bootstrap-status.ps1" in runner
    assert "install-shortcut.ps1" in runner
    assert "install_wsl_shortcut.ps1" in runner
    assert "install-sesami.sh" in runner
    assert "bootstrap-manifest.json" in runner
    assert "Copy-Item -Recurse" not in runner
