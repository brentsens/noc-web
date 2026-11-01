[CmdletBinding()]
param(
    [string]$Source = (Join-Path $PSScriptRoot '..\..\assets\windows\sesami-noc-operations.png'),
    [string]$Destination = (Join-Path $PSScriptRoot 'sesami-noc-operations.ico')
)

Add-Type -AssemblyName System.Drawing
$image = [System.Drawing.Image]::FromFile((Resolve-Path $Source))
try {
    $stream = [System.IO.File]::Open($Destination, [System.IO.FileMode]::Create)
    try { $image.Save($stream, [System.Drawing.Imaging.ImageFormat]::Icon) }
    finally { $stream.Dispose() }
} finally { $image.Dispose() }
