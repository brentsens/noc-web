[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BootstrapManifest,
    [Parameter(Mandatory = $true)][string]$Distribution,
    [switch]$ConfirmReplacement,
    [switch]$ConfirmPrerequisites,
    [switch]$ConfirmGitHubCli,
    [switch]$ConfirmNocTools
)

$ErrorActionPreference = 'Stop'
$SafeCategories = @(
    'BOOTSTRAP_READY', 'WSL_SETUP_REQUIRED', 'DISTRIBUTION_SETUP_REQUIRED',
    'RUNTIME_SETUP_REQUIRED', 'SOURCE_VERIFICATION_FAILED',
    'CONFIRMATION_DECLINED', 'PERMISSION_REQUIRED', 'FEATURE011_HANDOFF_FAILED',
    'DEPENDENCY_SETUP_REQUIRED'
)
$ControlledLinuxPath = '/usr/local/bin:/usr/bin:/bin'
$WslTimeoutMilliseconds = 30000
$WslExecutable = Join-Path $env:SystemRoot 'System32\wsl.exe'

function Write-BootstrapResult([string]$Category) {
    if ($SafeCategories -notcontains $Category) { $Category = 'RUNTIME_SETUP_REQUIRED' }
    [Console]::Out.WriteLine($Category)
    exit $(if ($Category -eq 'BOOTSTRAP_READY') { 0 } else { 1 })
}

function Test-SafeValue([string]$Value) {
    return -not [string]::IsNullOrWhiteSpace($Value) -and $Value.Length -le 260 -and
        $Value -notmatch '[\x00-\x1f`"'';&|<>]'
}

function Invoke-WslSafe([string]$LinuxCommand, [switch]$Capture) {
    if (-not (Test-SafeValue $Distribution) -or
        [string]::IsNullOrWhiteSpace($LinuxCommand) -or $LinuxCommand.Length -gt 1024 -or
        $LinuxCommand.Contains('"')) {
        throw 'invalid-input'
    }
    if (-not (Test-Path -LiteralPath $WslExecutable -PathType Leaf)) {
        throw 'wsl-not-available'
    }
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $WslExecutable
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $arguments = @(
            '--distribution', $Distribution, '--exec', '/usr/bin/env', '-i',
            "PATH=$ControlledLinuxPath", '/bin/sh', '-lc', $LinuxCommand
        )
    if ($null -ne $startInfo.PSObject.Properties['ArgumentList']) {
        foreach ($argument in $arguments) {
            [void]$startInfo.ArgumentList.Add($argument)
        }
    } else {
        $startInfo.Arguments = (($arguments | ForEach-Object { '"{0}"' -f $_ }) -join ' ')
    }
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    if (-not $process.Start()) { throw 'wsl-command-failed' }
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit($WslTimeoutMilliseconds)) {
        $process.Kill()
        $process.WaitForExit()
        throw 'wsl-command-timeout'
    }
    $stdout.Wait()
    $stderr.Wait()
    if ($process.ExitCode -ne 0) { throw 'wsl-command-failed' }
    if ($Capture) {
        $output = $stdout.Result
        if ($output.Length -gt 1024 -or $output -match '[\x00-\x08\x0b\x0c\x0e-\x1f]') {
            throw 'unsafe-wsl-output'
        }
        return @($output -split "`r?`n" | Where-Object { $_ -and $_.Length -le 260 })
    }
}

function Get-SafeWslValue([string]$LinuxCommand, [string]$Pattern) {
    $values = @(Invoke-WslSafe $LinuxCommand -Capture)
    if ($values.Count -ne 1 -or $values[0] -notmatch $Pattern) {
        throw 'unsafe-wsl-output'
    }
    return $values[0]
}

function ConvertTo-PosixShellLiteral([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value) -or $Value.Length -gt 260 -or
        $Value -match '[\x00-\x1f]') {
        throw 'invalid-path'
    }
    $singleQuote = [string][char]39
    $escapedSingleQuote = $singleQuote + '\' + $singleQuote + $singleQuote
    return $singleQuote + $Value.Replace($singleQuote, $escapedSingleQuote) + $singleQuote
}

function ConvertTo-SafeWslPath([string]$WindowsPath) {
    $linuxPath = Get-SafeWslValue `
        "wslpath -a -- $(ConvertTo-PosixShellLiteral $WindowsPath)" `
        '^[^\x00-\x1f]{1,240}$'
    if (-not $linuxPath.StartsWith('/')) {
        throw 'unsafe-wsl-path'
    }
    return $linuxPath
}

