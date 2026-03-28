# Validate Pending Factors
# Scans watchdog_data/pending/ for markers, submits to API for 16-check validation
# Usage: powershell -File scripts/autoresearch/validate-pending.ps1
# Requires: API server running on localhost:8000

$PendingDir = "D:\Finance\docker\autoresearch\watchdog_data\pending"
$ApiUrl = "http://127.0.0.1:8000/api/v1/auto-alpha/submit-factor"
$ApiKey = if ($env:QUANT_API_KEY) { $env:QUANT_API_KEY } else { "dev-key" }

# Check API server
try {
    $null = Invoke-RestMethod "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 3
} catch {
    Write-Host "ERROR: API server not running on localhost:8000" -ForegroundColor Red
    Write-Host "Start it first: make dev" -ForegroundColor Yellow
    exit 1
}

$markers = @(Get-ChildItem "$PendingDir\*.json" -ErrorAction SilentlyContinue)

if ($markers.Count -eq 0) {
    Write-Host "No pending markers found." -ForegroundColor Green
    exit 0
}

Write-Host "Found $($markers.Count) pending marker(s):" -ForegroundColor Yellow
foreach ($m in $markers) { Write-Host "  - $($m.Name)" }

foreach ($m in $markers) {
    $data = Get-Content $m.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    $code = $data.factor_code
    $results = $data.results
    $name = $m.BaseName

    if (-not $code) {
        Write-Host "  SKIP: $($m.Name) - no factor code" -ForegroundColor Gray
        continue
    }

    Write-Host "`nSubmitting: $name ..." -ForegroundColor Cyan

    $body = @{
        name = $name
        code = $code
        composite_score = $results.composite_score
        icir_20d = if ($results.icir_by_horizon) { $results.icir_by_horizon."20d" } else { 0 }
        large_icir_20d = $results.large_icir_20d
        description = "validate-pending: $($results.level)"
    } | ConvertTo-Json -Depth 3

    try {
        $resp = Invoke-RestMethod -Uri $ApiUrl -Method Post -Body $body -ContentType "application/json" -Headers @{"X-API-Key"=$ApiKey} -TimeoutSec 300

        Write-Host "  Validator: $($resp.validator_passed)/$($resp.validator_total)" -ForegroundColor $(if ($resp.deployed) { "Green" } else { "Yellow" })
        Write-Host "  Deployed: $($resp.deployed)"

        # Move processed marker
        $doneDir = "$PendingDir\done"
        if (-not (Test-Path $doneDir)) { New-Item -ItemType Directory -Path $doneDir | Out-Null }
        Move-Item $m.FullName "$doneDir\$($m.Name)"
    } catch {
        Write-Host "  FAILED: $_" -ForegroundColor Red
    }
}

Write-Host "`nDone." -ForegroundColor Green
