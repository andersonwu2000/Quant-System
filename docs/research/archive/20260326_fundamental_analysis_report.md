# 基本面 + 籌碼面因子 IC 分析報告

**日期**: 2026-03-26
**Universe**: 142 支台股（價格面板）, 49 支有基本面數據（FinMind TW50）
**數據期間**: 2019-01 ~ 2025-12（~7 年）
**持有期**: 20 天
**取樣**: 每 5 天
**方法**: Spearman cross-sectional IC

---

## 1. 因子清單

| 因子 | 類型 | 數據源 | 說明 |
|------|------|--------|------|
| pe_ratio | 基本面 | TaiwanStockPER | 本益比（反向：低 PE = 高分） |
| pb_ratio | 基本面 | TaiwanStockPER | 淨值比 |
| dividend_yield | 基本面 | TaiwanStockPER | 股利殖利率 |
| revenue_yoy | 基本面 | TaiwanStockMonthRevenue | 月營收 YoY 成長率 |
| revenue_momentum | 基本面 | TaiwanStockMonthRevenue | 連續 N 月 YoY > 0 的月數 |
| foreign_net | 籌碼面 | TaiwanStockInstitutionalInvestors | 外資 20 日淨買超（正規化） |
| trust_net | 籌碼面 | TaiwanStockInstitutionalInvestors | 投信 20 日淨買超（正規化） |
| margin_change | 籌碼面 | TaiwanStockMarginPurchaseShortSale | 融資餘額 20 日變化率 |
| foreign_holding_chg | 籌碼面 | TaiwanStockShareholding | 外資持股比例 20 日變化 |
| daytrading_ratio | 情緒面 | TaiwanStockDayTrading | 當沖比率（20 日均值） |
| momentum_6m | 價量（對照） | 本地 parquet | 6 月動量（baseline） |

---

## 2. IC 分析結果

| 因子 | 類型 | IC | ICIR | Hit% | 門檻 |
|------|------|---:|-----:|-----:|------|
| **revenue_yoy** | **基本面** | **+0.075** | **+0.317** | **62.7%** | **ICIR ≥ 0.3 ✅** |
| pe_ratio | 基本面 | -0.059 | -0.282 | 36.5% | ICIR 0.15~0.3 |
| momentum_6m | 價量 | +0.041 | +0.217 | 59.9% | ICIR 0.15~0.3 |
| revenue_momentum | 基本面 | +0.043 | +0.186 | 59.5% | ICIR 0.15~0.3 |
| dividend_yield | 基本面 | +0.031 | +0.139 | 58.6% | |
| foreign_holding_chg | 籌碼面 | +0.019 | +0.091 | 53.7% | |
| foreign_net | 籌碼面 | +0.018 | +0.086 | 54.6% | |
| daytrading_ratio | 情緒面 | +0.022 | +0.085 | 56.1% | |
| trust_net | 籌碼面 | +0.008 | +0.040 | 53.8% | |
| pb_ratio | 基本面 | -0.009 | -0.037 | 52.9% | |
| margin_change | 籌碼面 | +0.002 | +0.009 | 52.5% | |

---

## 3. 核心發現

### 3.1 revenue_yoy 是第一個通過 ICIR 0.3 的因子

在之前 15 次實驗、75 個 price-volume 因子中，**寬 universe 下沒有任何因子通過 ICIR 0.3**。

revenue_yoy（月營收 YoY 成長率）：
- **ICIR = +0.317** — 首次突破 0.3 門檻
- **IC = +0.075** — 比 momentum_6m（+0.041）高 83%
- **Hit Rate = 62.7%** — 穩定正相關
- 方向正確：高營收成長 → 高未來報酬

### 3.2 基本面因子整體優於籌碼面

| 類型 | 平均 |ICIR| | 最佳因子 | 最佳 ICIR |
|------|:--------:|---------|:--------:|
| **基本面** | **0.193** | revenue_yoy | **0.317** |
| 價量（對照） | 0.217 | momentum_6m | 0.217 |
| 籌碼面 | 0.045 | foreign_holding_chg | 0.091 |
| 情緒面 | 0.085 | daytrading_ratio | 0.085 |

### 3.3 PE 反向顯著

pe_ratio ICIR = -0.282：**高 PE 股票未來報酬更低**。
- 方向與 value 因子一致（低 PE = 高報酬）
- Hit Rate 36.5%（<50%，表示 IC 多數為負）
- 使用 1/PE（inverse）後即為正向 value 因子

### 3.4 籌碼面因子依然弱

所有籌碼面因子 ICIR < 0.1，與實驗 11、15 結論一致：
- 外資淨買超 ICIR 0.086（vs 實驗 15 的 0.15 — 正規化方式不同）
- 融資變化 ICIR 0.009（無效）
- 投信 ICIR 0.040（無效）

### 3.5 基本面因子的成本優勢

| 因子 | 預估年化換手率 | 原因 |
|------|:----------:|------|
| revenue_yoy | ~5% | 月頻更新，僅月底排名變動 |
| revenue_momentum | ~3% | 連續月數變化更慢 |
| pe_ratio | ~8% | 隨股價日常波動，但截面排名穩定 |
| momentum_6m | ~7% | 6 月窗口，排名變化緩慢 |

