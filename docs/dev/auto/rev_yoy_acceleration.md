# Auto-Discovery: rev_yoy_acceleration

**日期**: 2026-03-27T10:21:20.859052
**方向**: seasonal_revenue_patterns
**假說**: 營收 YoY 的月度加速度（本月 YoY - 上月 YoY）
**學術依據**: Earnings momentum acceleration

## L1-L5 快速評估

| 指標 | 值 |
|------|---:|
| IC (20d) | +0.0415 |
| Best ICIR | +0.8598 (5d) |
| Fitness | 18.70 |
| Turnover | 87.8% |
| Max Correlation | 0.000 () |
| Positive Years | 0/0 |

## StrategyValidator: 12/13

| 檢查 | 值 | 結果 |
|------|---:|:----:|
| universe_size | 875 | PASS |
| cagr | +20.93% | PASS |
| sharpe | 1.097 | PASS |
| max_drawdown | +23.45% | PASS |
| annual_cost_ratio | 28% | PASS |
| walkforward_positive_ratio | 100% | PASS |
| deflated_sharpe | 0.623 | FAIL |
| bootstrap_p_sharpe_positive | 99.6% | PASS |
| oos_return | +46.79% | PASS |
| vs_1n_excess | +4.36% | PASS |
| pbo | 0.000 | PASS |
| worst_regime | +14.29% | PASS |
| recent_period_sharpe | 1.216 | PASS |

**12/13 通過 — 可考慮進入 Paper Trading。**

## Walk-Forward: 100%


## 失敗項解讀

- **deflated_sharpe** (0.623): 多重測試校正後信心不足（測了 88 個因子）。這是統計保守，不代表因子無效

## 與現有因子比較

| 因子 | ICIR | 說明 |
|------|:----:|------|
| **rev_yoy_acceleration** | **+0.860** | **本次發現** |
| revenue_yoy（基線） | +0.674 | 已驗證的核心因子 |
| revenue_acceleration | +0.847 | 60d 最強因子 |
| momentum_6m | +0.217 | 最佳 price-volume 因子 |

## 下一步

- [ ] 人工審閱假說邏輯
- [ ] 決定是否加入正式因子庫
- [ ] 決定是否部署到 Paper Trading