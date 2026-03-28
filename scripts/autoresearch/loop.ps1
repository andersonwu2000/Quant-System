# Autoresearch loop — research + status report
# Usage: powershell -ExecutionPolicy Bypass -File scripts/autoresearch/loop.ps1
# Stop: Ctrl+C

param(
    [int]$StatusInterval = 600  # seconds between status reports (default 10 min)
)

# Enable hooks enforcement
$env:AUTORESEARCH = "1"

$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) { $ScriptDir = "D:\Finance\scripts\autoresearch" }

$prompt = @"
Read scripts/autoresearch/program.md for the full research protocol, then begin the experiment loop.
Start now. Your first action should be reading program.md.
"@

# --- Start status reporter (background) ---
Write-Host "Starting status reporter (every $($StatusInterval/60) min)..." -ForegroundColor Yellow

$statusJob = Start-Job -ScriptBlock {
    param($interval, $scriptPath)
    while ($true) {
        try { powershell -ExecutionPolicy Bypass -File $scriptPath 2>$null }
        catch {}
        Start-Sleep -Seconds $interval
    }
} -ArgumentList $StatusInterval, "$ScriptDir\status.ps1"

Write-Host "  Status reporter running (Job $($statusJob.Id)), reports at docs\research\status.md" -ForegroundColor Green

# --- Research loop (foreground) ---
try {
    while ($true) {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "  Autoresearch session starting...      " -ForegroundColor Cyan
        Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
        Write-Host "  Hooks: AUTORESEARCH=$env:AUTORESEARCH" -ForegroundColor Gray
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host ""

        # Status report before each session
        powershell -ExecutionPolicy Bypass -File "$ScriptDir\status.ps1" 2>$null

        claude -p $prompt --dangerously-skip-permissions --max-turns 200

        Write-Host ""
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Session ended. Restarting in 10s..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10
    }
} finally {
    Write-Host "`nStopping status reporter..." -ForegroundColor Yellow
    Stop-Job $statusJob -ErrorAction SilentlyContinue
    Remove-Job $statusJob -Force -ErrorAction SilentlyContinue
    powershell -ExecutionPolicy Bypass -File "$ScriptDir\status.ps1" 2>$null
    Write-Host "Final status report written." -ForegroundColor Green
}
