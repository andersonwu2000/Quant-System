# Factor Library Deduplication Report

**Date**: 2026-03-27
**Data**: TW50 stocks (`data/tw50_5yr.pkl`), 52 symbols, 2019-01 to 2025-12
**Method**: Pairwise IC time-series correlation (rank IC with 5-day forward returns)

## Summary

| Metric | Count |
|--------|-------|
| Total technical factors analyzed | 59 (of 66 in FACTOR_REGISTRY; 7 non-vectorized skipped) |
| Redundant pairs (IC corr > 0.8) | 39 |
| Useless factors (\|IC\| < 0.01) | 24 |
| Unique factors flagged | 35 |
| Remaining clean factors | 24 |

**Non-vectorized factors not analyzed**: adx, cci, williams_r, stochastic_k, beta, idio_skew, price_delay (require special computation or market returns)

---

## 1. Redundant Pairs (|IC time-series correlation| > 0.8)

Sorted by descending |correlation|:

| Factor A | Factor B | IC Corr | Recommend Remove | Reason |
|----------|----------|---------|-----------------|--------|
| gap | overnight_ret | +1.0000 | overnight_ret | Identical formula (open/close_prev - 1) |
| bollinger_pos | mean_reversion | -0.9980 | bollinger_pos | Both measure deviation from MA |
| momentum | momentum_12m | +0.9971 | momentum | momentum_12m has slightly better IC |
| max_daily_ret | max_ret | +0.9963 | max_ret | Both rolling max return, different windows |
| atr_ratio | hl_range | +0.9907 | hl_range | Both measure price range relative to price |
| atr_ratio | volatility | +0.9868 | atr_ratio | All in volatility cluster |
| ivol | volatility | +0.9801 | volatility | ivol has better IC (residual vol > total vol) |
| hl_range | volatility | +0.9793 | hl_range | Volatility cluster |
| atr_ratio | ivol | +0.9778 | atr_ratio | Volatility cluster |
| hl_range | ivol | +0.9729 | hl_range | Volatility cluster |
| max_daily_ret | volatility | +0.9611 | max_daily_ret | Volatility cluster |
| max_ret | volatility | +0.9603 | max_ret | Volatility cluster |
| alpha_3 | alpha_6 | +0.9552 | alpha_3 | Both open-volume correlation variants |
| alpha_101 | alpha_33 | -0.9507 | alpha_101 | Both intraday return variants |
| atr_ratio | max_daily_ret | +0.9458 | max_daily_ret | Volatility cluster |
| atr_ratio | max_ret | +0.9443 | max_ret | Volatility cluster |
| hl_range | max_daily_ret | +0.9438 | hl_range | Volatility cluster |
| alpha_33 | intraday_ret | -0.9433 | alpha_33 | Intraday return cluster |
| hl_range | max_ret | +0.9420 | hl_range | Volatility cluster |
| ivol | max_daily_ret | +0.9419 | max_daily_ret | Volatility cluster |
| ivol | max_ret | +0.9389 | max_ret | Volatility cluster |
| alpha_101 | intraday_ret | +0.9229 | alpha_101 | Intraday return cluster |
| alpha_14 | alpha_6 | +0.8992 | alpha_14 | Open-volume correlation family |
| bollinger_pos | rsi | +0.8729 | bollinger_pos | Mean-reversion/overbought family |
| mean_reversion | rsi | -0.8727 | mean_reversion | Mean-reversion/overbought family |
| alpha_33 | alpha_38 | +0.8726 | alpha_38 | Close/open ratio family |
| alpha_14 | alpha_3 | +0.8630 | alpha_3 | Open-volume family |
| alpha_101 | alpha_38 | -0.8534 | alpha_38 | Intraday return family |
| alpha_18 | alpha_33 | +0.8292 | alpha_33 | Close-open diff family |
| alpha_16 | alpha_44 | +0.8263 | alpha_44 | High-volume covariance family |
| alpha_38 | intraday_ret | -0.8254 | alpha_38 | Intraday return family |
| alpha_40 | alpha_6 | +0.8250 | alpha_40 | High-volume correlation family |
| alpha_3 | alpha_40 | +0.8180 | alpha_3 | Open-volume family |
| alpha_4 | mean_reversion | +0.8120 | alpha_4 | Low rank = mean-reversion proxy |
| alpha_4 | bollinger_pos | -0.8109 | alpha_4 | Low rank = mean-reversion proxy |
| illiquidity | lt_reversal | +0.8077 | illiquidity | Both capture low-liquidity/past-loser effect |
| alpha_18 | intraday_ret | -0.8073 | intraday_ret | Intraday return family |
| alpha_101 | alpha_18 | -0.8038 | alpha_101 | Intraday return family |
| alpha_13 | alpha_16 | +0.8028 | alpha_13 | Rank covariance family |

### Redundancy Clusters Identified

1. **Volatility cluster** (6 factors): volatility, ivol, atr_ratio, hl_range, max_ret, max_daily_ret
   - **Keep**: ivol (|IC|=0.0251, highest in cluster)
2. **Mean-reversion cluster** (4 factors): mean_reversion, bollinger_pos, rsi, alpha_4
   - **Keep**: rsi (|IC|=0.0151)
3. **Intraday return cluster** (4 factors): intraday_ret, alpha_33, alpha_101, alpha_38
   - **Keep**: alpha_18 (|IC|=0.0390, correlated with all)
4. **Open-volume correlation cluster** (4 factors): alpha_3, alpha_6, alpha_14, alpha_40
   - **Keep**: none (all have |IC| < 0.01)
5. **Gap/overnight** (2 factors): gap, overnight_ret
   - **Keep**: gap (identical, pick one)

---

