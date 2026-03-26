# Auto-Discovery: rev_accel_2nd_derivative

**日期**: 2026-03-27T05:17:38.367747
**方向**: revenue_acceleration_2nd_order
**假說**: 營收加速度的二階導數（加速度的變化率）
**學術依據**: Second-order momentum

## L1-L5 快速評估

| 指標 | 值 |
|------|---:|
| IC (20d) | +0.0228 |
| Best ICIR | +0.4705 (10d) |
| Fitness | 7.69 |
| Turnover | 85.4% |
| Max Correlation | 0.000 () |
| Positive Years | 0/0 |

## StrategyValidator: 10/13

| 檢查 | 值 | 結果 |
|------|---:|:----:|
| universe_size | 313 | PASS |
| cagr | +10.05% | PASS |
| sharpe | 0.728 | PASS |
| max_drawdown | +30.63% | PASS |
| annual_cost_ratio | 39.52% | FAIL |
| walkforward_positive_ratio | 80% | PASS |
| deflated_sharpe | 0.405 | FAIL |
| bootstrap_p_sharpe_positive | 100.0% | PASS |
| oos_return | +36.95% | PASS |
| vs_1n_excess | +2.49% | PASS |
| pbo | 0.000 | PASS |
| worst_regime | -4.07% | PASS |
| recent_period_sharpe | -1.575 | FAIL |

**10/13 通過 — 可考慮進入 Paper Trading。**

## 下一步

- [ ] 人工審閱假說邏輯
- [ ] 決定是否加入正式因子庫
- [ ] 決定是否部署到 Paper Trading