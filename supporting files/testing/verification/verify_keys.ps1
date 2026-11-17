$content = Get-Content "frontend\dist\assets\*.js" -Raw
$exactKey = $env:SUPABASE_SECRET_KEY
if ($exactKey) {
    $contains = $content.Contains($exactKey)
    Write-Host "Contains exact secret key: $contains"
} else {
    Write-Host "SUPABASE_SECRET_KEY not set in environment."
}

$publishableKey = $env:SUPABASE_PUBLISHABLE_KEY
if ($publishableKey) {
    $containsPub = $content.Contains($publishableKey)
    Write-Host "Contains public publishable key: $containsPub"
}
