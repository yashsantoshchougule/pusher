Add-Type -AssemblyName System.Drawing
$frames = @(1, 10, 25, 50, 75, 90, 100)

foreach ($f in $frames) {
    $padded = "{0:D3}" -f $f
    $file = "frontend/public/frames/ezgif-frame-$padded.jpg"
    $bmp = New-Object System.Drawing.Bitmap((Resolve-Path $file).Path)
    $w = $bmp.Width
    $h = $bmp.Height
    $midY = [int]($h / 2)
    $leftX = 0
    for ($i = 0; $i -lt $w; $i++) {
        $p = $bmp.GetPixel($i, $midY)
        if ($p.R -gt 25 -or $p.G -gt 25 -or $p.B -gt 25) {
            $leftX = $i
            break
        }
    }
    $rightX = $w - 1
    for ($i = $w - 1; $i -ge 0; $i--) {
        $p = $bmp.GetPixel($i, $midY)
        if ($p.R -gt 25 -or $p.G -gt 25 -or $p.B -gt 25) {
            $rightX = $i
            break
        }
    }
    $bmp.Dispose()
    Write-Host "Frame ${padded} - Left: $leftX, Right: $rightX, Width: $($rightX - $leftX)"
}