## 2. Useless Factors (|IC mean| < 0.01)

| Factor | IC Mean | ICIR | Also Redundant? |
|--------|---------|------|-----------------|
| vpt | +0.0012 | +0.0065 | No |
| alpha_2 | -0.0015 | -0.0087 | No |
| macd_hist | -0.0020 | -0.0087 | No |
| alpha_3 | -0.0028 | -0.0163 | Yes (with alpha_6) |
| vol_momentum | +0.0028 | +0.0145 | No |
| alpha_14 | -0.0030 | -0.0175 | Yes (with alpha_6) |
| alpha_13 | +0.0032 | +0.0182 | Yes (with alpha_16) |
| alpha_6 | -0.0033 | -0.0190 | Yes (with alpha_3) |
| alpha_4 | -0.0035 | -0.0167 | Yes (with mean_reversion) |
| alpha_7 | +0.0039 | +0.0222 | No |
| alpha_22 | -0.0044 | -0.0273 | No |
| alpha_30 | +0.0050 | +0.0331 | No |
| bollinger_pos | +0.0055 | +0.0245 | Yes (with mean_reversion) |
| alpha_15 | -0.0056 | -0.0339 | No |
| mean_reversion | -0.0056 | -0.0251 | Yes (with rsi) |
| alpha_40 | +0.0061 | +0.0328 | Yes (with alpha_6) |
| alpha_19 | +0.0082 | +0.0391 | No |
| alpha_8 | +0.0082 | +0.0389 | No |
| alpha_44 | -0.0084 | -0.0494 | Yes (with alpha_16) |
| alpha_20 | -0.0086 | -0.0423 | No |
| gap | +0.0091 | +0.0394 | Yes (with overnight_ret) |
| overnight_ret | +0.0091 | +0.0394 | Yes (with gap) |
| alpha_16 | +0.0098 | +0.0567 | Yes (with alpha_44) |
| alpha_12 | +0.0100 | +0.0570 | No |

---

## 3. Recommended Actions

### Factors to Mark as Redundant (35 total)

**Redundancy-only** (flagged due to high correlation with better factor):
- `momentum` -- corr +0.997 with momentum_12m
- `volatility` -- corr +0.980 with ivol
- `max_ret` -- corr +0.996 with max_daily_ret
- `max_daily_ret` -- corr +0.942 with ivol
- `atr_ratio` -- corr +0.978 with ivol
- `hl_range` -- corr +0.973 with ivol
- `illiquidity` -- corr +0.808 with lt_reversal
- `alpha_101` -- corr -0.804 with alpha_18
- `alpha_33` -- corr +0.829 with alpha_18
- `alpha_38` -- corr +0.873 with alpha_33
- `intraday_ret` -- corr -0.807 with alpha_18

**Useless-only** (|IC| < 0.01, no high redundancy):
- `vpt`, `alpha_2`, `macd_hist`, `vol_momentum`, `alpha_7`, `alpha_22`, `alpha_30`, `alpha_15`, `alpha_19`, `alpha_8`, `alpha_20`, `alpha_12`

**Both redundant AND useless**:
- `bollinger_pos`, `mean_reversion`, `gap`, `overnight_ret`, `alpha_3`, `alpha_4`, `alpha_6`, `alpha_13`, `alpha_14`, `alpha_16`, `alpha_40`, `alpha_44`

### Factors to Keep (24 surviving from 59 analyzed + 7 not analyzed)

| Factor | IC Mean | ICIR | Category |
|--------|---------|------|----------|
| momentum_12m | +0.0409 | +0.146 | Momentum |
| alpha_18 | +0.0390 | +0.201 | Kakushadze (best ICIR) |
| momentum_6m | +0.0366 | +0.134 | Momentum |
| close_to_high | -0.0372 | -0.145 | Technical |
| alpha_1 | -0.0336 | -0.181 | Kakushadze |
| lt_reversal | -0.0321 | -0.109 | Reversal |
| alpha_24 | +0.0307 | +0.144 | Kakushadze |
| alpha_53 | +0.0265 | +0.131 | Kakushadze |
| ivol | +0.0251 | +0.078 | Volatility (cluster rep) |
| alpha_10 | +0.0250 | +0.130 | Kakushadze |
| alpha_9 | +0.0243 | +0.118 | Kakushadze |
| ma_cross | +0.0234 | +0.092 | Technical |
| price_accel | -0.0212 | -0.096 | Technical |
| alpha_34 | +0.0200 | +0.108 | Kakushadze |
| obv_trend | +0.0171 | +0.086 | Volume |
| reversal | +0.0169 | +0.071 | Reversal |
| turnover_vol | -0.0160 | -0.103 | Liquidity |
| zero_days | +0.0154 | +0.097 | Liquidity |
| rsi | +0.0151 | +0.067 | Mean-reversion (cluster rep) |
| alpha_35 | +0.0134 | +0.068 | Kakushadze |
| momentum_1m | +0.0134 | +0.054 | Momentum |
| skewness | -0.0125 | -0.079 | Distribution |
| alpha_23 | +0.0124 | +0.064 | Kakushadze |
| alpha_17 | +0.0101 | +0.052 | Kakushadze |

---

## 4. Factor Count Summary

| Category | Before | After | Removed |
|----------|--------|-------|---------|
| Technical factors (vectorized) | 59 | 24 | 35 |
| Non-vectorized (not analyzed) | 7 | 7 | 0 |
| **Total FACTOR_REGISTRY** | **66** | **31** | **35** |
| Fundamental factors | 17 | 17 | 0 (not analyzed) |

**Note**: No factors were deleted from FACTOR_REGISTRY for backward compatibility. Redundant/useless factors are marked with comments only.
