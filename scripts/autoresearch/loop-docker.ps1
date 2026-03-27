# Autoresearch Docker loop — auto-restart on context exhaustion
# Claude Code runs on host, evaluate.py runs in Docker container

$prompt = @"
Read scripts/autoresearch/program.md for the full research protocol, then begin the experiment loop.

Docker-specific overrides:
- factor.py location: docker/autoresearch/work/factor.py
- results.tsv location: docker/autoresearch/work/results.tsv
- Run evaluate: docker exec autoresearch-agent python /app/evaluate.py
- Git operations: cd docker/autoresearch/work first
- NEVER modify files outside docker/autoresearch/work/

Start now. Read program.md first.
"@

while ($true) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Autoresearch (Docker) starting...     " -ForegroundColor Cyan
    Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    claude -p $prompt --dangerously-skip-permissions --max-turns 200

    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Session ended. Restarting in 10s..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
}
