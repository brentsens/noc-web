[CmdletBinding()]
param(
    [string]$Source,
    [string]$Destination
)

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($scriptDirectory)) {
    throw 'Unable to resolve the icon generator script directory.'
}
if ([string]::IsNullOrWhiteSpace($Source)) {
    $Source = Join-Path (Split-Path -Parent (Split-Path -Parent $scriptDirectory)) 'assets\windows\sesami-noc-operations.png'
}
if ([string]::IsNullOrWhiteSpace($Destination)) {
    $Destination = Join-Path $scriptDirectory 'sesami-noc-operations.ico'
}
if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
    throw 'Approved branding source is missing.'
}
Add-Type -AssemblyName System.Drawing
$temporarySource = $null
$image = $null
try {
    $resolvedSource = (Resolve-Path -LiteralPath $Source -ErrorAction Stop).Path
    $temporarySource = Join-Path ([System.IO.Path]::GetTempPath()) ("sesami-noc-operations-" + [guid]::NewGuid().ToString('N') + '.png')
    Copy-Item -LiteralPath $resolvedSource -Destination $temporarySource -ErrorAction Stop
    $image = [System.Drawing.Image]::FromFile($temporarySource)
    if ($null -eq $image) { throw 'Approved branding image could not be loaded.' }
    $sizes = @(16, 24, 32, 48, 64, 128, 256)
    $frames = @()
    foreach ($size in $sizes) {
        $bitmap = New-Object System.Drawing.Bitmap $size, $size
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        try {
            $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.DrawImage($image, 0, 0, $size, $size)
            $frame = New-Object System.IO.MemoryStream
            $bitmap.Save($frame, [System.Drawing.Imaging.ImageFormat]::Png)
            $frames += ,$frame.ToArray()
        } finally { $graphics.Dispose(); $bitmap.Dispose() }
    }
    $parent = Split-Path -Parent $Destination
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) { throw 'Icon output directory is missing.' }
    $stream = [System.IO.File]::Open($Destination, [System.IO.FileMode]::Create)
    try {
        $writer = New-Object System.IO.BinaryWriter $stream
        $writer.Write([UInt16]0); $writer.Write([UInt16]1); $writer.Write([UInt16]$frames.Count)
        $offset = 6 + (16 * $frames.Count)
        for ($index = 0; $index -lt $frames.Count; $index++) {
            $size = $sizes[$index]; $dimension = if ($size -eq 256) { 0 } else { $size }
            $writer.Write([byte]$dimension); $writer.Write([byte]$dimension); $writer.Write([byte]0); $writer.Write([byte]0)
            $writer.Write([UInt16]1); $writer.Write([UInt16]32); $writer.Write([UInt32]$frames[$index].Length); $writer.Write([UInt32]$offset)
            $offset += $frames[$index].Length
        }
        foreach ($frame in $frames) { $writer.Write($frame) }
        $writer.Dispose()
    } finally { $stream.Dispose() }
} finally {
    if ($null -ne $image) { $image.Dispose() }
    if ($temporarySource -and (Test-Path -LiteralPath $temporarySource -PathType Leaf)) {
        Remove-Item -LiteralPath $temporarySource -Force -ErrorAction SilentlyContinue
    }
}
