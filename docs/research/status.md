# Autoresearch Status Report

> Updated: 2026-03-29 06:25:34

## Dashboard

| Item | Value |
|------|-------|
| Agent | Running (Up 11 minutes) |
| Watchdog | Running (Up 49 minutes) |
| Experiments | 103 |
| Keep / Discard / Crash | 31 / 72 / 0 |
| L5 OOS Passed | 46 (44.7%) |
| L0 Early Reject | 0 |
| Deployed | 0 |
| Factor-Level PBO | 0.0 (N=13/31) |
| Best Score | 21.6703 |
| Best Factor | vol-adj 6-1 mom × new high freq (L5 OOS fail, score=21.67) |

## Experiments (latest first)

| Score | ICIR | Level | Status | Description |
|------:|-----:|-------|--------|-------------|
| 20.3142 | 0.4466 | L5 | discard | weighted 4-way 2x-mom+2x-newHigh (20.31 < 20.50, equal-weight better) |
| 19.9994 | 0.4502 | L5 | discard | 5-way rank +R² (20.00 < 20.50, no improvement) |
| 20.4986 | 0.4520 | L5 | keep | 4-way rank mom+close+newHigh+monotonicity — PASSED OOS! NEW BEST=20.50! tagged factor-4way-monotonicity-best |
| 0 | 0.0000 | L1 | discard | directional Hurst proxy (no signal) |
| 7.9261 | 0.2960 | L5 | discard | multi-TF momentum consistency (large ICIR=-0.10, reverses) |
| 0 | 0.0000 | L1 | discard | neg downside vol ratio 120d (no signal) |
| 19.3941 | 0.4414 | L5 | discard | 4-way with EMA-mom (19.39 < 20.14, no improvement) |
| 0 | 0.0000 | L1 | discard | avg dist above 60d median 120d (no signal) |
| 19.1146 | 0.4370 | L5 | discard | 4-way rank mom+buyPressure+newHigh+R² (19.11 < 20.14, close-str better) |
| 9.6471 | 0.2693 | L5 | discard | neg upper shadow ratio 60d (L5 pass but score=9.65, close-str variant) |
| 6.3861 | 0.2666 | L5 | discard | vol-weighted close position 20d (L5 pass but score too low) |
| 0 | 0.0000 | L1 | discard | high-volume day return 120d (no signal) |
| 19.5821 | 0.4501 | L5 | discard | 5-way rank +drawdown (19.58 < 4-way 20.14, no improvement) |
| 20.138 | 0.4501 | L5 | keep | 4-way rank mom+close+newHigh+R² — PASSED OOS! NEW BEST=20.14! tagged factor-4way-rank-best |
| 19.6746 | 0.4369 | L5 | keep | 3-way rank vol-adj-mom+close-str+new-high — PASSED OOS! score=19.67 tagged factor-3way-mom-close-newhigh |
| 0 | -0.0390 | L2 | discard | cumulative overnight gap 120d (no signal) |
| 13.0714 | 0.3452 | L5 | keep | rank-sum buying pressure + new high freq — PASSED OOS! tagged factor-rank-buying-pressure-new-high |
| 7.6227 | 0.2277 | L5 | keep | buying pressure (close-low)/(high-low) 60d — PASSED OOS! new microstructure dim tagged factor-buying-pressure-60d |
| 17.6628 | 0.4233 | L5 | keep | rank-sum monotonicity + new high freq — PASSED OOS! tagged factor-rank-monotonicity-new-high |
| 17.0512 | 0.4220 | L5 | discard | trend monotonicity Kendall 120d (L5 OOS fail, close) |
| 0 | 0.0000 | L1 | discard | rank-sum 6-1 mom + volume trend (volume killed signal) |
| 0.75 | 0.1965 | L3 | discard | close-to-VWAP 60d (3/8 years, unstable) |
| 16.8822 | 0.4377 | L5 | keep | 3-way rank-sum R²+newHigh+drawdown — PASSED OOS! tagged factor-3way-rank-sum |
| 15.0394 | 0.4167 | L5 | keep | rank-sum drawdown prox + new high freq — PASSED OOS! tagged factor-rank-sum-drawdown-new-high |
| 16.7881 | 0.4128 | L5 | keep | rank-sum trend R² + new high freq — PASSED OOS! tagged factor-rank-sum-r2-new-high |
| 0 | 0.0000 | L1 | discard | new high acceleration recent vs earlier 60d (no signal) |
| 0 | 0.0000 | L1 | discard | price efficiency × trend R² (multiplication killed signal) |
| 18.7454 | 0.4536 | L5 | discard | price efficiency ratio 120d (L5 OOS fail, score=18.75) |
| 0 | 0.0000 | L1 | discard | volume-weighted return 120d (no signal) |
| 0 | 0.0000 | L1 | discard | vol contraction × trend R² (no signal, killed by multiplication) |
| 5.0398 | 0.2122 | L4 | discard | neg vol ratio -log(20d/120d) (fitness=2.53) |
| 0 | -0.0724 | L2 | discard | max consecutive up streak 120d (no signal) |
| 15.9401 | 0.4027 | L5 | keep | vol-weighted close × new high freq — PASSED OOS! tagged factor-vol-close-x-new-high |
| 8.6023 | 0.2689 | L5 | keep | vol-weighted close position — PASSED OOS! new microstructure dim tagged factor-vol-weighted-close-position |
| 17.467 | 0.4261 | L5 | keep | close strength × new high freq — PASSED OOS! tagged factor-close-strength-x-new-high |
| 19.0992 | 0.4682 | L5 | discard | drawdown proximity × trend R² (L5 OOS fail, score=19.10) |
| 17.314 | 0.4306 | L5 | keep | 52w high proximity × new high freq — PASSED OOS! tagged factor-52w-high-x-new-high |
| 21.6703 | 0.4925 | L5 | discard | vol-adj 6-1 mom × new high freq (L5 OOS fail, score=21.67) |
| 20.5977 | 0.4813 | L5 | keep | trend R² × new high frequency — PASSED OOS! NEW BEST! tagged factor-trend-r2-x-new-high |
| 0 | 0.0000 | L1 | discard | Frog-in-the-Pan (no signal) |
| 0 | 0.0000 | L1 | discard | negative range expansion (no signal) |
| 0 | 0.0000 | L1 | discard | gap-up ratio 60d (IC=0.018 near miss) |
| 4.1392 | 0.1925 | L4 | discard | days since 20d low (fitness=1.76) |
| 2.2537 | 0.1930 | L4 | discard | EWM return 120d (fitness=0.67) |
| 13.5227 | 0.2917 | L5 | discard | new 30d high freq 250d (L5 OOS fail, worse than 20d/120d) |
| 15.3842 | 0.4051 | L5 | discard | normalized trend slope 120d (L5 OOS fail, duplicate of R²) |
| 4.3264 | 0.2595 | L4 | discard | Bollinger position (fitness=2.05) |
| 5.4637 | 0.2043 | L4 | discard | delta close strength (fitness=2.81) |
| 15.3842 | 0.4051 | L5 | keep | trend R² × direction 120d — PASSED OOS! tagged factor-trend-r2-direction |
| 0 | 0.0000 | L1 | discard | OBV slope 60d (no signal) |
| 13.3736 | 0.3843 | L5 | keep | new 10d high frequency 60d — PASSED OOS! tagged factor-new-10d-high-frequency |
| 3.8194 | 0.2089 | L4 | discard | EMA crossover EMA20/EMA60 (fitness=1.88) |
| 0 | 0.0000 | L1 | discard | upside/downside vol ratio 60d (no signal) |
| 0 | 0.0000 | L1 | discard | positive return fraction 60d (no signal) |
| 0 | 0.0993 | L2 | discard | neg normalized ATR 20d (ICIR=0.10, vol dim still weak) |
| 12.1319 | 0.3810 | L5 | keep | drawdown proximity (close/252d peak) — PASSED OOS! tagged factor-drawdown-proximity |
| 0 | -0.0485 | L2 | discard | return autocorrelation 60d (very weak) |
| 13.2449 | 0.3101 | L5 | keep | regime-conditional momentum — PASSED OOS! tagged factor-regime-momentum |
| 0 | 0.0000 | L1 | discard | revenue at new high (no signal, 4th revenue fail) |
| 17.3249 | 0.4056 | L5 | keep | high-low frequency spread — PASSED OOS! tagged factor-high-low-frequency-spread |
| 10.4823 | 0.2851 | L5 | keep | new 20d low avoidance — PASSED OOS! tagged factor-new-low-avoidance |
| 17.7842 | 0.4250 | L5 | keep | new 20d high frequency 120d — PASSED OOS! BEST SCORE tagged factor-new-high-frequency |
| 0 | 0.0000 | L1 | discard | vol-weighted close strength 60d (worse than unweighted) |
| 0 | 0.0000 | L1 | discard | intraday direction close-open (IC=0.019 near miss) |
| 0 | 0.0000 | L1 | discard | SMA60 slope (no signal) |
| 14.397 | 0.3398 | L5 | discard | close strength × 6-1 mom (L5 OOS fail, score=14.4) |
| 9.6222 | 0.2692 | L5 | keep | intraday close strength 60d — PASSED OOS! tagged factor-intraday-close-strength |
| 0 | 0.1471 | L2 | discard | neg close-vol rank corr 60d (worse window) |
| 5.7058 | 0.2062 | L4 | keep | neg close-vol rank corr 20d (fitness=2.97, near miss) |
| 10.7609 | 0.2300 | L5 | discard | vol-adj 12-1 momentum (L5 OOS fail) |
| 0 | 0.0000 | L1 | discard | negative realized skewness 60d |
| 0 | 0.0757 | L2 | discard | negative MAX 60d (worse with longer window) |
| 0 | 0.1313 | L2 | discard | negative MAX 20d (near miss ICIR=0.13) |
| 0 | 0.0000 | L1 | discard | up-volume ratio 60d (no signal) |
| 0 | 0.0000 | L1 | discard | up-volume ratio 60d (no signal) |
| 11.9935 | 0.4266 | L5 | keep | high-low trend (close in 120d range) — PASSED OOS! tagged factor-high-low-trend |
| 0 | 0.0000 | L1 | discard | price consistency (frac positive days 120d, no signal) |
| 15.0238 | 0.3222 | L5 | keep | skip-month momentum 6-2 — PASSED OOS! tagged factor-skip-month-momentum-6-2 |
| 6.4419 | 0.1657 | L5 | discard | price deceleration (flipped, L5 OOS fail) |
| 0.25 | -0.1657 | L3 | discard | price acceleration 3m-3m (negative IC, 1/8 years) |
| 0 | 0.0000 | L1 | discard | institutional aggregate 60d net buy (only 94 syms) |
| 0 | 0.0000 | L1 | discard | revenue YoY × 6-1 momentum combo (no signal) |
| 12.991 | 0.3287 | L5 | keep | volume-confirmed 6-1 momentum — PASSED OOS! tagged factor-vol-confirmed-momentum |
| 0 | 0.0000 | L1 | discard | ROE quality (data empty, 0 PE ratios) |
| 0 | 0.0000 | L1 | discard | range compression (neg log 10d/60d range) |
| 0 | 0.1237 | L2 | discard | idiosyncratic volatility 60d |
| 4.106 | -0.1669 | L4 | keep | mean reversion (neg 20d ret) — L4, fitness too low |
| 11.8171 | 0.3230 | L5 | keep | trend strength (close/SMA200) — PASSED OOS! tagged factor-trend-strength |
| 0 | 0.1012 | L2 | discard | price-volume divergence 60d |
| 12.2488 | 0.3721 | L5 | keep | 52-week high proximity — PASSED OOS! tagged factor-52w-high-proximity |
| 0 | 0.0000 | L1 | discard | trust net buy 20d sum (only 94 syms) |
| 18.9688 | 0.4091 | L5 | keep | vol-adjusted 6-1 momentum — PASSED OOS! tagged factor-vol-adj-momentum |
| 0 | 0.0000 | L1 | discard | 3-1 momentum (too short) |
| 15.0238 | 0.3222 | L5 | keep | 6-1 momentum (OOS fail but L5 reached, 8/8 years) |
| 0 | 0.0000 | L1 | discard | volume contraction log ratio 10d/120d |
| 0 | 0.0000 | L1 | discard | amihud illiquidity 20d |
| 0 | 0.1489 | L2 | discard | volume contraction (flipped sign, same ICIR) |
| 0 | -0.1489 | L2 | discard | volume trend 20d/60d (negative=good, near miss) |
| 0 | 0.0778 | L2 | discard | low volatility anomaly (neg 60d vol) |
| 0 | 0.0000 | L1 | discard | foreign investor 20d net buy |
| 0 | 0.0000 | L1 | discard | revenue acceleration (3m vs prior 3m yoy) |
| 0 | 0.0000 | L1 | discard | revenue yoy growth (single month) |
| 0 | 0.0000 | L1 | discard | baseline 12-1 momentum |

