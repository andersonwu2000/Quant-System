# Autoresearch All-in-One Launcher
# Usage: powershell -ExecutionPolicy Bypass -File scripts/autoresearch/run.ps1
#
# Starts:
#   1. Docker containers (agent + watchdog)
#   2. Status report generator (every 10 min)
#   3. Claude Code research loop (foreground)
#
# Stop: Ctrl+C (status job auto-cleans on exit)

param(
    [int]$StatusInterval = 600  # seconds between status reports (default 10 min)
)

$ErrorActionPreference = "Continue"
$WorkDir = "D:\Finance\docker\autoresearch\work"
$ScriptDir = "D:\Finance\scripts\autoresearch"
$DockerDir = "D:\Finance\docker\autoresearch"

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Autoresearch All-in-One Launcher" -ForegroundColor Cyan
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

# --- Step 1: Ensure Docker containers are running ---
Write-Host "`n[1/3] Checking Docker containers..." -ForegroundColor Yellow

$agentUp = docker ps --filter "name=autoresearch-agent" --format "{{.Status}}" 2>$null
if (-not $agentUp) {
    Write-Host "  Starting containers..." -ForegroundColor Gray

    # Init work/ if needed
    if (-not (Test-Path $WorkDir)) { New-Item -ItemType Directory -Path $WorkDir | Out-Null }
    if (-not (Test-Path "$WorkDir\factor.py")) {
        Copy-Item "$ScriptDir\factor.py" "$WorkDir\factor.py"
        Copy-Item "$ScriptDir\results.tsv" "$WorkDir\results.tsv"
    }
    if (-not (Test-Path "$WorkDir\.git")) {
        Push-Location $WorkDir
        git init --quiet
        "results.tsv`nrun.log" | Out-File -Encoding ascii .gitignore
        git add factor.py .gitignore
        git commit -m "init: autoresearch workspace" --quiet
        Pop-Location
    }

    Push-Location $DockerDir
    docker compose up -d 2>&1 | Out-Null
    Pop-Location

    # Verify
    $check = docker exec autoresearch-agent python -c "print('OK')" 2>$null
    if ($check -eq "OK") {
        Write-Host "  Containers started." -ForegroundColor Green
    } else {
        Write-Host "  ERROR: Container health check failed!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  Containers already running ($agentUp)" -ForegroundColor Green
}

# --- Step 2: Start status report job (background) ---
Write-Host "`n[2/3] Starting status reporter (every $($StatusInterval/60) min)..." -ForegroundColor Yellow

$statusJob = Start-Job -ScriptBlock {
    param($interval, $scriptPath)
    while ($true) {
        powershell -ExecutionPolicy Bypass -File $scriptPath 2>$null
        Start-Sleep -Seconds $interval
    }
} -ArgumentList $StatusInterval, "$ScriptDir\status.ps1"

Write-Host "  Status reporter running (Job ID: $($statusJob.Id))" -ForegroundColor Green
Write-Host "  Reports at: docs\research\status.md" -ForegroundColor Gray

# --- Step 3: Run Claude Code loop (foreground) ---
Write-Host "`n[3/3] Starting research loop..." -ForegroundColor Yellow
Write-Host "  Press Ctrl+C to stop everything.`n" -ForegroundColor Gray

$prompt = @"
Read scripts/autoresearch/program.md for the full research protocol, then begin the experiment loop.

CRITICAL Docker overrides (OVERRIDE anything in program.md):
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

try {
    while ($true) {
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "  Research session: $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Cyan
        Write-Host "========================================" -ForegroundColor Cyan

        claude -p $prompt --dangerously-skip-permissions --max-turns 200 --model sonnet

        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Session ended. Restarting in 10s..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10
    }
} finally {
    # Cleanup on Ctrl+C
    Write-Host "`nStopping status reporter..." -ForegroundColor Yellow
    Stop-Job $statusJob -ErrorAction SilentlyContinue
    Remove-Job $statusJob -Force -ErrorAction SilentlyContinue

    # Generate final status report
    powershell -ExecutionPolicy Bypass -File "$ScriptDir\status.ps1" 2>$null
    Write-Host "Final status report written." -ForegroundColor Green
    Write-Host "Containers still running. To stop: docker compose -f docker/autoresearch/docker-compose.yml down" -ForegroundColor Gray
}
