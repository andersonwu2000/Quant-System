# 系統現況追蹤報告書

> **報告日期**: 2026-03-26
> **版本**: v5.1
> **當前階段**: Phase A~I + R1-R4 完成, Shioaji 模擬整合通過
> **代碼庫**: 2026-03-22 起始，master 分支
> **架構設計**: `docs/dev/architecture/MULTI_ASSET_ARCHITECTURE.md`
> **開發計畫**: `docs/dev/DEVELOPMENT_PLAN.md` v7.2

---

## 1. 專案概要

多資產投資組合研究與優化系統，覆蓋台股、美股、ETF（含債券/商品 ETF 代理）、台灣期貨、美國期貨。面向個人投資者與家庭資產管理。

**Monorepo 結構**: Python 後端 + React 18 Web + Android Native (Kotlin/Compose) + TypeScript 共享套件。

**目標市場**: 台灣股市（手續費 0.1425%、證交稅 0.3%）為預設，透過 Yahoo Finance / FinMind / Shioaji 支援全球市場。

---

## 2. 技術棧

| 層級 | 技術 | 版本 |
|------|------|------|
| 後端語言 | Python | 3.12 |
| 型別檢查 | mypy strict + ruff lint | — |
| API 框架 | FastAPI + Uvicorn | — |
| 資料庫 | PostgreSQL 16 (prod) / SQLite (dev) | Alembic 4 migrations |
| Web 前端 | React 18 + Vite + Tailwind CSS | — |
| Mobile | Android Native (Kotlin + Jetpack Compose) | — |
| 共享套件 | `@quant/shared` TypeScript | — |
| 券商 SDK | Shioaji (永豐金) | 1.3.2 |
| CI/CD | GitHub Actions (9 jobs) | — |
| 容器 | Docker (multi-stage) + docker-compose | PostgreSQL 16 Alpine |

---

## 3. 代碼庫統計

### 3.1 總覽

| 指標 | 數值 |
|------|------|
| 後端 Python 檔案 (src/ + strategies/) | 149 (141 src + 8 strategies) |
| 後端 Python LOC | ~25,400 (24,573 + 786) |
| 測試檔案 | 91 |
| 測試 LOC | ~16,400 |
| 測試數量 (pytest collected) | **1,159** |
| Web 前端檔案 (.tsx/.ts) | 126 |
| Web 前端 LOC | 9,277 |
| Android 檔案 (.kt) | 40+ |
| 共享套件檔案 (.ts) | 11 |
| 共享套件 LOC | 1,257 |
| **全系統 LOC** | **~43,000** |

### 3.2 後端模組明細

| 模組 | 檔案數 | LOC | 功能描述 |
|------|--------|-----|----------|
| `src/api/` | 22 | ~3,300 | REST API (14 路由, 74 端點) + WebSocket (5 頻道) + JWT/RBAC 認證 + 限流 + 審計 |
| `src/data/` | 15 | 2,334 | 4 數據源 (Yahoo/FinMind/FRED/Shioaji) + Scanner + 磁碟快取 + 基本面 |
| `src/alpha/` | 24 | ~4,250 | Alpha 研究：27 因子 + 中性化 + 正交化 + Rolling IC + 分位數回測 + Pipeline (含 EW Sharpe 比較) + Regime + Attribution + **自動化 Alpha (config/universe/researcher/decision/executor/scheduler/factor_tracker/dynamic_pool/backtest_gate, OOS decay 校正, net alpha 過濾)** |
| `src/backtest/` | 11 | ~3,800 | 回測引擎：多資產/多幣別/FX 時序 + 40+ 績效指標 (含 Omega/Rolling Sharpe/VaR/CVaR/DSR) + HTML/CSV 報表 + Walk-forward + Randomized Backtest + PBO (CSCV) + K-Fold CV + Stress Test + **回測防禦 (存活者偏差偵測/價格異常偵測/融券借券成本)** + Deflated Sharpe Ratio + MinBTL + **Experiment Grid (parallel backtesting across parameter combinations)** |
| `src/execution/` | 16 | ~2,120 | `broker/` (base + simulated + sinopac) + `quote/` (sinopac) + `service.py` (ExecutionService) + OMS + 行情訂閱 + 對帳 + 交易時段 + 觸價委託 + **TWAP 拆單 (`smart_order.py`)** + backward-compat shims |
| `src/strategy/` | 12 | ~2,150 | 策略 ABC + `factors/` package (technical/fundamental/kakushadze — 27 因子 + **GPU-accelerated factors via PyTorch CUDA**) + 最佳化器 (3) + 研究工具 (multi-metric FundamentalFactorDef, **向量化因子計算 VECTORIZED_FACTORS**) + Registry + MultiAssetStrategy |
| `src/portfolio/` | 4 | ~1,260 | 組合最佳化 (14 方法: EW/InvVol/RP/MVO/BL/HRP/Robust/Resampled/CVaR/MaxDD/GMV/MaxSharpe/IndexTracking/SemiVariance) + 風險模型 (LW/GARCH/Factor Model Cov + VaR/CVaR 歷史+參數法) + James-Stein 均值收縮 + 幣別對沖 |
| `src/allocation/` | 4 | 713 | 戰術配置：宏觀四因子 + 跨資產信號 (動量/波動率/價值) + 戰術引擎 |
| `src/core/` | 6 | ~930 | 核心模型 (models.py) + 設定 (config.py) + 日誌 (logging.py) + Repository + **TWTradingCalendar (calendar.py)** + **trading_pipeline.py (共用交易流程)** |
| `src/domain/` | 3 | ~30 | Backward-compat shims (re-export from `src/core/`) |
| `src/risk/` | 4 | 573 | 風控引擎 (10 規則) + Kill Switch + RiskMonitor |
| `src/instrument/` | 3 | 331 | InstrumentRegistry + 自動推斷 (symbol → asset_class/market/currency) |
| `src/cli/` | 2 | 299 | CLI: backtest / server / status / factors |
| `src/notifications/` | 6 | 246 | Discord / LINE / Telegram 通知 |
| `src/scheduler/` | 2 | 206 | APScheduler：排程 rebalance（已接通策略→風控→下單→通知） |
| `src/` (根) | 2 | ~10 | Backward-compat shims: config.py, logging_config.py (re-export from `src/core/`) |
| `strategies/` | 8 | ~800 | 7 個內建策略 (pairs_trading: Engle-Granger 共整合 + OLS hedge ratio + Kalman Filter 動態 hedge ratio) |

---

## 4. 功能模組詳述

### 4.1 策略引擎（9 個策略）

| # | 策略 | 位置 | 邏輯 | 類型 |
|---|------|------|------|------|
| 1 | Momentum | `strategies/momentum.py` | 12-1 個月動量 | 規則型 |
| 2 | Mean Reversion | `strategies/mean_reversion.py` | Z-score 均值回歸 | 規則型 |
| 3 | RSI Oversold | `strategies/rsi_oversold.py` | RSI < 30 超賣反彈 | 規則型 |
| 4 | MA Crossover | `strategies/ma_crossover.py` | 快/慢均線交叉 | 規則型 |
| 5 | Multi-Factor | `strategies/multi_factor.py` | 動量+價值+品質 (risk-parity 加權) | 規則型 |
| 6 | Pairs Trading | `strategies/pairs_trading.py` | 統計套利：Engle-Granger 共整合 + OLS hedge ratio / Kalman Filter 動態 hedge ratio (fallback 相關性) | 規則型 |
| 7 | Sector Rotation | `strategies/sector_rotation.py` | 板塊相對動量輪動 | 規則型 |
| 8 | Alpha Pipeline | `src/alpha/strategy.py` | 可配置因子管線 (中性化→正交化→IC 加權→建構) | 管線型 |
| 9 | Multi-Asset | `src/strategy/multi_asset.py` | 兩層配置：戰術 → 資產內 Alpha → 組合最佳化 | 管線型 |

### 4.2 Alpha 因子庫（27 因子）