**所有基本面因子換手率預估 < 10%** — 在台股成本結構下均可盈利（實驗結論：>10% 幾乎不可能）。

---

## 4. 與 price-volume 因子全面對比

| 維度 | price-volume 最佳 | 基本面最佳 | 勝者 |
|------|:--:|:--:|:--:|
| ICIR（寬 universe） | momentum_6m +0.217 | **revenue_yoy +0.317** | **基本面** |
| IC 絕對值 | momentum_6m +0.041 | **revenue_yoy +0.075** | **基本面** |
| Hit Rate | momentum_6m 59.9% | **revenue_yoy 62.7%** | **基本面** |
| 換手率 | ~7% | **~5%** | **基本面** |
| 數據延遲 | 即時 | T+10（月營收每月 10 號前公布） | 價量 |

**revenue_yoy 在 IC、ICIR、Hit Rate、換手率四個維度都優於 momentum_6m。**

唯一劣勢是數據延遲：月營收每月 10 日前公布，而價格是即時的。但 20 天持有期足以容納這個延遲。

---

## 5. 下一步：K5 Walk-Forward 驗證

基於以上結果，K5 應測試以下組合：

| # | 策略 | 因子 | 預期 |
|---|------|------|------|
| 1 | revenue_yoy 單因子 | revenue_yoy | 最強信號 |
| 2 | revenue_yoy + momentum_6m | 基本面 + 動量 | 低相關組合 |
| 3 | revenue_yoy + pe_ratio(inv) | 成長 + 價值 | 經典組合 |
| 4 | revenue_yoy + momentum_6m + pe_ratio(inv) | 三因子 | 分散 |

---

## 6. K5 Walk-Forward 驗證結果

**設定**: 49 支台股（有基本面數據）、~5.5 年、20 天持有、DD 10%、50 bps 成本

### 策略比較

| 策略 | 年化 | Sharpe | MDD | Win% | 超額/年 | 超額 SR |
|------|------|--------|-----|------|---------|---------|
| revenue_yoy 單因子 | +17.9% | 1.01 | -25.7% | 58% | +0.4% | +0.03 |
| momentum_6m 單因子 | +18.2% | 1.12 | -19.1% | 61% | -0.3% | -0.03 |
| **rev_yoy + mom6m** | +21.5% | 1.10 | -24.8% | 60% | +1.8% | +0.13 |
| rev_yoy + value_pe | +17.6% | 1.01 | -24.0% | 62% | -1.5% | -0.12 |
| **rev + mom + value** | **+22.3%** | **1.19** | -22.5% | 60% | **+2.7%** | **+0.21** |

### 最佳策略：revenue_yoy + momentum_6m + value_pe（三因子）

年度分解：

| 年份 | 策略 | 基準 | 超額 |
|------|------|------|------|
| 2019 | +8.6% | +11.5% | -2.9% |
| 2020 | +43.0% | +26.2% | **+16.8%** |
| 2021 | +47.6% | +34.4% | **+13.2%** |
| 2022 | -12.6% | -5.4% | -7.2% |
| 2023 | +15.9% | +25.5% | -9.6% |
| 2024 | +14.8% | +11.2% | **+3.5%** |
| 2025 | +28.6% | +20.0% | **+8.6%** |

**7 年中 4 年正超額**，與之前最佳策略（RSI+動量+外資）一致。

### 與之前實驗對比

| 策略 | 超額/年 | 超額 SR | 數據源 |
|------|---------|---------|--------|
| 之前最佳：mom6m+turnover_vol 大型 | +3.1% | +0.20 | pure price-volume |
| 之前次佳：RSI+動量+外資 大型 | +6.4% | +0.39 | price + 籌碼 |
| **本次：rev_yoy + mom + value** | **+2.7%** | **+0.21** | **基本面 + price** |

### 分析

1. **三因子組合 Sharpe 1.19 是所有實驗中第二高**（僅次於 ivol 的 selection bias 結果）
2. **超額 SR 0.21 與之前 price-volume 最佳持平**（0.20）— 基本面因子尚未帶來超額的量級突破
3. **revenue_yoy 本身作為單因子的超額接近零**（+0.4%）— IC 高但轉化為實際 alpha 效率不高
4. **三因子組合效果 > 雙因子 > 單因子**，驗證了因子分散的價值
5. **2022 熊市和 2023 反彈期都跑輸基準** — 與之前動量策略的弱點一致

### 結論

基本面因子（revenue_yoy）IC 信號強（ICIR 0.317），但 Walk-Forward 超額 +2.7%/年，尚未實現質的突破。可能原因：
- 數據延遲（月營收 T+10 公布）
- Universe 僅 49 支（基本面數據覆蓋較窄）
- 需要更精細的組合方式（如 rolling IC 加權而非等權）

---

## 7. 數據檔案

- 完整結果：`docs/dev/test/fundamental_factor_analysis.csv`
- 分析腳本：`scripts/run_fundamental_analysis.py`
- 數據來源：`data/fundamental/`（FinMind）+ `data/market/`（Yahoo/FinMind）
