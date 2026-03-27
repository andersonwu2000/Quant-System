# Auto-Discovery: rev_zscore_36m

**日期**: 2026-03-27T20:49:39.208615
**方向**: revenue_surprise_magnitude
**假說**: 36 月 z-score（longer window, more stable）
**學術依據**: SUE with varying lookback

## L1-L5 快速評估

| 指標 | 值 |
|------|---:|
| IC (20d) | +0.0597 |
| Best ICIR | +0.6658 (60d) |
| Fitness | 17.65 |
| Turnover | 84.9% |
| Max Correlation | 0.033 (revenue_yoy) |
| Positive Years | 0/0 |

## StrategyValidator: 11/15

| 檢查 | 值 | 結果 |
|------|---:|:----:|
| universe_size | 875 | PASS |
| cagr | +15.33% | PASS |
| sharpe | 0.886 | PASS |
| max_drawdown | +27.95% | PASS |
| annual_cost_ratio | 27% | PASS |
| walkforward_positive_ratio | 83% | PASS |
| deflated_sharpe | 0.388 | FAIL |
| bootstrap_p_sharpe_positive | 99.3% | PASS |
| oos_sharpe | 3.993 | PASS |
| vs_1n_excess | -1.23% | FAIL |
| pbo | 0.850 | FAIL |
| worst_regime | -4.30% | PASS |
| recent_period_sharpe | -0.898 | FAIL |
| market_correlation | 0.543 | PASS |
| cvar_95 | -2.47% | PASS |

**11/15 通過（排除 DSR: 12/15）— 未達部署門檻 (需≥14/15)，僅供觀察。**

## Walk-Forward: 83%


## 失敗項解讀

- **deflated_sharpe** (0.388): 多重測試校正後信心不足（測了 100 個因子）。這是統計保守，不代表因子無效
- **vs_1n_excess** (-1.23%): 未達門檻
- **pbo** (0.850): 未達門檻
- **recent_period_sharpe** (-0.898): 近 252 天 Sharpe 為負，受市場環境影響。需觀察是暫時還是永久衰退

## 大規模 IC 驗證（865+ 支台股，92 個月）

| Factor | ICIR(5d) | ICIR(20d) | ICIR(60d) | Hit%(20d) |
|--------|:--------:|:---------:|:---------:|:---------:|
| **rev_zscore_36m** | +0.174 | **+0.359** | +0.387 | 65.2% |
| revenue_acceleration (基準) | +0.292 | +0.438 | +0.582 | 67.3% |
| revenue_new_high (基準) | +0.249 | +0.374 | +0.435 | 67.3% |

**大規模 ICIR(20d) = +0.359 — PASS (≥0.20)**

## 部署判定

**不符合部署條件：Validator (excl DSR) 12/15 < 14; DSR 0.388 < 0.70; recent_sharpe -0.898 < -0.10**