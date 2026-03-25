# 系統現況追蹤報告書

> **報告日期**: 2026-03-25
> **版本**: v4.0
> **當前階段**: Phase E（實盤交易）— E1/E4 程式碼完成，待券商整合測試
> **代碼庫**: 2026-03-22 起始，master 分支
> **架構設計**: `docs/dev/MULTI_ASSET_ARCHITECTURE.md`
> **開發計畫**: `docs/dev/DEVELOPMENT_PLAN.md` v4.2

---

## 1. 專案概要

多資產投資組合研究與優化系統，覆蓋台股、美股、ETF（含債券/商品 ETF 代理）、台灣期貨、美國期貨。面向個人投資者與家庭資產管理。

**Monorepo 結構**: Python 後端 + React 18 Web + React Native Mobile + TypeScript 共享套件。

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
| Mobile | React Native + Expo 52 | — |
| 共享套件 | `@quant/shared` TypeScript | — |
| 券商 SDK | Shioaji (永豐金) | 1.3.2 |
| CI/CD | GitHub Actions (9 jobs) | — |
| 容器 | Docker (multi-stage) + docker-compose | PostgreSQL 16 Alpine |

---

## 3. 代碼庫統計

### 3.1 總覽

| 指標 | 數值 |
|------|------|
| 後端 Python 檔案 (src/ + strategies/) | 110 |
| 後端 Python LOC | 17,687 |
| 測試檔案 | 51 |
| 測試 LOC | 10,025 |
| 測試數量 (pytest collected) | **726** |
| Web 前端檔案 (.tsx/.ts) | 126 |
| Web 前端 LOC | 9,277 |
| Mobile 檔案 (.tsx/.ts) | 40 |
| Mobile LOC | 3,004 |
| 共享套件檔案 (.ts) | 11 |
| 共享套件 LOC | 1,257 |
| **全系統 LOC** | **~41,250** |

### 3.2 後端模組明細

| 模組 | 檔案數 | LOC | 功能描述 |
|------|--------|-----|----------|
| `src/api/` | 20 | 3,027 | REST API (12 路由, 44 端點) + WebSocket (4 頻道) + JWT/RBAC 認證 + 限流 + 審計 |
| `src/data/` | 15 | 2,334 | 4 數據源 (Yahoo/FinMind/FRED/Shioaji) + Scanner + 磁碟快取 + 基本面 |
| `src/alpha/` | 11 | 2,158 | Alpha 研究：14 因子 + 中性化 + 正交化 + Rolling IC + 分位數回測 + Pipeline + Regime + Attribution |
| `src/backtest/` | 6 | 2,192 | 回測引擎：多資產/多幣別/FX 時序 + 40+ 績效指標 + HTML/CSV 報表 + Walk-forward |
| `src/execution/` | 10 | 1,956 | SinopacBroker + SimBroker + ExecutionService + OMS + 行情訂閱 + 對帳 + 交易時段 + 觸價委託 |
| `src/strategy/` | 8 | 1,401 | 策略 ABC + 因子庫 (14) + 最佳化器 (3) + 研究工具 + Registry + MultiAssetStrategy |
| `src/portfolio/` | 4 | 757 | 組合最佳化 (6 方法) + 風險模型 (Ledoit-Wolf) + 幣別對沖 |
| `src/allocation/` | 4 | 713 | 戰術配置：宏觀四因子 + 跨資產信號 (動量/波動率/價值) + 戰術引擎 |
| `src/domain/` | 3 | 653 | 領域模型：Instrument + Portfolio (多幣別) + Order (融資融券/零股) + Trade + RiskAlert |
| `src/risk/` | 4 | 573 | 風控引擎 (10 規則) + Kill Switch + RiskMonitor |
| `src/instrument/` | 3 | 331 | InstrumentRegistry + 自動推斷 (symbol → asset_class/market/currency) |
| `src/cli/` | 2 | 299 | CLI: backtest / server / status / factors |
| `src/notifications/` | 6 | 246 | Discord / LINE / Telegram 通知 |
| `src/scheduler/` | 2 | 206 | APScheduler：排程 rebalance（已接通策略→風控→下單→通知） |
| `src/` (根) | 2 | 226 | config.py (Pydantic Settings) + logging_config.py (structlog) |
| `strategies/` | 8 | 615 | 7 個內建策略 |

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
| 6 | Pairs Trading | `strategies/pairs_trading.py` | 統計套利：相關性配對 | 規則型 |
| 7 | Sector Rotation | `strategies/sector_rotation.py` | 板塊相對動量輪動 | 規則型 |
| 8 | Alpha Pipeline | `src/alpha/strategy.py` | 可配置因子管線 (中性化→正交化→IC 加權→建構) | 管線型 |
| 9 | Multi-Asset | `src/strategy/multi_asset.py` | 兩層配置：戰術 → 資產內 Alpha → 組合最佳化 | 管線型 |

