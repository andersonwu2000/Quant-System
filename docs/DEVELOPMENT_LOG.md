# 開發紀錄

> **專案**: 多資產投資組合研究與優化系統
> **起始日期**: 2026-03-22
> **AI 協作**: Claude Code (Anthropic)

---

## 專案背景

專案目標是建立一個涵蓋台股、美股、ETF、期貨的投資組合研究與優化平台，面向個人投資者與家庭資產管理。

關鍵技術決策：
- 數據源選擇 FinMind 作為台股主要來源（可擴展至美股）
- 券商選擇永豐金 Shioaji SDK（Python 原生、跨平台、模擬交易支援）
- 前端從 React Native 遷移至 Android 原生 (Jetpack Compose)

---

## 時間線

### Day 1 — 2026-03-22（4 commits）

**從零開始建立系統骨架。**

- 初始化 Python 後端：回測引擎、策略框架、風控引擎、SimBroker
- 7 個內建策略：Momentum、Mean Reversion、RSI、MA Crossover、Multi-Factor、Pairs Trading、Sector Rotation
- 資料層：Yahoo Finance DataFeed
- CLI 工具：`backtest` / `server` / `status` / `factors`
- 中文快速入門文件 + 系統規格說明書

**里程碑**: 可以跑第一個回測。

### Day 2 — 2026-03-23（22 commits）

**Monorepo 整合 + 全端架構建立 + 品質基礎。**

前端：
- React 18 + Vite + Tailwind Web Dashboard（8 個頁面）
- React Native + Expo 52 Mobile App（7 tabs）
- `@quant/shared` TypeScript 共享套件（型別/API/WS/格式化）
- 國際化 (i18n) 英文+繁體中文
- 深色主題、PageSkeleton、Toast、ErrorBoundary

後端：
- FastAPI REST API + WebSocket (4 頻道)
- JWT + API Key 雙模認證 + 5 級角色 (RBAC)
- Docker + docker-compose (API + PostgreSQL)
- GitHub Actions CI (9 jobs)
- Alembic 資料庫遷移（4 個 migration）
- 通知系統 (Discord / LINE / Telegram)

品質：
- mypy strict 全面通過
- ruff lint 零錯誤
- Vitest (Web) + Jest (Mobile) + Playwright (E2E) 測試框架
- 用戶管理系統（DB-backed auth, admin GUI）

**里程碑**: 完整的全端系統，可以在瀏覽器和手機上操作。

### Day 3 — 2026-03-24（30 commits）

**Alpha 研究層 + 多資產基礎設施 (Phase A-C)。**

Alpha 研究（11 個模組）：
- 因子庫：11 個技術因子 + 3 個基本面因子
- Pipeline：universe → 因子計算 → 中性化 → 正交化 → Rolling IC → 分位數回測 → 成本感知建構
- Regime 分析：Bull/Bear/Sideways 市場環境分類
- 因子歸因：weight-based + OLS regression 分解
- AlphaStrategy 適配器：Pipeline 包裝為 Strategy

Phase A — 多資產基礎設施：
- InstrumentRegistry：自動從 symbol 推斷 asset_class/market/currency
- 多幣別 Portfolio：`nav_in_base(fx_rates)` / `currency_exposure()`
- DataFeed 擴展：FX 時間序列、FRED 宏觀數據
- 管線整合：`weights_to_orders()` 支援乘數、lot_size

Phase B — 跨資產 Alpha：
- MacroFactorModel：成長/通膨/利率/信用（FRED z-scores）
- CrossAssetSignals：動量/波動率/價值 per AssetClass
- TacticalEngine：戰略權重 + 宏觀 + 跨資產 + regime → 戰術權重

Phase C — 組合最佳化：
- PortfolioOptimizer：6 方法 (EW/IV/RP/MVO/BL/HRP)
- RiskModel：Ledoit-Wolf 收縮共變異數 + 風險貢獻
- CurrencyHedger：分級對沖 + HedgeRecommendation

其他：
- FinMind 整合（台股數據 + 基本面）
- Walk-forward 回測
- Portfolio 持久化 (CRUD + rebalance preview)
- Alpha 前端頁面 + API