**價格因子 (11)**:

| 因子 | 函數 | 訊號方向 |
|------|------|---------|
| momentum | `momentum_factor()` | 正：追漲 |
| mean_reversion | `mean_reversion_factor()` | 負：逆勢 |
| volatility | `volatility_factor()` | 負：低波動溢酬 |
| rsi | `rsi_factor()` | 負：超賣 |
| ma_cross | `ma_cross_factor()` | 正：均線多頭 |
| vpt | `volume_price_trend()` | 正：量價齊升 |
| reversal | `short_term_reversal()` | 負：短期反轉 |
| illiquidity | `amihud_illiquidity()` | 正：流動性溢酬 |
| ivol | `idiosyncratic_vol()` | 負：低特質波動 |
| skewness | `skewness()` | 負：負偏態溢酬 |
| max_ret | `max_return()` | 負：彩券效應 |

**Kakushadze 101 精選 (10)** — Phase I2:

| 因子 | 函數 | 類型 |
|------|------|------|
| alpha_2 | `kakushadze_alpha_2()` | volume-price 相關 |
| alpha_3 | `kakushadze_alpha_3()` | volume-price 相關 |
| alpha_6 | `kakushadze_alpha_6()` | volume-price 相關 |
| alpha_12 | `kakushadze_alpha_12()` | 量價反轉 |
| alpha_33 | `kakushadze_alpha_33()` | 日內動量 |
| alpha_34 | `kakushadze_alpha_34()` | 波動率 regime |
| alpha_38 | `kakushadze_alpha_38()` | 均值回歸 |
| alpha_44 | `kakushadze_alpha_44()` | volume-price 相關 |
| alpha_53 | `kakushadze_alpha_53()` | Williams %R 變體 |
| alpha_101 | `kakushadze_alpha_101()` | 日內動量 |

**基本面因子 (6)** — 含 Phase I1 Fama-French 補齊:

| 因子 | 訊號 | 數據源 | 論文 |
|------|------|--------|------|
| value_pe | 低 P/E | FinMind | — |
| value_pb | 低 P/B | FinMind | — |
| quality_roe | 高 ROE | FinMind | — |
| size | -log(market_cap)，小市值溢酬 | FinMind `market_cap` | Fama-French (1993) SMB |
| investment | 負資產成長，保守投資溢酬 | FinMind `total_assets` | Fama-French (2015) CMA |
| gross_profit | (Revenue - COGS) / Total Assets | FinMind 財報 | Novy-Marx (2013) |

### 4.3 數據源

| 數據源 | 檔案 | 覆蓋 | 用途 |
|--------|------|------|------|
| Yahoo Finance | `yahoo.py` | 全球市場日線 | 回測主數據源 |
| FinMind | `finmind.py` + `finmind_fundamentals.py` | 台股日線 + 財報 | 台股回測 + 基本面因子 |
| FRED | `fred.py` | 美國經濟指標 | 宏觀因子 (成長/通膨/利率/信用) |
| Shioaji | `shioaji_feed.py` | 台股 1 分鐘 K 棒 + tick (2020-03 起) | 分鐘級回測 + 即時定價 |
| Scanner | `scanner.py` | Shioaji 市場排行 + 處置/注意股 | 動態 universe 篩選 |
| 快取 | `parquet_cache.py` | Parquet 磁碟快取 | 避免重複下載 |

### 4.4 風控規則（10 條）

| # | 規則 | 層級 | 預設閾值 | 說明 |
|---|------|------|---------|------|
| 1 | max_position_weight | 個股 | 5% | 單一標的權重上限 |
| 2 | max_order_notional | 個股 | 2% NAV | 單筆金額上限 |
| 3 | daily_drawdown_limit | 組合 | 3% | 日回撤觸發 kill switch |
| 4 | fat_finger_check | 個股 | 5% | 價格偏離參考價檢查 |
| 5 | max_daily_trades | 組合 | 100 | 當日交易次數上限 |
| 6 | max_order_vs_adv | 個股 | 10% ADV | 流動性限制 |
| 7 | price_circuit_breaker | 個股 | 10% | 漲跌停價格熔斷 |
| 8 | max_asset_class_weight | 跨資產 | 40% | 資產類別集中度上限 |
| 9 | max_currency_exposure | 跨資產 | 60% | 幣別暴露上限 |
| 10 | max_gross_leverage | 跨資產 | 1.5x | 總槓桿上限 |

### 4.5 交易執行層

| 模組 | 檔案 | 功能 | 狀態 |
|------|------|------|------|
| BrokerAdapter ABC | `broker.py` | 券商統一介面 (submit/cancel/query) | ✅ |
| PaperBroker | `broker.py` | 簡易紙上交易 stub | ✅ |
| SimBroker | `sim.py` | 回測模擬撮合 (sqrt 滑點, per-instrument 費率, 漲跌停) | ✅ |
| SinopacBroker | `sinopac_broker.py` | Shioaji SDK 封裝 (非阻塞下單, 成交回報, 斷線重連) | ✅ 程式碼 |
| SinopacQuoteManager | `sinopac_quote.py` | 即時行情訂閱 (tick/bidask STK + FOP callbacks) | ✅ 程式碼 |
| ExecutionService | `execution_service.py` | 模式路由 (backtest/paper/live) + 下單前檢查 | ✅ |
| OrderManager | `oms.py` | 訂單生命週期管理 + 成交記錄 | ✅ |
| Market Hours | `market_hours.py` | 台股時段驗證 + 盤外委託佇列 + 國定假日排除 (TWTradingCalendar) | ✅ |
| Reconcile | `reconcile.py` | EOD 持倉對帳 (diff + auto_correct) | ✅ |
| StopOrderManager | `stop_order.py` | 軟體觸價委託 (stop-loss / stop-profit) | ✅ |
| TWAPSplitter | `smart_order.py` | TWAP 拆單引擎 (大單拆 N 筆等量子單，降低 market impact) | ✅ |

**SinopacBroker 擴展功能**:
- `query_trading_limits()` — 交易額度/融資融券額度預檢
- `query_settlements()` — T+N 交割查詢
- `check_dispositions()` — 處置股清單查詢
- 非阻塞下單 (`timeout=0`, ~12ms vs ~136ms)

### 4.6 組合最佳化（14 方法）

| 方法 | 說明 |
|------|------|
| Equal Weight (EW) | 等權重 |
| Inverse Volatility (IV) | 反波動率加權 |
| Risk Parity (RP) | 風險平價（等風險貢獻） |
| Mean-Variance (MVO) | Markowitz 均值變異數 |
| Black-Litterman (BL) | 支援 `BLView` 主觀觀點 |
| Hierarchical Risk Parity (HRP) | 階層式風險平價 |
| Robust (Worst-case) | 橢圓不確定集穩健最佳化 |
| Resampled (Michaud) | 蒙地卡羅重取樣平均 |
| CVaR Optimization | 最小化 CVaR (Rockafellar-Uryasev LP 重構) |
| Max Drawdown | 最小化最大回撤（歷史模擬 SLSQP） |
| Global Minimum Variance (GMV) | 最小化組合波動率（獨立入口） |
| Maximum Sharpe (MaxSharpe) | Dinkelbach 分數規劃嚴格 MSR |
| Index Tracking | LASSO 稀疏追蹤（Benidis/Feng/Palomar） |

**風險模型**: 歷史 / EWM / Ledoit-Wolf 收縮 / GARCH(1,1) / PCA 因子模型共變異數 + 邊際風險貢獻 + VaR/CVaR (歷史+參數法) + James-Stein 均值收縮。

### 4.7 戰術配置

**宏觀四因子** (FRED 數據):
- Growth — 工業生產/PMI/就業
- Inflation — CPI/PPI/預期通膨
- Rates — 10Y 殖利率/期限利差
- Credit — 信用利差/BAA-AAA

**跨資產信號**: 動量 / 波動率 / 價值（per AssetClass）。

