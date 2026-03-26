# Auto-Discovery: rev_seasonal_deviation

**日期**: 2026-03-27T05:14:34.668409
**方向**: seasonal_revenue_patterns
**假說**: 實際營收 vs 同行業歷史同月平均的偏離
**學術依據**: Seasonal anomalies in earnings

## L1-L5 快速評估

| 指標 | 值 |
|------|---:|
| IC (20d) | +0.0238 |
| Best ICIR | +0.5212 (60d) |
| Fitness | 8.85 |
| Turnover | 82.5% |
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
| deflated_sharpe | 0.407 | FAIL |
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