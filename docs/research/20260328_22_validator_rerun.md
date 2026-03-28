# Validator 重新驗證報告 — 2026-03-28

> 修復 strategy_builder revenue bare symbol bug 後的完整重跑

## 1. revenue_momentum_hedged（865 支，2018-2025）

主力策略，基於營收加速度。

| Check | Result | Value | Threshold |
|-------|:------:|-------|-----------|
| universe_size | PASS | 865 | >= 50 |
| cagr | PASS | +11.13% | >= +8.00% |
| sharpe | PASS | 0.879 | >= 0.700 |
| max_drawdown | PASS | -27.27% | <= 40% |
| annual_cost_ratio | PASS | 25% | < 50% |
| walkforward | PASS | 75% | >= 60% |
| deflated_sharpe | PASS | 0.999 | N/A |
| bootstrap | PASS | 99.9% | >= 80% |
| **oos_sharpe** | **FAIL** | **-1.199** | >= 0.300 |
| vs_0050 | PASS | +2.42% | >= 0% |
| **pbo** | **FAIL** | **0.702** | <= 0.500 |
| worst_regime | PASS | -5.14% | >= -30% |
| recent_sharpe | PASS | 1.143 | >= 0.000 |
| market_corr | PASS | 0.529 | <= 0.90 |
| cvar_95 | PASS | -2.02% | >= -5% |

**Result: 13/15**

**分析：**
- 2025 年 OOS Sharpe -1.2 — 策略在 2025 年失效，可能是市場環境變化
- PBO 0.702 — portfolio 構建有過擬合傾向
- 對比舊實驗 #21（14/15, Sharpe 1.076）：CAGR 11% vs 14%, Sharpe 0.88 vs 1.08，表現下降

### 1b. Rolling OOS 重跑（865 支，OOS 2024-09-25 ~ 2026-03-27）

改為 rolling OOS（最近 1.5 年到昨天）+ Validator OOS 與 evaluate.py L5 分離後重跑。

| Check | Result | Value | 對比 §1 |
|-------|:------:|-------|---------|
| cagr | PASS | +11.60% | 11.13% → 11.60% |
| sharpe | PASS | 0.909 | 0.879 → 0.909 |
| max_drawdown | PASS | -27.27% | 不變 |
| walkforward | PASS | 75% | 不變 |
| bootstrap | PASS | 99.9% | 不變 |
| **oos_sharpe** | **FAIL** | **-0.732** | -1.199 → -0.732（改善但仍 FAIL） |
| vs_0050 | PASS | +2.92% | 2.42% → 2.92% |
| **pbo** | **FAIL** | **0.702** | 不變 |
| recent_sharpe | PASS | 2.847 | 1.143 → 2.847（大幅改善） |
| market_corr | PASS | 0.538 | 不變 |
| **Total** | | **13/15** | 不變 |

**結論：**
- OOS Sharpe 從 -1.2 改善到 -0.73 — 新窗口含 2024Q4（好）+ 2025（差）+ 2026Q1（好），比純 2025 好
- PBO 0.702 不變 — PBO 算 IS 期間穩定性，與 OOS 窗口無關
- Recent Sharpe 2.85 — 最近 1 年回彈，策略未永久失效
- **仍 FAIL 在 OOS Sharpe + PBO** — 策略在 2025 年確實表現差，不是窗口選擇問題

## 2. Autoresearch 批次驗證（25 個 tagged 因子，150 支）

修復 `strategy_builder.py` 的 bare symbol bug 後重跑。

| Factor | Score | Failed Checks |
|--------|:-----:|--------------|
| revwz_mafrac_combo | 14/15 | pbo |
| vwap_position_63d | 14/15 | oos_sharpe |
| 52wk_high | 13/15 | oos_sharpe, pbo |
| efficiency_ratio_126d | 13/15 | oos_sharpe, vs_0050 |
| ma150_fraction_63d | 13/15 | oos_sharpe, vs_0050 |
| revwz_200ma | 13/15 | oos_sharpe, pbo |
| revenue_accel_v2 | 12/15 | oos_sharpe, vs_0050, pbo |
| obv_revaccel_combo | 12/15 | oos_sharpe, vs_0050, pbo |
| obv_slope | 12/15 | oos_sharpe, vs_0050, pbo |
| tsi_25_13 | 12/15 | sharpe, oos_sharpe, vs_0050 |
| price_trend | 11/15 | wf, oos_sharpe, vs_0050, pbo |
| ad_line_63d | 11/15 | cagr, oos_sharpe, vs_0050 |
| rev_zscore | 11/15 | walkforward, oos_sharpe, vs_0050, pbo |
| rev_weighted_zscore | 11/15 | walkforward, oos_sharpe, vs_0050, pbo |
| robust_revz | 11/15 | walkforward, oos_sharpe, vs_0050, pbo |
| single_month_zscore | 11/15 | walkforward, oos_sharpe, vs_0050, pbo |
| efficiency_ratio_252d | 10/15 | oos_sharpe, vs_0050, pbo + 2 others |
| rev_zscore_3m | 10/15 | oos_sharpe, vs_0050, pbo + 2 others |
| weekly_obv_52w | 10/15 | oos_sharpe, pbo + 3 others |
| liquidity_cond | 9/15 | cagr, sharpe, mdd + 6 others |
| revenue_accel_v1 | 9/15 | oos_sharpe, pbo + 4 others |
| dual_norm_combo | 9/15 | cagr, sharpe + 3 others |
| ma200_fraction_63d | 9/15 | cagr, sharpe + 3 others |
| obv_mom_regime | 9/15 | cagr, sharpe + 3 others |
| rev_inconsistency | 9/15 | cagr, sharpe + 3 others |

**Passed: 0/25**

**對比修復前：** 之前大量 5/15（revenue 因子 0 交易），現在 9-14/15。revenue bug 修復確認生效。

## 3. Autoresearch Docker Validator 報告（4 個通過 14/15）

Watchdog 背景驗證產出的因子：

| Report | Composite | Sharpe | OOS Sharpe | PBO | Deployed? |
|--------|-----------|--------|-----------|-----|:---------:|
| #1 (unknown) | 20.27 | 1.503 | 2.085 | 0.780 | ✅ |
| #2 | 16.15 | 1.161 | 2.010 | 0.852 | ✅ |
| #3 | — | — | — | 0.918 | ✅ |
| #4 | — | — | — | 0.998 | ✅ |

**PBO 趨勢：0.780 → 0.852 → 0.918 → 0.998（系統性惡化）**

Agent 持續針對 IS 最佳化，OOS holdout 被 pass/fail 反饋間接學習。
新增 PBO <= 0.85 硬性部署門檻後，#3 和 #4 不會再被標為 DEPLOYED。

## 4. 結論

1. **revenue_momentum_hedged 在 2025 OOS 失效**（Sharpe -1.2）— 需要觀察是暫時性或永久性
2. **autoresearch 因子 PBO 系統性惡化** — 已新增 PBO <= 0.85 硬性門檻
3. **strategy_builder revenue bug 修復生效** — 從 5/15 提升到 9-14/15
4. **所有 25 個 tagged 因子均未通過部署門檻** — 主要卡在 oos_sharpe（2025 年普遍差）
