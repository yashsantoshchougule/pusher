Add-Type -AssemblyName System.Drawing

function Check-Colors($filePath) {
    $bmp = New-Object System.Drawing.Bitmap $filePath
    Write-Host "File: $filePath ($($bmp.Width)x$($bmp.Height))"
    
    # 5 sample locations across the image
    $pts = @(
        @{Name="Outer BG (top left)"; X=50; Y=150},
        @{Name="Card BG (right side)"; X=[int]($bmp.Width * 0.75); Y=[int]($bmp.Height * 0.25)},
        @{Name="Input box"; X=[int]($bmp.Width * 0.75); Y=[int]($bmp.Height * 0.40)},
        @{Name="Button"; X=[int]($bmp.Width * 0.75); Y=[int]($bmp.Height * 0.62)},
        @{Name="Heading text"; X=[int]($bmp.Width * 0.65); Y=[int]($bmp.Height * 0.29)}
    )
    
    foreach ($pt in $pts) {
        $c = $bmp.GetPixel($pt.X, $pt.Y)
        $hex = "#{0:X2}{1:X2}{2:X2}" -f $c.R, $c.G, $c.B
        Write-Host "  $($pt.Name) at ($($pt.X),$($pt.Y)): $hex (R=$($c.R), G=$($c.G), B=$($c.B))"
    }
    $bmp.Dispose()
}

Check-Colors "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888787427_46724f66.jpg"
Check-Colors "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888806351_a5d876b9.jpg"
