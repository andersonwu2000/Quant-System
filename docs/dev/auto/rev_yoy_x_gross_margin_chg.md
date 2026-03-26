# Auto-Discovery: rev_yoy_x_gross_margin_chg

**日期**: 2026-03-27T05:26:41.455395
**方向**: revenue_quality_interaction
**假說**: 營收成長且毛利率同步改善 = 真需求增長（非削價搶市）
**學術依據**: Novy-Marx (2013) gross profitability + revenue momentum

## L1-L5 快速評估

| 指標 | 值 |
|------|---:|
| IC (20d) | +0.0712 |
| Best ICIR | +0.8022 (60d) |
| Fitness | 22.78 |
| Turnover | 88.3% |
| Max Correlation | 0.000 () |
| Positive Years | 0/0 |

## StrategyValidator: 10/13

| 檢查 | 值 | 結果 |
|------|---:|:----:|
| universe_size | 313 | PASS |
| cagr | +10.05% | PASS |
| sharpe | 0.728 | PASS |
| max_drawdown | +30.63% | PASS |
| annual_cost_ratio | 52% | FAIL |
| walkforward_positive_ratio | 80% | PASS |
| deflated_sharpe | 0.409 | FAIL |
| bootstrap_p_sharpe_positive | 100.0% | PASS |
| oos_return | +36.95% | PASS |
| vs_1n_excess | +2.49% | PASS |
| pbo | 0.000 | PASS |
| worst_regime | -4.07% | PASS |
| recent_period_sharpe | -1.575 | FAIL |

**10/13 通過 — 可考慮進入 Paper Trading。**

## Walk-Forward: 80%


## 失敗項解讀

- **annual_cost_ratio** (52%): 交易成本佔 gross alpha 比例偏高。改善方向：降低換手（延長持有期 / 提高篩選門檻）
- **deflated_sharpe** (0.409): 多重測試校正後信心不足（測了 84 個因子）。這是統計保守，不代表因子無效
- **recent_period_sharpe** (-1.575): 近 252 天 Sharpe 為負，受市場環境影響。需觀察是暫時還是永久衰退

## 與現有因子比較

| 因子 | ICIR | 說明 |
|------|:----:|------|
| **rev_yoy_x_gross_margin_chg** | **+0.802** | **本次發現** |
| revenue_yoy（基線） | +0.674 | 已驗證的核心因子 |
| revenue_acceleration | +0.847 | 60d 最強因子 |
| momentum_6m | +0.217 | 最佳 price-volume 因子 |

## 下一步

- [ ] 人工審閱假說邏輯
- [ ] 決定是否加入正式因子庫
- [ ] 決定是否部署到 Paper Trading