### 4.2 Alpha 因子庫（14 因子）

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

**基本面因子 (3)**:

| 因子 | 訊號 | 數據源 |
|------|------|--------|
| value_pe | 低 P/E | FinMind |
| value_pb | 低 P/B | FinMind |
| quality_roe | 高 ROE | FinMind |

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
| Market Hours | `market_hours.py` | 台股時段驗證 + 盤外委託佇列 | ✅ |
| Reconcile | `reconcile.py` | EOD 持倉對帳 (diff + auto_correct) | ✅ |
| StopOrderManager | `stop_order.py` | 軟體觸價委託 (stop-loss / stop-profit) | ✅ |

**SinopacBroker 擴展功能**:
- `query_trading_limits()` — 交易額度/融資融券額度預檢
- `query_settlements()` — T+N 交割查詢
- `check_dispositions()` — 處置股清單查詢
- 非阻塞下單 (`timeout=0`, ~12ms vs ~136ms)

### 4.6 組合最佳化（6 方法）

| 方法 | 說明 |
|------|------|
| Equal Weight (EW) | 等權重 |
| Inverse Volatility (IV) | 反波動率加權 |
| Risk Parity (RP) | 風險平價（等風險貢獻） |
| Mean-Variance (MVO) | Markowitz 均值變異數 |
| Black-Litterman (BL) | 支援 `BLView` 主觀觀點 |
| Hierarchical Risk Parity (HRP) | 階層式風險平價 |

**風險模型**: 歷史 / EWM / Ledoit-Wolf 收縮共變異數 + 邊際風險貢獻。

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

### 5.1 REST 端點（11 路由模組, 44 端點）

| 模組 | 端點數 | 前綴 | 關鍵端點 |
|------|--------|------|---------|
| auth | 3 | `/api/v1/auth` | login, register, refresh |
| admin | 5 | `/api/v1/admin` | 用戶 CRUD, 審計日誌, 配置 |
| portfolio | 8 | `/api/v1/portfolio` | CRUD + rebalance-preview + 交易歷史 |
| backtest | 5 | `/api/v1/backtest` | 回測 + walk-forward + 歷史結果 |
| strategies | 4 | `/api/v1/strategies` | 列表 + 啟停控制 |
| orders | 2 | `/api/v1/orders` | 手動下單 + 訂單歷史 |
| risk | 4 | `/api/v1/risk` | 規則狀態 + kill switch + 告警 |
| alpha | 3 | `/api/v1/alpha` | Alpha 研究 + 因子查詢 |
| allocation | 1 | `/api/v1/allocation` | 戰術配置計算 |
| execution | 6 | `/api/v1/execution` | 執行狀態 + 交易時段 + 對帳 + Paper trading + 佇列 |
| system | 3 | `/api/v1/system` | 健康檢查 + Prometheus metrics |

### 5.2 WebSocket 頻道

| 頻道 | 說明 | 來源 |
|------|------|------|
| `portfolio` | 持倉 + NAV 即時更新 | 策略執行 / 成交回報 |
| `orders` | 訂單狀態變更 | OMS / SinopacBroker callback |
| `alerts` | 風控告警 | RiskEngine / Kill Switch |
| `market` | 即時行情 tick | SinopacQuoteManager (待接通) |

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

### 6.2 Mobile (React Native + Expo 52)

7 tabs: Dashboard / Backtest / Alpha / Strategies / Orders / Risk / Settings

