[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RuntimeConfig
)

$ErrorActionPreference = 'Stop'
try {
    $result = & wsl.exe --exec /bin/sh -lc "python3 -m scripts.install_runtime" 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'FEATURE011_HANDOFF_FAILED' }
    $result | Where-Object { $_ -match '^[A-Za-z0-9 .-]+: (READY|SETUP_REQUIRED|UNAVAILABLE)$' }
} catch {
    'FEATURE011_HANDOFF_FAILED'
    exit 1
}
