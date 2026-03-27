# Autoresearch Docker initialization
# Usage: powershell -ExecutionPolicy Bypass -File docker/autoresearch/init.ps1

$WorkDir = "D:\Finance\docker\autoresearch\work"
$ScriptDir = "D:\Finance\scripts\autoresearch"

# 1. Initialize work/ directory (first run only)
if (-not (Test-Path $WorkDir)) { New-Item -ItemType Directory -Path $WorkDir }
if (-not (Test-Path "$WorkDir\factor.py")) {
    Copy-Item "$ScriptDir\factor.py" "$WorkDir\factor.py"
    Copy-Item "$ScriptDir\results.tsv" "$WorkDir\results.tsv"
}

# 2. Initialize independent git repo
#    results.tsv is .gitignored so git reset won't erase it
if (-not (Test-Path "$WorkDir\.git")) {
    Push-Location $WorkDir
    git init
    "results.tsv`nrun.log" | Out-File -Encoding ascii .gitignore
    git add factor.py .gitignore
    git commit -m "init: autoresearch workspace"
    Pop-Location
}

# 3. Build and start containers
Push-Location "D:\Finance\docker\autoresearch"
docker compose build
docker compose up -d
Pop-Location

# 4. Verify container health
docker exec autoresearch-agent python -c "import numpy, pandas, scipy; print('OK')"

Write-Host "`nContainer ready. Start research with:" -ForegroundColor Green
Write-Host "  powershell -File scripts/autoresearch/loop-docker.ps1"
