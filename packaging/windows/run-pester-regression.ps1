[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$packageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repositoryRoot = Split-Path -Parent (Split-Path -Parent $packageRoot)
$nativeTempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
if ($nativeTempRoot -match '^[\\]{2}') {
    throw 'A native local Windows temporary directory is required.'
}

$stageRoot = Join-Path $nativeTempRoot ("sesami-noc-pester-" + [Guid]::NewGuid().ToString('N'))
$originalLocation = Get-Location

try {
    New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null

    $files = @(
        @{ Source = 'tests/windows/Feature012Bootstrap.Tests.ps1'; Destination = 'tests/windows/Feature012Bootstrap.Tests.ps1' },
        @{ Source = 'scripts/windows/bootstrap-install.ps1'; Destination = 'scripts/windows/bootstrap-install.ps1' },
        @{ Source = 'scripts/windows/bootstrap-status.ps1'; Destination = 'scripts/windows/bootstrap-status.ps1' },
        @{ Source = 'scripts/windows/install-shortcut.ps1'; Destination = 'scripts/windows/install-shortcut.ps1' },
        @{ Source = 'packaging/windows/bootstrap-manifest.json'; Destination = 'packaging/windows/bootstrap-manifest.json' }
    )

    foreach ($file in $files) {
        $source = Join-Path $repositoryRoot $file.Source
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
            throw "Required regression input is missing: $($file.Source)"
        }

        $destination = Join-Path $stageRoot $file.Destination
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Force
    }

    $nativeTestPath = [System.IO.Path]::GetFullPath(
        (Join-Path $stageRoot 'tests/windows/Feature012Bootstrap.Tests.ps1')
    )
    Set-Location -LiteralPath $stageRoot
    Import-Module Pester -RequiredVersion 6.2.0 -Force
    $result = Invoke-Pester -Path $nativeTestPath `
        -Output Detailed -PassThru
    if ($result.TotalCount -eq 0 -or $result.FailedCount -gt 0) {
        throw (
            'Pester regression failed: Total={0}; Passed={1}; Failed={2}; Skipped={3}; NotRun={4}.' -f
            $result.TotalCount,
            $result.PassedCount,
            $result.FailedCount,
            $result.SkippedCount,
            $result.NotRunCount
        )
    }
}
finally {
    Set-Location -LiteralPath $originalLocation.Path
    if (Test-Path -LiteralPath $stageRoot) {
        Remove-Item -LiteralPath $stageRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
