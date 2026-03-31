# Alpha Factor Autoresearch

Karpathy autoresearch pattern for quantitative factor research.

## Architecture

```
Docker 3-container design:

┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Agent           │    │  Evaluator        │    │  Watchdog        │
│  (Claude Code)   │───▶│  (Flask HTTP)     │    │  (Validator+PBO) │
│                  │    │                   │    │                  │
│  work/factor.py  │    │  evaluate.py (RO) │    │  watchdog.py     │
│  work/results.tsv│    │  /evaluate POST   │    │  factor_pbo.json │
│                  │    │  /learnings GET   │    │  deploy_queue/   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
       │ rw                    │ ro work/              │ ro work/
       └──── work/ ────────────┴───────────────────────┘
                               │ rw
                          watchdog_data/
```

### Key Files

| File | Location | Permission | Purpose |
|------|----------|-----------|---------|
| `factor.py` | work/ | Agent RW | compute_factor() — agent's only editable file |
| `results.tsv` | work/ | Agent RW | Experiment log (one row per experiment) |
| `evaluate.py` | evaluator container | READ ONLY | L0-L5 gates + large-scale IC + dedup + OOS |
| `program.md` | agent container | READ ONLY | Research protocol |
| `watchdog.py` | watchdog container | — | Validator (17 checks) + Factor-Level PBO |

## Usage

```powershell
# Start research loop (auto-restarts, includes status reporter + credentials refresher)
powershell -ExecutionPolicy Bypass -File scripts/autoresearch/loop.ps1

# Check status manually
powershell -File scripts/autoresearch/status.ps1

# Docker containers (started automatically by loop.ps1)
cd docker/autoresearch && docker compose up -d
```

## ICIR Methodology

**Method D** (median across horizons): L2 gate uses `median |ICIR|` across 5d/10d/20d/60d horizons.
- Threshold: ≥ 0.30 (pass), ≤ 1.00 (suspicious)
- Eliminates horizon selection bias without discriminating long-term factors

## Security Design

- **40-day revenue delay** enforced in evaluate.py (agent cannot bypass)
- **evaluate.py is READ ONLY** — OS permission + container isolation
- **OOS data hidden** — agent sees only PASS/FAIL, no OOS values or dates
- **watchdog_data/** isolated from agent (separate volume, agent has no access)
- **Git wrapper** blocks `reset --hard` and `clean -f` inside agent container
- **Credentials** mounted read-only; host-side refresher job handles token renewal
- **program.md** restricts file access to factor.py + results.tsv only
