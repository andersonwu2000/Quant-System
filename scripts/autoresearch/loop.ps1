# Autoresearch infinite loop wrapper
# -p + --max-turns allows multiple tool calls per session
# When context fills or max-turns reached, auto-restart
# State preserved in results.tsv + git

$prompt = @"
You are an autonomous alpha factor researcher. Execute these steps immediately without asking questions:

1. Read scripts/autoresearch/program.md for the full protocol
2. Read scripts/autoresearch/results.tsv to see what has been tried
3. Read scripts/autoresearch/factor.py to see current state
4. Start the experiment loop: edit factor.py -> git commit -> run evaluate.py -> record results -> repeat
5. NEVER pause, summarize, or ask for confirmation. Just keep running experiments.

Begin now. Your first action should be reading program.md.
"@

while ($true) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Autoresearch session starting...      " -ForegroundColor Cyan
    Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""

    claude -p $prompt --dangerously-skip-permissions --max-turns 200 --model sonnet

    Write-Host ""
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Session ended. Restarting in 10s..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
}
