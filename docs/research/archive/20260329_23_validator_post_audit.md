# Validator Post-Audit Rerun — 2026-03-29

> After fixing 15+ issues found in BACKTEST_MECHANISM_AUDIT and CODE_REVIEW, re-run Validator to establish new baseline.

## Method Changes Since Last Run (20260328)

| Change | Affected Check | Direction |
|--------|---------------|-----------|
| turnover denominator: initial_cash → avg NAV | annual_cost_ratio | slightly stricter |
| PBO: ffill(limit=5) → fillna(0.0) | construction_sensitivity | stricter (no fake returns) |
| PBO: discard remainder rows for equal partitions | construction_sensitivity | more correct |
| Regime: sum → compound | worst_regime | less strict (compound < sum for losses) |
| Permutation: seed 1000+i → hash-derived | permutation_p | different values |
| Permutation: skip when no compute_fn | permutation_p | N/A for hand-written strategies |
| evaluate.py _run_validator: top 20% → top 15 | (evaluate.py only) | — |
| OOS info leakage: 5 channels sealed | (security) | — |

## Results

**revenue_momentum_hedged, 884 stocks, 2018-01-01 ~ 2025-12-31**

| # | Check | Value | Threshold | Result | vs Previous |
|---|-------|------:|-----------|:------:|:-----------:|
| 1 | universe_size | 884 | >= 50 | PASS | 865→884 |
| 2 | cagr | +12.83% | >= 8% | PASS | 13.03%→12.83% |
| 3 | sharpe | 0.926 | >= 0.7 | PASS | 0.944→0.926 |
| 4 | max_drawdown | 29.88% | <= 40% | PASS | same |
| 5 | annual_cost_ratio | 22% | < 50% | PASS | 21%→22% |
| 6 | temporal_consistency | 75% | >= 60% | PASS | 100%→75% |
| 7 | deflated_sharpe | 0.924 | >= 0.70 | PASS | 0.932→0.924 |
| 8 | bootstrap_p_sharpe_positive | 99.7% | >= 80% | PASS | same |
| 9 | oos_sharpe | -0.728 | >= 0.30 | **FAIL** | -0.713→-0.728 |
| 10 | vs_ew_universe | +8.66% | >= 0% | PASS | 9.07%→8.66% |
| 11 | construction_sensitivity | **0.596** | <= 0.50 | **FAIL** | **0.408→0.596** |
| 12 | worst_regime | -10.81% | >= -30% | PASS | -10.65%→-10.81% |
| 13 | recent_period_sharpe | 2.447 | >= 0 | PASS | 2.566→2.447 |
| 14 | market_correlation | 0.536 | <= 0.80 | PASS | 0.529→0.536 |
| 15 | cvar_95 | -2.22% | >= -5% | PASS | -2.20%→-2.22% |
| — | permutation_p | skipped | < 0.10 | N/A | no compute_fn |

**Result: 13/15 (permutation skipped)**

## Analysis

### construction_sensitivity 0.408 → 0.596 (FAIL)

Root cause: `fillna(0.0)` replaces `ffill(limit=5)`. Old method forward-filled missing returns (fabricating data), inflating variant correlation → artificially low PBO. New method treats missing days as 0 return (no position), which is more conservative and correct.

0.596 > 0.50 threshold means the strategy's top-N and weighting variants produce inconsistent results. This is a real finding, not an artifact.

### temporal_consistency 100% → 75%

IS period truncated due to OOS overlap fix (IS end moved earlier). Fewer WF folds → some years excluded → ratio changed.

### permutation_p: skipped

`RevenueMomentumStrategy` is hand-written without `compute_fn`. Permutation test requires a standalone factor function to shuffle cross-sectionally. Autoresearch factors (built via strategy_builder) have `_compute_fn` and will be tested.

## Deployment Status

| Condition | Status |
|-----------|:------:|
| 15 HARD_CHECKS all pass | **FAIL** (construction_sensitivity) |
| Factor-Level PBO ≤ 0.70 | N/A (no factors accumulated yet) |

**revenue_momentum_hedged is NOT deployment-eligible** under current standards. The construction_sensitivity failure indicates the strategy's equal-weight top-N construction is sensitive to N and weighting method.

## Comparison with Previous Baseline

| Metric | 20260328 (pre-audit) | 20260329 (post-audit) | Delta |
|--------|:---:|:---:|:---:|
| Total passed | 15/16 | 13/15 | -2 |
| construction_sensitivity | 0.408 PASS | 0.596 FAIL | methodology fix |
| permutation_p | 0.000 PASS | skipped | design change |
| oos_sharpe | -0.713 FAIL | -0.728 FAIL | still fail |

The pre-audit 15/16 result was inflated by ffill fabricating correlated returns in PBO calculation. Post-audit 13/15 is more honest.
