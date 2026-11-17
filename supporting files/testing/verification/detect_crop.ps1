Add-Type -AssemblyName System.Drawing
$imgPath = (Resolve-Path "frontend/public/frames/ezgif-frame-014.jpg").Path
$bmp = New-Object System.Drawing.Bitmap($imgPath)
$w = $bmp.Width
$h = $bmp.Height
Write-Host "Dimensions: $w x $h"

$midY = [int]($h / 2)
$leftX = 0
for ($i = 0; $i -lt $w; $i++) {
    $p = $bmp.GetPixel($i, $midY)
    if ($p.R -gt 20 -or $p.G -gt 20 -or $p.B -gt 20) {
        $leftX = $i
        break
    }
}

$rightX = $w - 1
for ($i = $w - 1; $i -ge 0; $i--) {
    $p = $bmp.GetPixel($i, $midY)
    if ($p.R -gt 20 -or $p.G -gt 20 -or $p.B -gt 20) {
        $rightX = $i
        break
    }
}

$bmp.Dispose()
Write-Host "Left boundary: $leftX, Right boundary: $rightX, Width: $($rightX - $leftX)"
