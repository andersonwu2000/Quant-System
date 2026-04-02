# Autoresearch Status Report

> Updated: 2026-04-02 18:15:53

## Dashboard

| Item | Value |
|------|-------|
| Agent | Running (Up 5 hours) |
| Evaluator | Running (Up 5 hours (unhealthy)) |
| Watchdog | Running (Up 5 hours) |
| Experiments | 40 |
| Keep / Discard / Crash | 0 / 40 / 0 |
| Level Distribution | L0:0 L1:26 L2:14 L3:0 L4:0 L5:0 |
| Deployed | 0 |
| Factor-Level PBO | N/A |
| ICIR Method | Method D (median \|ICIR\| ??0.30) |
| Best Score | 0 |
| Best Factor | N/A |

## Experiments (latest first)

| Score | ICIR | Level | Status | Description |
|------:|-----:|-------|--------|-------------|
| noise | noise | L1 | discard | Book value growth proxy: inferred from price / PBR decomposition over 252 days. |
| noise | noise | L1 | discard | Trailing 60-day Sharpe ratio: risk-adjusted momentum over recent two months. |
| noise | noise | L1 | discard | Foreign buy ratio 20-day: foreign_buy / (foreign_buy + foreign_sell) accumulatio |
| near | near | L2 | discard | 10-day smoothed 52-week range position: time-averaged behavioral anchoring signa |
| weak | weak | L2 | discard | Rank-averaged composite: 52w-range position + idiosyncratic momentum (equal weig |
| noise | noise | L1 | discard | Moving average ratio: 20-day MA over 60-day MA captures medium-term trend streng |
| noise | noise | L1 | discard | Dividend yield momentum: current dividend yield vs its 12-month historical avera |
| weak | weak | L2 | discard | 52w-range × idiosyncratic momentum: behavioral breakout with firm-specific exces |
| weak | weak | L2 | discard | OBV×range + idiosyncratic momentum: microstructure accumulation plus firm-specif |
| noise | noise | L2 | discard | OBV z-score × 52w-range: normalized volume accumulation at behavioral breakout l |
| weak | weak | L2 | discard | OBV momentum × 52-week range position: double-confirmation breakout signal. |
| noise | noise | L1 | discard | Chaikin Money Flow (CMF) 20-day: volume-weighted intraday close position. |
| noise | noise | L1 | discard | OBV momentum 40-day: net volume accumulation on up-days vs down-days over 40 day |
| noise | noise | L2 | discard | OBV momentum: net volume weighted by daily direction over 20 days. |
| noise | noise | L1 | discard | Gross margin improvement: recent 2-quarter gross margin vs prior 2-quarter avera |
| noise | noise | L1 | discard | Gross margin improvement: recent 2-quarter gross margin vs prior 2-quarter avera |
| noise | noise | L1 | discard | Trust fund (投信) 20-day cumulative net buying normalized by average volume. |
| noise | noise | L1 | discard | GARP (Growth at Reasonable Price): revenue YoY growth divided by price-to-book r |
| noise | noise | L1 | discard | Volume surge x intraday buying pressure: institutional accumulation signal. |
| noise | noise | L1 | discard | Volume surge x 20d intraday buying pressure: institutional accumulation. |
| noise | noise | L1 | discard | Volume surge x intraday buying pressure: institutional accumulation signal. |
| weak | weak | L2 | discard | Low realized volatility signal (negative vol = positive signal). |
| noise | noise | L1 | discard | Risk-adjusted 3-month momentum (in-sample Sharpe ratio of recent returns). |
| noise | noise | L1 | discard | Low realized volatility signal (negative vol = positive signal). |
| noise | noise | L1 | discard | Low realized volatility signal (negative vol = positive signal). |
| noise | noise | L1 | discard | EPS YoY growth from quarterly financial statements. |
| noise | noise | L1 | discard | EPS YoY growth from quarterly financial statements. |
| noise | noise | L1 | discard | Baseline: 12-1 momentum (skip most recent month). |
| noise | noise | L1 | discard | Amihud illiquidity premium signal. |
| noise | noise | L1 | discard | Baseline: 12-1 momentum (skip most recent month). |
| noise | noise | L1 | discard | Foreign institutional cumulative flow ratio signal. |
| noise | noise | L1 | discard | Revenue YoY growth acceleration signal. |
| noise | noise | L2 | discard | Revenue YoY growth acceleration signal. |
| near | near | L2 | discard | Baseline: 12-1 momentum (skip most recent month). |
| near | near | L2 | discard | Idiosyncratic momentum: firm-specific return orthogonal to market moves. |
| noise | noise | L1 | discard | Baseline: 12-1 momentum (skip most recent month). |
| noise | noise | L1 | discard | Short sale balance decline: short-squeeze pressure signal. |
| near | near | L2 | discard | 52-week range position: behavioral anchoring momentum signal. |
| noise | noise | L2 | discard | Volume-weighted intraday buying pressure: smart-money accumulation signal. |
| noise | noise | L2 | discard | Baseline: 12-1 momentum (skip most recent month). |

## Alerts

- `[2026-04-02 10:06:23] STALE: No new results for 275 minutes`
- `[2026-04-02 10:07:24] STALE: No new results for 276 minutes`
- `[2026-04-02 10:08:25] STALE: No new results for 277 minutes`
- `[2026-04-02 10:09:26] STALE: No new results for 278 minutes`
- `[2026-04-02 10:10:27] STALE: No new results for 279 minutes`
- `[2026-04-02 10:11:28] STALE: No new results for 280 minutes`
- `[2026-04-02 10:12:29] STALE: No new results for 281 minutes`
- `[2026-04-02 10:13:30] STALE: No new results for 282 minutes`
- `[2026-04-02 10:14:31] STALE: No new results for 283 minutes`
- `[2026-04-02 10:15:33] STALE: No new results for 284 minutes`

---
*Auto-generated by `scripts/autoresearch/status.ps1`*