**里程碑**: 從單一股票系統升級為多資產平台。Phase A-C 3 天完成。

### Day 4 — 2026-03-25（18 commits）

**Phase D 系統整合 + Phase E 實盤交易層。**

Phase D — 系統整合：
- MultiAssetStrategy：兩層配置策略（戰術→Alpha→最佳化）
- 跨資產風控：`max_asset_class_weight` / `max_currency_exposure` / `max_gross_leverage`
- AllocationPage 前端
- Bug fixes：FX per-bar 更新 / 總權重驗證 / FRED ffill

Phase E — 交易執行層：
- **SinopacBroker**：Shioaji SDK 封裝（非阻塞下單、成交回報 callback、斷線重連）
- **ExecutionService**：模式路由 (backtest → SimBroker, paper/live → SinopacBroker)
- **SinopacQuoteManager**：即時行情訂閱 (tick/bidask STK + FOP)
- **ShioajiFeed**：Shioaji 歷史數據源 (1 分鐘 K 棒 / tick / snapshot)
- **ShioajiScanner**：市場排行 + 處置/注意股排除 + 動態 universe
- **StopOrderManager**：軟體觸價委託 (stop-loss/profit)
- 交易時段管理（盤前/盤中/零股/定盤 + 盤外佇列）
- EOD 持倉對帳 + 自動修正
- Order 模型擴展：OrderCondition (融資/融券/當沖) + StockOrderLot (零股/定盤)
- Scheduler rebalance job 接通完整策略→風控→下單→Portfolio→通知流程

前端：
- Paper Trading 頁面
- Guide 系統（7 章教學）
- Android 原生 App：Kotlin Jetpack Compose, 8 個 screen

**里程碑**: 系統可以做紙上交易了（待 API Key）。Shioaji SDK 已安裝。

### Day 5 — 2026-03-26（25 commits）

**多資產 Alpha 擴展 + Phase F 自動化 Alpha + Phase G 學術最佳化 + Phase H 進階。**

多資產 Alpha 擴展：
- neutralize.py：INDUSTRY/SIZE 缺少資料時自動退化為 MARKET（ETF/期貨安全）
- universe.py：`asset_classes` / `exclude_asset_classes` 篩選
- cross_section.py：年化改為從實際交易日推算
- UniversePicker +Futures tab（13 個期貨合約）
- 中性化方法警告 tooltip

Phase F — 自動化 Alpha 研究：
- **F1 核心引擎** (6 檔案)：AutoAlphaConfig → UniverseSelector → AlphaResearcher → AlphaDecisionEngine → AlphaExecutor → AlphaScheduler
- **F2 基礎設施** (3 檔案)：AlphaStore (DB 持久化) + AlertManager (通知) + SafetyChecker (回撤熔斷)
- **F3 API** (10 端點)：start/stop/run-now/status/history/snapshots + WS auto-alpha 頻道
- **F4 進階** (3 檔案)：FactorPerformanceTracker (累計 IC + 回撤 per factor) + DynamicFactorPool (ICIR 排名自動新增/移除) + REGIME_FACTOR_BIAS (Bull/Bear/Sideways 偏好矩陣)
- Auto-Alpha Dashboard 前端

Phase G — 學術級組合最佳化（基於 Palomar 教科書 + 9 篇論文）：
- **G1**: CVaR 最佳化 (Rockafellar & Uryasev 2000) + VaR/CVaR 績效指標
- **G2**: Robust 組合 (橢圓不確定集) + Portfolio Resampling (Michaud) + James-Stein 均值收縮 (Jorion 1986)
- **G3**: Multiple Randomized Backtest + CSCV/PBO (Bailey et al. 2015) + k-fold 時序 CV + 壓力測試
- **G4**: GARCH 波動率 + PCA 因子模型共變異數
- **G5**: Index Tracking (LASSO) + Maximum Sharpe (Dinkelbach) + GMV
- **G6**: Pairs Trading 升級（Engle-Granger 共整合）
- **G7**: Omega Ratio + Rolling Sharpe
- **G8**: 存活偏差偵測 + 借券成本 + 離群值偵測

