# Auto-Alpha Discovery Report

**日期**: 2026-03-27 08:00~08:30
**模式**: 自動化因子研究 (3 rounds planned, 1.5 completed)

---

## Round 1: rev_seasonal_deviation — DEPLOYED

### 因子定義

**營收季節偏離** — 當月營收 vs 過去 3 年同月平均的偏離比率。

```
factor = current_month_revenue / mean(same_month_3_years_ago) - 1
```

- **學術依據**: Seasonal anomalies in earnings (Post-Earnings Announcement Drift 的變體)
- **直覺**: 如果公司 3 月營收遠高於過去 3 年的 3 月平均，代表超預期的成長

### 評估結果

| 指標 | 值 |
|------|-----|
| ICIR | **0.814** (通過 Harvey 閾值) |
| Fitness (WorldQuant) | **19.60** |
| Sharpe | **1.415** |
| CAGR | **30.50%** |
| vs 0050 Sharpe | 1.415 > 0.857 |

### Validator 通過（推斷 ~10+/13）

回測通過全歷史 (2018-2025) + Walk-Forward (2021-2025, 5年) + OOS + DSR。
因已自動部署，表示 `_try_auto_deploy()` 檢查通過：
- Sharpe > 0050 ✅
- CAGR > 8% ✅ (30.50%)
- Validator ≥ 10/13 ✅

### 部署

- **NAV**: $500,000 (5% of total)
- **Auto-stop**: 2026-04-26 (30 天觀察期)
- **Kill switch**: 3% daily drawdown

---

## Round 2: rev_accel_2nd_derivative — IC 通過，Validator 中斷

### 因子定義

**營收加速度二階導數** — `latest_yoy - previous_yoy`，衡量 YoY 成長的加速/減速。

### 評估結果

| 指標 | 值 |
|------|-----|
| ICIR | **0.860** (更高!) |
| Fitness | **18.70** |

Validator 回測在 2025-03 附近中斷（進程結束，可能記憶體問題）。
**建議**: 下次單獨跑此因子的完整 Validator 驗證。

---

## Round 3: 未執行

進程在 Round 2 Validator 回測中結束。

---

## 總結

| Round | Factor | ICIR | Fitness | Sharpe | Status |
|-------|--------|------|---------|--------|--------|
| 1 | rev_seasonal_deviation | 0.814 | 19.60 | 1.415 | **DEPLOYED** |
| 2 | rev_accel_2nd_derivative | 0.860 | 18.70 | ? | IC PASS, Validator 中斷 |
| 3 | — | — | — | — | 未執行 |

### 值得注意

1. **兩個因子都通過了 IC 篩選** — ICIR > 0.5 (Harvey 2016 基準)
2. **rev_seasonal_deviation 是純營收因子**，不依賴技術面，和現有 revenue_acceleration 互補
3. **rev_accel_2nd_derivative ICIR 0.860** 比 rev_seasonal_deviation 更高，值得後續驗證
4. Validator 對 875 支股票的全歷史回測約需 7 分鐘/因子

### 下一步

- 監控 rev_seasonal_deviation 在 paper trading 的表現 (30 天)
- 單獨跑 rev_accel_2nd_derivative 的完整 Validator
- 考慮將 rev_seasonal_deviation 加入 revenue_momentum 策略的多因子組合
