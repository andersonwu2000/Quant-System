# 系統架構指南

> 從 CLAUDE.md 分拆，供 Claude Code 理解系統架構時參考。
> CLAUDE.md 保留行為規範和開發規則，本文件保留技術架構細節。

---

## 資料流

DataFeed → Strategy.on_bar() → 目標權重 → RiskEngine → SimBroker/Broker → Trade → Portfolio 更新

## 核心設計決策

- **策略回傳目標權重 dict**（`dict[str, float]`），不是訂單。`weights_to_orders()`（`src/strategy/engine.py`）負責轉換。
- **風控規則是純函式工廠**（`src/risk/rules.py`），無繼承。每個回傳 `RiskRule` dataclass。引擎循序執行，第一個 REJECT 即停止。
- **時間因果性**：`Context` 包裹 `DataFeed` + `Portfolio`，回測時截斷數據到 `current_time`。`HistoricalFeed.set_current_date()` 在 feed 層強制執行。
- **所有金額使用 `Decimal`**，不用 `float`。
- **時區處理**：所有 DatetimeIndex 正規化為 tz-naive。`HistoricalFeed.load()` 和 `YahooFeed._download()` 都會移除時區。

## 模組邊界

詳細清單見 `docs/claude/SYSTEM_STATUS_REPORT.md` §4。

- `src/core/` — `models.py`（**統一** Instrument, Bar, Position, Order, Portfolio, Trade, enums）、`config.py`（Pydantic Settings）、`logging.py`（structlog）、`repository.py`、`calendar.py`（TWTradingCalendar — 台股交易日曆含國定假日）、`trading_pipeline.py`（`execute_one_bar()` — 回測/實盤共用交易流程）
- `src/instrument/` — `InstrumentRegistry`（get/get_or_create/search/by_market/by_asset_class），`_infer_instrument()` 自動推斷資產類型，成本模板（TW_STOCK_DEFAULTS 等）
- `src/alpha/` — Alpha 研究層（個股選擇）。`pipeline.py` 端到端流程：universe 過濾 → 因子計算 → 中性化 → 正交化 → 組合信號 → quantile 回測 → 成本感知建構。`AlphaStrategy` 將 pipeline 包裝為 `Strategy`。`filter_strategy.py` 條件篩選（13 個內建因子計算器）。`regime.py` 市場環境分類。`auto/`（9 檔：AutoAlphaConfig, UniverseSelector, AlphaResearcher, AlphaDecisionEngine, AlphaExecutor, AlphaScheduler, AlphaStore, AlertManager, SafetyChecker, FactorPerformanceTracker, DynamicFactorPool）
- `src/allocation/` — 戰術資產配置（跨資產選擇）。4 個總經因子（FRED z-scores）、跨資產動量/波動/價值、TacticalEngine 整合
- `src/portfolio/` — 多資產組合優化。14 種方法（EW/InverseVol/RiskParity/MVO/BL/HRP/Robust/Resampled/CVaR/MaxDD/GMV/MaxSharpe/IndexTracking）。風險模型：5 種共變異數估計（historical/EWM/Ledoit-Wolf/GARCH/PCA）。匯率避險
- `src/strategy/` — Strategy ABC（`on_bar()` → 權重），`factors/` 套件（66 技術因子 + 17 基本面 = 83 個），optimizers（等權/信號/風險平價），registry（自動發現 `strategies/`），research（IC 分析、因子衰減）
- `src/risk/` — RiskEngine 執行宣告式規則；5% 日回撤 kill switch。RealtimeRiskMonitor 即時監控（2%/3%/5% 分級警示）
- `src/execution/` — `broker/`：BrokerAdapter ABC, PaperBroker, SimBroker（滑價/佣金/稅/T+N 結算）, SinopacBroker（Shioaji SDK）。`quote/`：SinopacQuoteManager（tick/bidask 訂閱）。ExecutionService（模式感知路由：backtest/paper/live），TWAP 拆單，OMS，交易時段驗證
- `src/backtest/` — BacktestEngine，40+ 分析指標，HTML/CSV 報告，walk-forward，`validator.py`（**StrategyValidator — 13 項強制驗證閘門**），`experiment.py`（平行網格回測）
- `src/data/` — DataFeed ABC，YahooFeed（本地優先：讀 `data/market/*.parquet`），FinMindFeed，FredDataSource，LocalMarketData
- `src/api/` — FastAPI REST + WebSocket，14 個路由模組，JWT 認證，Prometheus
- `src/notifications/` — Discord / LINE / Telegram
- `src/scheduler/` — APScheduler，三條執行路徑（見排程章節）

## 新增元件

**新增策略**：在 `strategies/` 建立檔案，繼承 `Strategy`（`src/strategy/base.py`），實作 `name()` 和 `on_bar(ctx) -> dict[str, float]`。在 `_resolve_strategy()` 中註冊（`src/api/routes/backtest.py` 和 `src/cli/main.py`）。

