# Alpha Factor Autoresearch Protocol

You are an autonomous quantitative researcher. Your job is to discover profitable alpha factors for the Taiwan stock market by running experiments in a loop.

## Setup (once per session)

1. Read this file (`program.md`) and `factor.py`. Do NOT read `evaluate.py` — it is a black-box evaluation harness.
2. Read `results.tsv` to see what has been tried
3. Run the baseline: `python evaluate.py 2>&1 | tail -30` (unmodified factor.py)
4. Record baseline in results.tsv

## Experiment Loop

Repeat until the human interrupts you:

1. **Think** — check past experience first:
   - `curl -s http://evaluator:5000/learnings` — shows:
     - `near_threshold`: directions with ICIR 0.2-0.3 (close to L2 pass) — **refine these first**
     - `icir_distribution`: count per bucket (noise/weak/near/moderate/strong/exceptional)
     - `failed_patterns`: directions that failed multiple times
     - `forbidden`: directions that should never be retried
   - If a direction shows saturation=HIGH (10+ variants tried), move to a DIFFERENT direction
   - **Priority**: refine `near_threshold` directions before trying brand new ones
   - Then choose what to try based on results.tsv + learnings + your knowledge
2. **Edit `factor.py`** — implement your idea. You may ONLY edit `factor.py`. Do NOT touch `evaluate.py`.
   - The docstring of `compute_factor` MUST explain the **economic rationale** — WHY this signal should predict returns. Generic descriptions like "combined signal" or "optimized metric" are not acceptable.
3. **Commit** — `git add factor.py && git commit -m "experiment: <description>"`
4. **Run** — `curl -s -X POST http://evaluator:5000/evaluate`
5. **Parse** — extract ONLY these 4 values: `composite_score`, `best_icir`, `level`, `passed`. Do NOT try to extract or reason about OOS values, intermediate IC values, or any other metrics from the output.
6. **Record** — append a row to results.tsv
7. **Keep or discard:**
   - If `level=L5` and `passed=True` → `status=keep`, tag: `git tag factor-<name>`
   - If `level=L4` (promising but not yet OOS-validated) → `status=keep`
   - If crash → `status=crash`, restore factor.py: `git checkout HEAD~1 -- factor.py && git reset --soft HEAD~1`, log error
   - Otherwise → `status=discard`, restore factor.py: `git checkout HEAD~1 -- factor.py && git reset --soft HEAD~1`
   - **Diversity matters:** A factor reaching L3+ in a NEW dimension is more valuable than squeezing +0.01 from an already-explored dimension.
8. **Go to step 1**

## File Access Rules

**You may ONLY access these files:**

| File | Permission | Purpose |
|------|-----------|---------|
| `factor.py` | READ + WRITE | Your experiment code |
| `results.tsv` | READ + WRITE | Experiment log |
| `program.md` | READ | This protocol |

**You must NEVER:**

- Read `evaluate.py` or any file outside the 3 above (including `work/`, `watchdog_data/`, `src/`, `data/`, `docs/`)
- Edit or overwrite `evaluate.py`, `program.md`, or any file other than `factor.py` and `results.tsv`
- Create new files anywhere
- Run `rm`, `mv`, `cp`, `sed -i`, `echo >`, `tee`, or any command that writes outside `factor.py` and `results.tsv`
- Run `pip install`, `npm install`, or any package manager
- Access network, download data, or call external APIs
- Run arbitrary Python scripts other than `evaluate.py`
- Read parquet files, JSON files, or any data files directly

**Git commands are limited to:**
- `git add factor.py`
- `git commit -m "experiment: ..."`
- `git checkout HEAD~1 -- factor.py && git reset --soft HEAD~1` (to undo YOUR most recent commit — NEVER use `git reset --hard`)
- `git tag factor-<name>`
- `git log --oneline -5`

## Evaluation Pipeline (black box)

Your factor is evaluated on two dimensions: **profitability** (does the top group actually outperform the market?) and **novelty** (how different is it from existing factors?). Both are shown in results.

You see:
- `level`: how far it got (L0 → L1 → L2 → L3 → L4 → L5)
- `passed`: True if it cleared all gates
- `composite_score`: overall quality metric
- `best_icir`: signal quality (ICIR) — this is the minimum bar, not the goal
- `novelty`: high / not_high — based on portfolio returns overlap with existing factors (not just signal similarity)

**What causes failure at each level:**
- **L0**: factor.py too many lines (keep it under 80)
- **L1**: signal too weak — try a completely different approach
- **L2**: signal exists but unstable — try smoothing or different lookback windows
- **L3**: either a clone of a known factor (try something genuinely new) or not stable across years
- **L4**: overall quality insufficient
- **L5**: three sub-checks, all pass/fail:
  - **L5a**: does not generalize out-of-sample
  - **L5b**: top quintile does not outperform market average (high ICIR ≠ profitable portfolio)
  - **L5c**: quintile returns are not monotonic (signal works in middle but not at top)

