Add-Type -AssemblyName System.Drawing

$b1 = New-Object System.Drawing.Bitmap "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888787427_46724f66.jpg"
$b2 = New-Object System.Drawing.Bitmap "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888806351_a5d876b9.jpg"

Write-Host "Image 1: $($b1.Width)x$($b1.Height)"
Write-Host "Image 2: $($b2.Width)x$($b2.Height)"

# In Image 2, the browser window is 1024x575.
# Let's crop the card from Image 2 and Image 1 and compare.
# Let's sample:
# 1. Background outside card:
# Image 1 (20, 20):
$c1_bg = $b1.GetPixel(20, 20)
# Image 2 (20, 100):
$c2_bg = $b2.GetPixel(20, 100)
Write-Host ("Outer BG: Img1=#{0:x2}{1:x2}{2:x2}, Img2=#{3:x2}{4:x2}{5:x2}" -f $c1_bg.R, $c1_bg.G, $c1_bg.B, $c2_bg.R, $c2_bg.G, $c2_bg.B)

# 2. Card background:
# In Image 1, right side above heading:
$c1_card = $b1.GetPixel(600, 100)
# In Image 2, right side above heading:
$c2_card = $b2.GetPixel(600, 130)
Write-Host ("Card BG: Img1=#{0:x2}{1:x2}{2:x2}, Img2=#{3:x2}{4:x2}{5:x2}" -f $c1_card.R, $c1_card.G, $c1_card.B, $c2_card.R, $c2_card.G, $c2_card.B)

# 3. Input background:
# In Image 1, First Name:
$c1_inp = $b1.GetPixel(650, 180)
# In Image 2, First Name:
$c2_inp = $b2.GetPixel(650, 210)
Write-Host ("Input BG: Img1=#{0:x2}{1:x2}{2:x2}, Img2=#{3:x2}{4:x2}{5:x2}" -f $c1_inp.R, $c1_inp.G, $c1_inp.B, $c2_inp.R, $c2_inp.G, $c2_inp.B)

# 4. Button:
$c1_btn = $b1.GetPixel(700, 360)
$c2_btn = $b2.GetPixel(700, 380)
Write-Host ("Button: Img1=#{0:x2}{1:x2}{2:x2}, Img2=#{3:x2}{4:x2}{5:x2}" -f $c1_btn.R, $c1_btn.G, $c1_btn.B, $c2_btn.R, $c2_btn.G, $c2_btn.B)

# 5. Checkbox:
# Find green checkbox
Write-Host "Checking tabs in Img 1 vs Img 2:"
$c1_tab_active = $b1.GetPixel(800, 80)
$c2_tab_active = $b2.GetPixel(750, 140)
Write-Host ("Tab Active: Img1=#{0:x2}{1:x2}{2:x2}, Img2=#{3:x2}{4:x2}{5:x2}" -f $c1_tab_active.R, $c1_tab_active.G, $c1_tab_active.B, $c2_tab_active.R, $c2_tab_active.G, $c2_tab_active.B)

$c1_tab_inactive = $b1.GetPixel(680, 80)
$c2_tab_inactive = $b2.GetPixel(640, 140)
Write-Host ("Tab Inactive: Img1=#{0:x2}{1:x2}{2:x2}, Img2=#{3:x2}{4:x2}{5:x2}" -f $c1_tab_inactive.R, $c1_tab_inactive.G, $c1_tab_inactive.B, $c2_tab_inactive.R, $c2_tab_inactive.G, $c2_tab_inactive.B)

$b1.Dispose()
$b2.Dispose()
