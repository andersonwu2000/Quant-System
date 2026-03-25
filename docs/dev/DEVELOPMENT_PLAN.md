# 開發計畫書

> **version**: v6.0
> **date**: 2026-03-26

---

## 1. 專案現況

多資產投資組合研究與優化系統，涵蓋台股、美股、ETF（含債券/商品 ETF 代理）、期貨。Python 後端 + React Web + React Native Mobile 單體倉庫。後端 128 檔案、22.5K LOC、975 tests。具備 13 種組合最佳化方法、14 個 Alpha 因子、10 條風控規則、68 個 API 端點。回測引擎與策略框架已成熟，自動化 Alpha 排程系統已實作。

**主要阻塞**：永豐金 Shioaji API Key 尚在審核中。所有券商整合程式碼均已完成（含 83 個 mock 測試），但從未對接真實券商 API 進行驗證。

---

## 2. 已完成階段總覽

| 階段 | 完成日 | 摘要 |
|------|--------|------|
| A 基礎設施 | 2026-03-24 | InstrumentRegistry、多幣別 Portfolio、DataFeed 擴展、FRED 數據源 |
| B 跨資產 Alpha | 2026-03-24 | 宏觀因子模型、跨資產信號、戰術配置引擎、Allocation API |
| C 組合最佳化 | 2026-03-24 | 6 種最佳化器 (EW/IV/RP/MVO/BL/HRP)、Ledoit-Wolf 風險模型、幣別對沖 |
| D 系統整合 | 2026-03-25 | MultiAssetStrategy、跨資產風控、AllocationPage 前端、5 新 Alpha 因子 |
| E 實盤交易 | 2026-03-25 | SinopacBroker、ExecutionService、即時行情架構、Scanner、觸價委託、83 tests |
| F 自動化 Alpha | 2026-03-26 | 排程引擎 (7 jobs)、因子篩選、Regime 調適、動態因子池、安全熔斷、10 API 端點 |
| G 學術基準升級 | 2026-03-26 | +7 最佳化方法、GARCH/PCA 共變異數、VaR/CVaR、PBO/Randomized/Stress Test |

---

## 3. 當前阻塞與待辦

### 3.1 阻塞項（需外部條件）

| 項目 | 阻塞原因 | 解除後工作 |
|------|---------|-----------|
| Shioaji 整合測試 | 等待 API Key 核發 | 真實環境 login/下單/行情驗證 |
| E2 即時行情 broadcast | 需 API Key 取得 tick 資料 | WS `market` 頻道接 SinopacQuoteManager |
| E3 Paper Trading 循環 | 需 API Key 跑 simulation=True | 排程→下單→回報→對帳→通知 完整驗證 |

### 3.2 已實作但缺入口的孤島

| 模組 | 現況 | 需要 |
|------|------|------|
| G3 回測工具 (Randomized/PBO/Stress) | 純 Python 函數，無 API | 新增 API 端點 + 前端入口 |
| F4 DynamicFactorPool | 獨立模組，未接入主流程 | 整合至 AlphaDecisionEngine 每日排程 |
| F2d Alembic migration | AlphaStore schema 定義完成 | 實作 `005_auto_alpha.py` migration |

### 3.3 文件標記修正

以下項目在先前版本標記有誤，實際狀態：

- **F3b WS auto-alpha 頻道**: 已完成（先前標記「待實作」）
- **F3c Auto-Alpha Dashboard**: 已完成（先前標記「待實作」）
- **E3 排程整合**: 部分完成 — AlphaScheduler 已實作，但 Paper Trading 循環需 API Key 驗證

---

## 4. Phase H：實用精煉

只排入有明確實用價值、難度合理的項目。

### H1: Deflated Sharpe Ratio + MinBTL — P0, 低難度

**動機**：系統已有 PBO 和 Randomized Backtest，但缺少最基本的多重測試校正。測試過越多策略，越需要 DSR 來判斷 Sharpe 是否為偽陽性。

**實作**：
- `deflated_sharpe()` — 校正 N_trials、skewness、kurtosis（Bailey et al. 2015）
- `min_backtest_length()` — 給定 N 策略，最短回測長度避免偽陽性

**位置**: `src/backtest/analytics.py` 新增 2 個函數 + 對應 tests。

### H2: Downside Risk 最佳化 — P1, 低難度

**動機**：投資者最在意的是下行風險，而非對稱波動。Semi-variance 只懲罰低於目標報酬的波動，比 MVO 更貼近真實風險偏好。

**實作**：
- `OptimizationMethod.SEMI_VARIANCE` — semi-covariance matrix + SLSQP
- 整合至現有 PortfolioOptimizer 框架

**位置**: `src/portfolio/optimizer.py`。

### H3: Kalman Filter Pairs Trading — P1, 中難度

**動機**：現有 Pairs Trading 使用靜態 OLS hedge ratio（Engle-Granger），當共整合關係漂移時會失效。Kalman Filter 可動態追蹤 hedge ratio。

**實作**：
- `KalmanHedgeRatio` — 線上更新 hedge ratio + 動態 spread
- 升級 `strategies/pairs_trading.py`，可選 `method='kalman'`

---

## 5. 未來方向（不排入開發計畫）

以下項目有潛在價值，但目前不具備實施條件或優先度不足：

- **IB 美股對接** — 等台股 Paper Trading 跑穩、確認架構可行後再擴展
- **期貨/選擇權交易** — InstrumentRegistry 已支援，但需先驗證股票交易流程
- **MVSK / 非高斯建模** (Tyler's M-estimator, skewed-t) — 學術性大於實用性，現有 Ledoit-Wolf + GARCH 已足夠
- **HERC / NCO** — HRP 已夠用，等出現明確需求再實作
- **EVaR / 非線性收縮 (RMT)** — 實作複雜度高，邊際改善有限

---

## 6. 里程碑時間線

| 日期 | 里程碑 |
|------|--------|
| 2026-03-22~23 | 股票交易系統（回測 + 7 策略 + 風控 + API + Web + Mobile） |
| 2026-03-24 | Phase A~C（基礎設施 + 跨資產 Alpha + 組合最佳化） |
| 2026-03-25 | Phase D~E（系統整合 + 實盤交易架構） |
| 2026-03-26 | Phase F~G（自動化 Alpha + 學術基準升級） |
| TBD | Shioaji API Key 取得 → 整合測試 |
| TBD | Paper Trading 完整循環驗證 |
| TBD | H1: Deflated Sharpe Ratio + MinBTL |
| TBD | H2: Downside Risk 最佳化 |
| TBD | H3: Kalman Filter Pairs Trading |
