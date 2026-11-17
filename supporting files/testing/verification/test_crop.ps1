Add-Type -AssemblyName System.Drawing
$srcPath = (Resolve-Path "frontend/public/frames/ezgif-frame-014.jpg").Path
$destPath = (Resolve-Path "frontend/public/frames").Path + "/test-crop-014.jpg"

$srcBmp = New-Object System.Drawing.Bitmap($srcPath)
$cropRect = New-Object System.Drawing.Rectangle(660, 0, 690, 1080)
$destBmp = $srcBmp.Clone($cropRect, $srcBmp.PixelFormat)

$encoder = [System.Drawing.Imaging.ImageFormat]::Jpeg
$destBmp.Save($destPath, $encoder)

$srcBmp.Dispose()
$destBmp.Dispose()

$test = New-Object System.Drawing.Bitmap($destPath)
Write-Host "Cropped dimensions: $($test.Width) x $($test.Height), File size: $((Get-Item $destPath).Length)"
$test.Dispose()
Remove-Item $destPath
