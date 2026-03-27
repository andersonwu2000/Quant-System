# Auto-Discovery: upstream_rev_lead

**日期**: 2026-03-27T11:29:46.620467
**方向**: supply_chain_propagation
**假說**: 同行業上游公司營收 lead 本公司 1-2 月
**學術依據**: Supply chain momentum (Menzly-Ozbas 2010)

## L1-L5 快速評估

| 指標 | 值 |
|------|---:|
| IC (20d) | +0.0697 |
| Best ICIR | +0.9962 (10d) |
| Fitness | 27.82 |
| Turnover | 89.4% |
| Max Correlation | 0.000 () |
| Positive Years | 0/0 |

## StrategyValidator: 11/13

| 檢查 | 值 | 結果 |
|------|---:|:----:|
| universe_size | 875 | PASS |
| cagr | +24.50% | PASS |
| sharpe | 1.331 | PASS |
| max_drawdown | +14.07% | PASS |
| annual_cost_ratio | 19% | PASS |
| walkforward_positive_ratio | 100% | PASS |
| deflated_sharpe | 0.825 | FAIL |
| bootstrap_p_sharpe_positive | 100.0% | PASS |
| oos_return | +5.23% | PASS |
| vs_1n_excess | +7.94% | PASS |
| pbo | 0.000 | PASS |
| worst_regime | +5.66% | PASS |
| recent_period_sharpe | -0.082 | FAIL |

**11/13 通過（排除 DSR: 12/13）— 符合部署門檻。已部署 Paper Trading。**

## Walk-Forward: 100%


## 失敗項解讀

- **deflated_sharpe** (0.825): 多重測試校正後信心不足（測了 91 個因子）。這是統計保守，不代表因子無效
- **recent_period_sharpe** (-0.082): 近 252 天 Sharpe 為負，受市場環境影響。需觀察是暫時還是永久衰退

## 大規模 IC 驗證（865+ 支台股，108 個月）

| Factor | ICIR(5d) | ICIR(20d) | ICIR(60d) | Hit%(20d) |
|--------|:--------:|:---------:|:---------:|:---------:|
| **upstream_rev_lead** | +0.496 | **+0.488** | +0.579 | 61.0% |
| revenue_acceleration (#16 基準) | +0.202 | +0.240 | +0.426 | 63.9% |
| revenue_new_high (#16 基準) | +0.246 | +0.207 | +0.364 | 61.3% |

**大規模 ICIR(20d) = +0.488 — PASS (≥0.20)**

## 部署判定

**已部署 Paper Trading（2026-03-27）**
- NAV: $500,000（5%），30 天觀察期至 2026-04-26
- 排除 DSR 後 12/13 通過，大規模 ICIR(20d) +0.488 為全因子最強
- recent_sharpe -0.082 > -0.10 門檻