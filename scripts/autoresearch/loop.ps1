# Autoresearch loop — auto-restart on context exhaustion
# Usage: powershell -ExecutionPolicy Bypass -File scripts/autoresearch/loop.ps1
# Stop: Ctrl+C

$prompt = @"
Read scripts/autoresearch/program.md for the full research protocol, then begin the experiment loop.
Start now. Your first action should be reading program.md.
"@

while ($true) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Autoresearch session starting...      " -ForegroundColor Cyan
    Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""

    claude -p $prompt --dangerously-skip-permissions --max-turns 200

    Write-Host ""
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Session ended. Restarting in 10s..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
}