function Get-WindowsBootstrapContext {
    $desktop = [Environment]::GetFolderPath([Environment+SpecialFolder]::Desktop)
    $userShellFolders = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
    try {
        $redirected = (Get-ItemProperty -Path $userShellFolders -Name Desktop -ErrorAction Stop).Desktop
        if ($redirected) {
            $candidate = [Environment]::ExpandEnvironmentVariables([string]$redirected)
            if (Test-Path -LiteralPath $candidate -PathType Container) { $desktop = $candidate }
        }
    } catch { }
    return [pscustomobject]@{
        WindowsUser = [Environment]::UserName
        UserProfile = $env:USERPROFILE
        Desktop = $desktop
    }
}

function Get-WslIdentity {
    $linuxUser = Get-SafeWslValue 'id -un' '^[a-z_][a-z0-9_-]{0,63}$'
    $linuxUid = Get-SafeWslValue 'id -u' '^[1-9][0-9]*$'
    $linuxHome = Get-SafeWslValue 'getent passwd $(id -u) | cut -d: -f6' '^/[A-Za-z0-9._/-]{1,240}$'
    if (-not (Test-SafeValue $linuxUser) -or $linuxUser -eq 'root' -or
        $linuxUid -notmatch '^[1-9][0-9]*$' -or -not $linuxHome.StartsWith('/')) {
        throw 'invalid-linux-identity'
    }
    [pscustomobject]@{ LinuxUser = $linuxUser; LinuxUid = $linuxUid; LinuxHome = $linuxHome }
}

function Get-RuntimePrerequisiteAssessment(
    [string]$LinuxPackageRoot,
    [switch]$IncludeNocTools
) {
    $scriptArguments = if ($IncludeNocTools) { ' --include-noc-tools' } else { '' }
    $result = @(Invoke-WslSafe (
        "cd $(ConvertTo-PosixShellLiteral $LinuxPackageRoot) && " +
        "/bin/sh scripts/bootstrap/check_runtime_prerequisites.sh$scriptArguments || true"
    ) -Capture)
    $family = $null
    $ghAttestation = $null
    $packages = @()
    $capabilities = @()
    $ready = $false
    foreach ($line in $result) {
        if ($line -match '^DISTRO_FAMILY=([a-z0-9._-]+)$' -and $null -eq $family) {
            $family = $Matches[1]
        } elseif ($line -match '^GH_ATTESTATION=(ready|missing|unsupported)$' -and $null -eq $ghAttestation) {
            $ghAttestation = $Matches[1]
        } elseif ($line -match '^MISSING_UBUNTU_PACKAGES=([a-z0-9-]+(?: [a-z0-9-]+)*)$' -and $packages.Count -eq 0) {
            $packages = @($Matches[1] -split ' ')
        } elseif ($line -match '^MISSING_CAPABILITIES=([a-z0-9.+-]+(?: [a-z0-9.+-]+)*)$' -and $capabilities.Count -eq 0) {
            $capabilities = @($Matches[1] -split ' ')
        } elseif ($line -eq 'PREREQUISITES_READY' -and -not $ready) {
            $ready = $true
        } else {
            throw 'invalid-prerequisite-result'
        }
    }
    if ($null -eq $family -or $null -eq $ghAttestation -or
        (($packages.Count -gt 0 -or $capabilities.Count -gt 0) -and $ready)) {
        throw 'invalid-prerequisite-result'
    }
    return [pscustomobject]@{
        DistributionFamily = $family
        GhAttestation = $ghAttestation
        Packages = $packages
        Capabilities = $capabilities
        Ready = $ready
    }
}

function Confirm-UbuntuPrerequisiteInstallation([string]$InstallCommand) {
    if (-not $ConfirmPrerequisites) { return $false }
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        $message = "The following approved Ubuntu command will run in WSL:`n`n$InstallCommand"
        return [System.Windows.Forms.MessageBox]::Show(
            $message, 'SESAMI NOC Operations', 'YesNo', 'Warning'
        ) -eq 'Yes'
    } catch {
        return $false
    }
}

function Confirm-GitHubCliProvisioning([string]$InstallCommand) {
    if (-not $ConfirmGitHubCli) { return $false }
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        $message = "The following official GitHub CLI action will run in WSL:`n`n" +
            "$InstallCommand`n`nIt configures https://cli.github.com/packages, then runs apt-get update and apt-get install --yes gh."
        return [System.Windows.Forms.MessageBox]::Show(
            $message, 'SESAMI NOC Operations', 'YesNo', 'Warning'
        ) -eq 'Yes'
    } catch {
        return $false
    }
}

