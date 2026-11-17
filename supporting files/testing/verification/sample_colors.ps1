Add-Type -AssemblyName System.Drawing

function Sample-Points($path, $isBrowser) {
    $bmp = New-Object System.Drawing.Bitmap $path
    Write-Host "=== $path ($($bmp.Width)x$($bmp.Height)) ==="
    
    # We want:
    # 1. Outer background (top-left outside the card)
    # 2. Card background (right half, e.g. empty area between tabs and heading or below social buttons)
    # 3. Heading text ("Create an account")
    # 4. Input background (middle of Email field)
    # 5. Button background (middle of "Create account" button)
    # 6. Active Tab background (Sign Up tab)
    # 7. Inactive Tab background (Log In tab)
    
    # If it's a full browser screenshot (Image 2), card starts lower due to browser chrome (~80px) and taskbar (~48px)
    $yOff = if ($isBrowser) { 80 } else { 0 }
    $hEff = if ($isBrowser) { $bmp.Height - 128 } else { $bmp.Height }
    
    $samples = @(
        @{ Name="Outer Background"; X=[int]($bmp.Width * 0.05); Y=[int]($yOff + 20) },
        @{ Name="Card Background"; X=[int]($bmp.Width * 0.92); Y=[int]($yOff + $hEff * 0.5) },
        @{ Name="Active Tab (Sign Up)"; X=[int]($bmp.Width * 0.8); Y=[int]($yOff + $hEff * 0.17) },
        @{ Name="Inactive Tab (Log In)"; X=[int]($bmp.Width * 0.65); Y=[int]($yOff + $hEff * 0.17) },
        @{ Name="Heading Text Area"; X=[int]($bmp.Width * 0.62); Y=[int]($yOff + $hEff * 0.24) },
        @{ Name="Email Input Field"; X=[int]($bmp.Width * 0.7); Y=[int]($yOff + $hEff * 0.38) },
        @{ Name="Button (Create account)"; X=[int]($bmp.Width * 0.7); Y=[int]($yOff + $hEff * 0.60) },
        @{ Name="Google Social Button"; X=[int]($bmp.Width * 0.65); Y=[int]($yOff + $hEff * 0.78) }
    )
    
    foreach ($s in $samples) {
        $c = $bmp.GetPixel($s.X, $s.Y)
        $r = [int]$c.R
        $g = [int]$c.G
        $b = [int]$c.B
        $hex = "#{0:x2}{1:x2}{2:x2}" -f $r, $g, $b
        Write-Host ("{0,-25} at ({1,4},{2,4}): {3}  (R={4,3}, G={5,3}, B={6,3})" -f $s.Name, $s.X, $s.Y, $hex, $r, $g, $b)
    }
    $bmp.Dispose()
}

Sample-Points "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888787427_46724f66.jpg" $false
Sample-Points "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888806351_a5d876b9.jpg" $true
