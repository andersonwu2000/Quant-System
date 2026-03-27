# Auto-Discovery: rev_seasonal_deviation

**日期**: 2026-03-27T08:08:44.622530
**方向**: seasonal_revenue_patterns
**假說**: 實際營收 vs 同行業歷史同月平均的偏離
**學術依據**: Seasonal anomalies in earnings

## L1-L5 快速評估

| 指標 | 值 |
|------|---:|
| IC (20d) | +0.0480 |
| Best ICIR | +0.8144 (10d) |
| Fitness | 19.60 |
| Turnover | 82.9% |
| Max Correlation | 0.000 () |
| Positive Years | 0/0 |

## StrategyValidator: 12/13

| 檢查 | 值 | 結果 |
|------|---:|:----:|
| universe_size | 875 | PASS |
| cagr | +30.50% | PASS |
| sharpe | 1.415 | PASS |
| max_drawdown | +21.95% | PASS |
| annual_cost_ratio | 16% | PASS |
| walkforward_positive_ratio | 100% | PASS |
| deflated_sharpe | 0.880 | FAIL |
| bootstrap_p_sharpe_positive | 100.0% | PASS |
| oos_return | +39.40% | PASS |
| vs_1n_excess | +13.94% | PASS |
| pbo | 0.000 | PASS |
| worst_regime | +1.24% | PASS |
| recent_period_sharpe | 0.039 | PASS |

**12/13 通過 — 可考慮進入 Paper Trading。**

## Walk-Forward: 100%


## 失敗項解讀

- **deflated_sharpe** (0.880): 多重測試校正後信心不足（測了 85 個因子）。這是統計保守，不代表因子無效

## 與現有因子比較

| 因子 | ICIR | 說明 |
|------|:----:|------|
| **rev_seasonal_deviation** | **+0.814** | **本次發現** |
| revenue_yoy（基線） | +0.674 | 已驗證的核心因子 |
| revenue_acceleration | +0.847 | 60d 最強因子 |
| momentum_6m | +0.217 | 最佳 price-volume 因子 |

## 下一步

- [ ] 人工審閱假說邏輯
- [ ] 決定是否加入正式因子庫
- [ ] 決定是否部署到 Paper Trading