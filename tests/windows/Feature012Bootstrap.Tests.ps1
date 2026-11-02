# Requires -Modules @{ ModuleName = 'Pester'; ModuleVersion = '6.2.0' }
# These tests inspect package contracts and simulate Windows integration points.
# They never invoke bootstrap-install.ps1, WSL, a browser, or a real shortcut.

Describe 'Feature 012 Windows bootstrap package contracts' {
    BeforeAll {
        function Get-StagedResourcePath {
            param(
                [Parameter(Mandatory)]
                [string]$RelativePath
            )

            $resourceRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
            $resourcePath = Join-Path $resourceRoot $RelativePath
            if (-not (Test-Path -LiteralPath $resourcePath -PathType Leaf)) {
                throw "Required staged regression input is missing: $RelativePath"
            }

            return $resourcePath
        }

        $installSource = Get-Content -LiteralPath (Get-StagedResourcePath 'scripts/windows/bootstrap-install.ps1') -Raw
        $statusSource = Get-Content -LiteralPath (Get-StagedResourcePath 'scripts/windows/bootstrap-status.ps1') -Raw
        $shortcutSource = Get-Content -LiteralPath (Get-StagedResourcePath 'scripts/windows/install-shortcut.ps1') -Raw
        $manifestSource = Get-Content -LiteralPath (Get-StagedResourcePath 'packaging/windows/bootstrap-manifest.json') -Raw
    }

    It 'is guide-only for WSL and distribution prerequisites' {
        $installSource | Should -Not -Match '(?im)\bwsl(?:\.exe)?\s+--install\b'
        $installSource | Should -Not -Match '(?im)\bwsl(?:\.exe)?\s+--update\b'
        $installSource | Should -Match 'WSL_SETUP_REQUIRED'
        $installSource | Should -Match 'DISTRIBUTION_SETUP_REQUIRED'
        $installSource | Should -Match 'RUNTIME_SETUP_REQUIRED'
    }

    It 'reports categorized bootstrap failures without raw subprocess output' {
        foreach ($category in @(
                'SOURCE_VERIFICATION_FAILED',
                'CONFIRMATION_DECLINED',
                'PERMISSION_REQUIRED',
                'FEATURE011_HANDOFF_FAILED',
                'DEPENDENCY_SETUP_REQUIRED'
            )) {
            $installSource | Should -Match $category
        }
        $installSource | Should -Match '2>\$null'
        $installSource | Should -Not -Match 'Write-(Host|Error|Warning).*\$(output|_).*'
    }

    It 'requires explicit confirmation before replacement or optional provisioning' {
        $installSource | Should -Match '\[switch\]\$ConfirmReplacement'
        $installSource.IndexOf('CONFIRMATION_DECLINED') |
            Should -BeLessThan $installSource.IndexOf('provision_dependencies')
        $manifestSource | Should -Match '"requiresConfirmation"\s*:\s*true'
    }

    It 'hands runtime ownership to Feature 011 without creating a shortcut itself' {
        $installSource | Should -Match 'scripts\.install_runtime'
        $installSource | Should -Not -Match '(?im)(New-Object\s+-ComObject\s+WScript\.Shell|CreateShortcut|\.lnk)'
        $shortcutSource | Should -Match 'WScript\.Shell'
        $shortcutSource | Should -Match 'DesktopDirectory'
    }

    It 'keeps optional status independent and never performs a sign-in' {
        $statusSource | Should -Match 'TOOL_STATUS='
        $statusSource | Should -Match 'external\.nocTools'
        $statusSource | Should -Match 'assess_external_capabilities'
        $statusSource | Should -Not -Match '(?im)\b(login|signin|auth)\b'
    }

    It 'classifies an approved noc-tools artifact as unavailable rather than setup-required' {
        $statusSource | Should -Match '\$hasApprovedNocToolsArtifact'
        $statusSource | Should -Match "\$state = 'unavailable'"
        $manifestSource | Should -Match '"tool"\s*:\s*"nocTools"'
        $manifestSource | Should -Match '"compatibility"\s*:\s*"noc-inv-contract=1"'
    }

    It 'defines a single branded shortcut and preserves Feature 011 reuse ownership' {
        $shortcutSource | Should -Match 'SESAMI NOC Operations\.lnk'
        $shortcutSource | Should -Match 'Assert-ShortcutDirectoryPolicy'
        $shortcutSource | Should -Not -Match '(?im)Start-Process.*python'
        $installSource | Should -Not -Match '(?im)systemctl\s+--user\s+(start|enable)'
    }
}

Describe 'Feature 012 Windows shortcut launch simulation' {
    BeforeAll {
        function Invoke-MockedShortcutLaunch {
            param([string]$ShortcutPath)

            $shortcutFile = Get-Item -LiteralPath $ShortcutPath -ErrorAction Stop
            $shell = New-Object -ComObject WScript.Shell
            $shortcut = $shell.CreateShortcut($shortcutFile.FullName)
            $process = Start-Process -FilePath $shortcut.TargetPath -ArgumentList $shortcut.Arguments `
                -WindowStyle Hidden -PassThru
            $process.WaitForExit() | Out-Null
            Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -UseBasicParsing |
                Select-Object -ExpandProperty StatusCode
        }
    }

    BeforeEach {
        Mock Get-Item {
            [pscustomobject]@{ FullName = 'C:\Users\operator\Desktop\SESAMI NOC Operations.lnk' }
        } -ParameterFilter { $LiteralPath -eq 'C:\Users\operator\Desktop\SESAMI NOC Operations.lnk' }
        Mock New-Object {
            $shell = [pscustomobject]@{}
            $shell | Add-Member -MemberType ScriptMethod -Name CreateShortcut -Value {
                param($Path)
                [pscustomobject]@{
                    TargetPath = 'C:\Windows\System32\wscript.exe'
                    Arguments = '"C:\Users\operator\AppData\Local\SESAMI\launch-hidden.vbs"'
                }
            }
            $shell
        } -ParameterFilter { $ComObject -eq 'WScript.Shell' }
        Mock Start-Process {
            $process = [pscustomobject]@{ ExitCode = 0 }
            $process | Add-Member -MemberType ScriptMethod -Name WaitForExit -Value { $true }
            $process
        } -ParameterFilter {
            $FilePath -eq 'C:\Windows\System32\wscript.exe' -and $WindowStyle -eq 'Hidden'
        }
        Mock Invoke-WebRequest {
            [pscustomobject]@{ StatusCode = 200 }
        } -ParameterFilter { $Uri -eq 'http://127.0.0.1:8000/api/health' }
    }

    It 'simulates a hidden first shortcut launch without touching the workstation' {
        Invoke-MockedShortcutLaunch 'C:\Users\operator\Desktop\SESAMI NOC Operations.lnk' |
            Should -Be 200
        Should -Invoke Start-Process -Times 1 -Exactly
        Should -Invoke Invoke-WebRequest -Times 1 -Exactly
    }

    It 'simulates a rerun reusing one launcher and service endpoint' {
        Invoke-MockedShortcutLaunch 'C:\Users\operator\Desktop\SESAMI NOC Operations.lnk' |
            Should -Be 200
        Invoke-MockedShortcutLaunch 'C:\Users\operator\Desktop\SESAMI NOC Operations.lnk' |
            Should -Be 200
        Should -Invoke Start-Process -Times 2 -Exactly
        Should -Invoke Invoke-WebRequest -Times 2 -Exactly
        Should -Invoke Get-Item -Times 2 -Exactly
    }
}
