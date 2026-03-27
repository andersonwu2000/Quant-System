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

## 大規模 IC 驗證（865 支台股，108 個月）

> 實驗 #17 結果（`docs/dev/test/20260327_17_auto_factor_large_scale.md`）

| Factor | ICIR(5d) | ICIR(20d) | ICIR(60d) | Hit%(20d) |
|--------|:--------:|:---------:|:---------:|:---------:|
| **rev_seasonal_deviation** | +0.253 | **+0.221** | +0.192 | 58.5% |
| revenue_acceleration | +0.409 | +0.384 | +0.616 | 64.0% |
| revenue_new_high | +0.277 | +0.345 | +0.448 | 62.0% |

**大 universe 下 ICIR 從 L5 的 0.814 降至 0.221 — 小樣本高估明顯。**

因子有效但弱（排第 4），且 60d 衰退至 0.192。不建議單獨部署，可作為組合輔助因子。

## 下一步

- [x] 大規模 IC 驗證 — **有效但弱 (ICIR 0.221)**
- [ ] 人工審閱假說邏輯
- [ ] 考慮與 revenue_acceleration 組合而非單獨部署