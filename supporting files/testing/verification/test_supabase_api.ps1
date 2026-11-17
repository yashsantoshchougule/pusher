$apiKey = if ($env:SUPABASE_PUBLISHABLE_KEY) { $env:SUPABASE_PUBLISHABLE_KEY } else { "test-anon-key" }
$supabaseUrl = if ($env:SUPABASE_URL) { $env:SUPABASE_URL } else { "https://your-project.supabase.co" }

$headers = @{
    'apikey' = $apiKey
}

Write-Host "--- Test 1: GET /auth/v1/health ---"
try {
    $res = Invoke-RestMethod -Uri "$supabaseUrl/auth/v1/health" -Headers $headers -Method Get
    Write-Host "Result: $($res | Out-String)"
} catch {
    Write-Host "Error: $($_.Exception.Message)"
}

Write-Host "`n--- Test 2: GET /auth/v1/settings ---"
try {
    $res2 = Invoke-RestMethod -Uri "$supabaseUrl/auth/v1/settings" -Headers $headers -Method Get
    Write-Host "Settings: $($res2 | ConvertTo-Json -Depth 3)"
} catch {
    Write-Host "Error: $($_.Exception.Message)"
}

Write-Host "`n--- Test 3: GET /auth/v1/.well-known/jwks.json ---"
try {
    $res3 = Invoke-RestMethod -Uri "$supabaseUrl/auth/v1/.well-known/jwks.json" -Method Get
    Write-Host "JWKS keys found: $($res3.keys.Count)"
} catch {
    Write-Host "Error: $($_.Exception.Message)"
}
