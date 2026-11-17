Add-Type -AssemblyName System.Drawing

$bmp1 = New-Object System.Drawing.Bitmap "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888787427_46724f66.jpg"
$bmp2 = New-Object System.Drawing.Bitmap "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888806351_a5d876b9.jpg"

Write-Host "Image 1 size: $($bmp1.Width)x$($bmp1.Height)"
Write-Host "Image 2 size: $($bmp2.Width)x$($bmp2.Height)"

# Let's inspect unique dominant colors in both images
function Get-Palette($bmp, $label) {
    Write-Host "=== Palette for $label ==="
    $counts = @{}
    # Scan right side of the card
    for ($x = [int]($bmp.Width * 0.6); $x -lt [int]($bmp.Width * 0.9); $x += 10) {
        for ($y = [int]($bmp.Height * 0.2); $y -lt [int]($bmp.Height * 0.8); $y += 10) {
            $c = $bmp.GetPixel($x, $y)
            # quantize
            $qr = [Math]::Round($c.R / 10) * 10
            $qg = [Math]::Round($c.G / 10) * 10
            $qb = [Math]::Round($c.B / 10) * 10
            $k = "#{0:X2}{1:X2}{2:X2}" -f $qr, $qg, $qb
            if ($counts.ContainsKey($k)) { $counts[$k]++ } else { $counts[$k] = 1 }
        }
    }
    $counts.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 6 | ForEach-Object {
        Write-Host "  Color: $($_.Key) Count: $($_.Value)"
    }
}

Get-Palette $bmp1 "Image 1"
Get-Palette $bmp2 "Image 2"

$bmp1.Dispose()
$bmp2.Dispose()
