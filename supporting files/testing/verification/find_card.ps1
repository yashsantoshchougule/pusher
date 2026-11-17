Add-Type -AssemblyName System.Drawing

function Find-Card($path) {
    $bmp = New-Object System.Drawing.Bitmap $path
    $midY = [int]($bmp.Height * 0.5)
    Write-Host "Finding card bounds along Y=$midY for $path"
    
    # Outer BG color is roughly at (10, midY)
    $bg = $bmp.GetPixel(10, $midY)
    
    $left = -1
    $right = -1
    for ($x = 0; $x -lt $bmp.Width; $x++) {
        $c = $bmp.GetPixel($x, $midY)
        $diff = [Math]::Abs($c.R - $bg.R) + [Math]::Abs($c.G - $bg.G) + [Math]::Abs($c.B - $bg.B)
        if ($diff -gt 30) {
            if ($left -eq -1) { $left = $x }
            $right = $x
        }
    }
    Write-Host "  Card left: $left, right: $right (Width: $($right - $left))"
    
    # Sample center of right side of card:
    $cardRightCenterX = [int]($left + ($right - $left) * 0.75)
    $cardColor = $bmp.GetPixel($cardRightCenterX, $midY)
    $hex = "#{0:x2}{1:x2}{2:x2}" -f $cardColor.R, $cardColor.G, $cardColor.B
    Write-Host "  Right half of card at ($cardRightCenterX, $midY): $hex"
    
    $bmp.Dispose()
}

Find-Card "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888787427_46724f66.jpg"
Find-Card "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888806351_a5d876b9.jpg"
