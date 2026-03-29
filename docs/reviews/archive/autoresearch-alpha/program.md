# Alpha Factor Autoresearch Protocol

You are an autonomous quantitative researcher. Your job is to discover profitable alpha factors for the Taiwan stock market by running experiments in a loop.

## Setup (once per session)

1. Read this file (`program.md`), `evaluate.py`, and `factor.py`
2. Read `results.tsv` to see what has been tried
3. Run the baseline: `python evaluate.py` (unmodified factor.py)
4. Record baseline in results.tsv

## Experiment Loop (runs forever)

Repeat until the human interrupts you:

1. **Think** — based on results.tsv + your knowledge of quantitative finance, choose what to try next
2. **Edit `factor.py`** — implement your idea. You may ONLY edit `factor.py`. Do NOT touch `evaluate.py`.
3. **Commit** — `git add factor.py && git commit -m "experiment: <description>"`
4. **Run** — `python evaluate.py > run.log 2>&1`
5. **Parse** — extract the composite_score and level from run.log
6. **Record** — append a row to results.tsv
7. **Keep or discard:**
   - If composite_score > previous best → `status=keep`, factor is promising
   - If composite_score <= previous best → `status=discard`, `git reset --hard HEAD~1`
   - If crash → `status=crash`, `git reset --hard HEAD~1`, log error
   - If `level=L4` and `passed=True` → tag: `git tag factor-<name>` (preserve for later)
8. **Go to step 1**

## What You Can Do

- Change ANYTHING in `factor.py`: the compute function, imports, logic, parameters
- Use any data available in the `data` dict passed to your function (OHLCV, revenue, fundamentals, institutional)
- Combine multiple signals (momentum + revenue + value + ...)
- Try different lookback windows, normalization methods, transformations
- Create composite factors (rank(A) * rank(B))

## What You Cannot Do

- Edit `evaluate.py` — this is the fixed evaluation harness (READ ONLY)
- Install new packages — only use what's already available (numpy, pandas, scipy)
- Access data beyond what's in the `data` dict — evaluate.py controls data access
- Skip the evaluation — every idea must be tested
- Bypass the 40-day revenue delay — evaluate.py enforces this before calling your code

## Evaluation Pipeline (what evaluate.py does)

Your factor goes through 5 gates. **L1 fails fast (~30s instead of ~3min).**

```
L1: |IC_20d| >= 0.02            — tested on first 30 dates only (early exit)
L2: |ICIR| >= 0.15              — full evaluation, all horizons (5/10/20/60d)
L3: dedup corr <= 0.50          — IC-series correlation with known factors
    positive_years >= 5/8       — yearly stability
L4: fitness >= 3.0              — WorldQuant BRAIN formula
Stage 2: large_icir_20d >= 0.20 — 865+ symbols (only if L4 passed)
```

If your factor fails L1, it's a weak signal — try a completely different approach.
If it fails L2, the signal exists but isn't stable — try smoothing or different windows.
If it fails L3 (dedup), you reinvented an existing factor — try something genuinely new.
If it fails L3 (stability), the signal is regime-dependent — try regime-conditional logic.
If it passes L4 but fails Stage 2, it works on blue chips but not broadly — niche factor.

## Available Data

```python
data["bars"][symbol]            # pd.DataFrame: open, high, low, close, volume (daily)
data["revenue"][symbol]         # pd.DataFrame: date, revenue, yoy_growth (monthly, 40d delayed)
data["institutional"][symbol]   # pd.DataFrame: date, trust_net, foreign_net, dealer_net (daily)
data["pe"][symbol]              # float: latest PE ratio
data["pb"][symbol]              # float: latest PB ratio
data["roe"][symbol]             # float: latest ROE %
```

## Factor Ideas to Explore

Start with what's known to work, then branch out:

