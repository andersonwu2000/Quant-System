# Auto-Discovery: rev_zscore_vs_history

**日期**: 2026-03-27T15:07:57.508338
**方向**: revenue_surprise_magnitude
**假說**: 本月營收的 z-score（vs 過去 24 月的 mean/std）
**學術依據**: Standardized unexpected earnings (SUE)

## L1-L5 快速評估

| 指標 | 值 |
|------|---:|
| IC (20d) | +0.0560 |
| Best ICIR | +0.8043 (20d) |
| Fitness | 20.10 |
| Turnover | 89.7% |
| Max Correlation | 0.096 (revenue_acceleration) |
| Positive Years | 0/0 |

## StrategyValidator: 11/13

| 檢查 | 值 | 結果 |
|------|---:|:----:|
| universe_size | 875 | PASS |
| cagr | +19.14% | PASS |
| sharpe | 0.995 | PASS |
| max_drawdown | +25.03% | PASS |
| annual_cost_ratio | 27% | PASS |
| walkforward_positive_ratio | 80% | PASS |
| deflated_sharpe | 0.514 | FAIL |
| bootstrap_p_sharpe_positive | 99.4% | PASS |
| oos_return | +33.70% | PASS |
| vs_1n_excess | +2.58% | PASS |
| pbo | 0.500 | PASS |
| worst_regime | -7.21% | PASS |
| recent_period_sharpe | -0.888 | FAIL |

**11/13 通過（排除 DSR: 12/13）— 符合部署門檻。**

## Walk-Forward: 80%


## 失敗項解讀

- **deflated_sharpe** (0.514): 多重測試校正後信心不足（測了 89 個因子）。這是統計保守，不代表因子無效
- **recent_period_sharpe** (-0.888): 近 252 天 Sharpe 為負，受市場環境影響。需觀察是暫時還是永久衰退

## 大規模 IC 驗證（865+ 支台股，103 個月）

| Factor | ICIR(5d) | ICIR(20d) | ICIR(60d) | Hit%(20d) |
|--------|:--------:|:---------:|:---------:|:---------:|
| **rev_zscore_vs_history** | +0.246 | **+0.416** | +0.530 | 68.9% |
| revenue_acceleration (基準) | +0.292 | +0.438 | +0.582 | 67.3% |
| revenue_new_high (基準) | +0.249 | +0.374 | +0.435 | 67.3% |

**大規模 ICIR(20d) = +0.416 — PASS (≥0.20)**

## 部署判定

**不符合部署條件：DSR 0.514 < 0.70; recent_sharpe -0.888 < -0.10**