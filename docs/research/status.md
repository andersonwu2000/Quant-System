# Autoresearch Status Report

> Updated: 2026-04-01 10:56:42

## Dashboard

| Item | Value |
|------|-------|
| Agent | Running (Up 6 hours) |
| Evaluator | Running (Up About an hour (healthy)) |
| Watchdog | Running (Up 7 hours) |
| Experiments | 99 |
| Keep / Discard / Crash | 0 / 99 / 0 |
| Level Distribution | L0:0 L1:54 L2:45 L3:0 L4:0 L5:0 |
| Deployed | 0 |
| Factor-Level PBO | N/A |
| ICIR Method | Method D (median \|ICIR\| ??0.30) |
| Best Score | 0 |
| Best Factor | N/A |

## Experiments (latest first)

| Score | ICIR | Level | Status | Description |
|------:|-----:|-------|--------|-------------|
| noise | noise | L1 | discard | Volume-weighted return 120d: each daily return is weighted by its |
| noise | noise | L2 | discard | Overnight gap momentum: cumulative overnight return (open/prev close) |
| near | near | L2 | discard | Pain ratio 120d: return divided by average drawdown (not max). |
| noise | noise | L1 | discard | Long-term Calmar ratio 240d: annual return over max drawdown. The |
| near | near | L2 | discard | Calmar ratio 120d: return over max drawdown. Unlike return/volatility |
| near | near | L2 | discard | Weighted new high frequency: count of new 252d high days in the last |
| near | near | L2 | discard | New high count: fraction of days in the past 120 days where close |
| noise | noise | L2 | discard | Quiet momentum acceleration: change in quiet momentum signal between |
| noise | noise | L1 | discard | Volume asymmetry 120d: log ratio of average volume on up-close days |
| noise | noise | L1 | discard | Volume asymmetry 120d: log ratio of average volume on up-close days |
| weak | weak | L2 | discard | Smoothed stochastic position: EWM of daily (close-low)/(high-low) |
| near | near | L2 | discard | Smoothed stochastic position: EWM of daily (close-low)/(high-low) |
| near | near | L2 | discard | Smoothed stochastic position: EWM of daily (close-low)/(high-low) |
| noise | noise | L1 | discard | Garman-Klass adjusted momentum: 120-day return normalized by |
| noise | noise | L1 | discard | Drawdown recovery speed: how quickly stocks recover from their |
| noise | noise | L1 | discard | Foreign flow momentum: slope of cumulative foreign net buying over |
| noise | noise | L1 | discard | PER compression: negative change in PER over 120 days while stock |
| noise | noise | L1 | discard | Ranked quiet momentum: 120d return / mean intraday range, then |
| noise | noise | L1 | discard | Idiosyncratic momentum: stock-specific return after removing the |
| noise | noise | L1 | discard | Idiosyncratic momentum: stock-specific return after removing the |
| noise | noise | L1 | discard | Idiosyncratic momentum: stock-specific return after removing the |
| noise | noise | L1 | discard | Directional variance ratio: variance ratio signed by the direction of |
| near | near | L2 | discard | Directional variance ratio: variance ratio signed by the direction of |
| noise | noise | L2 | discard | Variance ratio: ratio of 5-day return variance to 5x daily return |
| noise | noise | L2 | discard | Price efficiency ratio 120d: net price change divided by total absolute |
| noise | noise | L1 | discard | Cumulative intraday return over 60 days: sum of (close/open - 1). |
| noise | noise | L1 | discard | Cumulative intraday return over 60 days: sum of (close/open - 1). |
| near | near | L2 | discard | Price efficiency ratio: net price change divided by sum of absolute |
| near | near | L2 | discard | Price efficiency ratio: net price change divided by sum of absolute |
| weak | weak | L2 | discard | Price efficiency ratio: net price change divided by sum of absolute |
| noise | noise | L1 | discard | Trend linearity: sign(slope) × R² of linear fit to log-prices over |
| noise | noise | L1 | discard | Trend linearity: sign(slope) × R² of linear fit to log-prices over |
| noise | noise | L1 | discard | Chaikin money flow 60d: volume-weighted close position in daily range, |
| noise | noise | L1 | discard | Chaikin money flow 60d: volume-weighted close position in daily range, |
| noise | noise | L1 | discard | Chaikin money flow 60d: volume-weighted close position in daily range, |
| noise | noise | L1 | discard | Negative dealer net flow 40d: dealers in Taiwan hedge their structured |
| weak | weak | L2 | discard | Close position in daily range: average of (close-low)/(high-low) over |
| weak | weak | L2 | discard | Close position in daily range: average of (close-low)/(high-low) over |
| weak | weak | L2 | discard | Close position in daily range: average of (close-low)/(high-low) over |
| noise | noise | L2 | discard | Volume concentration ratio: fraction of total 60d volume occurring |
| near | near | L2 | discard | Volume concentration ratio: fraction of total 60d volume occurring |
| near | near | L2 | discard | Smoothed quiet momentum 120d: 120-day return divided by EWM range |
| near | near | L2 | discard | Quiet momentum 120d with volume confirmation: 120-day return divided |
| near | near | L2 | discard | Quiet momentum 120d with volume confirmation: 120-day return divided |
| noise | noise | L1 | discard | Multi-window quiet momentum: average of quiet momentum scores across |
| near | near | L2 | discard | Multi-window quiet momentum: average of quiet momentum scores across |
| near | near | L2 | discard | Quiet trend: log return over 120 days divided by median daily range |
| near | near | L2 | discard | Quiet momentum 120d with true range: 120-day return divided by average |
| weak | weak | L2 | discard | Quiet momentum 120d with true range: 120-day return divided by average |
| near | near | L2 | discard | Quiet momentum 120d skip-5d: 120-day return (skipping last 5 days) |
| noise | noise | L1 | discard | Quiet momentum 180d: 180-day return divided by average intraday |
| noise | noise | L1 | discard | Quiet momentum 90d with skip: 90-day return (skipping last 5d) divided |
| noise | noise | L1 | discard | Quiet momentum (60d window): 60-day return divided by average |
| weak | weak | L2 | discard | Quiet momentum (60d window): 60-day return divided by average |
| near | near | L2 | discard | Intraday-to-overnight return ratio: ratio of average intraday return |
| noise | noise | L2 | discard | Classic 12-month momentum skipping most recent month (Jegadeesh-Titman). |
| noise | noise | L1 | discard | Abnormal volume decline with positive momentum: stocks where volume is |
| noise | noise | L1 | discard | Abnormal volume decline with positive momentum: stocks where volume is |
| noise | noise | L2 | discard | Total institutional flow persistence: sum of all three institutional |
| noise | noise | L2 | discard | Negative intraday range (narrow range anomaly): average (high-low)/close |
| noise | noise | L1 | discard | Exponentially decay-weighted momentum 120d: recent returns get more |
| noise | noise | L1 | discard | Exponentially decay-weighted momentum 120d: recent returns get more |
| weak | weak | L2 | discard | Volume-return asymmetry: difference between average returns on up-volume |
| noise | noise | L1 | discard | Volume-return asymmetry: difference between average returns on up-volume |
| noise | noise | L1 | discard | Pure 60-day momentum: raw 60-day return captures intermediate-term |
| noise | noise | L1 | discard | Pure 60-day momentum: raw 60-day return captures intermediate-term |
| noise | noise | L1 | discard | Frog-in-the-pan momentum: 120d return sign-weighted by information |
| noise | noise | L1 | discard | 60-day mean reversion (contrarian): stocks that fell the most over 60 |
| noise | noise | L1 | discard | Frog-in-the-pan momentum: 120d return sign-weighted by information |
| noise | noise | L1 | discard | Frog-in-the-pan momentum: 120d return sign-weighted by information |
| noise | noise | L1 | discard | Price trend strength via 200d moving average slope: normalized slope |
| noise | noise | L1 | discard | Price trend strength via 200d moving average slope: normalized slope |
| noise | noise | L1 | discard | Price trend strength via 200d moving average slope: normalized slope |
| weak | weak | L2 | discard | Margin usage decline 60d: declining margin usage signals reduced |
| weak | weak | L2 | discard | Momentum-quality composite: 120d return (skip 20d) divided by realized |
| noise | noise | L1 | discard | Momentum-quality composite: 120d return (skip 20d) divided by realized |
| noise | noise | L1 | discard | High-volume day returns: average return on days when volume exceeds |
| noise | noise | L2 | discard | Margin usage 60-day change (negative). Declining margin usage means |
| noise | noise | L1 | discard | High-volume day returns: average return on days when volume exceeds |
| noise | noise | L1 | discard | Negative PBR (value factor): stocks with low price-to-book ratios |
| noise | noise | L1 | discard | Idiosyncratic volatility (negative): low-idiovol stocks outperform |
| noise | noise | L1 | discard | Trend consistency score: fraction of 5-day rolling windows showing |
| noise | noise | L1 | discard | Trend consistency score: fraction of 5-day rolling windows showing |
| noise | noise | L1 | discard | Return skewness 60d: stocks with negative return skewness (more small |
| noise | noise | L1 | discard | Return skewness 60d: stocks with negative return skewness (more small |
| noise | noise | L2 | discard | Baseline: simple 20-day return. Starting point ??replace with your own factor lo |
| noise | noise | L2 | discard | Negative max daily return (anti-lottery): stocks with extreme positive |
| noise | noise | L1 | discard | Negative max daily return (anti-lottery): stocks with extreme positive |
| weak | weak | L2 | discard | 120-day momentum with 20-day skip. |
| weak | weak | L2 | discard | Volatility contraction with upward bias: ratio of recent (10d) range |
| weak | weak | L2 | discard | Volatility contraction with upward bias: ratio of recent (10d) range |
| noise | noise | L2 | discard | Baseline: simple 20-day return. Starting point ??replace with your own factor lo |
| weak | weak | L2 | discard | Baseline: simple 20-day return. Starting point ??replace with your own factor lo |
| weak | weak | L2 | discard | Quality momentum: 6-month return (skip last 5d) divided by 1-year |
| noise | noise | L1 | discard | Volume-weighted average price position: close relative to VWAP-like |
| noise | noise | L1 | discard | Investment trust (投信) net buying intensity: Taiwan investment trusts |
| noise | noise | L1 | discard | On-balance volume (OBV) trend: cumulative volume flow direction over 60d. |
| noise | noise | L1 | discard | Return consistency: fraction of positive weekly returns over 6 months. |
| noise | noise | L1 | discard | Baseline: 12-1 momentum (skip most recent month). |

## Alerts

- `[2026-04-01 02:46:29] STALE: No new results for 187 minutes`
- `[2026-04-01 02:47:31] STALE: No new results for 188 minutes`
- `[2026-04-01 02:48:33] STALE: No new results for 189 minutes`
- `[2026-04-01 02:49:35] STALE: No new results for 190 minutes`
- `[2026-04-01 02:50:37] STALE: No new results for 191 minutes`
- `[2026-04-01 02:51:39] STALE: No new results for 192 minutes`
- `[2026-04-01 02:52:41] STALE: No new results for 193 minutes`
- `[2026-04-01 02:53:43] STALE: No new results for 194 minutes`
- `[2026-04-01 02:54:45] STALE: No new results for 195 minutes`
- `[2026-04-01 02:55:47] STALE: No new results for 196 minutes`

---
*Auto-generated by `scripts/autoresearch/status.ps1`*
