# Autoresearch loop — Docker isolated agent + status report
# Usage: powershell -ExecutionPolicy Bypass -File scripts/autoresearch/loop.ps1
# Modes:
#   -Docker   : run agent inside Docker container (true isolation, default)
#   -Host     : run agent on host (legacy, needs hooks)
# Stop: Ctrl+C

param(
    [int]$StatusInterval = 600,
    [switch]$HostMode
)

$ScriptDir = $PSScriptRoot
if (-not $ScriptDir) { $ScriptDir = "D:\Finance\scripts\autoresearch" }
$ProjectDir = "D:\Finance"

# Docker mode prompt (paths inside container)
$dockerPrompt = @"
Read /app/program.md for the full research protocol, then begin the experiment loop.
Start now. Your first action should be reading program.md.
"@

# Host mode prompt (paths on host)
$hostPrompt = @"
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

Write-Host "  Status reporter running (Job $($statusJob.Id))" -ForegroundColor Green

# --- Ensure Docker containers are up ---
if (-not $HostMode) {
    Write-Host "Checking Docker containers..." -ForegroundColor Yellow
    $evalUp = docker ps --filter "name=autoresearch-evaluator" --format "{{.Status}}" 2>$null
    if (-not $evalUp) {
        Write-Host "  Starting containers..." -ForegroundColor Gray
        Push-Location "$ProjectDir\docker\autoresearch"
        docker compose up -d 2>$null
        Pop-Location
        Start-Sleep 5
    }
    # Ensure work/ has git repo (volume mount overwrites image content)
    $workDir = "$ProjectDir\docker\autoresearch\work"
    if (-not (Test-Path "$workDir\.git")) {
        Write-Host "  Initializing work/ git repo..." -ForegroundColor Gray
        git -C $workDir init --quiet
        git -C $workDir config user.email "agent@autoresearch"
        git -C $workDir config user.name "autoresearch-agent"
        if (Test-Path "$workDir\factor.py") {
            git -C $workDir add factor.py .gitignore 2>$null
            git -C $workDir commit -m "init: baseline" --quiet 2>$null
        }
    }

    # Verify evaluator health
    $health = docker exec autoresearch-agent bash -c "curl -s http://evaluator:5000/health" 2>$null
    if ($health -match "ok") {
        Write-Host "  Evaluator healthy." -ForegroundColor Green
    } else {
        Write-Host "  WARNING: Evaluator not responding. Falling back to host mode." -ForegroundColor Red
        $HostMode = $true
    }
}

if ($HostMode) {
    $env:AUTORESEARCH = "1"
    Write-Host "  Mode: HOST (hooks enforced)" -ForegroundColor Yellow
} else {
    Write-Host "  Mode: DOCKER (true isolation)" -ForegroundColor Green
}

# --- Research loop ---
try {
    while ($true) {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "  Autoresearch session starting...      " -ForegroundColor Cyan
        Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
        Write-Host "  Mode: $(if ($HostMode) { 'HOST' } else { 'DOCKER' })" -ForegroundColor Gray
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host ""

        powershell -ExecutionPolicy Bypass -File "$ScriptDir\status.ps1" 2>$null

        if ($HostMode) {
            claude -p $hostPrompt --dangerously-skip-permissions --max-turns 200
        } else {
            docker exec `
                -e "HOME=/home/researcher" `
                autoresearch-agent `
                claude -p $dockerPrompt --dangerously-skip-permissions --max-turns 200
        }

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
