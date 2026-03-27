# Autoresearch Docker loop — auto-restart on context exhaustion
# Claude Code runs on host, evaluate.py runs in Docker container

$prompt = @"
Read scripts/autoresearch/program.md for the full research protocol, then begin the experiment loop.

CRITICAL — Docker overrides (these OVERRIDE anything in program.md):
- factor.py is at: docker/autoresearch/work/factor.py (NOT scripts/autoresearch/factor.py)
- results.tsv is at: docker/autoresearch/work/results.tsv
- To run evaluate.py: docker exec autoresearch-agent python /app/evaluate.py
  (do NOT run python scripts/autoresearch/evaluate.py directly)
- All git operations must cd to docker/autoresearch/work/ first:
  cd docker/autoresearch/work && git add factor.py && git commit -m "experiment: ..."
  cd docker/autoresearch/work && git reset --hard HEAD~1
- run.log: docker exec autoresearch-agent python /app/evaluate.py > docker/autoresearch/work/run.log 2>&1
- NEVER modify files outside docker/autoresearch/work/

Start now. Read program.md first, then read docker/autoresearch/work/results.tsv.
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
