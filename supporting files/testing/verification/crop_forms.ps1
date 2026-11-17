Add-Type -AssemblyName System.Drawing

function Save-Crop($src, $dst, $x, $y, $w, $h) {
    $bmp = New-Object System.Drawing.Bitmap $src
    $rect = New-Object System.Drawing.Rectangle $x, $y, $w, $h
    $crop = $bmp.Clone($rect, $bmp.PixelFormat)
    $crop.Save($dst, [System.Drawing.Imaging.ImageFormat]::Png)
    $crop.Dispose()
    $bmp.Dispose()
    Write-Host "Saved $dst"
}

Save-Crop "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888787427_46724f66.jpg" "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\scratch\crop_img1_form.png" 550 50 450 500
Save-Crop "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888806351_a5d876b9.jpg" "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\scratch\crop_img2_form.png" 550 100 450 450
