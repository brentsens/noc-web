param(
    [Parameter(Mandatory = $true)]
    [string]$Distribution,
    [Parameter(Mandatory = $true)]
    [string]$LinuxUser,
    [string]$ShortcutPath = (Join-Path ([Environment]::GetFolderPath("DesktopDirectory")) "SESAMI NOC Operations.lnk"),
    [string]$HealthUrl = "http://127.0.0.1:8000",
    [Parameter(Mandatory = $true)]
    [string]$RepositoryRoot,
    [switch]$RerunSetup,
    [switch]$StopBeforeRun,
    [switch]$Execute,
    [switch]$InstallerOnly
)

$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1) {
    throw "Shortcut installer acceptance must run under Windows PowerShell 5.1."
}
if ($InstallerOnly -and $RerunSetup) {
    throw "Installer-only validation must not rerun workstation setup."
}

if ($RerunSetup) {
    if (-not $RepositoryRoot -or $RepositoryRoot.Contains("..")) {
        throw "A validated WSL repository path is required for setup rerun."
    }
    & wsl.exe --distribution $Distribution --user $LinuxUser --exec "$RepositoryRoot/scripts/install.sh" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Installer rerun failed."
    }
}

$shortcutPath = [IO.Path]::GetFullPath($ShortcutPath)
if (-not $InstallerOnly) {
    if (-not (Test-Path -LiteralPath $shortcutPath -PathType Leaf)) {
        throw "Launcher shortcut is missing."
    }

    $desktopDirectory = [Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)
    if (-not $desktopDirectory) {
        throw "The OS-reported Desktop directory is unavailable."
    }
    $desktopItem = Get-Item -LiteralPath $desktopDirectory -Force
    $desktopIsReparsePoint = (($desktopItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)
    if ($desktopIsReparsePoint -and $desktopDirectory -match "(?i)OneDrive" -and -not $RerunSetup) {
        throw "Run this acceptance with -RerunSetup to verify shortcut installation to the redirected Desktop."
    }

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $hostPath = [IO.Path]::GetFileNameWithoutExtension($shortcut.TargetPath)
    if ($hostPath -ne "wscript") {
        throw "Shortcut does not target the hidden Windows Script Host."
    }

    $launcherPath = [regex]::Match($shortcut.Arguments, '^"([^"]+\.vbs)"$').Groups[1].Value
    if (-not $launcherPath -or -not (Test-Path -LiteralPath $launcherPath -PathType Leaf)) {
        throw "Shortcut launcher target is invalid."
    }

    $launcherSource = Get-Content -LiteralPath $launcherPath -Raw
    if (-not $launcherSource.Contains($Distribution) -or -not $launcherSource.Contains($LinuxUser)) {
        throw "Launcher does not target the configured WSL identity."
    }
    if ($launcherSource -notmatch '127\.0\.0\.1|localhost') {
        throw "Launcher does not target localhost."
    }
    if ($launcherSource -match '(?i)(token|password|secret|credential)\s*[:=]') {
        throw "Launcher contains a credential-like setting."
    }

    $sameName = Get-ChildItem -LiteralPath (Split-Path -Parent $shortcutPath) -Filter "SESAMI NOC Operations.lnk" -File
    if ($sameName.Count -ne 1) {
        throw "Launcher shortcut is duplicated."
    }

    $cscriptPath = Join-Path $env:SystemRoot "System32\cscript.exe"
    $cscriptAvailable = Test-Path -LiteralPath $cscriptPath -PathType Leaf
}

$installerPathLinux = "$RepositoryRoot/scripts/windows/install-shortcut.ps1"
$installerPath = & wsl.exe --distribution $Distribution --user $LinuxUser --exec wslpath -w $installerPathLinux
if ($LASTEXITCODE -ne 0 -or -not $installerPath) {
    throw "Shortcut installer path could not be resolved."
}

$testRoot = Join-Path $env:TEMP ("noc-web-shortcut-installer-" + [guid]::NewGuid().ToString("N"))
$targetDirectory = Join-Path $testRoot "target"
$reparseDestination = Join-Path $testRoot "configured-destination"
$launcherSourceTest = Join-Path $testRoot "launch-hidden.vbs"
try {
    New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
    New-Item -ItemType Junction -Path $reparseDestination -Target $targetDirectory | Out-Null
    Set-Content -LiteralPath $launcherSourceTest -Value "Option Explicit" -Encoding ASCII

    . $installerPath -LauncherSource $launcherSourceTest `
        -ShortcutDirectory $reparseDestination -DefineHelpersOnly
    $osDesktop = [Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)
    if (-not $osDesktop -or (Resolve-ShortcutDirectory "Desktop") -ne $osDesktop) {
        throw "The OS-reported Desktop directory was not resolved."
    }
    $osDesktopItem = Get-Item -LiteralPath $osDesktop -Force
    if (($osDesktopItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        $script:ShortcutInstallFailureReason = "none"
        Assert-ShortcutDirectoryPolicy $osDesktop $true
        if ($script:ShortcutInstallFailureReason -ne "none") {
            throw "The OS-reported Desktop reparse point was rejected."
        }
    }

    $resolvedRedirectedDesktop = Resolve-ShortcutDirectory "Desktop" $reparseDestination
    $script:ShortcutInstallFailureReason = "none"
    Assert-ShortcutDirectoryPolicy $resolvedRedirectedDesktop $true
    if ($script:ShortcutInstallFailureReason -ne "none") {
        throw "The OS-reported Desktop reparse-point exception was not preserved."
    }

    $script:ShortcutInstallFailureReason = "none"
    try {
        Resolve-ShortcutDirectory "Desktop" ""
        throw "An empty OS-reported Desktop path was accepted."
    }
    catch {
        if ($script:ShortcutInstallFailureReason -ne "desktop_unavailable") {
            throw "An empty OS-reported Desktop path failed with an unexpected reason: $script:ShortcutInstallFailureReason"
        }
    }

    $script:ShortcutInstallFailureReason = "none"
    try {
        Assert-ShortcutDirectoryPolicy $reparseDestination $false
        throw "An arbitrary configured reparse-point destination was accepted."
    }
    catch {
        if ($script:ShortcutInstallFailureReason -ne "destination_unsafe") {
            throw "An arbitrary reparse-point destination failed with an unexpected reason: $script:ShortcutInstallFailureReason"
        }
    }

    $script:ShortcutInstallFailureReason = "none"
    try {
        Assert-NotReparsePoint $reparseDestination "install_path_unsafe"
        throw "A LocalAppData-style reparse-point check was bypassed."
    }
    catch {
        if ($script:ShortcutInstallFailureReason -ne "install_path_unsafe") {
            throw "A LocalAppData-style reparse-point check failed with an unexpected reason: $script:ShortcutInstallFailureReason"
        }
    }

    $installerOutput = & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass `
        -File $installerPath `
        -LauncherSource $launcherSourceTest `
        -ShortcutDirectory $reparseDestination 2>&1
    $installerExitCode = $LASTEXITCODE
    $installerOutputText = $installerOutput -join "`n"
    if ($installerExitCode -eq 0) {
        throw "Shortcut installer accepted an arbitrary configured reparse-point destination."
    }
    if ($installerOutputText -notmatch "SHORTCUT_INSTALL_FAILED" -or
        $installerOutputText -notmatch "SHORTCUT_INSTALL_REASON=destination_unsafe") {
        throw "Shortcut installer did not return the safe destination failure category."
    }
    if ($installerOutputText -match "CommandNotFoundException") {
        throw "Shortcut installer called a helper before it was defined."
    }
}
finally {
    if (Test-Path -LiteralPath $reparseDestination) {
        Remove-Item -LiteralPath $reparseDestination -Force
    }
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Recurse -Force
    }
}