**流程**: 戰略權重 + 宏觀偏離 + 跨資產信號 + Regime → 戰術權重。

---

## 5. API 架構

### 5.1 REST 端點（14 路由模組, 74 端點）

| 模組 | 端點數 | 前綴 | 關鍵端點 |
|------|--------|------|---------|
| auth | 3 | `/api/v1/auth` | login, register, refresh |
| admin | 5 | `/api/v1/admin` | 用戶 CRUD, 審計日誌, 配置 |
| portfolio | 8 | `/api/v1/portfolio` | CRUD + rebalance-preview + 交易歷史 |
| backtest | 8 | `/api/v1/backtest` | 回測 + walk-forward + randomized + PBO + stress-test + 歷史結果 |
| strategies | 4 | `/api/v1/strategies` | 列表 + 啟停控制 |
| orders | 2 | `/api/v1/orders` | 手動下單 + 訂單歷史 |
| risk | 4 | `/api/v1/risk` | 規則狀態 + kill switch + 告警 |
| alpha | 3 | `/api/v1/alpha` | Alpha 研究 + 因子查詢 |
| allocation | 1 | `/api/v1/allocation` | 戰術配置計算 |
| execution | 6 | `/api/v1/execution` | 執行狀態 + 交易時段 + 對帳 + Paper trading + 佇列 |
| auto_alpha | 10 + WS | `/api/v1/auto-alpha` | 自動 Alpha: config/start/stop/status/history/performance/alerts/run-now + WebSocket `/ws` |
| system | 3 | `/api/v1/system` | 健康檢查 + Prometheus metrics |

### 5.2 WebSocket 頻道

| 頻道 | 說明 | 來源 |
|------|------|------|
| `portfolio` | 持倉 + NAV 即時更新 | 策略執行 / 成交回報 |
| `orders` | 訂單狀態變更 | OMS / SinopacBroker callback |
| `alerts` | 風控告警 | RiskEngine / Kill Switch |
| `market` | 即時行情 tick | SinopacQuoteManager (待接通) |
| `auto-alpha` | 自動 Alpha 流水線即時事件 | AlphaScheduler.run_full_cycle() |

### 5.3 安全機制

| 機制 | 實作 |
|------|------|
| 認證 | JWT (HS256) + API Key 雙模式 |
| 授權 | 5 級角色：viewer < researcher < trader < risk_manager < admin |
| 密碼 | PBKDF2-SHA256 |
| Token 撤銷 | `valid_after` 時間戳 per user |
| 帳戶鎖定 | 5 次失敗 → 15 分鐘鎖定 |
| 限流 | slowapi: 60 req/min (backtest: 10/min) |
| 審計 | AuditMiddleware: 記錄所有 POST/PUT/DELETE |
| CORS | `QUANT_ALLOWED_ORIGINS` 白名單 |

---

## 6. 前端架構

### 6.1 Web (React 18 + Vite + Tailwind)

| # | 頁面 | 路由 | 功能 |
|---|------|------|------|
| 1 | Dashboard | `/` | NAV 走勢, 持倉表, MarketTicker (WS) |
| 2 | Portfolio | `/portfolio` | 投資組合 CRUD + 再平衡預覽 + SavedPortfoliosPanel (建立/檢視/刪除/Rebalance Preview) |
| 3 | Strategies | `/strategies` | 9 策略列表 + 啟停控制 |
| 4 | Orders | `/orders` | OrderForm + 訂單歷史 |
| 5 | Backtest | `/backtest` | UniversePicker + ParamsEditor + 績效圖表 + 月報熱力圖 |
| 6 | Alpha | `/alpha` | AlphaConfigForm + 因子研究結果 |
| 7 | Allocation | `/allocation` | 戰術配置計算 + 資產配比圖 |
| 8 | Risk | `/risk` | 10 規則狀態 + 告警列表 + Kill Switch |
| 9 | Settings | `/settings` | Getting Started 快速入門指南 + API Key / 密碼 / 語言 / 主題 |
| 10 | Admin | `/admin` | 用戶管理 + 審計日誌 |

**共用 UI 元件**: Card, DataTable (TanStack Virtual), Toast, PageSkeleton, ErrorBoundary

**i18n**: 英文 + 繁體中文 (`useT` hook + localStorage 持久化)

### 6.2 Android Native (Jetpack Compose)

Backtest tab 含 UniversePickerSheet（Material 3 bottom sheet），支援：
- 市場分頁（US / TW / ETF）+ 搜尋 + 板塊分組
- 預設組合（e.g. FAANG, 台灣50）+ 批次操作
- 股票資料 (`StockData.kt`) 鏡像 Web `stocks.ts`
- i18n（en + zh-TW）via `strings.xml`

### 6.3 共享套件 (`@quant/shared`)

- 型別定義 (1:1 對應後端 Pydantic schemas)
- Platform-agnostic HTTP client (`ClientAdapter` 注入)
- WSManager (auto-reconnect + exponential backoff)
- 30+ typed API endpoint 定義
- Number/currency/date formatters

---

## 7. 測試覆蓋

### 7.1 後端測試（1,138 tests）

| 分類 | 檔案數 | 測試數 | 說明 |
|------|--------|--------|------|
| Execution 層 | 8 | ~184 | SinopacBroker, QuoteManager, ExecutionService, MarketHours, Reconcile, StopOrder, ShioajiFeed, **TWAPSplitter** |
| Alpha 層 | 20 | ~225 | 因子, Pipeline, Regime, Attribution, Rolling IC, **Auto Alpha (config/universe/researcher/store/alerts/safety/backtest_gate, OOS decay, net alpha filter)**, Kakushadze 101, Momentum Crash, **Fundamental Factors (size/investment/gross_profit)** |
| 策略 + 回測 | 12 | ~147 | 各策略, 引擎, 分析, Walk-forward, Randomized, PBO, K-Fold, StressTest |
| 風控 | 3 | ~60 | 規則, Kill Switch, Monitor |
| API + 整合 | 6 | ~100 | REST 端點, Portfolio API, Auth, WebSocket |
| 數據 | 5 | ~80 | Yahoo, FinMind, FRED, Shioaji, Scanner |
| 核心 + 領域模型 | 7 | ~56 | Order, Portfolio, Instrument, OMS, **TradingPipeline** |
| 其他 | 7 | ~46 | Config, Notifications, 雜項 |

### 7.2 前端測試

| 平台 | 框架 | 檔案數 |
|------|------|--------|
| Web | Vitest + jsdom | 18 |
| Web E2E | Playwright | 3 |
| Android | JUnit / Compose Test | — |
| Shared | Vitest | 4 |

### 7.3 CI/CD Pipeline（9 jobs）

| Job | 內容 | 依賴 |
|-----|------|------|
| `backend-lint` | ruff check + mypy strict | — |
| `backend-test` | pytest | — |
| `web-typecheck` | tsc --noEmit | — |
| `web-test` | vitest | web-typecheck |
| `web-build` | vite build | web-typecheck |
| `shared-test` | vitest (@quant/shared) | — |
| `android-build` | assembleDebug + upload artifact | — |
| `e2e-test` | Playwright chromium (build+preview, retries=2) | web-build |
| `release` | 自動建立 GitHub Release + APK 附件 | 所有上述 jobs（master push 限定）|

### 7.4 本地 Pre-push Hook

- **位置**：`.githooks/pre-push`
- **啟用**：`make setup-hooks`（執行 `git config core.hooksPath .githooks`）
- **執行內容**：ruff lint → mypy → pytest tests/unit/ → web typecheck
- **跳過選項**：`git push --no-verify` / `SKIP_LINT=1` / `SKIP_TESTS=1`
- **完整模式**：`FULL_CHECK=1 git push`（加跑 web/shared vitest）

---

## 8. 基礎設施

### 8.1 資料庫

