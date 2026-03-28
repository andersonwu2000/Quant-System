# Alpha Factor Autoresearch

Karpathy autoresearch pattern for quantitative factor research.

## Architecture

```
evaluate.py   (READ ONLY, black box)  ← L0-L5 gates + large-scale IC + OOS holdout
factor.py     (agent's only file)     ← compute_factor(symbols, as_of, data)
program.md    (research protocol)     ← experiment loop instructions
results.tsv   (experiment log)        ← one row per experiment
```

## Usage

```powershell
# Start research loop (auto-restarts on context exhaustion)
powershell -ExecutionPolicy Bypass -File scripts/autoresearch/loop.ps1

# Check status
powershell -File scripts/autoresearch/status.ps1

# Docker watchdog (background Validator + Factor-Level PBO)
docker compose -f docker/autoresearch/docker-compose.yml up -d
```

## Data Flow

```
Agent (host)                    Watchdog (Docker)
─────────────                   ─────────────────
edit factor.py                  monitors watchdog_data/
run evaluate.py                 ← factor_returns + pending markers
record results.tsv              runs Validator (16 checks)
                                computes Factor-Level PBO
                                writes deployment reports
```

## Security Design

- **40-day revenue delay** enforced in evaluate.py (agent cannot bypass)
- **evaluate.py is READ ONLY** (OS-enforced, agent cannot modify)
- **OOS data hidden** — agent sees only PASS/FAIL, no OOS values or dates
- **watchdog_data/** isolated from agent — factor_returns, pending markers, PBO results
- **program.md** restricts file access to factor.py + results.tsv only
