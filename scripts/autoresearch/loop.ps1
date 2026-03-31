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

# --- Start credentials refresher (background, every 30 min) ---
# credentials is :ro mount — Claude Code in container can't refresh.
# Host-side `claude --version` triggers token refresh via SDK.
Write-Host "Starting credentials refresher (every 30 min)..." -ForegroundColor Yellow
$credJob = Start-Job -ScriptBlock {
    # Check immediately on startup, then every 10 min
    while ($true) {
        try {
            $creds = Get-Content "$env:USERPROFILE\.claude\.credentials.json" -Raw | ConvertFrom-Json
            $expiresMs = $creds.claudeAiOauth.expiresAt
            $expiresAt = [DateTimeOffset]::FromUnixTimeMilliseconds($expiresMs).LocalDateTime
            $remaining = ($expiresAt - (Get-Date)).TotalMinutes
            if ($remaining -lt 120) {
                # Proactive refresh: 2 hours before expiry (was 60 min — too late)
                claude --version 2>$null
                # Verify refresh worked
                Start-Sleep -Seconds 3
                $newCreds = Get-Content "$env:USERPROFILE\.claude\.credentials.json" -Raw | ConvertFrom-Json
                $newMs = $newCreds.claudeAiOauth.expiresAt
                $newAt = [DateTimeOffset]::FromUnixTimeMilliseconds($newMs).LocalDateTime
                $newRemaining = ($newAt - (Get-Date)).TotalMinutes
                if ($newRemaining -gt $remaining + 10) {
                    Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Credentials refreshed: $([int]$remaining)m -> $([int]$newRemaining)m"
                } else {
                    Write-Output "[$(Get-Date -Format 'HH:mm:ss')] WARNING: refresh may have failed (remaining=$([int]$newRemaining)m)"
                }
            }
        } catch {
            Write-Output "[$(Get-Date -Format 'HH:mm:ss')] Credentials check error: $_"
        }
        Start-Sleep -Seconds 600  # Check every 10 min (was 30 min)
    }
}
Write-Host "  Credentials refresher running (Job $($credJob.Id))" -ForegroundColor Green

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
$consecutiveFails = 0
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

        $sessionStart = Get-Date
        if ($HostMode) {
            claude -p $hostPrompt --dangerously-skip-permissions --max-turns 200
        } else {
            docker exec `
                -e "HOME=/home/researcher" `
                -e "CLAUDE_CONFIG_DIR=/home/researcher/.claude" `
                autoresearch-agent `
                claude -p $dockerPrompt --dangerously-skip-permissions --max-turns 200
        }

        # Detect auth failure — back off instead of crash-loop
        $sessionDuration = (Get-Date) - $sessionStart
        if ($sessionDuration.TotalSeconds -lt 30) {
            $consecutiveFails++
            Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Session lasted < 30s ($consecutiveFails consecutive). Possible auth issue." -ForegroundColor Red
            if ($consecutiveFails -ge 3) {
                $backoff = [math]::Min(300, 60 * $consecutiveFails)
                Write-Host "  Backing off for $backoff seconds (run '/login' to refresh credentials)..." -ForegroundColor Red
                Start-Sleep -Seconds $backoff
            }
        } else {
            $consecutiveFails = 0
        }

        Write-Host ""
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Session ended. Restarting in 10s..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10
    }
} finally {
    Write-Host "`nStopping background jobs..." -ForegroundColor Yellow
    Stop-Job $statusJob -ErrorAction SilentlyContinue
    Remove-Job $statusJob -Force -ErrorAction SilentlyContinue
    Stop-Job $credJob -ErrorAction SilentlyContinue
    Remove-Job $credJob -Force -ErrorAction SilentlyContinue
    # Reset factor.py to neutral baseline (avoid half-written factor persisting)
    $baselineCode = @'
"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Baseline: simple 20-day return. Starting point — replace with your own factor logic."""
    results: dict[str, float] = {}
    for sym in symbols:
        bars = data["bars"].get(sym)
        if bars is None or len(bars) < 20:
            continue
        b = bars.loc[:as_of]
        if len(b) < 20:
            continue
        ret = b["close"].iloc[-1] / b["close"].iloc[-20] - 1
        results[sym] = float(ret)
    return results
'@
    $baselineCode | Set-Content "$workDir\factor.py" -Encoding UTF8
    git -C $workDir add factor.py 2>$null
    git -C $workDir commit -m "reset: baseline (session ended)" --quiet 2>$null
    Write-Host "  factor.py reset to baseline." -ForegroundColor Gray
    powershell -ExecutionPolicy Bypass -File "$ScriptDir\status.ps1" 2>$null
    Write-Host "Final status report written." -ForegroundColor Green
}