- **Production**: PostgreSQL 16 (Docker Alpine)
- **Development**: SQLite (`data/quant.db`)
- **ORM**: SQLAlchemy + Alembic
- **Migrations** (4):
  1. `001_initial_schema` — 基礎表結構
  2. `002_add_users_table` — 用戶 + 角色
  3. `003_add_token_valid_after` — Token 撤銷
  4. `004_portfolio_persistence` — 投資組合持久化

### 8.2 Docker

```yaml
services:
  api:  Uvicorn (2 workers), Python 3.12-slim, non-root appuser, port 8000
  db:   PostgreSQL 16-alpine, health check, pg_data volume
volumes:
  pg_data, cache_data
```

### 8.3 配置體系

所有配置透過 `QUANT_` 前綴環境變數或 `.env` 設定 (Pydantic Settings)。

**關鍵配置群組**:

| 群組 | 變數 | 說明 |
|------|------|------|
| 運行模式 | `QUANT_MODE` | `backtest` / `paper` / `live` |
| 券商 | `QUANT_SINOPAC_API_KEY`, `SECRET_KEY`, `CA_PATH`, `CA_PASSWORD` | Shioaji 認證 |
| 數據源 | `QUANT_DATA_SOURCE` | `yahoo` / `finmind` / `shioaji` |
| 風控 | `QUANT_MAX_POSITION_PCT`, `MAX_DAILY_DRAWDOWN_PCT` | 風控閾值 |
| 交易 | `QUANT_COMMISSION_RATE`, `TAX_RATE`, `DEFAULT_SLIPPAGE_BPS` | 交易成本 |
| 認證 | `QUANT_API_KEY`, `JWT_SECRET` | API 認證 |
| 通知 | `QUANT_DISCORD_WEBHOOK_URL`, `LINE_NOTIFY_TOKEN`, `TELEGRAM_*` | 告警通知 |
| 排程 | `QUANT_SCHEDULER_ENABLED`, `REBALANCE_CRON` | 定時任務 |

---

## 9. 功能完成度矩陣

### 9.1 核心功能

| 功能 | 狀態 | 備註 |
|------|------|------|
| 回測引擎 | ✅ 完成 | 多資產/多幣別/FX 時序/40+ 指標/Walk-forward/Randomized/PBO(CSCV)/K-Fold/StressTest |
| 策略框架 | ✅ 完成 | 9 策略 + Strategy ABC + Registry |
| 數據源 | ✅ 完成 | Yahoo + FinMind + FRED + Shioaji (kbars/ticks/snapshot) |
| Alpha 研究 | ✅ 完成 | 27 因子 (11 技術 + 10 Kakushadze + 6 基本面)/中性化/正交化/Rolling IC/Pipeline/Regime/Attribution/Momentum Crash 防護 |
| 戰術配置 | ✅ 完成 | 宏觀四因子 + 跨資產信號 + TacticalEngine |
| 組合最佳化 | ✅ 完成 | 14 方法 (含 CVaR/MaxDD/Robust/Resampled/GMV/MaxSharpe/IndexTracking/SemiVariance) + LW/GARCH/Factor Cov + VaR/CVaR + James-Stein + 風險貢獻 |
| 幣別對沖 | ✅ 完成 | 分級對沖 + HedgeRecommendation |
| 兩層整合 | ✅ 完成 | MultiAssetStrategy (allocation → alpha → optimizer) |
| 風控引擎 | ✅ 完成 | 10 規則 + Kill Switch + 跨資產規則 |
| InstrumentRegistry | ✅ 完成 | 自動推斷 symbol → asset_class/market/currency |
| 多幣別 Portfolio | ✅ 完成 | nav_in_base / currency_exposure / per-bar FX |
| API | ✅ 完成 | 74 端點 + WebSocket + JWT/RBAC + 限流 + 審計 |
| Web 前端 | ✅ 完成 | 11 頁 + i18n (en/zh) + 深色主題 |
| Android | ✅ 完成 | Jetpack Compose + Material 3 + UniversePicker |
| Android Native | 🟡 進行中 | Backtest tab + UniversePickerSheet (Material 3) + i18n |

### 9.2 交易執行（Phase E）

| 功能 | 狀態 | 說明 |
|------|------|------|
| SinopacBroker | ✅ 程式碼 | 下單/撤單/改單/持倉/帳務/成交回報/斷線重連 |
| ExecutionService | ✅ 整合 | 模式路由 + AppState 接通 + startup 初始化 |
| 非阻塞下單 | ✅ 程式碼 | `timeout=0` (~12ms) |
| 交易時段管理 | ✅ 完成 | 盤前/盤中/零股/定盤 + 盤外佇列 + **TWTradingCalendar (國定假日排除)** |
| EOD 對帳 | ✅ 完成 | reconcile + auto_correct |
| 觸價委託 | ✅ 完成 | StopOrderManager (stop-loss/profit) |
| 融資融券 | ✅ 模型 | OrderCondition (Cash/Margin/Short/DayTrade) + StockOrderLot |
| 交易額度預檢 | ✅ 程式碼 | query_trading_limits / settlements / dispositions |
| 市場掃描器 | ✅ 完成 | VolumeRank / ChangeRank + 處置/注意股排除 |
| 即時行情 | 🟡 架構 | SinopacQuoteManager 完成，WS broadcast 待接通 |
| 排程 Rebalance | ✅ 整合 | scheduler/jobs.py 接通策略→風控→下單→Portfolio→通知 |
| **整合測試** | ✅ 模擬通過 | API Key 已取得，模擬 login/下單驗證通過 (2026-03-26)。Deal callback + tick streaming 需生產 CA 憑證 |
| 期貨選擇權 | ❌ 待辦 | Shioaji 支援 FuturesPriceType + ComboOrder |
| IB 美股 | ❌ 待辦 | Shioaji 完成後 |

### 9.3 自動化 Alpha（Phase F）

| 功能 | 狀態 | 說明 |
|------|------|------|
| AutoAlphaConfig | ✅ 完成 | 排程/篩選/安全閾值配置 (F1a) |
| UniverseSelector | ✅ 完成 | Scanner × 靜態約束 × 處置股排除 (F1b) |
| AlphaResearcher | ✅ 完成 | AlphaPipeline + Regime + 持久化 (F1c) |
| AlphaDecisionEngine | ✅ 完成 | ICIR/Hit Rate 篩選 + Regime 調適 + **Net Alpha 過濾** (F1d) |
| BacktestGate | ✅ 完成 | Stage 3.5: 執行前回測驗證 (Sharpe/成本門檻) |
| AlphaExecutor | ✅ 完成 | weights→orders→risk→execution→performance (F1e) |
| AlphaScheduler | ✅ 完成 | 8 排程 job: 08:30~13:35 + backtest gate (F1f) |
| AlphaStore | ✅ 完成 | DB 持久化: ResearchSnapshot + FactorScore (F2a) |
| AlertManager | ✅ 完成 | Regime/IC/回撤告警 → 通知 (F2b) |
| SafetyChecker | ✅ 完成 | 回撤熔斷 5% + 連續虧損暫停 5 天 + **Kill Switch 恢復機制** (3 天冷靜→50%~100% 漸進恢復) (F2c) |
| Auto-Alpha API | ✅ 完成 | 10 端點 (F3a) |
| FactorPerformanceTracker | ✅ 完成 | 累計 IC + 回撤 per factor (F4b)；已整合至 AlphaDecisionEngine + AlphaScheduler |
| DynamicFactorPool | ✅ 完成 | ICIR 排名自動新增/移除因子 (F4c)；已整合至 AlphaDecisionEngine.decide() + AlphaScheduler.run_full_cycle() |
| REGIME_FACTOR_BIAS | ✅ 完成 | Bull/Bear/Sideways 因子偏好矩陣 (F4a) |
| DB Migration (F2d) | 🟡 待實作 | Alembic 005_auto_alpha.py |
| WS auto-alpha 頻道 (F3b) | ✅ 完成 | 即時推送流水線進度 (stage_started/stage_completed/decision/execution/alert/error) |
| Web Dashboard (F3c) | 🟡 待實作 | Auto-Alpha 前端頁面 |

