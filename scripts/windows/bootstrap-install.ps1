[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Distribution,
    [Parameter(Mandatory = $true)][string]$InstallRoot,
    [switch]$ConfirmReplacement
)

$ErrorActionPreference = 'Stop'
function Write-BootstrapResult([string]$Category) {
    [Console]::Out.WriteLine($Category)
    exit $(if ($Category -eq 'BOOTSTRAP_READY') { 0 } else { 1 })
}
try {
    $wsl = & wsl.exe -l -q 2>$null
    if ($LASTEXITCODE -ne 0) { Write-BootstrapResult 'WSL_SETUP_REQUIRED' }
    if ($wsl -notcontains $Distribution) { Write-BootstrapResult 'DISTRIBUTION_SETUP_REQUIRED' }
    if (-not $ConfirmReplacement) { Write-BootstrapResult 'CONFIRMATION_DECLINED' }
    $command = "cd '$InstallRoot' && python3 -m scripts.install_runtime"
    & wsl.exe --distribution $Distribution --exec /bin/sh -lc $command 2>$null
    if ($LASTEXITCODE -ne 0) { Write-BootstrapResult 'FEATURE011_HANDOFF_FAILED' }
    Write-BootstrapResult 'BOOTSTRAP_READY'
} catch {
    Write-BootstrapResult 'RUNTIME_SETUP_REQUIRED'
}
