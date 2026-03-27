# 實驗報告 #17：自動發現因子 — 大規模 IC 驗證

> 日期：2026-03-27
> Universe：865 支台股（min 500 bars）
> 期間：2017-01 ~ 2025-12（108 個月度取樣點）
> 方法：月度 Spearman IC → ICIR，forward returns 5d / 20d / 60d
> 耗時：231 秒

---

## 1. 結果

| Factor | Type | ICIR(5d) | ICIR(20d) | ICIR(60d) | N | Hit%(20d) |
|--------|------|:--------:|:---------:|:---------:|:-:|:---------:|
| **revenue_acceleration** | existing | +0.409 | **+0.384** | **+0.616** | 100 | 64.0% |
| **revenue_new_high** | existing | +0.277 | **+0.345** | **+0.448** | 100 | 62.0% |
| **revenue_momentum** | existing | +0.282 | +0.273 | **+0.499** | 98 | 60.2% |
| **rev_seasonal_deviation** | NEW | +0.253 | +0.221 | +0.192 | 94 | 58.5% |
| **revenue_yoy** | existing | +0.304 | +0.162 | +0.243 | 100 | 53.0% |
| rev_accel_2nd_derivative | NEW | -0.256 | +0.010 | +0.075 | 105 | 48.6% |

---

## 2. 分析

### rev_seasonal_deviation（自動發現）

- **ICIR(20d) +0.221，Hit 58.5%** — 有效但弱
- 60d ICIR 衰減到 +0.192（不像 acceleration 越長越強）
- **問題**：短期有效（5d +0.253）但長期衰退 — 可能是短期反應而非結構性 alpha
- **與 Validator 的差異**：Validator 顯示 Sharpe 1.415，但大 universe IC 檢驗只排第 4
- **結論**：有效但不如 revenue_acceleration，不宜單獨部署

### rev_accel_2nd_derivative（自動發現）

- **ICIR(20d) +0.010** — 大 universe 下基本無效
- 5d 甚至是負的 (-0.256)，Hit 48.6% < 50%
- **結論**：不可用，不應部署

### 現有因子排名

1. **revenue_acceleration** — 全面最強，60d ICIR +0.616
2. **revenue_new_high** — 第二強，60d ICIR +0.448
3. **revenue_momentum** — 第三，60d ICIR +0.499（比 new_high 的 60d 更強）
4. rev_seasonal_deviation — 弱有效
5. revenue_yoy — 弱有效
6. rev_accel_2nd_derivative — 無效

---

## 3. 與實驗 #16 的比較

| Factor | #16 ICIR(20d) | #17 ICIR(20d) | #16 ICIR(60d) | #17 ICIR(60d) |
|--------|:------------:|:------------:|:------------:|:------------:|
| revenue_acceleration | +0.240 | **+0.384** | +0.426 | **+0.616** |
| revenue_new_high | +0.207 | **+0.345** | +0.364 | **+0.448** |
| revenue_yoy | +0.037 | **+0.162** | +0.112 | **+0.243** |

**本次結果比 #16 更高**，原因：
- #17 使用 108 個月（2017-2025）vs #16 的 123 個月（2016-2025）— 時間範圍不同
- #17 簡化版腳本（無 ADV 限制、漲跌停過濾等），#16 更嚴謹
- **基準應以 #16 為準**（更長時間、更完整方法論）
- #17 主要用途：比較新因子與現有因子的**相對排序**，而非絕對數值

---

## 4. 結論

1. **revenue_acceleration 持續為最強因子**，在 865 支大 universe 下 60d ICIR +0.616，穩健
2. **rev_seasonal_deviation 有效但弱** (ICIR 0.221)，不建議單獨部署
3. **rev_accel_2nd_derivative 在大 universe 下無效** (ICIR 0.010)，應從部署列表移除
4. **營收因子排序穩定**：acceleration > new_high > momentum > yoy

### 部署建議

| Factor | 可否部署 | 理由 |
|--------|:------:|------|
| revenue_acceleration | ✅ | ICIR +0.384/+0.616，已在 paper trading |
| revenue_new_high | ✅ | ICIR +0.345/+0.448，可作為輔助因子 |
| rev_seasonal_deviation | ⚠️ | ICIR +0.221，弱有效，需組合使用 |
| rev_accel_2nd_derivative | ❌ | ICIR +0.010，大 universe 無效 |

### 部署門檻更新

- 自動部署門檻從 10/13 提高到 **12/13**
- 新增硬性要求：**recent_period_sharpe > 0**（最近 1 年不能虧）
- 新增建議：自動因子在寫 `docs/dev/auto` 報告前，應先通過大規模 IC 檢驗