### 9.4 外部依賴狀態

| 依賴 | 狀態 | 備註 |
|------|------|------|
| shioaji SDK | ✅ 已安裝 v1.3.2 | `pip install shioaji` |
| Shioaji API Key | ✅ 已取得 | 模擬模式驗證通過 (2026-03-26) |
| CA 憑證 (.pfx) | ❌ 未取得 | 生產環境必需：deal callback + tick streaming |
| PostgreSQL | ✅ Docker ready | `docker compose up -d` |

---

## 10. 設計缺陷與技術債追蹤

| 編號 | 狀態 | 嚴重度 | 問題 | 影響 |
|------|------|--------|------|------|
| D-01~D-07 | ✅ 已修復 | — | Phase A 管線整合 (乘數/費率/FX/Registry) | — |
| D-08 | 延後 | 低 | Alpha Pipeline GIL 限制 (CPU-bound 因子計算) | 大 universe 效能 |
| D-10~D-18 | ✅ 已修復 | — | 模型統一/FX per-bar/總權重驗證/FRED ffill | — |
| D-19 | Phase E5 | 中 | 期貨展期模擬 (近月→次月 roll) | 期貨回測連續性 |
| D-20 | ✅ | — | SinopacBroker 核心 + ExecutionService | — |
| D-21 | ✅ | — | 交易時段管理 + 盤外佇列 | — |
| D-22 | ✅ | — | EOD 對帳 + 自動修正 | — |
| D-23 | ✅ | — | Execution API routes (6 端點) | — |
| D-24 | ✅ | — | ShioajiFeed 數據源 (kbars/ticks/snapshot) | — |
| D-25 | ✅ | — | ShioajiScanner + 處置/注意股排除 | — |
| D-26 | ✅ | — | Order 融資融券/零股欄位 | — |
| D-27 | 待辦 | 中 | WebSocket `market` 頻道未接入 SinopacQuoteManager | 前端無即時行情 |
| D-28 | ✅ 已修復 | 低 | FastAPI `on_event` deprecated → lifespan handler | 已遷移至 lifespan context manager |
| D-29 | ✅ 已修復 | 低 | CI backend-test count 過時 (326 vs 726) | CLAUDE.md 數字已更新 |
| D-30 | ✅ | — | Auto-Alpha API routes (10 端點, Phase F3a) | — |
| D-31 | ✅ 已修復 | 高 | SPA fallback 路徑穿越漏洞 | `app.py` 加入 `is_relative_to()` 防護 |
| D-32 | ✅ 已修復 | 高 | auto-alpha WS 端點無認證 | 加入 token 認證邏輯 |
| D-33 | ✅ 已修復 | 中 | `_run_now_tasks` 無限增長（記憶體洩漏） | 加入 50 筆上限 + 自動清除 |
| D-34 | ✅ 已修復 | 中 | 全域例外處理器缺失 | 加入 500 fallback handler |
| D-35 | ✅ 已修復 | 中 | WSManager 無重連上限 / WS 連線數無限 | MAX_RETRIES=20, 200/channel |
| D-36 | ✅ 已修復 | 低 | 前端全部頁面 async handler 缺少 mounted 檢查 | 8 個頁面均已加入 mountedRef 保護 |
| D-37 | ✅ 已修復 | 中 | `alpha_tasks` 跨線程無鎖保護 | 加入 `alpha_lock` threading.Lock |
| D-38 | ✅ 已修復 | 中 | 資料庫連線池未配置 pool_size/pool_recycle | PostgreSQL: pool_size=10, pool_pre_ping=True |
| D-39 | ✅ 已修復 | 中 | `asyncio.get_event_loop()` deprecated | 改用 `get_running_loop()` |
| D-40 | ✅ 已修復 | 中 | 前端 WS URL 不含認證 Token | login 存 token，WS URL 附帶 `?token=` |
| D-41 | ✅ 已修復 | 中 | 後端缺少 server-side ping | 加入 `_server_ping_loop` 每 30 秒偵測死連線 |
| D-42 | ✅ 已修復 | 中 | broadcast 無 backpressure | 同 channel 前次未完成時丟棄 + 批次 50 並行 |
| D-43 | ✅ 已修復 | 低 | useWs 每次建立新 WSManager | singleton + refCount 共享機制 |
| D-44 | ✅ 已修復 | 中 | backtest 結果全存記憶體 | 加入 1 小時自動過期清除 |
| D-45 | ✅ 已修復 | 高 | 台股回測 tz-aware index 比較錯誤 | yfinance 回傳 Asia/Taipei 時區，多層防護確保 tz-naive (yahoo/finmind/feed/context/parquet_cache) |

---

## 11. 學術基準差距分析

> **參考書籍**：*Portfolio Optimization: Theory and Application* (D. P. Palomar, 608 頁, 15 章)
> **參考論文**（已下載至 `docs/ref/`）：
> - Rockafellar & Uryasev (2000). *Optimization of Conditional Value-at-Risk.* — CVaR 最佳化奠基論文
> - Bailey, Borwein, López de Prado, Zhu (2015). *The Probability of Backtest Overfitting.* — CSCV 回測過擬合檢測
> - López de Prado (2016). *Building Diversified Portfolios that Outperform Out of Sample.* — HRP 方法論
> **P1 論文**（已下載至 `docs/ref/`）：
> - Jorion (1986). *Bayes-Stein Estimation for Portfolio Analysis.* — 均值收縮
> - Ledoit & Wolf (2004). *Honey, I Shrunk the Sample Covariance Matrix.* — 線性收縮（已實作）
> - Ledoit & Wolf (2014). *Nonlinear Shrinkage of the Covariance Matrix for Portfolio Selection.* — 非線性收縮
> - Wang, Zhou, Ying, Palomar (2024). *Efficient High-Order Portfolios Design via the Skew-t Distribution.* — MVSK
> - Engle (1982). *Autoregressive Conditional Heteroscedasticity.* — ARCH/GARCH
> - Benidis, Feng, Palomar (2018). *Sparse Portfolios for High-Dimensional Financial Index Tracking.* — 稀疏追蹤
> **比對範圍**：書中 15 章 + 9 篇論文 vs 本系統現有實作

### 11.1 數據建模層（書 Part I, Ch.2–5）

