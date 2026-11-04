param(
    [Parameter(Mandatory = $true)][string]$Distribution,
    [Parameter(Mandatory = $true)][string]$LinuxLauncher,
    [string]$IconPath = '',
    [switch]$DefineHelpersOnly
)

$ErrorActionPreference = 'Stop'

function Resolve-WslExecutableForShortcut {
    $systemRoot = $env:SystemRoot
    if ([string]::IsNullOrWhiteSpace($systemRoot)) {
        throw 'wsl_executable_missing'
    }
    $native = Join-Path $systemRoot 'System32\wsl.exe'
    $sysnative = Join-Path $systemRoot 'Sysnative\wsl.exe'
    if ([Environment]::Is64BitProcess) {
        if (Test-Path -LiteralPath $native -PathType Leaf) { return $native }
        throw 'wsl_executable_missing'
    }
    if ([Environment]::Is64BitOperatingSystem) {
        if (Test-Path -LiteralPath $sysnative -PathType Leaf) { return $sysnative }
        throw 'wsl_executable_missing'
    }
    if (Test-Path -LiteralPath $native -PathType Leaf) { return $native }
    throw 'wsl_executable_missing'
}

function Assert-SafeShortcutValue([string]$Value, [int]$MaxLength = 260) {
    if ([string]::IsNullOrWhiteSpace($Value) -or $Value.Length -gt $MaxLength) {
        throw 'shortcut_argument_invalid'
    }
    if ($Value -match '[\x00-\x1f"]') {
        throw 'shortcut_argument_invalid'
    }
}

function Invoke-WslNativeShortcutInstall {
    Assert-SafeShortcutValue $Distribution 63
    Assert-SafeShortcutValue $LinuxLauncher 240
    if ($LinuxLauncher -notmatch '^/[A-Za-z0-9._/-]+$' -or $LinuxLauncher.Contains('..')) {
        throw 'shortcut_argument_invalid'
    }

    $wslPath = Resolve-WslExecutableForShortcut
    $desktop = [Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)
    if (-not $desktop -or -not (Test-Path -LiteralPath $desktop -PathType Container)) {
        throw 'desktop_unavailable'
    }

    $shortcutPath = Join-Path $desktop 'SESAMI NOC Operations.lnk'
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $wslPath
    $shortcut.Arguments = (
        '--distribution ' + $Distribution +
        ' --exec ' + $LinuxLauncher
    )
    $shortcut.WorkingDirectory = $desktop
    $shortcut.WindowStyle = 7
    $shortcut.Description = 'Start SESAMI NOC Operations'
    if (-not [string]::IsNullOrWhiteSpace($IconPath) -and
        (Test-Path -LiteralPath $IconPath -PathType Leaf)) {
        $shortcut.IconLocation = $IconPath
    }
    $shortcut.Save()
}

if ($DefineHelpersOnly) {
    return
}

try {
    Invoke-WslNativeShortcutInstall
    Write-Output 'SHORTCUT_INSTALLED'
    Write-Output 'SHORTCUT_TARGET=wsl.exe'
    exit 0
}
catch {
    Write-Output 'SHORTCUT_INSTALL_FAILED'
    Write-Output ("SHORTCUT_INSTALL_REASON=" + $_.Exception.Message)
    exit 1
}
