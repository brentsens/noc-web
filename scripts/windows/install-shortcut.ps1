param(
    [Parameter(Mandatory = $true)]
    [string]$LauncherSource,
    [Parameter(Mandatory = $true)]
    [AllowEmptyString()]
    [string]$ShortcutDirectory,
    [switch]$DefineHelpersOnly
)

$ErrorActionPreference = "Stop"

function Set-ShortcutInstallFailure([string]$Reason) {
    $script:ShortcutInstallFailureReason = $Reason
    throw "shortcut_install_failed"
}

function Assert-NotReparsePoint([string]$Path, [string]$FailureReason) {
    try {
        $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    }
    catch {
        Set-ShortcutInstallFailure $FailureReason
    }
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        Set-ShortcutInstallFailure $FailureReason
    }
}

function Assert-NoReparsePointInUserPath([string]$Path, [string]$UserProfile) {
    $profileRoot = [IO.Path]::GetFullPath($UserProfile).TrimEnd("\") + "\"
    $fullPath = [IO.Path]::GetFullPath($Path)
    if (-not $fullPath.StartsWith($profileRoot, [StringComparison]::OrdinalIgnoreCase)) {
        Set-ShortcutInstallFailure "destination_invalid"
    }

    $relativePath = $fullPath.Substring($profileRoot.Length)
    $currentPath = $profileRoot.TrimEnd("\")
    foreach ($segment in $relativePath.Split([IO.Path]::DirectorySeparatorChar)) {
        if (-not $segment) {
            continue
        }
        $currentPath = Join-Path $currentPath $segment
        if (Test-Path -LiteralPath $currentPath) {
            Assert-NotReparsePoint $currentPath "destination_unsafe"
        }
    }
}

function Assert-ShortcutDirectoryPolicy([string]$Path, [bool]$IsOperatingSystemDesktop) {
    if (-not $IsOperatingSystemDesktop) {
        Assert-NoReparsePointInUserPath $Path $env:USERPROFILE
    }
}

function Resolve-ShortcutDirectory(
    [string]$ConfiguredDirectory,
    [string]$DesktopDirectory
) {
    if ($PSBoundParameters.ContainsKey("DesktopDirectory")) {
        $desktopDirectory = $DesktopDirectory
    }
    else {
        $desktopDirectory = [Environment]::GetFolderPath(
            [Environment+SpecialFolder]::DesktopDirectory
        )
    }
    if (-not $desktopDirectory) {
        Set-ShortcutInstallFailure "desktop_unavailable"
    }

    $useOperatingSystemDesktop = (
        -not $ConfiguredDirectory -or
        [string]::Equals(
            $ConfiguredDirectory,
            "Desktop",
            [StringComparison]::OrdinalIgnoreCase
        )
    )
    if ($useOperatingSystemDesktop) {
        if (-not (Test-Path -LiteralPath $desktopDirectory -PathType Container)) {
            Set-ShortcutInstallFailure "desktop_unavailable"
        }
        return $desktopDirectory
    }

    if (-not [IO.Path]::IsPathRooted($ConfiguredDirectory) -or
        $ConfiguredDirectory.StartsWith("\\")) {
        Set-ShortcutInstallFailure "destination_invalid"
    }
    $shortcutDirectoryPath = [IO.Path]::GetFullPath($ConfiguredDirectory)
    Assert-ShortcutDirectoryPolicy $shortcutDirectoryPath $false
    if (-not (Test-Path -LiteralPath $shortcutDirectoryPath -PathType Container)) {
        New-Item -ItemType Directory -Path $shortcutDirectoryPath -Force | Out-Null
        Assert-ShortcutDirectoryPolicy $shortcutDirectoryPath $false
    }
    return $shortcutDirectoryPath
}

function Invoke-ShortcutInstall {
    $launcherSourcePath = [IO.Path]::GetFullPath($LauncherSource)
    if (-not (Test-Path -LiteralPath $launcherSourcePath -PathType Leaf)) {
        Set-ShortcutInstallFailure "launcher_source_invalid"
    }

    $useOperatingSystemDesktop = (
        -not $ShortcutDirectory -or
        [string]::Equals(
            $ShortcutDirectory,
            "Desktop",
            [StringComparison]::OrdinalIgnoreCase
        )
    )
    $shortcutDirectoryPath = Resolve-ShortcutDirectory $ShortcutDirectory
    Assert-ShortcutDirectoryPolicy $shortcutDirectoryPath $useOperatingSystemDesktop

    $localAppData = [Environment]::GetFolderPath(
        [Environment+SpecialFolder]::LocalApplicationData
    )
    if (-not $localAppData) {
        Set-ShortcutInstallFailure "local_app_data_unavailable"
    }
    if (Test-Path -LiteralPath $localAppData) {
        Assert-NotReparsePoint $localAppData "install_path_unsafe"
    }

    $installDirectory = Join-Path $localAppData "SESAMI\NOC Operations"
    $applicationDirectory = Join-Path $localAppData "SESAMI"
    if (Test-Path -LiteralPath $applicationDirectory) {
        Assert-NotReparsePoint $applicationDirectory "install_path_unsafe"
    }
    else {
        New-Item -ItemType Directory -Path $applicationDirectory -Force | Out-Null
    }
    if (-not (Test-Path -LiteralPath $installDirectory -PathType Container)) {
        New-Item -ItemType Directory -Path $installDirectory -Force | Out-Null
    }
    Assert-NotReparsePoint $installDirectory "install_path_unsafe"

    $launcherPath = Join-Path $installDirectory "launch-hidden.vbs"
    $temporaryLauncher = Join-Path $installDirectory "launch-hidden.vbs.new"
    if (Test-Path -LiteralPath $launcherPath) {
        Assert-NotReparsePoint $launcherPath "install_path_unsafe"
    }
    if (Test-Path -LiteralPath $temporaryLauncher) {
        Assert-NotReparsePoint $temporaryLauncher "install_path_unsafe"
    }
    $shortcutPath = Join-Path $shortcutDirectoryPath "SESAMI NOC Operations.lnk"
    if (Test-Path -LiteralPath $shortcutPath) {
        Assert-NotReparsePoint $shortcutPath "destination_unsafe"
    }
    Copy-Item -LiteralPath $launcherSourcePath -Destination $temporaryLauncher -Force
    Move-Item -LiteralPath $temporaryLauncher -Destination $launcherPath -Force

    $hostPath = Join-Path $env:SystemRoot "System32\wscript.exe"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $hostPath
    $shortcut.Arguments = '"' + $launcherPath + '"'
    $shortcut.WorkingDirectory = $installDirectory
    $shortcut.Description = "Start SESAMI NOC Operations"
    $shortcut.Save()
}

if ($DefineHelpersOnly) {
    return
}

$script:ShortcutInstallFailureReason = "shortcut_write_failed"
try {
    Invoke-ShortcutInstall
    Write-Output "SHORTCUT_INSTALLED"
    exit 0
}
catch {
    Write-Output "SHORTCUT_INSTALL_FAILED"
    Write-Output "SHORTCUT_INSTALL_REASON=$script:ShortcutInstallFailureReason"
    exit 1
}