**特色**: Victory Native 圖表, Expo SecureStore 憑證, OfflineBanner, Role-based 功能控制

### 6.2.1 Android Native (Jetpack Compose)

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

### 7.1 後端測試（726 tests）

| 分類 | 檔案數 | 測試數 | 說明 |
|------|--------|--------|------|
| Execution 層 | 7 | ~170 | SinopacBroker, QuoteManager, ExecutionService, MarketHours, Reconcile, StopOrder, ShioajiFeed |
| Alpha 層 | 9 | ~100 | 因子, Pipeline, Regime, Attribution, Rolling IC |
| 策略 + 回測 | 8 | ~120 | 各策略, 引擎, 分析, Walk-forward |
| 風控 | 3 | ~60 | 規則, Kill Switch, Monitor |
| API + 整合 | 6 | ~100 | REST 端點, Portfolio API, Auth, WebSocket |
| 數據 | 5 | ~80 | Yahoo, FinMind, FRED, Shioaji, Scanner |
| 領域模型 | 6 | ~50 | Order, Portfolio, Instrument, OMS |
| 其他 | 7 | ~46 | Config, Notifications, 雜項 |

### 7.2 前端測試

| 平台 | 框架 | 檔案數 |
|------|------|--------|
| Web | Vitest + jsdom | 18 |
| Web E2E | Playwright | 3 |
| Mobile | Jest | 14 |
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
| `e2e-test` | Playwright chromium | — |
| `release` | 自動建立 GitHub Release + APK 附件 | 所有上述 jobs（master push 限定）|

### 7.4 本地 Pre-push Hook

- **位置**：`.githooks/pre-push`
- **啟用**：`make setup-hooks`（執行 `git config core.hooksPath .githooks`）
- **執行內容**：ruff lint → mypy → pytest tests/unit/ → web/mobile typecheck
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
| 回測引擎 | ✅ 完成 | 多資產/多幣別/FX 時序/40+ 指標/Walk-forward |
| 策略框架 | ✅ 完成 | 9 策略 + Strategy ABC + Registry |
| 數據源 | ✅ 完成 | Yahoo + FinMind + FRED + Shioaji (kbars/ticks/snapshot) |
| Alpha 研究 | ✅ 完成 | 14 因子/中性化/正交化/Rolling IC/Pipeline/Regime/Attribution |
| 戰術配置 | ✅ 完成 | 宏觀四因子 + 跨資產信號 + TacticalEngine |
| 組合最佳化 | ✅ 完成 | 6 方法 + Ledoit-Wolf + 風險貢獻 |
| 幣別對沖 | ✅ 完成 | 分級對沖 + HedgeRecommendation |
| 兩層整合 | ✅ 完成 | MultiAssetStrategy (allocation → alpha → optimizer) |
| 風控引擎 | ✅ 完成 | 10 規則 + Kill Switch + 跨資產規則 |
| InstrumentRegistry | ✅ 完成 | 自動推斷 symbol → asset_class/market/currency |
| 多幣別 Portfolio | ✅ 完成 | nav_in_base / currency_exposure / per-bar FX |
| API | ✅ 完成 | 44 端點 + WebSocket + JWT/RBAC + 限流 + 審計 |
| Web 前端 | ✅ 完成 | 10 頁 + i18n (en/zh) + 深色主題 |
| Mobile | ✅ 完成 | 7 tabs + Expo SecureStore + OfflineBanner |
| Android Native | 🟡 進行中 | Backtest tab + UniversePickerSheet (Material 3) + i18n |

### 9.2 交易執行（Phase E）

