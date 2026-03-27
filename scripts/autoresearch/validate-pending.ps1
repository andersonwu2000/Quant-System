# Validate Pending Factors
# Scans docs/research/autoresearch/ for reports marked "Validator: pending"
# Submits each to API for 15-check validation
# Usage: powershell -File scripts/autoresearch/validate-pending.ps1
# Requires: API server running on localhost:8000

$ReportDir = "D:\Finance\docs\research\autoresearch"
$ApiUrl = "http://127.0.0.1:8000/api/v1/auto-alpha/submit-factor"

# Check API server
try {
    $null = Invoke-RestMethod "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 3
} catch {
    Write-Host "ERROR: API server not running on localhost:8000" -ForegroundColor Red
    Write-Host "Start it first: make dev" -ForegroundColor Yellow
    exit 1
}

$reports = Get-ChildItem "$ReportDir\*.md" | Where-Object { $_.Name -ne "status.md" }
$pending = @()

foreach ($r in $reports) {
    $content = Get-Content $r.FullName -Raw -Encoding UTF8
    if ($content -match "Validator: pending") {
        $pending += $r
    }
}

if ($pending.Count -eq 0) {
    Write-Host "No pending reports found." -ForegroundColor Green
    exit 0
}

Write-Host "Found $($pending.Count) pending report(s):" -ForegroundColor Yellow
foreach ($r in $pending) {
    Write-Host "  - $($r.Name)"
}

foreach ($r in $pending) {
    $content = Get-Content $r.FullName -Raw -Encoding UTF8

    # Extract factor code from ```python ... ``` block
    $code = ""
    if ($content -match '(?s)```python\r?\n(.+?)```') {
        $code = $Matches[1].Trim()
    }

    # Extract name from filename (timestamp_name.md)
    $name = $r.BaseName -replace '^\d{8}_\d{6}_', ''

    # Extract composite score
    $score = 0
    if ($content -match 'Composite Score \| ([0-9.]+)') {
        $score = [double]$Matches[1]
    }

    if (-not $code) {
        Write-Host "  SKIP: $($r.Name) - no factor code found" -ForegroundColor Gray
        continue
    }

    Write-Host "`nSubmitting: $name ..." -ForegroundColor Cyan

    $body = @{
        name = $name
        code = $code
        composite_score = $score
        icir_20d = 0
        large_icir_20d = 0
        description = "validate-pending batch submission"
    } | ConvertTo-Json -Depth 3

    try {
        $resp = Invoke-RestMethod -Uri $ApiUrl -Method Post -Body $body -ContentType "application/json" -Headers @{"X-API-Key"="dev-key"} -TimeoutSec 300

        Write-Host "  Validator: $($resp.validator_passed)/$($resp.validator_total)" -ForegroundColor $(if ($resp.deployed) { "Green" } else { "Yellow" })
        Write-Host "  Deployed: $($resp.deployed)"
        Write-Host "  Message: $($resp.message)"

        # Update report: replace "pending" with actual results
        $validatorLine = "Validator: $($resp.validator_passed)/$($resp.validator_total) | Deployed: $($resp.deployed)"
        $content = $content -replace 'Validator: pending', $validatorLine
        $content | Out-File $r.FullName -Encoding UTF8

        Write-Host "  Report updated: $($r.Name)" -ForegroundColor Green
    } catch {
        Write-Host "  FAILED: $_" -ForegroundColor Red
    }
}

Write-Host "`nDone." -ForegroundColor Green
