# Autoresearch Status Report Generator
# Usage: powershell -File scripts/autoresearch/status.ps1
# Output: docs/research/status.md

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'

$ScriptDir = "D:\Finance\scripts\autoresearch"
$WatchdogData = "D:\Finance\docker\autoresearch\watchdog_data"
$OutFile = "D:\Finance\docs\research\status.md"
$Now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

# --- Gather data ---

$agentUp = docker ps --filter "name=autoresearch-agent" --format "{{.Status}}" 2>$null
$watchdogUp = docker ps --filter "name=autoresearch-watchdog" --format "{{.Status}}" 2>$null
$agentLabel = if ($agentUp) { "Running ($agentUp)" } else { "Stopped" }
$watchdogLabel = if ($watchdogUp) { "Running ($watchdogUp)" } else { "Stopped" }

$results = @()
$bestScore = 0
$bestFactor = "N/A"
$total = 0; $keepN = 0; $discardN = 0; $crashN = 0; $l5N = 0; $l0N = 0

# Docker mode: read from work/ (current cycle); fallback to host results.tsv (legacy)
$dockerResults = "D:\Finance\docker\autoresearch\work\results.tsv"
$resultsFile = if (Test-Path $dockerResults) { $dockerResults } else { "$ScriptDir\results.tsv" }
if (Test-Path $resultsFile) {
    $lines = Get-Content $resultsFile -Encoding UTF8 | Select-Object -Skip 1 | Where-Object { $_.Trim() -ne "" -and -not $_.StartsWith("#") }
    $total = $lines.Count
    foreach ($line in $lines) {
        $cols = $line -split "`t"
        if ($cols.Count -ge 6) {
            $scoreRaw = $cols[1]
            $score = 0.0
            try { $score = [double]$scoreRaw } catch { $score = 0.0 }
            $icir = $cols[2]
            $level = $cols[3]
            $st = $cols[4]
            $desc = $cols[5]
            if ($st -eq "keep") { $keepN++ }
            if ($st -eq "discard") { $discardN++ }
            if ($st -eq "crash") { $crashN++ }
            if ($level -eq "L5") { $l5N++ }
            if ($level -eq "L0") { $l0N++ }
            if ($score -gt $bestScore) { $bestScore = $score; $bestFactor = $desc }
            # For bucketed scores, track best by bucket rank
            if ($score -eq 0 -and $scoreRaw -match "high|medium|low") {
                $bucketRank = @{"high"=3;"medium"=2;"low"=1;"none"=0}
                $rank = if ($bucketRank.ContainsKey($scoreRaw)) { $bucketRank[$scoreRaw] } else { 0 }
                if ($rank -gt $bestScore) { $bestScore = $rank; $bestFactor = "$desc (score=$scoreRaw)" }
            }
            $results += [PSCustomObject]@{ Score=$scoreRaw; ICIR=$icir; Level=$level; St=$st; Desc=$desc }
        }
    }
}

$passRate = if ($total -gt 0) { [math]::Round($l5N / $total * 100, 1) } else { 0 }

$alerts = docker logs autoresearch-watchdog --tail 200 2>&1 |
    Where-Object { $_ -match "ALERT|STALE|crashed|DEPLOYED" } |
    Select-Object -Last 10

# Factor-Level PBO from watchdog_data
$pboInfo = "N/A"
if (Test-Path "$WatchdogData\factor_pbo.json") {
    $pbo = Get-Content "$WatchdogData\factor_pbo.json" -Raw | ConvertFrom-Json
    $pboInfo = "$($pbo.factor_pbo) (N=$($pbo.n_independent)/$($pbo.n_total_factors))"
}

# Count deployed reports
$deployReports = @(Get-ChildItem "D:\Finance\docs\research\autoresearch\*.md" -ErrorAction SilentlyContinue).Count

# --- Build report ---
$sb = [System.Text.StringBuilder]::new()

[void]$sb.AppendLine("# Autoresearch Status Report")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("> Updated: $Now")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("## Dashboard")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("| Item | Value |")
[void]$sb.AppendLine("|------|-------|")
[void]$sb.AppendLine("| Agent | $agentLabel |")
[void]$sb.AppendLine("| Watchdog | $watchdogLabel |")
[void]$sb.AppendLine("| Experiments | $total |")
[void]$sb.AppendLine("| Keep / Discard / Crash | $keepN / $discardN / $crashN |")
[void]$sb.AppendLine("| L5 OOS Passed | $l5N ($passRate%) |")
[void]$sb.AppendLine("| L0 Early Reject | $l0N |")
[void]$sb.AppendLine("| Deployed | $deployReports |")
[void]$sb.AppendLine("| Factor-Level PBO | $pboInfo |")
[void]$sb.AppendLine("| Best Score | $bestScore |")
[void]$sb.AppendLine("| Best Factor | $bestFactor |")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("## Experiments (latest first)")
[void]$sb.AppendLine("")
[void]$sb.AppendLine("| Score | ICIR | Level | Status | Description |")
[void]$sb.AppendLine("|------:|-----:|-------|--------|-------------|")

for ($i = $results.Count - 1; $i -ge 0; $i--) {
    $r = $results[$i]
    [void]$sb.AppendLine("| $($r.Score) | $($r.ICIR) | $($r.Level) | $($r.St) | $($r.Desc) |")
}

# Kept factors summary
$kept = @($results | Where-Object { $_.St -eq "keep" })
if ($kept.Count -gt 0) {
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("## Kept Factors")
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("| Score | ICIR | Level | Description |")
    [void]$sb.AppendLine("|------:|-----:|-------|-------------|")
    foreach ($k in $kept) {
        [void]$sb.AppendLine("| $($k.Score) | $($k.ICIR) | $($k.Level) | $($k.Desc) |")
    }
}

# Deployed factors
$reportFiles = @(Get-ChildItem "D:\Finance\docs\research\autoresearch\*.md" -ErrorAction SilentlyContinue)
if ($reportFiles.Count -gt 0) {
    [void]$sb.AppendLine("")
    [void]$sb.AppendLine("## Deployed Factors")
    [void]$sb.AppendLine("")
    foreach ($rf in $reportFiles) {
        $rfContent = Get-Content $rf.FullName -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
        $rfTitle = if ($rfContent -match '# Factor Report: (.+)') { $Matches[1] } else { $rf.BaseName }
        $rfValidator = if ($rfContent -match 'Validator: (\d+/\d+)') { $Matches[1] } else { "?" }
        [void]$sb.AppendLine("- **$rfTitle** ($rfValidator) - ``$($rf.Name)``")
    }
}

[void]$sb.AppendLine("")
[void]$sb.AppendLine("## Alerts")
[void]$sb.AppendLine("")
if ($alerts) {
    foreach ($a in $alerts) { [void]$sb.AppendLine("- ``$a``") }
} else {
    [void]$sb.AppendLine("None.")
}

[void]$sb.AppendLine("")
[void]$sb.AppendLine("---")
[void]$sb.AppendLine("*Auto-generated by ``scripts/autoresearch/status.ps1``*")

# --- Write ---
[System.IO.File]::WriteAllText($OutFile, $sb.ToString(), [System.Text.UTF8Encoding]::new($true))
Write-Host "Status report: $OutFile" -ForegroundColor Green