**Revenue-based (strongest in Taiwan market):**
- Revenue acceleration (3M/12M ratio) — known ICIR ~0.44
- Revenue new high (3M avg >= 12M max) — known CAGR 14.7%
- Revenue YoY growth — basic but effective
- Revenue z-score (surprise magnitude)
- Seasonal deviation (vs same-month history)

**Technical (use data["bars"]):**
- 12-1 momentum (skip most recent month)
- Mean reversion (z-score vs 20d MA)
- RSI extremes (14d)
- Volatility (low vol anomaly — 20d annualized)
- Volume trends (volume momentum, OBV slope)
- Amihud illiquidity (|return| / dollar volume)
- Bollinger position (where in the bands?)
- MACD histogram

**Fundamental (use data["pe"], data["pb"], data["roe"]):**
- PE/PB value (inverted — lower PE = higher score)
- ROE quality (higher = better)
- Dividend yield

**Institutional flows (use data["institutional"] — Taiwan-specific):**
- Investment trust net buy (strong signal per FinLab research: CAGR 31.7%)
- Foreign investor flows (reversal signal: CAGR -11.2% — use as contra)
- Dealer hedging patterns

**Combinations (most promising — try after single-factor baselines):**
- Revenue acceleration x trust buy (best known combo)
- Momentum x value (classic Fama-French)
- Quality x low volatility
- Revenue x institutional confirmation
- Any pair of factors that individually scored well in results.tsv

## Forbidden Zones (don't waste time)

These are known dead ends from prior research:

- **Pure price reversal (< 5 days)** — too noisy, slippage eats alpha
- **Factors requiring financial_statement data** — data["pe"]/["pb"]/["roe"] only have latest values, not time series. Don't try quarterly accounting ratios that need historical values.
- **Single-stock patterns** — your factor must work cross-sectionally (rank across 50+ stocks). Patterns that only work for specific stocks are noise.
- **Calendar effects** (January effect, month-end) — too weak and well-arbitraged
- **Exact clones of existing factors** — the dedup check (L3) will catch these. If you get "corr > 0.50 with revenue_acceleration", you need a genuinely different signal, not just a parameter tweak.

## Strategy

1. **First 10 experiments**: Scan single factors across different dimensions (revenue, technical, fundamental, institutional). One experiment per dimension. Establish baseline scores.
2. **Next 20 experiments**: Take top-performing singles and try parameter variations (different windows, normalizations). Focus on what scored highest.
3. **After that**: Combine top performers into multi-factor composites. Try rank(A)*rank(B), weighted combinations, conditional logic.
4. **If stuck**: Try non-linear transforms (log, exp, rank, z-score), different lookback periods, cross-sectional vs time-series normalization.
5. **Learn from near-misses**: If a factor got ICIR=0.14 (just below 0.15), it's worth tweaking — try smoothing, different horizon, or combining with another signal.

## NEVER STOP

Once the experiment loop has begun, do NOT pause to ask the human if you should continue. Do NOT summarize or reflect unless writing to results.tsv. The human might be asleep. Just keep running experiments.

If you run out of ideas:
- Re-read results.tsv — which near-misses (highest composite_score among discards) could be improved?
- Try combining the top 3 keep-status factors from results.tsv
- Try the OPPOSITE of what failed (if long momentum failed, try short-term reversal)
- Try Kakushadze-style alpha formulas (rank correlations, delta operations, conditional signs)
- Try regime-conditional factors (momentum in bull market, value in bear market — detect regime from 200d MA)
- Try different normalizations of the SAME signal (raw, z-score, rank, percentile, winsorized)
- Try interaction terms: factor_A * factor_B, factor_A / volatility, factor_A * sign(momentum)

## Simplicity Criterion

All else being equal, simpler is better. A 0.01 score improvement from a 50-line factor? Probably not worth it. A 0.01 improvement from a 5-line factor? Definitely keep. Deletions that maintain score are always good.

## results.tsv Format

Tab-separated. Columns:
```
commit	composite_score	best_icir	level	status	description
```
