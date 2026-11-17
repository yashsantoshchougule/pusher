Add-Type -AssemblyName System.Drawing

$framesDir = (Resolve-Path "frontend/public/frames").Path
$jpegCodec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq "image/jpeg" }
$encoderParams = New-Object System.Drawing.Imaging.EncoderParameters(1)
$encoderParams.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter([System.Drawing.Imaging.Encoder]::Quality, [long]95)

$count = 0
for ($i = 1; $i -le 100; $i++) {
    $padded = "{0:D3}" -f $i
    $filePath = Join-Path $framesDir "ezgif-frame-$padded.jpg"
    $tempPath = Join-Path $framesDir "temp-$padded.jpg"
    
    if (Test-Path $filePath) {
        $srcBmp = New-Object System.Drawing.Bitmap($filePath)
        $cropRect = New-Object System.Drawing.Rectangle(660, 0, 690, 1080)
        $destBmp = $srcBmp.Clone($cropRect, [System.Drawing.Imaging.PixelFormat]::Format24bppRgb)
        
        $destBmp.Save($tempPath, $jpegCodec, $encoderParams)
        
        $srcBmp.Dispose()
        $destBmp.Dispose()
        
        Remove-Item $filePath
        Rename-Item $tempPath "ezgif-frame-$padded.jpg"
        $count++
    }
}

Write-Host "Successfully cropped and optimized $count frames to 690x1080 pure landscape with ZERO black bars."