Phase H — 進階：
- Deflated Sharpe Ratio + MinBTL
- Semi-variance 組合最佳化
- Kalman Filter 動態 hedge ratio (Pairs Trading)

Phase I — Alpha 因子庫擴展：
- Fama-French 補齊：size (SMB)、investment (CMA)、gross_profitability (Novy-Marx)
- Kakushadze 101 精選：10 個 price-volume 因子（向量化實作）
- 因子篩選閾值校正：ICIR 0.3→0.5 (Harvey 2016)、OOS decay 0.42 (McLean-Pontiff)
- Momentum Crash 防護 (Daniel & Moskowitz 2016)
- 因子庫重構為 package：`src/strategy/factors/` (technical.py + fundamental.py + kakushadze.py)
- 向量化因子計算 VECTORIZED_FACTORS — 15x 加速

Bug 修復與穩定性：
- **台股回測崩潰修復 (D-45)**：Yahoo Finance 對下市台股回傳空 DataFrame (RangeIndex)，對上市台股回傳 tz-aware index (Asia/Taipei)，兩者與 tz-naive Timestamp 比較時報 `'>=' not supported between numpy.ndarray and Timestamp`。在 yahoo/finmind/feed/context/parquet_cache 五層加入防護
- Android 二次啟動 crash 修復
- DatetimeIndex 反序列化防護（Parquet 快取）
- T1 Bug：最低手續費、零股滑點、除權息過濾
- 28 項 App 穩定性問題修復

基礎設施：
- **Tailscale 行動連線**：README 新增教學，Android cleartext 白名單加入所有 Tailscale 裝置
- 實驗網格框架 + GPU 因子運算
- 本地優先資料存儲 + 實驗結果持久化

架構重構 R1-R4：
- **R1** TWAP Smart Order (`src/execution/smart_order.py`)：大單拆 N 筆等量子單
- **R2** 台股交易日曆 (`src/core/calendar.py`)：TWTradingCalendar 國定假日排除
- **R3** Trading Pipeline (`src/core/trading_pipeline.py`)：`execute_one_bar()` 回測/實盤共用
- **R4** Broker 子套件重構：`src/execution/broker/` + `src/execution/quote/`

Shioaji 整合測試：
- API Key 取得，模擬模式 (simulation=True) 驗證通過
- login + 基本下單 + 帳務查詢 + 處置股查詢 — 全部通過
- Deal callback + tick streaming 需生產環境 CA 憑證

Android 修復 + CI 完善 + 文件重寫

**里程碑**: 系統從「可用」升級為「學術級」。27 因子、1,151 tests、147 後端檔案。Shioaji 模擬整合通過。台股回測穩定性驗證（14 支半導體股 on Android）。

---

## 數字摘要

| 指標 | 數值 |
|------|------|
| 開發天數 | 5 天 |
| Git commits | 145 |
| 檔案變更 | 512+ |
| 新增程式碼 | ~91,000 行 |
| Python 後端 | 147 檔案 |
| Python 測試 | 89 檔案, **1,151 tests** |
| Web 前端 (TS/TSX) | 143 檔案 |
| Android (Kotlin) | 56 檔案 |
| 共享套件 (TS) | 11 檔案 |
| 策略數 | 9 |
| Alpha 因子 | 27 (11 技術 + 10 Kakushadze + 6 基本面) |
| 最佳化方法 | 14 (EW/IV/RP/MVO/BL/HRP/CVaR/Robust/Resampled/MaxSharpe/GMV/IndexTracking/Semi-variance/MaxDrawdown) |
| 風控規則 | 12 |
| API 端點 | 74 |
| 數據源 | 5 (Yahoo/FinMind/FRED/Shioaji/Scanner) |
| 參考論文 | 21 篇 (已下載分類至 `docs/ref/`) |
| CI Jobs | 9 + Release pipeline |

---

## 技術演進

### 架構演進