try {
    if (-not (Test-Path -LiteralPath $WslExecutable -PathType Leaf)) {
        Write-BootstrapResult 'WSL_SETUP_REQUIRED'
    }
    if (-not (Test-SafeValue $Distribution)) { Write-BootstrapResult 'DISTRIBUTION_SETUP_REQUIRED' }
    try {
        Invoke-WslSafe 'true' | Out-Null
    } catch {
        Write-BootstrapResult 'DISTRIBUTION_SETUP_REQUIRED'
    }
    $windowsContext = Get-WindowsBootstrapContext
    if (-not (Test-SafeValue $windowsContext.WindowsUser) -or
        -not (Test-Path -LiteralPath $windowsContext.UserProfile -PathType Container)) {
        Write-BootstrapResult 'RUNTIME_SETUP_REQUIRED'
    }
    $identity = Get-WslIdentity
    $packageRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $linuxPackageRoot = ConvertTo-SafeWslPath $packageRoot
    try {
        $kernel = Get-SafeWslValue 'uname -r' '^[A-Za-z0-9._+-]{1,120}$'
        if ($kernel -notmatch 'microsoft-standard-WSL2') { throw 'wsl1' }
    } catch {
        Write-BootstrapResult 'WSL_SETUP_REQUIRED'
    }
    try {
        Invoke-WslSafe 'systemctl --user show-environment >/dev/null' | Out-Null
    } catch {
        Write-BootstrapResult 'RUNTIME_SETUP_REQUIRED'
    }

    $prerequisites = Get-RuntimePrerequisiteAssessment $linuxPackageRoot
    [Console]::Out.WriteLine("DETECTED_DISTRIBUTION_FAMILY=$($prerequisites.DistributionFamily)")
    if ($prerequisites.DistributionFamily -eq 'ubuntu' -and $prerequisites.Packages.Count -gt 0) {
        $packages = $prerequisites.Packages
        $approvedPackages = @('python3', 'python3-venv', 'ca-certificates')
        if ($packages.Count -eq 0 -or @($packages | Where-Object { $_ -notin $approvedPackages }).Count -ne 0) {
            Write-BootstrapResult 'RUNTIME_SETUP_REQUIRED'
        }
        $installCommand = 'sudo apt-get update && sudo apt-get install --yes ' + ($packages -join ' ')
        [Console]::Out.WriteLine("APPROVED_UBUNTU_PREREQUISITE_INSTALL=$installCommand")
        if (-not (Confirm-UbuntuPrerequisiteInstallation $installCommand)) {
            Write-BootstrapResult 'RUNTIME_SETUP_REQUIRED'
        }
        try {
            Invoke-WslSafe $installCommand | Out-Null
        } catch {
            Write-BootstrapResult 'RUNTIME_SETUP_REQUIRED'
        }
        try {
            $prerequisites = Get-RuntimePrerequisiteAssessment $linuxPackageRoot
        } catch {
            Write-BootstrapResult 'RUNTIME_SETUP_REQUIRED'
        }
    }
    $nonGitHubCapabilities = @(
        $prerequisites.Capabilities | Where-Object { $_ -ne 'gh-attestation' }
    )
    if ($prerequisites.Packages.Count -gt 0 -or $nonGitHubCapabilities.Count -gt 0) {
        $missingCapabilities = @($prerequisites.Capabilities + $prerequisites.Packages) -join ' '
        if ($missingCapabilities) {
            [Console]::Out.WriteLine("MISSING_RUNTIME_CAPABILITIES=$missingCapabilities")
        }
        Write-BootstrapResult 'RUNTIME_SETUP_REQUIRED'
    }
    if ($prerequisites.GhAttestation -ne 'ready') {
        if ($prerequisites.DistributionFamily -ne 'ubuntu') {
            [Console]::Out.WriteLine("MISSING_RUNTIME_CAPABILITIES=gh-attestation-$($prerequisites.GhAttestation)")
            Write-BootstrapResult 'RUNTIME_SETUP_REQUIRED'
        }
        $githubCliScript = "$linuxPackageRoot/scripts/bootstrap/provision_github_cli.sh"
        $githubCliCommand = "sudo /bin/sh $(ConvertTo-PosixShellLiteral $githubCliScript)"
        [Console]::Out.WriteLine("GITHUB_CLI_CAPABILITY=$($prerequisites.GhAttestation)")
        [Console]::Out.WriteLine('APPROVED_GITHUB_CLI_SOURCE=https://cli.github.com/packages')
        [Console]::Out.WriteLine("APPROVED_GITHUB_CLI_COMMAND=$githubCliCommand")
        if (-not (Confirm-GitHubCliProvisioning $githubCliCommand)) {
            Write-BootstrapResult 'RUNTIME_SETUP_REQUIRED'
        }
        try {
            Invoke-WslSafe $githubCliCommand | Out-Null
            $prerequisites = Get-RuntimePrerequisiteAssessment $linuxPackageRoot
        } catch {
            Write-BootstrapResult 'RUNTIME_SETUP_REQUIRED'
        }
        if ($prerequisites.GhAttestation -ne 'ready') {
            Write-BootstrapResult 'RUNTIME_SETUP_REQUIRED'
        }
    }
    if (-not $prerequisites.Ready) {
        Write-BootstrapResult 'RUNTIME_SETUP_REQUIRED'
    }
    if (-not $ConfirmReplacement) { Write-BootstrapResult 'CONFIRMATION_DECLINED' }

    try {
        $approvedRelease = (Get-Content -LiteralPath $BootstrapManifest -Raw -ErrorAction Stop |
            ConvertFrom-Json -ErrorAction Stop).releaseAssets.tag
        if ($approvedRelease -notmatch '^v[0-9]+\.[0-9]+\.[0-9]+$') { throw 'invalid-release' }
        [Console]::Out.WriteLine("APPROVED_RELEASE=$approvedRelease")
    } catch {
        Write-BootstrapResult 'SOURCE_VERIFICATION_FAILED'
    }
    $linuxManifest = ConvertTo-SafeWslPath $BootstrapManifest
    $linuxRoot = "$($identity.LinuxHome)/.local/share/sesami-noc-operations/noc-web"
    $recordPath = "$($identity.LinuxHome)/.local/state/sesami-noc-operations/release-record.json"
    try {
        Invoke-WslSafe "cd $(ConvertTo-PosixShellLiteral $linuxPackageRoot) && exec python3 -m scripts.bootstrap.acquire_release --manifest $(ConvertTo-PosixShellLiteral $linuxManifest) --install-root $(ConvertTo-PosixShellLiteral $linuxRoot) --record-path $(ConvertTo-PosixShellLiteral $recordPath) --distribution $(ConvertTo-PosixShellLiteral $Distribution)" | Out-Null
    } catch {
        Write-BootstrapResult 'SOURCE_VERIFICATION_FAILED'
    }
    if ($ConfirmNocTools) {
        try {
        $nocToolsPrerequisites = Get-RuntimePrerequisiteAssessment $linuxPackageRoot -IncludeNocTools
        if (-not $nocToolsPrerequisites.Ready) {
            $missingCapabilities = @(
                $nocToolsPrerequisites.Capabilities + $nocToolsPrerequisites.Packages
            ) -join ' '
            if ($missingCapabilities) {
                [Console]::Out.WriteLine("MISSING_OPTIONAL_NOC_TOOLS_CAPABILITIES=$missingCapabilities")
            }
            Write-BootstrapResult 'DEPENDENCY_SETUP_REQUIRED'
        }
        Invoke-WslSafe "cd $(ConvertTo-PosixShellLiteral $linuxRoot) && exec python3 -m scripts.bootstrap.provision_dependencies --manifest $(ConvertTo-PosixShellLiteral $linuxManifest) --install-root $(ConvertTo-PosixShellLiteral $identity.LinuxHome) --noc-bin $(ConvertTo-PosixShellLiteral "$($identity.LinuxHome)/.local/bin") --confirmed" | Out-Null
        foreach ($command in @('tix', 'noc-start', 'noc-status', 'noc-handover')) {
            Invoke-WslSafe "command -v '$command' >/dev/null" | Out-Null
        }
        $contract = Get-SafeWslValue "noc-inv --contract-version" '^noc-inv-contract=[0-9]+$'
        if ($contract -ne 'noc-inv-contract=1') { throw 'noc-tools-contract' }
    } catch {
        Write-BootstrapResult 'DEPENDENCY_SETUP_REQUIRED'
    }
    }
    Write-BootstrapResult 'BOOTSTRAP_READY'
} catch {
    Write-BootstrapResult 'FEATURE011_HANDOFF_FAILED'
}
