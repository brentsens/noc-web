[CmdletBinding()]
param([string]$IsccPath)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$project = Join-Path $PSScriptRoot 'SESAMI-NOC-Operations-Setup.iss'
$required = @(
  (Join-Path $root 'assets\windows\sesami-noc-operations.png'),
  (Join-Path $PSScriptRoot 'sesami-noc-operations.ico'),
  (Join-Path $PSScriptRoot 'bootstrap-manifest.json'),
  (Join-Path $root 'scripts\windows\bootstrap-install.ps1')
)
if ($required | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) }) { throw 'Required packaging input is missing.' }
if (-not $IsccPath) {
  $candidates = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe")
  $IsccPath = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}
if (-not $IsccPath) { throw 'Inno Setup 6 ISCC.exe was not found.' }
& $IsccPath /Qp $project
if ($LASTEXITCODE -ne 0) { throw 'ISCC.exe failed.' }
$output = Join-Path $root 'dist\windows\SESAMI-NOC-Operations-Setup.exe'
if (-not (Test-Path -LiteralPath $output -PathType Leaf) -or (Get-Item $output).Length -eq 0) { throw 'Expected installer was not produced.' }
