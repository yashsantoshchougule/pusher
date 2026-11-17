Add-Type -AssemblyName System.Drawing

function Dump-Horizontal-Slice($path, $y) {
    $bmp = New-Object System.Drawing.Bitmap $path
    Write-Host "Horizontal slice at Y=$y in $path (width=$($bmp.Width))"
    for ($x = 0; $x -lt $bmp.Width; $x += 40) {
        $c = $bmp.GetPixel($x, $y)
        $hex = "#{0:x2}{1:x2}{2:x2}" -f $c.R, $c.G, $c.B
        Write-Host ("  X={0,4}: {1}" -f $x, $hex)
    }
    $bmp.Dispose()
}

Dump-Horizontal-Slice "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888787427_46724f66.jpg" 300
Dump-Horizontal-Slice "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888806351_a5d876b9.jpg" 300