| 書中技術 | 系統現況 | 差距 | 嚴重度 | 說明 |
|----------|---------|------|--------|------|
| 非高斯分布建模 (skewed-t, GH) | ❌ 未實作 | 缺少 | 中 | 書 Ch.2 證實金融數據有厚尾+偏態；系統隱含假設常態分布 |
| Heavy-tailed ML 估計 (Tyler's M-estimator) | ❌ 未實作 | 缺少 | 中 | 替代 Gaussian ML，對離群值更穩健（參考 `fitHeavyTail` vignette） |
| 均值收縮估計 (James-Stein / grand-mean) | ✅ Phase G2c | — | — | `shrink_mean()` in `risk_model.py`：Jorion (1986) 公式，`OptimizerConfig.shrink_mean` 整合 |
| 共變異數收縮 (Ledoit-Wolf linear) | ✅ 已實作 | — | — | `risk_model.py` 支援 LW 線性收縮（target: scaled identity / diagonal） |
| 共變異數非線性收縮 (RMT) | ❌ 未實作 | 缺少 | 中 | **Ledoit & Wolf (2014)**: 每個 eigenvalue 獨立收縮 d(λᵢ)=α/(λᵢ\|s(λᵢ)\|²), N=500 T=120 OOS variance 比線性低 10-20%. Python: `analytical_shrinkage` |
| 因子模型共變異數 (PCA / Fama-French / Barra) | ✅ Phase G4b | — | — | `factor_model_covariance()` in `risk_model.py`：PCA 因子模型 Σ = BΣ_fB^T + Ψ |
| Black-Litterman 觀點融合 | ✅ 已實作 | — | — | `BLView` + WLS 公式（書 Ch.3 eq.(3.19)） |
| GARCH / Stochastic Volatility | ✅ Phase G4a | — | — | `garch_covariance()` in `risk_model.py`：GARCH(1,1) per-asset 波動率 → DCC-like 共變異數 |
| Kalman Filter 均值/波動率估計 | ❌ 未實作 | 缺少 | 低 | 書 Ch.4 推薦替代滾動窗口，用於時變參數 |
| 圖模型 (Graph Learning for Σ) | ❌ 未實作 | 缺少 | 低 | 書 Ch.5：稀疏精度矩陣估計，學術前沿 |

### 11.2 組合最佳化層（書 Part II, Ch.6–15）

| 書中技術 | 系統現況 | 差距 | 嚴重度 | 論文/章節依據 |
|----------|---------|------|--------|-------------|
| Equal Weight (1/N) | ✅ | — | — | |
| Global Minimum Variance (GMV) | ✅ Phase G5d | — | — | `OptimizationMethod.GMV` 獨立入口 |
| Inverse Volatility | ✅ | — | — | |
| Risk Parity | ✅ | — | — | 參考 `riskParityPortfolio` vignette 改進 |
| Mean-Variance (Markowitz) | ✅ | — | — | |
| Maximum Sharpe Ratio | ✅ Phase G5c | — | — | Dinkelbach 分數規劃 SLSQP 嚴格 MSR |
| Black-Litterman | ✅ | — | — | |
| HRP | ✅ | — | — | López de Prado (2016) — 已實作核心 |
| **CVaR/ES 組合** | ✅ 已實作 | — | — | Rockafellar & Uryasev (2000) LP 重構；`compute_var/compute_cvar` + `_optimize_cvar`；BacktestResult 含 `var_95/cvar_95` |
| **Drawdown 組合 (CDaR/MaxDD)** | ✅ 已實作 | — | — | `_optimize_max_drawdown` 歷史模擬 SLSQP |
| Downside Risk / Semi-variance | ✅ Phase H2 | — | — | `OptimizationMethod.SEMI_VARIANCE` — semi-covariance SLSQP |
| **MVSK 高階矩** | ❌ 未實作 | **缺少** | **中** | **Wang et al. (2024)**: RFPA 演算法, O(N²) 複雜度 (vs Q-MVSK O(N³)). 用 ghMST skew-t 分布建模, N=400 < 1 秒. CRRA utility λ=(1,ξ/2,ξ(ξ+1)/6,ξ(ξ+1)(ξ+2)/24), ξ=6. 見 `highOrderPortfolios` R 套件 |
| **Robust 組合 (Worst-case)** | ✅ Phase G2a | — | — | `_optimize_robust` 橢圓不確定集 SLSQP |
| **Index Tracking (稀疏追蹤)** | ✅ Phase G5b | — | — | `_optimize_index_tracking` LASSO 稀疏追蹤 (Benidis/Feng/Palomar) |
| Portfolio Resampling | ✅ 已實作 | — | — | `_optimize_resampled` Michaud 蒙地卡羅重取樣 |
| **Pairs Trading (協整合+Kalman)** | ✅ G6a+H3 | — | — | Engle-Granger 共整合 + OLS hedge ratio + Kalman Filter 動態 hedge ratio (`method="kalman"`) |
| Graph-Based (HERC, NCO) | ⚠️ 部分 | 不足 | 低 | HRP 已有但缺 HERC/NCO |
| Deep Learning Portfolios | ❌ 未實作 | 缺少 | 低 | 書 Ch.16：端到端 DL，學術實驗階段 |
| Utility-Based / Kelly | ❌ 未實作 | 缺少 | 低 | 書 Ch.7 |

### 11.3 回測方法論（書 Ch.8 + Bailey et al. 2015）

| 技術 | 系統現況 | 差距 | 嚴重度 | 論文依據 |
|------|---------|------|--------|---------|
| Walk-forward Backtest | ✅ | — | — | |
| Vanilla (Train/Test Split) | ✅ | — | — | |
| **Multiple Randomized Backtest** | ✅ Phase G3a | — | — | `src/backtest/randomized.py` + API `POST /api/v1/backtest/randomized`：隨機抽取資產子集 + 隨機時段 → N 次回測 → 績效分布 (Sharpe/Return/Drawdown) + P(Sharpe>0) |
| **CSCV (PBO)** | ✅ Phase G3b | — | — | `src/backtest/overfitting.py` + API `POST /api/v1/backtest/pbo`：Bailey et al. (2017) CSCV 實作，S 等分 → C(S,S/2) 組合 → IS/OOS 排名比較 → PBO |
| **Deflated Sharpe Ratio** | ✅ Phase H1 | — | — | `deflated_sharpe()` + `min_backtest_length()` — Bailey et al. (2014) 多重測試校正 |
| **Minimum Backtest Length (MinBTL)** | ❌ 未實作 | **缺少** | **中** | **Bailey & López de Prado (2014)**: MinBTL = (1 + (1-γ₃SR̂+(γ₄-1)/4 SR̂²)(z_α/(SR̂-SR*))²). 給定 N 策略數→最短回測所需觀察數. 實作: ~15 行 Python. |
| k-fold Cross-validation | ✅ Phase G3c | — | — | `src/backtest/kfold.py`：k 折時序交叉驗證，各折獨立 BacktestResult + avg/std Sharpe |
| Synthetic Data Stress Test | ✅ Phase G3d | — | — | `src/backtest/stress_test.py` + API `POST /api/v1/backtest/stress-test`：4 預定義情境 (Bear Market / High Vol / Flash Crash / Regime Change) |

**七宗罪防護現況**（書 Ch.8.2, Luo et al. 2014）：

| Sin | 描述 | 系統防護 | 狀態 | 改善方案 |
|-----|------|---------|------|---------|
| #1 Survivorship Bias | 用存活標的回測 | ✅ G8: 存活者偏差偵測 + 警告標記 | ⚠️ | 偵測+警告已實作；完整解需 point-in-time universe |
| #2 Look-ahead Bias | 未來資訊洩漏 | ✅ Context 時間截斷 + `set_current_date()` | ✅ | — |
| #3 Storytelling Bias | 事後合理化 | ✅ PBO (CSCV) 可客觀量化過擬合 | ✅ | — |
| #4 Data Snooping | 過度參數搜索 | ✅ PBO + Randomized Backtest + k-fold CV + DSR | ✅ | — |
| #5 Turnover & Cost | 忽略交易成本 | ✅ SimBroker per-instrument 費率 + sqrt 滑點 | ✅ | — |
| #6 Outliers | 極端值影響 | ✅ G8: 因子 winsorize + 回測引擎價格異常偵測 | ✅ | — |
| #7 Shorting Cost | ✅ G8b | SimConfig.short_borrow_rate 已實作，賣出時自動加計日借券成本 | ✅ | SimBroker `short_borrow_rate` 參數 (annual rate / 252) |

### 11.4 HRP 改進空間（López de Prado 2016）

現有 HRP 實作已涵蓋論文核心：hierarchical clustering → quasi-diagonalization → recursive bisection。
但論文指出幾個系統尚未處理的細節：

| 論文要點 | 系統現況 | 改善 |
|----------|---------|------|
| Distance metric: d(i,j) = √(0.5(1-ρ_{i,j})) | ✅ 已使用相關距離 | — |
| Linkage: single linkage | ⚠️ 需確認（scipy 預設 single） | 驗證 linkage 方法 |
| Out-of-sample 穩定性 | 未驗證 | 用 Multiple Randomized Backtest 比較 HRP vs MVO |
| Monte Carlo 模擬驗證 | 未做 | 論文用 10,000 次模擬證明 HRP > CLA；系統應複現 |

### 11.5 績效衡量缺口（書 Ch.6 + Rockafellar 2000）

| 指標 | 系統現況 | 差距 | 說明 |
|------|---------|------|------|
| Sharpe Ratio | ✅ | — | |
| Sortino Ratio | ✅ | — | |
| Calmar Ratio | ✅ | — | |
| Max Drawdown | ✅ | — | |
| Annualized Return/Vol | ✅ | — | |
| Information Ratio | ✅ | — | |
| Turnover 統計 | ✅ | — | |
| **CVaR (Conditional VaR)** | ✅ Phase G1 | — | `compute_cvar()` 歷史+參數法；BacktestResult 含 `cvar_95` |
| **VaR (Value at Risk)** | ✅ Phase G1 | — | `compute_var()` 歷史+參數法；BacktestResult 含 `var_95` |
| **EVaR (Entropic VaR)** | ❌ | **缺少** | 書 Ch.10：比 CVaR 更嚴格的 coherent risk measure |
| Omega Ratio | ✅ G7 | `compute_omega_ratio()` in analytics.py | |
| Rolling Sharpe | ✅ G7 | `compute_rolling_sharpe()` in analytics.py (63-day window) | 書 Ch.6：穩定性檢視 |
| **Deflated Sharpe Ratio** | ✅ H1 | `deflated_sharpe()` + `min_backtest_length()` in analytics.py | Bailey et al. (2014)：校正多重測試效應後的 Sharpe |

### 11.6 優先改善建議（論文驅動）

根據 3 篇 P0 論文的具體方法 × 系統缺口 × 實務價值：

| 優先級 | 項目 | 論文/章節 | 狀態 | 預估難度 |
|--------|------|---------|------|---------|
| ✅ G1 | **CVaR 風險度量 + 最佳化** | Rockafellar & Uryasev (2000) | `OptimizationMethod.CVAR` + `compute_var/cvar` | 中 |
| ✅ G3b | **CSCV 回測過擬合檢測 (PBO)** | Bailey et al. (2015) Algorithm 2.3 | `src/backtest/overfitting.py` | 中 |
| ✅ G3a | **Multiple Randomized Backtest** | 書 Ch.8.4.4 | `src/backtest/randomized.py` | 低 |
| ✅ G1 | **VaR/CVaR 績效指標** | Rockafellar (2000) | `var_95`, `cvar_95` in BacktestResult | 低 |
| ✅ G2a | **Robust 組合 (worst-case)** | 書 Ch.14 | `_optimize_robust` 橢圓不確定集 | 中 |
| ✅ G2b | **Portfolio Resampling (Michaud)** | 書 Ch.14 | `_optimize_resampled` | 低 |
| ✅ G2c | **均值收縮 (James-Stein)** | 書 Ch.3 (Jorion 1986) | `shrink_mean()` in risk_model.py | 低 |
| ✅ G4a | **GARCH 波動率** | 書 Ch.4 | `garch_covariance()` in risk_model.py | 中 |
| ✅ G4b | **因子模型共變異數** | 書 Ch.3 eq.(3.15) | `factor_model_covariance()` PCA | 中 |
| ✅ G5b | **Index Tracking** | 書 Ch.13 (Benidis/Feng/Palomar) | `_optimize_index_tracking` LASSO | 中 |
| ✅ G5c | **Maximum Sharpe** | 書 Ch.6 (Dinkelbach) | `_optimize_max_sharpe` | 低 |
| ✅ G5d | **GMV** | 書 Ch.6 | `OptimizationMethod.GMV` | 低 |
| ✅ G6a | **Pairs Trading 共整合** | 書 Ch.15 | Engle-Granger + OLS hedge ratio | 中 |
| ✅ G7 | **Omega Ratio + Rolling Sharpe** | — | `compute_omega_ratio/compute_rolling_sharpe` | 低 |
| ✅ G8 | **回測防護 (存活偏差/借券/異常)** | 書 Ch.8.2 | survivorship_bias + short_borrow + outlier detect | 低 |
| ✅ H1 | **Deflated Sharpe Ratio** | Bailey et al. (2014) §3 | `deflated_sharpe()` 校正 N_trials + skew/kurtosis | 低 |
| ✅ H1 | **MinBTL** | Bailey et al. (2014) | `min_backtest_length()` 最短回測長度 given N trials | 低 |
| 🟡 P1 | **MVSK 高階矩** | **Wang et al. (2024)**: RFPA O(N^2) + ghMST skew-t 建模 | ❌ 需移植 `highOrderPortfolios` R 套件 | 高 |
| 🟡 P1 | **非高斯建模 (skewed-t)** | 書 Ch.2 + **Wang (2024)** ghMST fitting + `fitHeavyTail` | ❌ 穩健共變異數 + 厚尾 ML 估計 | 高 |
| ✅ H2 | **Downside Risk / Semi-variance** | 書 Ch.10 | `OptimizationMethod.SEMI_VARIANCE` semi-covariance + SLSQP | 低 |
| 🟡 P1 | **EVaR (Entropic VaR)** | 書 Ch.10 | ❌ 比 CVaR 更嚴格 | 中 |
| ✅ H3 | **Kalman Filter 動態 hedge ratio** | 書 Ch.15 | `KalmanHedgeRatio` + `method='kalman'` in PairsTradingStrategy | 中 |
| 🟢 P2 | **HERC / NCO** | 書 Ch.12 | ❌ HRP 擴展 | 中 |
| 🟢 P2 | **非線性收縮** | **Ledoit & Wolf (2014)**: d(λ)=α/(λ\|s(λ)\|^2) via Marcenko-Pastur, N=500 T=120 OOS -10~20% | ❌ Python: `analytical_shrinkage` 可整合 | 中 |
| 🔵 P3 | Deep Learning Portfolios | 書 Ch.16 | ❌ 學術實驗階段 | 高 |

### 11.7 Alpha 因子研究差距分析（論文驅動）

> 參考論文（已下載至 `docs/ref/papers/alpha/`）：10 篇

#### 11.7.1 因子庫完整性

| 論文 | 系統現有因子 | 缺少的因子 | 影響 |
|------|------------|-----------|------|
| **Fama & French (1993)** 3-factor | ✅ market (隱含), value_pe/pb (≈HML) | ❌ SMB (市值因子) — 系統無獨立 size factor | 中 |
| **Fama & French (2015)** 5-factor | ✅ quality_roe (≈RMW), ✅ investment (CMA), ✅ size (SMB) | — Phase I1 完成 | **已完成** |
| **Novy-Marx (2013)** gross profitability | ✅ gross_profit | — Phase I1 完成 | **已完成** |
| **Kakushadze (2016)** 101 Alphas | 14/101 | ❌ 87 個公式可直接轉為 `factors.py` 函式。多數為 price-volume 因子，平均持有期 0.6-6.4 天，平均相關性僅 15.9%。 | **高** |

**建議新增因子**（按影響力排序）：
1. ~~`gross_profitability`~~ ✅ Phase I1 完成
2. ~~`investment`~~ ✅ Phase I1 完成
3. ~~`size`~~ ✅ Phase I1 完成
4. 從 Kakushadze 101 中挑選低相關、高 Sharpe 的 10-20 個公式

#### 11.7.2 因子篩選閾值

| 論文 | 發現 | 系統影響 |
|------|------|---------|
| **Harvey et al. (2016)** | 審查 316 因子，多數為 data mining。建議 t-stat > **3.0**（非傳統 2.0）才算顯著。 | ✅ Phase I3：`DecisionConfig.min_icir` 從 0.3 提高至 **0.5**。 |
| **McLean & Pontiff (2016)** | 學術發表後因子報酬**衰減 58%**。post-publication 平均 OOS alpha = 0.42 × in-sample alpha。 | ✅ Phase I3：`AlphaResearcher._report_to_scores()` 現在以 `icir * oos_decay_factor (0.42)` 作為 eligibility 判斷依據。 |
| **DeMiguel et al. (2009)** | N>25 T<500 時 1/N 幾乎無法被最佳化打敗。 | ✅ Phase I3：`AlphaReport.vs_equal_weight_sharpe` 報告 composite L/S 與 EW 的 Sharpe 差異。 |

#### 11.7.3 動態因子配置（Regime-aware）

| 論文 | 發現 | 系統影響 |
|------|------|---------|
| **Asness et al. (2013)** Value+Momentum Everywhere | Value 和 momentum 在股票、債券、外匯、商品期貨中**普遍有效**，且兩者負相關（組合 Sharpe 更高）。 | `REGIME_FACTOR_BIAS` 中 momentum + value 應作為**核心組合**，跨資產 Alpha (`cross_asset.py`) 已有但未與 auto-alpha 整合。 |
| **Daniel & Moskowitz (2016)** Momentum Crashes | Momentum crash 在**恐慌狀態**（市場下跌 + 高波動率）後發生，loser 組合有 option-like 凸性報酬。動態策略：σ_target / σ_realized 調整曝險，可**翻倍** Sharpe。 | `SafetyChecker` 應新增 **momentum crash 偵測**：(1) 市場跌幅 > 20% + VIX > 30 → 暫停 momentum 因子；(2) `REGIME_FACTOR_BIAS[BEAR]["momentum"]` 應從 0.5 降至 **0.2** 或 0。(3) 考慮 volatility-scaling：w_mom × (σ_target / σ_realized_20d)。 |

#### 11.7.4 ML 方法（進階）

| 論文 | 發現 | 系統影響 |
|------|------|---------|
| **Gu, Kelly, Xiu (2020)** ML Asset Pricing | Trees + Neural Nets **翻倍** 傳統方法的 Sharpe (1.35 vs ~0.6)。關鍵：非線性交互效應。Top 預測因子：momentum variants + liquidity + volatility。920+ 特徵，但主要信號集中在少數。 | 系統的 `AlphaDecisionEngine` 用線性 ICIR 加權。論文顯示**非線性方法大幅優於線性**。長期可考慮 gradient boosting 替代 IC 加權。但**短期內穩定性存疑**——論文的 OOS R² 僅 0.16-0.40%，且 top 特徵與系統已有因子高度重疊。 |

#### 11.7.5 Alpha 研究論文收藏統計

| 子領域 | 已下載 | 待下載 | 說明 |
|--------|--------|--------|------|
| 因子理論基礎 | 4/4 | 0 | Fama-French 93/15, Harvey 16, McLean-Pontiff 16 |
| 因子組合與權重 | 3/3 | 0 | DeMiguel 09, Asness 13, Novy-Marx 13 |
| IC 分析與公式 | 1/2 | 1 | Kakushadze 101 ✅; 缺 Kakushadze 4000 |
| Regime 與動態 | 1/2 | 1 | Momentum Crashes ✅; 缺 Ang-Bekaert 04 (HMM) |
| ML 方法 | 1/1 | 0 | Gu-Kelly-Xiu 20 ✅ |
| 書籍 | 0/3 | 3 | Qian/Grinold-Kahn/López de Prado (教科書，非論文) |

---

## 12. 開發路線圖

### 12.1 已完成

| 階段 | 完成日期 | 里程碑 |
|------|---------|--------|
| Phase A | 2026-03-24 | 多資產基礎設施 (InstrumentRegistry + 多幣別 Portfolio + DataFeed 擴展) |
| Phase B | 2026-03-24 | 跨資產 Alpha (宏觀因子 + 跨資產信號 + 戰術配置引擎) |
| Phase C | 2026-03-24 | 組合最佳化 (6 方法 + Ledoit-Wolf + 幣別對沖) |
| Phase D | 2026-03-25 | 系統整合 (MultiAssetStrategy + 跨資產風控 + Allocation 前端 + Alpha 強化) |
| Phase E1 | 2026-03-25 | 交易執行核心 (SinopacBroker + ExecutionService + 對帳 + 交易時段) |
| Phase E4 | 2026-03-25 | Shioaji 進階 (DataFeed + Scanner + 非阻塞 + 觸價 + 融資融券 + 額度預檢) |
| Phase F | 2026-03-26 | 自動化 Alpha (F1a-f 核心引擎 + F2a-c 持久化/告警/安全 + F3a-c API + WS + Dashboard + F4a-c Regime/因子追蹤/動態池) |
| Phase G | 2026-03-26 | 學術基準升級 (G1-G8: +7 最佳化方法 + GARCH/Factor Cov + VaR/CVaR + PBO/Randomized/k-fold/Stress + 共整合 Pairs + Omega/Rolling Sharpe + 回測防護) |
| Phase H | 2026-03-26 | 實用精煉 (Deflated Sharpe + MinBTL + Semi-Variance + Kalman Filter Pairs), 1,006 tests |
| Phase H | 2026-03-26 | 實用精煉 (H1: DSR+MinBTL, H2: Semi-Variance 最佳化, H3: Kalman Pairs Trading) |
| Phase I | 2026-03-26 | Alpha 因子庫擴展 — 27 因子 (11 技術 + 10 Kakushadze + 6 基本面)，向量化 15x 加速 |
| Phase R1 | 2026-03-26 | Smart Order — TWAP 拆單引擎 (降低 market impact, ExecutionService 整合) |
| Phase R2 | 2026-03-26 | 台股交易日曆 — TWTradingCalendar (國定假日排除) |
| Phase R3 | 2026-03-26 | Trading Pipeline 抽取 — `execute_one_bar()` 共用交易流程，BacktestEngine 改用 |
| Phase R4 | 2026-03-26 | Broker 子套件重構 — broker/ + quote/ subpackage |
| Shioaji 整合 | 2026-03-26 | API Key 取得 + 模擬模式驗證通過 (deal callback 需生產 CA) |

### 12.2 進行中 / 待辦

> **原則**：策略驗證優先於生產環境整合。如果策略 Sharpe < 0，連上生產環境只會更快虧錢。

| 項目 | 優先級 | 前置條件 | 說明 |
|------|--------|---------|------|
| **Alpha 策略盈利驗證** | **🔴 P0** | **Shioaji API Key ✅** | **擴大 universe(150+) → IC 分析 → Walk-forward → PBO 檢測。見 DEVELOPMENT_PLAN.md §3** |
| Stage 3.5 Validation Backtest | 🔴 P0 | — | Decision→Execution 之間加入回測閘門 |
| cost_drag 嚴格過濾 | 🔴 P0 | — | cost_drag > 預期 alpha → 排除因子 |
| Kill Switch 冷靜期恢復 | 🟡 P1 | — | 5 天冷靜後半倉恢復，非永久停止 |
| Phase F DB Migration (F2d) | 🟡 P1 | — | Alembic 005_auto_alpha.py |
| CA 憑證整合 | 🟡 P1 | **策略驗證通過** | deal callback + tick streaming |
| Paper Trading 實測 | 🟡 P1 | CA 憑證 | 模擬帳戶跑完整循環 |
| WS market 頻道接通 | 🟡 P1 | CA 憑證 | SinopacQuoteManager → broadcast |
| 期貨選擇權交易 | 🟢 P2 | — | FuturesPriceType + ComboOrder |
| IB 美股對接 | 🟢 P2 | Paper Trading 穩定 | IBBroker(BrokerAdapter) |

---

## 13. 快速啟動指南

### 13.1 開發環境

```bash
# 後端
make install          # pip install -e ".[dev]"
make test             # pytest tests/ -v (1138 tests)
make lint             # ruff check + mypy strict
make dev              # API 熱重載 port 8000

# 前端
make install-apps     # bun install
make web              # Web dev server port 3000
cd apps/android && ./gradlew assembleDebug   # Android debug APK

# 全端
make start            # 後端 + Web 並行
```

### 13.2 Paper Trading 模式

```bash
# .env
QUANT_MODE=paper
QUANT_SINOPAC_API_KEY=your_key
QUANT_SINOPAC_SECRET_KEY=your_secret
QUANT_SINOPAC_CA_PATH=./Sinopac.pfx
QUANT_SINOPAC_CA_PASSWORD=your_password

# 啟動
make dev
```

### 12.3 Docker

```bash
docker compose up -d  # API (8000) + PostgreSQL
```
