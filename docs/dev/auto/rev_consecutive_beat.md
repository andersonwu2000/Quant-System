# Auto-Discovery: rev_consecutive_beat

**日期**: 2026-03-27T10:31:05.203037
**方向**: revenue_acceleration_2nd_order
**假說**: 連續 N 月營收超越去年同月的月數
**學術依據**: Earnings consistency premium

## L1-L5 快速評估

| 指標 | 值 |
|------|---:|
| IC (20d) | +0.0208 |
| Best ICIR | +0.5824 (10d) |
| Fitness | 9.02 |
| Turnover | 86.7% |
| Max Correlation | 0.000 () |
| Positive Years | 0/0 |

## StrategyValidator: 10/13

| 檢查 | 值 | 結果 |
|------|---:|:----:|
| universe_size | 875 | PASS |
| cagr | +12.51% | PASS |
| sharpe | 0.789 | PASS |
| max_drawdown | +28.44% | PASS |
| annual_cost_ratio | 20% | PASS |
| walkforward_positive_ratio | 80% | PASS |
| deflated_sharpe | 0.316 | FAIL |
| bootstrap_p_sharpe_positive | 97.9% | PASS |
| oos_return | +21.70% | PASS |
| vs_1n_excess | -4.06% | FAIL |
| pbo | 0.000 | PASS |
| worst_regime | -11.27% | PASS |
| recent_period_sharpe | -0.308 | FAIL |

**10/13 通過 — 未達部署門檻 (需 ≥12/13)，僅供觀察。**

## Walk-Forward: 80%


## 失敗項解讀

- **deflated_sharpe** (0.316): 多重測試校正後信心不足（測了 89 個因子）。這是統計保守，不代表因子無效
- **vs_1n_excess** (-4.06%): 未達門檻
- **recent_period_sharpe** (-0.308): 近 252 天 Sharpe 為負，受市場環境影響。需觀察是暫時還是永久衰退

## 不合格原因

1. **recent_period_sharpe = -0.308** — 最近 1 年虧損，因子已衰退
2. **vs_1n_excess = -4.06%** — 跑輸 0050
3. **deflated_sharpe = 0.316** — 多重測試後信心極低
4. 10/13 未達新部署門檻 (≥12/13)

**結論：不適合部署。**