# AutoResearch Runbook

> Operational guide for the automated factor research system.
> Read this file to operate the system. For architecture details, see `docs/claude/ARCHITECTURE.md`.

---

## 1. System Boundary

| System | Purpose | Scope |
|--------|---------|-------|
| **AutoResearch** | Factor factory: generate, evaluate, and filter alpha factors | `scripts/autoresearch/`, `docker/autoresearch/` |
| **AutoAlpha** | Production engine: deploy, monitor, and manage live/paper strategies | `src/alpha/auto/`, `src/api/routes/auto_alpha.py` |

AutoResearch discovers factors. AutoAlpha deploys them. They connect via the `/auto-alpha/submit-factor` API endpoint.

---

## 2. Single Evaluation Standard

**`scripts/autoresearch/evaluate.py` is the sole evaluation harness. It is READ ONLY.**

- The agent (Claude Code) can only edit `factor.py` and `results.tsv`
- The agent cannot read `evaluate.py`, `watchdog_data/`, or `src/`
- All thresholds, safety delays, and anti-overfitting measures are hardcoded in `evaluate.py`
- Revenue data is truncated by 40 calendar days BEFORE passing to the factor function (agent cannot bypass)

The legacy `src/alpha/auto/factor_evaluator.py` is **deprecated** (AP-2). Do not use it.

---

## 3. L1-L5 Gate Summary

All gates use In-Sample (IS) data unless noted. Period split is rolling:
- IS: 2017-01-01 to `today - 90d - 549d`
- OOS1: `today - 90d - 548d` to `today - 90d - 274d` (L5 only, agent cannot see values)
- OOS2: `today - 274d` to `today - 1d` (StrategyValidator only)

| Gate | What It Checks | Threshold | Fail Action |
|------|---------------|-----------|-------------|
| **L0** | Code complexity | factor.py <= 80 lines | Reject |
| **L1** | Quick IC screen | \|IC(20d)\| >= 0.02 OR \|IC(60d)\| >= 0.03 | Try different direction |
| **L2** | Multi-horizon ICIR + cost | median \|ICIR\| >= 0.15, <= 0.50 (4 horizons) | Signal unstable |
| **L3a** | IC-series dedup vs baseline | correlation <= 0.65 | Clone / saturated |
| **L3b** | Rolling 12-month stability | >= 50% positive IC months | Regime-dependent |
| **L4** | WorldQuant BRAIN fitness | fitness >= 3.0 | Insufficient composite quality |
| **L5a** | OOS1 IC direction + consistency | Same sign as IS, >= 50% positive months | Overfitting IS |
| **L5b** | Top quintile vs universe (IS+OOS1) | Top quintile outperforms | IC high but unprofitable |
| **L5c** | Quantile monotonicity (IS+OOS1) | \|Spearman\| > 0.5 across quintiles | Non-monotonic signal |
| **Stage 2** | Large-scale IC (865+ stocks) | Informational (no hard block) | Small-sample bias check |

After L5, passing factors go to StrategyValidator (16 gates: 7 hard + 9 soft).

---

## 4. Promotion and Deploy Conditions

See `docs/claude/PROMOTION_POLICY.md` for full rules.

**research -> paper:**
- All 7 hard gates pass
- Soft gate failures <= 2
- Validator decision is "pass" or "pass-with-warning"

**paper -> live:**
- All hard gates re-validated on paper-period data
- 30+ days paper trading with 0 invariant violations
- Paper Sharpe within 50% of backtest Sharpe

**Demotion triggers:**
- Any hard gate failure on rolling re-validation -> immediate freeze
- 3+ soft gate warnings -> freeze promotion
- Rolling 6-month Sharpe < 0 (two consecutive checks) -> de-list

---

## 5. Starting the System

### Docker mode (recommended)

```bash
# Start autoresearch containers
docker compose -f docker/autoresearch/docker-compose.yml up -d

# Start research loop (in a separate terminal or via API)
claude -p scripts/autoresearch/program.md
```

### API mode

```bash
# Start via API (requires trader role)
curl -X POST http://localhost:8000/auto-alpha/start \
  -H "X-API-Key: YOUR_KEY"
```

### Watchdog

The watchdog (`docker/autoresearch/watchdog.py`) enforces family saturation (max 3 per family at L4+), portfolio dedup (corr > 0.85 blocked), and full 16-gate Validator before deployment.

---

## 6. Emergency Stop

### Option A: Docker down (fastest)

```bash
docker compose -f docker/autoresearch/docker-compose.yml down
```

### Option B: Silence watchdog

```bash
python scripts/silence_watchdog.py
```

This pauses the watchdog without stopping containers. The agent continues but cannot deploy.

### Option C: API stop

```bash
curl -X POST http://localhost:8000/auto-alpha/stop \
  -H "X-API-Key: YOUR_KEY"
```

### Option D: Stop a specific deployed strategy

```bash
curl -X POST http://localhost:8000/auto-alpha/deployed/{name}/stop \
  -H "X-API-Key: YOUR_KEY"
```

---

## 7. Session Reset

```bash
python scripts/autoresearch/preflight.py --clean
```

This clears stale state (results.tsv, temporary files) while preserving baseline IC series and deployed factors.

---

## 8. Fail-Closed Principles

These are non-negotiable. Violations are bugs.

1. **Data insufficient -> reject.** Never pass a factor because validation data is missing. Return worst-case values (-999, 1.0) on exception.
2. **Revenue delay is enforced in evaluate.py, not in factor code.** The agent cannot bypass the 40-day truncation.
3. **Generic fallback is poison.** Never use "default value if not found". If data lookup fails, raise or return None.
4. **Agent safety relies on isolation, not instructions.** Docker volume mounts are the real protection. Prompt rules can be circumvented (`git reset --hard`).
5. **OOS values are never exposed to the agent.** L5 returns only pass/fail. The eval server returns bucketed ICIR (none/weak/moderate/strong).
6. **Thresholdout noise preserves holdout validity.** Laplace noise is added to L5 comparisons (scale=0.05). Budget tracked; warn after 200 L5 queries.

---

## 9. Monitoring

### Check system status

```bash
curl http://localhost:8000/auto-alpha/status -H "X-API-Key: YOUR_KEY"
```

### View experiment history

```bash
# Results TSV (inside container)
docker exec autoresearch-agent cat /app/results.tsv

# Or via API
curl http://localhost:8000/auto-alpha/history?limit=10 -H "X-API-Key: YOUR_KEY"
```

### View deployed strategies

```bash
curl http://localhost:8000/auto-alpha/deployed -H "X-API-Key: YOUR_KEY"
```

### View watchdog learnings

```bash
curl http://evaluator:5000/learnings  # from inside Docker network
# Or read directly:
cat docker/autoresearch/watchdog_data/learnings.jsonl
```

---

## 10. Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Agent stuck in loop | factor.py syntax error | Check container logs, reset factor.py |
| All factors fail L1 | Data not loaded | Check `data/market/` has parquet files |
| L3 blocks everything | Direction saturated | Check saturation via learnings API |
| Deploy fails silently | Slot limit reached | Check `deployed` endpoint, stop old strategies |
