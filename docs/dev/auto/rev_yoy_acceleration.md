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

**12/13 通過 — 符合 Validator 門檻 (≥12/13)，但大規模 IC 不合格。**

## Walk-Forward: 100%


## 失敗項解讀

- **deflated_sharpe** (0.623): 多重測試校正後信心不足（測了 88 個因子）。這是統計保守，不代表因子無效

## 大規模 IC 驗證（865 支台股，106 個月）

| Factor | ICIR(5d) | ICIR(20d) | ICIR(60d) | Hit%(20d) |
|--------|:--------:|:---------:|:---------:|:---------:|
| **rev_yoy_acceleration** | +0.059 | **+0.104** | +0.175 | 54.3% |
| revenue_acceleration (#16 基準) | +0.202 | +0.240 | +0.426 | 63.9% |
| revenue_new_high (#16 基準) | +0.246 | +0.207 | +0.364 | 61.3% |

**大規模 ICIR(20d) = +0.104 — FAIL (<0.20)**

L5 ICIR 0.860 在大 universe 下降為 0.104（縮水 88%）。小樣本嚴重高估。

## 部署判定

**不符合部署條件：大規模 ICIR(20d) 0.104 < 0.20**

Validator 12/13 通過但大規模 IC 不合格。因子在全 universe 下信號太弱。