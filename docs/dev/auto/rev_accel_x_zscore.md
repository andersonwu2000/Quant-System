# Auto-Discovery: rev_accel_x_zscore

**日期**: 2026-03-27T20:18:25.568559
**方向**: factor_combination
**假說**: acceleration × z-score composite
**學術依據**: Multi-signal composite

## L1-L5 快速評估

| 指標 | 值 |
|------|---:|
| IC (20d) | +0.0470 |
| Best ICIR | +0.8478 (60d) |
| Fitness | 19.57 |
| Turnover | 88.2% |
| Max Correlation | 0.192 (revenue_acceleration) |
| Positive Years | 0/0 |

## StrategyValidator: 12/15

| 檢查 | 值 | 結果 |
|------|---:|:----:|
| universe_size | 875 | PASS |
| cagr | +19.14% | PASS |
| sharpe | 0.995 | PASS |
| max_drawdown | +25.03% | PASS |
| annual_cost_ratio | 27% | PASS |
| walkforward_positive_ratio | 83% | PASS |
| deflated_sharpe | 0.502 | FAIL |
| bootstrap_p_sharpe_positive | 99.4% | PASS |
| oos_sharpe | 3.733 | PASS |
| vs_1n_excess | +2.58% | PASS |
| pbo | 0.850 | FAIL |
| worst_regime | -7.21% | PASS |
| recent_period_sharpe | -0.888 | FAIL |
| market_correlation | 0.550 | PASS |
| cvar_95 | -2.51% | PASS |

**12/15 通過（排除 DSR: 13/15）— 未達部署門檻 (需≥14/15)，僅供觀察。**

## Walk-Forward: 83%


## 失敗項解讀

- **deflated_sharpe** (0.502): 多重測試校正後信心不足（測了 97 個因子）。這是統計保守，不代表因子無效
- **pbo** (0.850): 未達門檻
- **recent_period_sharpe** (-0.888): 近 252 天 Sharpe 為負，受市場環境影響。需觀察是暫時還是永久衰退

## 大規模 IC 驗證（865+ 支台股，103 個月）

| Factor | ICIR(5d) | ICIR(20d) | ICIR(60d) | Hit%(20d) |
|--------|:--------:|:---------:|:---------:|:---------:|
| **rev_accel_x_zscore** | +0.246 | **+0.416** | +0.530 | 68.9% |
| revenue_acceleration (基準) | +0.292 | +0.438 | +0.582 | 67.3% |
| revenue_new_high (基準) | +0.249 | +0.374 | +0.435 | 67.3% |

**大規模 ICIR(20d) = +0.416 — PASS (≥0.20)**

## 部署判定

**不符合部署條件：Validator (excl DSR) 13/15 < 14; DSR 0.502 < 0.70; recent_sharpe -0.888 < -0.10**