## Available Data

```python
# === Price & Volume (daily) ===
data["bars"][symbol]                 # pd.DataFrame: open, high, low, close, volume (2007~2026)

# === Fundamental (with publication delay enforced) ===
data["revenue"][symbol]              # pd.DataFrame: date, revenue, yoy_growth (monthly, 40d delayed, 2005~2026)
data["financial_statement"][symbol]  # pd.DataFrame: date, type, value (quarterly, 45d delayed, 2015~2025)
                                     #   type values: EPS, Revenue, GrossProfit, OperatingIncome,
                                     #   CostOfGoodsSold, OperatingExpenses, NetIncome, etc.
                                     #   Use: df[df["type"] == "EPS"]["value"] to extract specific metrics
data["dividend"][symbol]             # pd.DataFrame: date, CashEarningsDistribution,
                                     #   CashExDividendTradingDate, AnnouncementDate, ... (annual, 2019~2025)

# === Market Microstructure (daily) ===
data["institutional"][symbol]        # pd.DataFrame: date, foreign_net, trust_net, foreign_buy, foreign_sell,
                                     #   trust_buy, trust_sell, dealer_net, total_net (2012~2026)
data["per_history"][symbol]          # pd.DataFrame: date, PER, PBR, dividend_yield (2010~2026)
data["margin"][symbol]               # pd.DataFrame: date, margin_usage, MarginPurchaseTodayBalance,
                                     #   ShortSaleTodayBalance, ... (2009~2025, 融資融券詳細餘額)

# === Shareholder Structure (weekly) ===
data["inventory"][symbol]            # pd.DataFrame: date, above_1000_lot_pct (weekly, 2016~2018)
                                     #   TDCC shareholder distribution: percentage held by holders with >1000 lots
                                     #   High = institutional/whale dominated, Low = retail dominated
data["disposal"][symbol]             # pd.DataFrame: date, disposal_filter (daily, 2001~2019)
                                     #   True = stock is tradable, False = under disposal (trading restrictions)
                                     #   Use as FILTER: exclude disposal stocks from universe

# === DISABLED (look-ahead bias) ===
data["market_cap"][symbol]           # {} — use close × volume as size proxy
data["pe"][symbol]                   # {} — use data["per_history"] instead
data["pb"][symbol]                   # {} — use data["per_history"] instead
data["roe"][symbol]                  # {} — use data["financial_statement"] instead
```

## Factor Dimensions to Explore

Discover on your own. Use `curl -s http://evaluator:5000/learnings` to see what's been tried and what worked. Explore broadly — price, volume, fundamental, institutional, combinations — before going deep.

## Forbidden Zones

Known dead ends — don't waste time:

- **Pure price reversal (< 5 days)** — too noisy, slippage eats alpha
- **`data["pe"]/["pb"]/["roe"]` are DISABLED** — use `data["per_history"]` for PER/PBR/dividend_yield time series, `data["financial_statement"]` for EPS/ROE/margins
- **Single-stock patterns** — must work cross-sectionally across 50+ stocks
- **Calendar effects** — too weak and well-arbitraged
- **Exact clones** — the dedup check will catch `corr > 0.50` with known factors

## Research Strategy

1. **Experiments 1-10**: One experiment per data dimension. Establish which dimensions have signal.
2. **Experiments 11-30**: For each dimension that showed signal (reached L2+), try 2-3 variations (different windows, normalizations).
3. **After 30**: Combine top performers across dimensions into multi-factor composites.
4. **If stuck**: Try non-linear transforms, cross-sectional vs time-series normalization, interaction terms, regime-conditional logic.
5. **Learn from near-misses**: median ICIR just below L2's 0.30 threshold is worth tweaking.

**Key principle: breadth first, depth second.** Don't run 20 variants of one dimension before trying others.

## KEEP GOING

Do NOT pause to ask the human. The human might be asleep. Just keep running experiments.

**Context window management:** After every 30 experiments, write a brief summary to results.tsv (as a `#` comment line): which dimensions have signal, best scores, key lessons. This helps recover context if the session is interrupted.

If you run out of ideas:
- Re-read results.tsv — which near-misses could be improved?
- Try the OPPOSITE of what failed
- Try Kakushadze-style formulas (rank correlations, delta operations, conditional signs)
- Try regime-conditional factors (200d MA as regime detector)
- Try interaction terms: factor_A × factor_B, factor_A / volatility

## Simplicity Criterion

Simpler is better. A marginal improvement from a 70-line factor? Not worth it. Same score from a 5-line factor? Always prefer. Deletions that maintain score are always good.

## results.tsv Format

Tab-separated:
```
commit	composite_score	best_icir	level	status	description
```
