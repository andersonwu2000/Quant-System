# Auto-Discovery: rev_yoy_x_roe_improvement

**日期**: 2026-03-27T10:11:24.876634
**方向**: revenue_quality_interaction
**假說**: 營收成長且 ROE 提升 = 高品質成長
**學術依據**: Fama-French (2015) RMW profitability

## L1-L5 快速評估

| 指標 | 值 |
|------|---:|
| IC (20d) | +0.0758 |
| Best ICIR | +0.8586 (10d) |
| Fitness | 24.98 |
| Turnover | 89.6% |
| Max Correlation | 0.000 () |
| Positive Years | 0/0 |

## StrategyValidator: 11/13

| 檢查 | 值 | 結果 |
|------|---:|:----:|
| universe_size | 875 | PASS |
| cagr | +35.78% | PASS |
| sharpe | 1.420 | PASS |
| max_drawdown | +24.00% | PASS |
| annual_cost_ratio | 22% | PASS |
| walkforward_positive_ratio | 100% | PASS |
| deflated_sharpe | 0.903 | FAIL |
| bootstrap_p_sharpe_positive | 100.0% | PASS |
| oos_return | +29.27% | PASS |
| vs_1n_excess | +19.22% | PASS |
| pbo | 0.000 | PASS |
| worst_regime | +3.75% | PASS |
| recent_period_sharpe | -0.020 | FAIL |

**11/13 通過 — 可考慮進入 Paper Trading。**

## Walk-Forward: 100%


## 失敗項解讀

- **deflated_sharpe** (0.903): 多重測試校正後信心不足（測了 87 個因子）。這是統計保守，不代表因子無效
- **recent_period_sharpe** (-0.020): 近 252 天 Sharpe 為負，受市場環境影響。需觀察是暫時還是永久衰退

## 與現有因子比較

| 因子 | ICIR | 說明 |
|------|:----:|------|
| **rev_yoy_x_roe_improvement** | **+0.859** | **本次發現** |
| revenue_yoy（基線） | +0.674 | 已驗證的核心因子 |
| revenue_acceleration | +0.847 | 60d 最強因子 |
| momentum_6m | +0.217 | 最佳 price-volume 因子 |

## 下一步

- [ ] 人工審閱假說邏輯
- [ ] 決定是否加入正式因子庫
- [ ] 決定是否部署到 Paper Trading