```
Day 1:  Python 回測 CLI
         ↓
Day 2:  + React Web + Mobile + API + Auth + Docker + CI
         ↓
Day 3:  + Alpha Pipeline + 多資產 (Registry/Portfolio/Allocation/Optimizer)
         ↓
Day 4:  + Shioaji 券商 + Paper Trading + Android Native
         ↓
Day 5:  + Auto-Alpha + 學術最佳化 (14 方法) + 27 因子 + R1-R4 重構 + Shioaji 模擬整合
         + 台股回測穩定性修復 + Tailscale 行動連線 + 實驗框架
```

### 開發方法

- **AI 協作開發**: 程式碼由 Claude Code 撰寫，開發者負責方向決策、code review、測試驗證
- **平行 Agent**: 最多 3 個 Agent 同時開發不同模組，大幅縮短開發時間
- **測試驅動**: 每個功能附帶完整單元測試（mock SDK、mock API），保持 CI 綠燈
- **論文驅動**: Phase G/H 直接從學術論文（Rockafellar, Bailey, Ledoit-Wolf, Wang 等）翻譯數學公式為 Python 實作
- **文件同步**: CLAUDE.md / SYSTEM_STATUS_REPORT / DEVELOPMENT_PLAN / MULTI_ASSET_ARCHITECTURE 持續更新

### 關鍵決策紀錄

| 日期 | 決策 | 原因 |
|------|------|------|
| 03-22 | 選擇 Python + FastAPI | 量化生態系最完整 |
| 03-23 | Monorepo 架構 | Web + Mobile + Shared 共用型別 |
| 03-24 | FinMind 作為台股數據源 | 免費 + 財報支援 + API 品質 |
| 03-24 | Ledoit-Wolf 收縮 | 解決 N >> T 時共變異數估計問題 |
| 03-25 | 永豐金 Shioaji | Python 原生 SDK、唯一支援 `simulation=True` 的台灣券商 |
| 03-25 | Android 取代 React Native | Expo prebuild 問題多，原生 Compose 更穩定 |
| 03-26 | Auto-Alpha 架構 | 手動 Alpha 研究無法即時跟蹤因子衰減 |
| 03-26 | 基於論文實作 Phase G | Palomar 教科書 + 9 篇 P0/P1 論文作為實作依據 |

---

## 開發階段對照

| Phase | 名稱 | 天數 | Commits | 核心產出 |
|-------|------|------|---------|---------|
| — | 基礎系統 | Day 1-2 | 26 | 回測引擎 + 7 策略 + 風控 + API + Web + Mobile + CI |
| A | 多資產基礎設施 | Day 3 | 5 | InstrumentRegistry + 多幣別 Portfolio + FX + FRED |
| B | 跨資產 Alpha | Day 3 | 2 | 宏觀因子 + 跨資產信號 + 戰術配置引擎 |
| C | 組合最佳化 | Day 3 | 2 | 6 方法 + Ledoit-Wolf + 幣別對沖 |
| D | 系統整合 | Day 4 | 3 | MultiAssetStrategy + 跨資產風控 + Allocation 前端 |
| E | 實盤交易 | Day 4-5 | 8 | SinopacBroker + ExecutionService + Scanner + StopOrder |
| F | 自動化 Alpha | Day 5 | 5 | 12 模組: Researcher → Decision → Executor → Scheduler → Store |
| G | 學術最佳化 | Day 5 | 4 | CVaR + Robust + PBO + GARCH + IndexTracking + 更多 |
| H | 進階 | Day 5 | 3 | Deflated SR + Semi-variance + Kalman Pairs |
| I | Alpha 因子擴展 | Day 5 | — | 27 因子 + 向量化 15x + 閾值校正 + Momentum Crash |
| R1-R4 | 架構重構 | Day 5 | — | TWAP + 交易日曆 + Trading Pipeline + Broker 子套件 |

---

## 關鍵決策紀錄

### 2026-03-26：策略驗證優先於生產環境整合

**問題**: Shioaji API Key 已取得，是否應該立即申請 CA 憑證進入生產環境？

**決策**: **否。先驗證 Alpha 策略盈利能力。**

