Add-Type -AssemblyName System.Drawing

$b1 = New-Object System.Drawing.Bitmap "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888787427_46724f66.jpg"
$b2 = New-Object System.Drawing.Bitmap "C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888806351_a5d876b9.jpg"

Write-Host "Image 1: $($b1.Width) x $($b1.Height)"
Write-Host "Image 2: $($b2.Width) x $($b2.Height)"

# Let's crop both to just the card and see
# In Image 1:
# Card is from roughly (40, 30) to (980, 570)
# In Image 2:
# Card is from roughly (84, 120) to (940, 520)

Write-Host "Checking specific elements in Image 1:"
# Let's check text color of "Create an account"
# Find darkest pixel in "Create an account" area
function Get-Darkest($bmp, $rx1, $ry1, $rx2, $ry2) {
    $minLum = 999
    $best = $null
    for ($x = $rx1; $x -lt $rx2; $x++) {
        for ($y = $ry1; $y -lt $ry2; $y++) {
            $c = $bmp.GetPixel($x, $y)
            $lum = $c.R * 0.299 + $c.G * 0.587 + $c.B * 0.114
            if ($lum -lt $minLum) {
                $minLum = $lum
                $best = $c
            }
        }
    }
    return $best
}

$c1_text = Get-Darkest $b1 600 120 700 160
Write-Host ("Image 1 Title text color: #{0:x2}{1:x2}{2:x2}" -f $c1_text.R, $c1_text.G, $c1_text.B)

$c2_text = Get-Darkest $b2 580 150 700 200
Write-Host ("Image 2 Title text color: #{0:x2}{1:x2}{2:x2}" -f $c2_text.R, $c2_text.G, $c2_text.B)

# Button color (center of "Create account" button)
$c1_btn = Get-Darkest $b1 600 320 800 380
Write-Host ("Image 1 Button color: #{0:x2}{1:x2}{2:x2}" -f $c1_btn.R, $c1_btn.G, $c1_btn.B)

$c2_btn = Get-Darkest $b2 600 320 800 380
Write-Host ("Image 2 Button color: #{0:x2}{1:x2}{2:x2}" -f $c2_btn.R, $c2_btn.G, $c2_btn.B)

# Check active tab color (Sign Up)
$c1_tab = Get-Darkest $b1 750 80 850 115
Write-Host ("Image 1 Active Tab color: #{0:x2}{1:x2}{2:x2}" -f $c1_tab.R, $c1_tab.G, $c1_tab.B)

$c2_tab = Get-Darkest $b2 700 130 820 165
Write-Host ("Image 2 Active Tab color: #{0:x2}{1:x2}{2:x2}" -f $c2_tab.R, $c2_tab.G, $c2_tab.B)

# Check input field background
# Find brightest pixel in input area
function Get-Brightest($bmp, $rx1, $ry1, $rx2, $ry2) {
    $maxLum = -1
    $best = $null
    for ($x = $rx1; $x -lt $rx2; $x++) {
        for ($y = $ry1; $y -lt $ry2; $y++) {
            $c = $bmp.GetPixel($x, $y)
            $lum = $c.R * 0.299 + $c.G * 0.587 + $c.B * 0.114
            if ($lum -gt $maxLum) {
                $maxLum = $lum
                $best = $c
            }
        }
    }
    return $best
}

$c1_input = Get-Brightest $b1 600 200 800 260
Write-Host ("Image 1 Input bg: #{0:x2}{1:x2}{2:x2}" -f $c1_input.R, $c1_input.G, $c1_input.B)

$c2_input = Get-Brightest $b2 600 220 800 280
Write-Host ("Image 2 Input bg: #{0:x2}{1:x2}{2:x2}" -f $c2_input.R, $c2_input.G, $c2_input.B)

$b1.Dispose()
$b2.Dispose()
