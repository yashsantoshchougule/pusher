Add-Type -AssemblyName System.Drawing

$b1 = New-Object System.Drawing.Bitmap "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888787427_46724f66.jpg"
$b2 = New-Object System.Drawing.Bitmap "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888806351_a5d876b9.jpg"

Write-Host "Image 1: $($b1.Width)x$($b1.Height)"
Write-Host "Image 2: $($b2.Width)x$($b2.Height)"

# In Image 1, where did it come from?
# Look at Image 1 top-left corner: (50, 50) is #DADCC7 / #EBEBD8
# Look at Image 2 top-left corner: (50, 50) is Chrome tab bar #202124!
# In Image 2, the browser content starts at Y=74!
# Let's check pixel (50, 75) in Image 2:
$p = $b2.GetPixel(50, 75)
Write-Host ("Image 2 content top-left (50, 75): #{0:x2}{1:x2}{2:x2}" -f $p.R, $p.G, $p.B)

# Let's crop the card from Image 1:
# In Image 1, card starts at X=53, Y=33, and ends at X=971, Y=566 (Width=918, Height=533)
# In Image 2, card starts at X=94, Y=127, and ends at X=855, Y=525 (Width=761, Height=398)
Write-Host "Image 1 is a direct crop of the card from the browser!"

$b1.Dispose()
$b2.Dispose()