**理由**:
- CA 憑證是執行品質的改善（成交回報、即時行情），不是盈利能力的保證
- 如果策略 Sharpe < 0，連上生產環境只會更快虧錢
- 首次實測 10 支台股，只有 momentum (IC=+0.157) 有信號，但 universe 太小統計不可靠
- ICIR 門檻 0.5 符合 Harvey et al. (2016) t>3.0 標準，不應下調
- 問題在 universe 規模（10 支太少），不是門檻設定

**下一步**: 用 Shioaji Scanner 取 150+ 支台股跑完整 Alpha 驗證 → 通過後再申請 CA 憑證

### 2026-03-26：Decision → Execution 之間需要回測閘門

**問題**: Auto-Alpha 的 Decision 選出因子後直接進入 Execution，沒有驗證近期 OOS 表現。

**決策**: 新增 Stage 3.5 Validation Backtest（架構已設計，待實作）。

### 2026-03-26：Alpha 策略驗證完成 — 15 次實驗的最終結論

**過程**: 從 10 支大型股 → 142 支寬 universe → 66 因子 → 籌碼面 → 分層策略 → 嚴格統計檢驗，共 15 次實驗。

**結論**:
- **台股 142 支、66 個 price-volume + 9 個籌碼面因子：沒有任何因子通過 ICIR 0.5 門檻**
- 最佳策略 (mom6m + turnover_vol 大型股) 毛超額 +7.3%/年，但成本拖累 6.6% → **淨超額僅 +0.7%**
- **統計不顯著** (t=0.24, p=0.81)，**OOS 為負** (-3.2%)
- 1/N 等權在台股很難被公開數據因子打敗（DeMiguel 2009 驗證）
- 實驗報告見 `docs/research/20260326_1.md` ~ `20260326_6.md`

### 2026-03-26：即時行情 + 風控即時化完成

- WebSocket `market` 頻道接入 SinopacQuoteManager tick/bidask broadcast ✅
- `RealtimeRiskMonitor` — 逐 tick 更新 NAV、分級告警 (2%/3%/5%)、kill switch ✅
- `GET /api/v1/risk/realtime` 端點 ✅
- 19 tests passed ✅

### 2026-03-26：Auto-Alpha 系統改善（基於實驗結論）

- 預設因子從 66 個改為 3 個（RSI + momentum + momentum_6m）
- 預設大型股分層（size_filter="large"）
- Emergency DD 放寬 5% → 10%（Kill switch 太嚴會錯過反彈）
- run-now 優先讀本地 Parquet 快取
- 訂單管理新增改單/取消功能（PUT/DELETE /orders/{id}）

---

## 已知限制與待辦

### 策略研究現狀
- **台股公開數據的量化 alpha 天花板約 +0.7%/年（淨超額，統計不顯著）**
- 需要即時/獨家數據源（即時法人、分析師預期修正）才可能突破
- 或接受 1/N + 月度再平衡 + DD control 作為基線策略

### 阻塞項
- Shioaji CA 憑證 → deal callback + tick streaming 完整循環
- PostgreSQL production → 目前僅 SQLite

### 工程待辦
- ~~FastAPI `on_event` deprecated → lifespan handler~~ ✅ D-28
- WebSocket `market` 頻道接入 SinopacQuoteManager (D-27)
- Auto-Alpha DB migration (Alembic 005)
- ~~台股回測 tz-aware / empty DataFrame crash~~ ✅ D-45
- ngrok domain 被舊 agent 佔用 → 已改用 Tailscale
- Stage 3.5 Validation Backtest 實作

---

## 參考資源

- `docs/claude/SYSTEM_STATUS_REPORT.md` — 系統現況追蹤（738 行）
- `docs/plans/DEVELOPMENT_PLAN.md` — 開發計畫 v7.0
- `docs/architecture/MULTI_ASSET_ARCHITECTURE.md` — 架構設計
- `docs/ref/REFERENCES.md` — 論文索引 (21 篇 + 6 本書 + 10 個 code references)
- `docs/ref/papers/` — 按 portfolio/data-modeling/backtesting/alpha 分類的論文 PDF