## Kept Factors

| Score | ICIR | Level | Description |
|------:|-----:|-------|-------------|
| 15.0238 | 0.3222 | L5 | 6-1 momentum (OOS fail but L5 reached, 8/8 years) |
| 18.9688 | 0.4091 | L5 | vol-adjusted 6-1 momentum — PASSED OOS! tagged factor-vol-adj-momentum |
| 12.2488 | 0.3721 | L5 | 52-week high proximity — PASSED OOS! tagged factor-52w-high-proximity |
| 11.8171 | 0.3230 | L5 | trend strength (close/SMA200) — PASSED OOS! tagged factor-trend-strength |
| 4.106 | -0.1669 | L4 | mean reversion (neg 20d ret) — L4, fitness too low |
| 12.991 | 0.3287 | L5 | volume-confirmed 6-1 momentum — PASSED OOS! tagged factor-vol-confirmed-momentum |
| 15.0238 | 0.3222 | L5 | skip-month momentum 6-2 — PASSED OOS! tagged factor-skip-month-momentum-6-2 |
| 11.9935 | 0.4266 | L5 | high-low trend (close in 120d range) — PASSED OOS! tagged factor-high-low-trend |
| 5.7058 | 0.2062 | L4 | neg close-vol rank corr 20d (fitness=2.97, near miss) |
| 9.6222 | 0.2692 | L5 | intraday close strength 60d — PASSED OOS! tagged factor-intraday-close-strength |
| 17.7842 | 0.4250 | L5 | new 20d high frequency 120d — PASSED OOS! BEST SCORE tagged factor-new-high-frequency |
| 10.4823 | 0.2851 | L5 | new 20d low avoidance — PASSED OOS! tagged factor-new-low-avoidance |
| 17.3249 | 0.4056 | L5 | high-low frequency spread — PASSED OOS! tagged factor-high-low-frequency-spread |
| 13.2449 | 0.3101 | L5 | regime-conditional momentum — PASSED OOS! tagged factor-regime-momentum |
| 12.1319 | 0.3810 | L5 | drawdown proximity (close/252d peak) — PASSED OOS! tagged factor-drawdown-proximity |
| 13.3736 | 0.3843 | L5 | new 10d high frequency 60d — PASSED OOS! tagged factor-new-10d-high-frequency |
| 15.3842 | 0.4051 | L5 | trend R² × direction 120d — PASSED OOS! tagged factor-trend-r2-direction |
| 20.5977 | 0.4813 | L5 | trend R² × new high frequency — PASSED OOS! NEW BEST! tagged factor-trend-r2-x-new-high |
| 17.314 | 0.4306 | L5 | 52w high proximity × new high freq — PASSED OOS! tagged factor-52w-high-x-new-high |
| 17.467 | 0.4261 | L5 | close strength × new high freq — PASSED OOS! tagged factor-close-strength-x-new-high |
| 8.6023 | 0.2689 | L5 | vol-weighted close position — PASSED OOS! new microstructure dim tagged factor-vol-weighted-close-position |
| 15.9401 | 0.4027 | L5 | vol-weighted close × new high freq — PASSED OOS! tagged factor-vol-close-x-new-high |
| 16.7881 | 0.4128 | L5 | rank-sum trend R² + new high freq — PASSED OOS! tagged factor-rank-sum-r2-new-high |
| 15.0394 | 0.4167 | L5 | rank-sum drawdown prox + new high freq — PASSED OOS! tagged factor-rank-sum-drawdown-new-high |
| 16.8822 | 0.4377 | L5 | 3-way rank-sum R²+newHigh+drawdown — PASSED OOS! tagged factor-3way-rank-sum |
| 17.6628 | 0.4233 | L5 | rank-sum monotonicity + new high freq — PASSED OOS! tagged factor-rank-monotonicity-new-high |
| 7.6227 | 0.2277 | L5 | buying pressure (close-low)/(high-low) 60d — PASSED OOS! new microstructure dim tagged factor-buying-pressure-60d |
| 13.0714 | 0.3452 | L5 | rank-sum buying pressure + new high freq — PASSED OOS! tagged factor-rank-buying-pressure-new-high |
| 19.6746 | 0.4369 | L5 | 3-way rank vol-adj-mom+close-str+new-high — PASSED OOS! score=19.67 tagged factor-3way-mom-close-newhigh |
| 20.138 | 0.4501 | L5 | 4-way rank mom+close+newHigh+R² — PASSED OOS! NEW BEST=20.14! tagged factor-4way-rank-best |
| 20.4986 | 0.4520 | L5 | 4-way rank mom+close+newHigh+monotonicity — PASSED OOS! NEW BEST=20.50! tagged factor-4way-monotonicity-best |

## Alerts

None.

---
*Auto-generated by `scripts/autoresearch/status.ps1`*
