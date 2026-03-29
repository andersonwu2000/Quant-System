# Factor Validation Report

**Date**: 2026-03-28 17:13
**Factors tested**: 25
**Validator**: 15 checks (CAGR, Sharpe, MDD, WF, DSR, Bootstrap, OOS, Benchmark, PBO, Regime, Recent, Correlation, CVaR, Universe, Cost)

---

## Summary

| Factor | Result | Score | Details |
|--------|--------|-------|---------|
| 52wk_high | **FAIL** | 13/15 | oos_sharpe, pbo |
| ad_line_63d | **FAIL** | 11/15 | cagr, oos_sharpe, vs_0050_excess |
| dual_norm_combo | **FAIL** | 13/15 | oos_sharpe, vs_0050_excess |
| efficiency_ratio_126d | **FAIL** | 13/15 | oos_sharpe, vs_0050_excess |
| efficiency_ratio_252d | **FAIL** | 12/15 | oos_sharpe, vs_0050_excess, pbo |
| liquidity_cond_stage2pass | **FAIL** | 9/15 | cagr, sharpe, max_drawdown |
| ma150_fraction_63d | **FAIL** | 13/15 | oos_sharpe, vs_0050_excess |
| ma200_fraction_63d | **FAIL** | 12/15 | oos_sharpe, vs_0050_excess, pbo |
| obv_mom_regime | **FAIL** | 9/15 | cagr, sharpe, walkforward_positive_ratio |
| obv_revaccel_combo | **FAIL** | 13/15 | oos_sharpe, vs_0050_excess |
| obv_slope | **FAIL** | 12/15 | oos_sharpe, vs_0050_excess, pbo |
| price_trend | **FAIL** | 11/15 | walkforward_positive_ratio, oos_sharpe, vs_0050_excess |
| rev_inconsistency | **FAIL** | 9/15 | cagr, sharpe, oos_sharpe |
| rev_weighted_zscore | **FAIL** | 13/15 | oos_sharpe, vs_0050_excess |
| rev_zscore | **FAIL** | 11/15 | sharpe, oos_sharpe, vs_0050_excess |
| rev_zscore_3m | **FAIL** | 10/15 | cagr, sharpe, oos_sharpe |
| revenue_accel_v1 | **FAIL** | 9/15 | cagr, sharpe, walkforward_positive_ratio |
| revenue_accel_v2 | **FAIL** | 12/15 | oos_sharpe, vs_0050_excess, pbo |
| revwz_200ma | **FAIL** | 13/15 | oos_sharpe, pbo |
| revwz_mafrac_combo | **FAIL** | 14/15 | oos_sharpe |
| robust_revz | **FAIL** | 11/15 | cagr, sharpe, oos_sharpe |
| single_month_zscore | **FAIL** | 11/15 | sharpe, oos_sharpe, vs_0050_excess |
| tsi_25_13 | **FAIL** | 12/15 | sharpe, oos_sharpe, vs_0050_excess |
| vwap_position_63d | **FAIL** | 14/15 | oos_sharpe |
| weekly_obv_52w | **FAIL** | 10/15 | cagr, sharpe, oos_sharpe |

**Passed: 0/25**
