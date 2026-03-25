# 開發計畫書

> **version**: v6.1
> **date**: 2026-03-26

---

## 1. 專案現況

多資產投資組合研究與優化系統，涵蓋台股、美股、ETF（含債券/商品 ETF 代理）、期貨。Python 後端 + React Web + Android Native 單體倉庫。後端 128 檔案、22.5K LOC、1,006 tests。具備 14 種組合最佳化方法、14 個 Alpha 因子、10 條風控規則、71 個 API 端點。回測引擎與策略框架已成熟，自動化 Alpha 排程系統已實作。Phase A~H 全部完成。

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
| H 實用精煉 | 2026-03-26 | Deflated Sharpe Ratio + MinBTL、Semi-Variance 最佳化、Kalman Filter Pairs Trading |

---

## 3. 當前阻塞與待辦

### 3.1 阻塞項（需外部條件）

| 項目 | 阻塞原因 | 解除後工作 |
|------|---------|-----------|
| Shioaji 整合測試 | 等待 API Key 核發 | 真實環境 login/下單/行情驗證 |
| E2 即時行情 broadcast | 需 API Key 取得 tick 資料 | WS `market` 頻道接 SinopacQuoteManager |
| E3 Paper Trading 循環 | 需 API Key 跑 simulation=True | 排程→下單→回報→對帳→通知 完整驗證 |

### 3.2 已解決的孤島（v6.1 整合完成）

| 模組 | 整合方式 |
|------|---------|
| G3 回測工具 (Randomized/PBO/Stress) | ✅ 已新增 3 個 API 端點 (`/backtest/randomized`, `/pbo`, `/stress-test`) |
| F4 DynamicFactorPool | ✅ 已整合至 `AlphaDecisionEngine.decide()` + `AlphaScheduler.run_full_cycle()` |
| F3b WS auto-alpha 頻道 | ✅ 已完成 |
| F3c Auto-Alpha Dashboard | ✅ 已完成 |

### 3.3 低優先級待辦

| 項目 | 優先級 | 說明 |
|------|--------|------|
| F2d Alembic migration | 🟢 P2 | AlphaStore 目前使用 JSON 檔案，正式部署時需 DB migration |
| FastAPI lifespan handler | 🟢 P2 | 替換 deprecated `on_event` (DeprecationWarning) |

---

## 4. Phase H：實用精煉 ✅ (2026-03-26 完成)

| 項目 | 說明 | 論文依據 |
|------|------|---------|
| H1 ✅ | `deflated_sharpe()` + `min_backtest_length()` — 多重測試校正 | Bailey & López de Prado (2014) |
| H2 ✅ | `OptimizationMethod.SEMI_VARIANCE` — 下行風險最佳化（第 14 個方法） | Markowitz downside framework |
| H3 ✅ | `KalmanHedgeRatio` + `PairsTradingStrategy(method="kalman")` | Kalman Filter state-space model |

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
| 2026-03-26 | Phase F~H（自動化 Alpha + 學術升級 + 實用精煉），1,006 tests |
| TBD | Shioaji API Key 取得 → 整合測試 → Paper Trading 驗證 |
| TBD | Alpha 自動化擴展至 ETF / 跨資產配置（下一階段） |
