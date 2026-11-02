[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$Distribution)

$ErrorActionPreference = 'Stop'
$ToolIds = @(
    'external.atlas', 'external.copilot', 'external.datadogMcp',
    'external.microsoft365', 'external.nocTools'
)
$ToolStates = @('installed', 'setup_required', 'ready', 'unavailable')

function Write-Status([string]$Category) {
    [Console]::Out.WriteLine($Category)
    exit $(if ($Category -eq 'BOOTSTRAP_READY') { 0 } else { 1 })
}

function Test-SafeValue([string]$Value) {
    return -not [string]::IsNullOrWhiteSpace($Value) -and $Value.Length -le 260 -and
        $Value -notmatch '[\x00-\x1f`"'';&|<>]'
}

function Invoke-WslSafe([string]$LinuxCommand) {
    $output = & wsl.exe --distribution $Distribution --exec /bin/sh -lc $LinuxCommand 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'wsl-command-failed' }
    return @($output | Where-Object { $_ -is [string] })
}

function Test-ApprovedNocToolsArtifact {
    try {
        $packageRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
        $manifestPath = Join-Path $packageRoot 'bootstrap-manifest.json'
        $manifest = Get-Content -LiteralPath $manifestPath -Raw -ErrorAction Stop |
            ConvertFrom-Json -ErrorAction Stop
        $entry = @($manifest.toolEntries | Where-Object { $_.tool -eq 'nocTools' }) |
            Select-Object -First 1
        return $null -ne $entry -and
            $entry.source -match '^https://github\.com/' -and
            $entry.sha256 -match '^[0-9a-f]{64}$' -and
            -not [string]::IsNullOrWhiteSpace($entry.target)
    } catch {
        return $false
    }
}

function Get-Feature011Readiness {
    $command = 'cd "$HOME/.local/share/sesami-noc-operations/noc-web" && exec .venv/bin/python -c ''import json; from pathlib import Path; from backend.services.dependency_readiness import assess_external_capabilities; print(json.dumps(assess_external_capabilities(Path.home() / ".local" / "bin", timeout_seconds=15), separators=(",", ":")))'''
    try {
        $payload = (Invoke-WslSafe $command) -join "`n" | ConvertFrom-Json -ErrorAction Stop
        $result = @{}
        foreach ($item in @($payload)) {
            if ($ToolIds -notcontains $item.id -or $ToolStates -notcontains $item.installationStatus) {
                throw 'invalid-readiness-result'
            }
            $result[$item.id] = [string]$item.installationStatus
        }
        return $result
    } catch {
        return @{}
    }
}

try {
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
        Write-Status 'WSL_SETUP_REQUIRED'
    }
    if (-not (Test-SafeValue $Distribution)) {
        Write-Status 'DISTRIBUTION_SETUP_REQUIRED'
    }
    $distributions = @(& wsl.exe --list --quiet 2>$null | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($LASTEXITCODE -ne 0 -or $distributions -notcontains $Distribution) {
        Write-Status 'DISTRIBUTION_SETUP_REQUIRED'
    }
    & wsl.exe --distribution $Distribution --exec systemctl --user is-active noc-web 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Status 'RUNTIME_SETUP_REQUIRED'
    }

    $readiness = Get-Feature011Readiness
    $hasApprovedNocToolsArtifact = Test-ApprovedNocToolsArtifact
    'BOOTSTRAP_READY'
    foreach ($toolId in $ToolIds) {
        $state = if ($readiness.ContainsKey($toolId)) { $readiness[$toolId] } else { 'unavailable' }
        if ($toolId -eq 'external.nocTools' -and $state -eq 'setup_required' -and $hasApprovedNocToolsArtifact) {
            $state = 'unavailable'
        }
        "TOOL_STATUS=$toolId=$state"
    }
} catch {
    Write-Status 'RUNTIME_SETUP_REQUIRED'
}