if ($Execute) {
    if ($InstallerOnly) {
        throw "Installer-only validation cannot execute the Windows launcher."
    }
    $health = [Uri]$HealthUrl
    if ($health.Scheme -ne "http" -or $health.Host -notin @("127.0.0.1", "localhost")) {
        throw "Acceptance health URL must be localhost-only."
    }
    $healthUrl = $HealthUrl.TrimEnd("/") + "/api/health"
    $before = & wsl.exe --distribution $Distribution --user $LinuxUser --exec systemctl --user show noc-web.service --property MainPID --value
    if ($LASTEXITCODE -ne 0 -and -not $StopBeforeRun) {
        throw "Managed service status could not be checked."
    }
    if ($StopBeforeRun) {
        & wsl.exe --distribution $Distribution --user $LinuxUser --exec systemctl --user stop noc-web.service
        if ($LASTEXITCODE -ne 0) {
            throw "Managed service could not be stopped for acceptance."
        }
        & wsl.exe --distribution $Distribution --user $LinuxUser --exec systemctl --user reset-failed noc-web.service
        if ($LASTEXITCODE -ne 0) {
            throw "Managed service failure state could not be reset for acceptance."
        }
        Start-Sleep -Seconds 2
        $before = "0"
    }

    $afterCscript = $null
    if ($cscriptAvailable) {
        $cscriptArguments = '//NoLogo "' + $launcherPath.Replace('"', '""') + '"'
        $cscriptProcess = Start-Process -FilePath $cscriptPath -ArgumentList $cscriptArguments -WindowStyle Hidden -PassThru
        if (-not $cscriptProcess.WaitForExit(70000)) {
            $cscriptProcess.Kill()
            throw "Generated launcher did not exit through cscript within its bounded acceptance window."
        }
        if ($cscriptProcess.ExitCode -ne 0) {
            throw "Generated launcher failed through cscript.exe."
        }

        $afterCscript = & wsl.exe --distribution $Distribution --user $LinuxUser --exec systemctl --user show noc-web.service --property MainPID --value
        if ($LASTEXITCODE -ne 0 -or $afterCscript -eq "0") {
            throw "Generated launcher did not leave the user service active through cscript."
        }
    }
    else {
        Write-Output "cscript.exe unavailable; generated-VBS console-host regression skipped."
    }

    $process = Start-Process -FilePath $shortcut.TargetPath -ArgumentList $shortcut.Arguments -WindowStyle Hidden -PassThru
    if (-not $process.WaitForExit(70000)) {
        $process.Kill()
        throw "Hidden launcher did not exit within its bounded acceptance window."
    }
    if ($process.ExitCode -ne 0) {
        throw "Hidden launcher returned a failure status."
    }

    $response = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 5 -UseBasicParsing
    if ($response.StatusCode -ne 200) {
        throw "NOC Web did not become healthy."
    }
    $after = & wsl.exe --distribution $Distribution --user $LinuxUser --exec systemctl --user show noc-web.service --property MainPID --value
    if ($LASTEXITCODE -ne 0 -or $after -eq "0") {
        throw "Launcher did not leave the user service active."
    }
    if ($afterCscript -and $afterCscript -ne $after) {
        throw "Hidden Windows Script Host launch did not reuse the service started by cscript."
    }
    if (-not $StopBeforeRun -and $before -ne $after) {
        throw "Launcher did not reuse the existing user service."
    }
}

if ($InstallerOnly) {
    Write-Output "Windows shortcut installer regression passed."
}
else {
    Write-Output "Windows launcher acceptance checks passed."
}