**新增數據源**：在 `src/data/sources/` 建立檔案，繼承 `DataFeed`，實作 `get_bars()`、`get_latest_price()`、`get_universe()`。輸出：`DataFrame[open, high, low, close, volume]` + tz-naive `DatetimeIndex`。在 `create_feed()` 工廠中註冊。

## API 層

**路由**（`src/api/routes/`）：auth, admin, portfolio, strategies, orders, backtest, risk, system — 皆掛載在 `/api/v1` 下。

**核心端點**（完整列表見 `docs/api-reference-zh.md`）：
- `POST /api/v1/auth/login` — JWT token
- `POST /api/v1/backtest` — 執行回測
- `POST /api/v1/strategy/rebalance` — 一鍵再平衡
- `GET /api/v1/execution/paper-trading/status` — Paper trading 狀態
- `POST /api/v1/auto-alpha/start` — 啟動 auto-alpha 排程
- `GET /api/v1/system/health` — 健康檢查

**中介層**：AuditMiddleware, JWT 認證, 限流（slowapi）, CORS, Prometheus。

**WebSocket**（`src/api/ws.py`）：channels — `portfolio`, `alerts`, `orders`, `market`。Token 認證。

## 前端架構

**共用套件**（`apps/shared/`）：TypeScript 型別、API 客戶端、WS 管理、格式化工具。

**Web**（`apps/web/`）：React 18 + Vite + Tailwind，11 個頁面（Dashboard, Trading, Strategies, Research, Auto-Alpha, Risk, Guide, Settings, Admin）。路徑別名：`@core`, `@feat`, `@shared`。

**Android**（`apps/android/`）：Kotlin + Jetpack Compose + Material 3 + Hilt DI。

**國際化**：英文 + 繁體中文。

## 策略

13 個策略（11 個內建 + 2 個管線）：

| 策略 | 檔案 | 邏輯 |
|------|------|------|
| 營收動能避險版 | `strategies/revenue_momentum_hedged.py` | **Paper Trading 主策略** — revenue_acceleration + 空頭避險 |
| 營收動能 | `strategies/revenue_momentum.py` | 以 revenue_acceleration（3M/12M）排序 |
| Alpha 管線 | `src/alpha/strategy.py` | 可配置因子管線 + 中性化 + 成本感知建構 |
| 多資產 | `src/strategy/multi_asset.py` | 戰術配置 → 個股選擇 → 組合優化 |
| + 9 個其他 | `strategies/*.py` | Momentum, MA, Mean Reversion, RSI, Multi-Factor, Pairs, Sector, Trust Follow, Combo |

## 排程

三條獨立執行路徑 — **不應同時運行**：

| 路徑 | 觸發方式 | Cron | 設定 |
|------|---------|------|------|
| **統一交易管線** | APScheduler | `QUANT_TRADING_PIPELINE_CRON`（預設：每月 11 日 08:30） | `QUANT_SCHEDULER_ENABLED` |
| **Auto-Alpha** | `/auto-alpha/start` API | 8 階段 08:30~13:35 | 手動啟停 |
| **Alpha 研究** | `scripts/alpha_research_agent.py` | 手動 / 背景 | -- |

## 基礎設施

- **資料庫**：PostgreSQL 16（開發用 SQLite）。Alembic 遷移。
- **Docker**：多階段建置，非 root 用戶。`docker-compose.yml` = api + db。
- **CI/CD**：9 個 jobs（lint, test, typecheck, build, e2e, release+APK）。

## 設定

所有設定透過 `QUANT_` 前綴環境變數或 `.env` 檔案。見 `src/core/config.py` 和 `.env.example`。

## Paper Trading 架構（2026-03-27 建立）

**狀態管理**：
- Portfolio 狀態持久化到 `data/paper_trading/portfolio_state.json`（atomic write）
- 每次 `apply_trades()` 後自動存檔，啟動時自動載入
- `nav_sod` 持久化以維持 daily drawdown 計算

**並發模型**：
- `state.mutation_lock`（asyncio.Lock）保護所有 portfolio mutation
- 三條 mutation 路徑：rebalance API、scheduled pipeline、kill switch monitor
- Shioaji tick callback 從背景線程觸發 → `asyncio.run_coroutine_threadsafe` 排程到 event loop
- `threading.Lock` 保護 `RealtimeRiskMonitor.on_price_update` 的價格更新（不涉及 cash/positions）

**Kill Switch**：
- 雙路徑：`_kill_switch_monitor`（5 秒輪詢）+ `RealtimeRiskMonitor`（tick 驅動）
- re-trigger guard：`state.kill_switch_fired` flag，需 `POST /risk/kill-switch/reset` 手動重置
- 觸發後：停止策略 → 清倉（submit_orders + apply_trades）→ 持久化 → WebSocket 廣播

**Pipeline**：
- `asyncio.wait_for(timeout)` 防掛死
- 執行記錄（JSON）：started/completed/failed/crashed
- 啟動時偵測 crashed 記錄
- 月度冪等性檢查（同日不重跑）

## 安全性

JWT (HS256) + API Key 雙模式認證，5 級角色階層，PBKDF2 密碼雜湊，token 撤銷，帳號鎖定，限流，稽核日誌，非 root 容器。