| 功能 | 狀態 | 說明 |
|------|------|------|
| SinopacBroker | ✅ 程式碼 | 下單/撤單/改單/持倉/帳務/成交回報/斷線重連 |
| ExecutionService | ✅ 整合 | 模式路由 + AppState 接通 + startup 初始化 |
| 非阻塞下單 | ✅ 程式碼 | `timeout=0` (~12ms) |
| 交易時段管理 | ✅ 完成 | 盤前/盤中/零股/定盤 + 盤外佇列 |
| EOD 對帳 | ✅ 完成 | reconcile + auto_correct |
| 觸價委託 | ✅ 完成 | StopOrderManager (stop-loss/profit) |
| 融資融券 | ✅ 模型 | OrderCondition (Cash/Margin/Short/DayTrade) + StockOrderLot |
| 交易額度預檢 | ✅ 程式碼 | query_trading_limits / settlements / dispositions |
| 市場掃描器 | ✅ 完成 | VolumeRank / ChangeRank + 處置/注意股排除 |
| 即時行情 | 🟡 架構 | SinopacQuoteManager 完成，WS broadcast 待接通 |
| 排程 Rebalance | ✅ 整合 | scheduler/jobs.py 接通策略→風控→下單→Portfolio→通知 |
| **整合測試** | ❌ 待辦 | **需 Shioaji API Key + CA 憑證** |
| 期貨選擇權 | ❌ 待辦 | Shioaji 支援 FuturesPriceType + ComboOrder |
| IB 美股 | ❌ 待辦 | Shioaji 完成後 |

### 9.3 外部依賴狀態

| 依賴 | 狀態 | 備註 |
|------|------|------|
| shioaji SDK | ✅ 已安裝 v1.3.2 | `pip install shioaji` |
| Shioaji API Key | ❌ 未取得 | 需至 sinotrade.com.tw 申請 |
| CA 憑證 (.pfx) | ❌ 未取得 | 同上 |
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
| D-28 | 待辦 | 低 | FastAPI `on_event` deprecated → lifespan handler | DeprecationWarning |
| D-29 | ✅ 已修復 | 低 | CI backend-test count 過時 (326 vs 726) | CLAUDE.md 數字已更新 |

---

## 11. 開發路線圖

### 已完成

| 階段 | 完成日期 | 里程碑 |
|------|---------|--------|
| Phase A | 2026-03-24 | 多資產基礎設施 (InstrumentRegistry + 多幣別 Portfolio + DataFeed 擴展) |
| Phase B | 2026-03-24 | 跨資產 Alpha (宏觀因子 + 跨資產信號 + 戰術配置引擎) |
| Phase C | 2026-03-24 | 組合最佳化 (6 方法 + Ledoit-Wolf + 幣別對沖) |
| Phase D | 2026-03-25 | 系統整合 (MultiAssetStrategy + 跨資產風控 + Allocation 前端 + Alpha 強化) |
| Phase E1 | 2026-03-25 | 交易執行核心 (SinopacBroker + ExecutionService + 對帳 + 交易時段) |
| Phase E4 | 2026-03-25 | Shioaji 進階 (DataFeed + Scanner + 非阻塞 + 觸價 + 融資融券 + 額度預檢) |

### 進行中 / 待辦

| 項目 | 優先級 | 前置條件 | 說明 |
|------|--------|---------|------|
| Shioaji 整合測試 | 🔴 P0 | API Key + CA | 模擬環境端到端驗證 |
| WS market 頻道接通 | 🟡 P1 | API Key | SinopacQuoteManager → broadcast |
| Paper Trading 實測 | 🟡 P1 | 整合測試通過 | 模擬帳戶跑完整循環 |
| 期貨選擇權交易 | 🟡 P1 | — | FuturesPriceType + ComboOrder |
| 期貨展期模擬 | 🟢 P2 | — | R1/R2 連續合約 + roll cost |
| IB 美股對接 | 🟢 P2 | Shioaji 完成 | IBBroker(BrokerAdapter) |
| 擴展績效歸因 | 🟢 P2 | — | 資產配置 + 選股 + 匯率歸因 |
| CI 更新 | 🟢 P2 | — | 更新 test count, 修復 deprecation |

---

## 12. 快速啟動指南

### 12.1 開發環境

```bash
# 後端
make install          # pip install -e ".[dev]"
make test             # pytest tests/ -v (726 tests)
make lint             # ruff check + mypy strict
make dev              # API 熱重載 port 8000

# 前端
make install-apps     # bun install
make web              # Web dev server port 3000
make mobile           # Expo dev server

# 全端
make start            # 後端 + Web 並行
```

### 12.2 Paper Trading 模式

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
