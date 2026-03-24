# 系統現況追蹤報告書

> **專案名稱**: 量化交易系統 (Quantitative Trading System)
> **報告日期**: 2026-03-24
> **報告版本**: v1.2
> **目標定位**: 具備真實 Alpha 研究與實盤交易能力的量化交易平台，面向個人投資者與家族資產管理
> **當前階段**: Alpha 研究層已完成，下一步為實盤交易能力
> **代碼庫起始日期**: 2026-03-22
> **當前分支**: master

---

## 目錄

1. [專案總覽](#1-專案總覽)
2. [架構概覽](#2-架構概覽)
3. [模組清單與程式碼統計](#3-模組清單與程式碼統計)
4. [後端模組詳細盤點](#4-後端模組詳細盤點)
5. [前端模組詳細盤點](#5-前端模組詳細盤點)
6. [策略庫盤點](#6-策略庫盤點)
7. [基礎設施與部署](#7-基礎設施與部署)
8. [測試覆蓋現況](#8-測試覆蓋現況)
9. [CI/CD 流水線](#9-cicd-流水線)
10. [安全機制現況](#10-安全機制現況)
11. [已知缺陷與待辦事項](#11-已知缺陷與待辦事項)
12. [功能完成度評估](#12-功能完成度評估)
13. [差距分析](#13-差距分析)
14. [開發路線圖](#14-開發路線圖)

---

## 1. 專案總覽

### 1.1 產品定位與階段目標

本系統的長期目標是成為面向個人投資者及家族資產管理的量化交易平台。**當前優先目標是建立真實的 Alpha 研究能力與實盤交易能力**，商業化發佈為後續階段。

**系統演進路線：**

```
[已完成] Alpha 研究層            [當前目標] 自用實盤            [遠期] 商業化
─────────────────────          ──────────────          ──────────
✅ 因子發現/驗證/合成 pipeline   • 券商 API 對接          • 用戶引導
✅ 橫截面分析框架                • Paper → Live 交易      • 多帳戶管理
✅ 交易成本感知的組合建構         • 即時行情串流            • 訂閱/授權
✅ AlphaStrategy 適配器          • 通知事件串接            • 合規與部署
```

**現有能力：**

- **Alpha 研究層**: 端到端 Pipeline — 股票池篩選 → 因子中性化 → 正交化 → 合成 → 分位數驗證 → 成本感知組合建構
- **回測引擎**: 歷史數據驗證策略績效，40+ 績效指標，步進分析
- **多策略支援**: 動量、均值回歸、多因子、配對交易、板塊輪動等 7 策略 + Alpha 策略
- **風險管理**: 宣告式風險規則、自動熔斷機制
- **投資組合管理**: 持倉追蹤、再平衡預覽、T+N 交割
- **多平台前端**: Web 儀表板 + 行動端 App
- **通知系統**: Discord / LINE / Telegram 多渠道通知

### 1.2 技術棧摘要

| 層級 | 技術選型 |
|------|---------|
| 後端語言 | Python 3.12, 嚴格 mypy 型別檢查 |
| Web 框架 | FastAPI + Uvicorn |
| 資料庫 | PostgreSQL 16 (生產) / SQLite (開發) |
| ORM/遷移 | SQLAlchemy 2.0 + Alembic |
| 前端框架 | React 18 + Vite 5 + Tailwind CSS |
| 行動端 | React Native + Expo 52 |
| 共享套件 | @quant/shared (TypeScript 型別、API 客戶端、WebSocket) |
| 套件管理 | pip (後端) / bun (前端 monorepo) |
| 容器化 | Docker + docker-compose |
| CI/CD | GitHub Actions (9 jobs) |
| 監控 | Prometheus + structlog |

### 1.3 專案結構

```
Portfolio/
├── src/                    # Python 後端 (75 檔, ~8,600 LOC)
│   ├── alpha/              #   Alpha 研究層 (8 檔, ~1,300 LOC)
│   ├── domain/             #   領域模型與持久化
│   ├── strategy/           #   策略引擎、因子庫、研究工具
│   ├── risk/               #   風險引擎與規則
│   ├── execution/          #   模擬券商與訂單管理
│   ├── backtest/           #   回測引擎與分析
│   ├── data/               #   數據源與快取
│   ├── api/                #   REST API + WebSocket
│   ├── notifications/      #   多渠道通知
│   ├── scheduler/          #   排程任務
│   └── cli/                #   命令列工具
├── tests/                  # Python 測試 (36 檔, ~7,000 LOC)
├── strategies/             # 策略插件 (8 檔, ~615 LOC)
├── migrations/             # 資料庫遷移 (4 版本)
├── apps/                   # 前端 monorepo (~11,000 LOC)
│   ├── shared/             #   @quant/shared 共享套件
│   ├── web/                #   React Web 儀表板
│   └── mobile/             #   React Native 行動端
├── scripts/                # 輔助腳本
├── docs/                   # 文件
└── .github/workflows/      # CI/CD 定義
```

---

## 2. 架構概覽

### 2.1 系統架構

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Alpha 研究層 (src/alpha/)                     │
│                                                                     │
│  ┌─────────────┐   ┌──────────────┐   ┌───────────────────────┐    │
│  │ 因子 Pipeline │   │ 橫截面分析引擎 │   │ 組合建構器             │    │
│  │              │   │              │   │                       │    │
│  │ 原始因子     │   │ 分位數排序   │   │ 交易成本感知的權重最佳化 │    │
│  │   ↓         │   │ 行業中性化   │   │ 換手率約束             │    │
│  │ 中性化/正交  │   │ 規模中性化   │   │ 風險預算               │    │
│  │   ↓         │   │ IC/IR 時序   │   │ Alpha 衰減調適         │    │
│  │ 合成 Alpha  │   │ 多空收益歸因 │   │                       │    │
│  └──────┬──────┘   └──────┬───────┘   └───────────┬───────────┘    │
│         └─────────────────┼────────────────────────┘               │
│                           ↓                                        │
│                   AlphaStrategy (自動從 Alpha 信號生成權重)           │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
  ╔═════════════════════════╧═══════════════════════════════╗
  ║              交易系統                                    ║
  ║                                                        ║
  ║  DataFeed (Yahoo/FinMind)                              ║
  ║      ↓                                                 ║
  ║  Strategy.on_bar(ctx) → 目標權重 dict[str, float]       ║
  ║      ↓                                                 ║
  ║  weights_to_orders() 轉換為訂單列表                      ║
  ║      ↓                                                 ║
  ║  RiskEngine.check_orders() → 宣告式規則逐一過濾          ║
  ║      ↓                                                 ║
  ║  SimBroker / Broker → 執行撮合 (滑點/手續費/稅)          ║
  ║      ↓                                                 ║
  ║  Trade → Portfolio.apply_trades() → 更新持倉與淨值       ║
  ╚════════════════════════════════════════════════════════╝
```

### 2.2 Alpha 研究層 (`src/alpha/`)

端到端 Pipeline，提供系統化的因子發現、驗證、合成能力。

**模組結構：**

| 模組 | 功能 |
|------|------|
| `universe.py` | 股票池篩選：流動性、市值、上市天數、數據完整性、產業 |
| `neutralize.py` | 因子中性化：winsorize + standardize + 4 種方法 (市場/行業/規模/行業+規模) |
| `cross_section.py` | 分位數組合回測：N 分位收益、多空價差、單調性分數 |
| `turnover.py` | 換手率分析：成本侵蝕、盈虧平衡成本、淨 IC |
| `orthogonalize.py` | 因子正交化：逐步 (Gram-Schmidt) + 對稱 (PCA/ZCA) |
| `construction.py` | 成本感知組合建構：換手率懲罰、最大換手率約束、Alpha 衰減混合 |
| `pipeline.py` | 端到端 Pipeline：AlphaConfig → 研究報告 + 生產權重生成 |
| `strategy.py` | AlphaStrategy 適配器：包裝為 Strategy 子類，已註冊至 registry |

**設計原則：**
1. **與交易系統零衝突** — Alpha 層產出 `dict[str, float]` 權重，完全相容 Strategy 介面
2. **研究與生產共用** — 同一套因子定義在研究和回測/實盤中皆可使用
3. **純函式優先** — 中性化、正交化、標準化皆為無狀態純函式
4. **DataFrame in / DataFrame out** — 統一為 `pd.DataFrame(index=date, columns=symbols)`

**Pipeline 執行流程：**

```
AlphaConfig → UniverseFilter → 因子計算 → winsorize → standardize
→ neutralize → 單因子分析 (IC/衰減/分位數/換手率) → orthogonalize
→ combine (等權/IC加權) → 合成因子驗證 → construct_portfolio → 報告
```

### 2.3 關鍵設計決策

| 決策 | 說明 | 原因 |
|------|------|------|
| 策略回傳權重而非訂單 | `on_bar()` → `dict[str, float]` | 解耦策略邏輯與執行細節，便於風控介入 |
| 風險規則為純函式工廠 | 無繼承，返回 `RiskRule` dataclass | 可組合、可測試、宣告式 |
| 所有金額使用 `Decimal` | 禁止 `float` | 避免浮點精度問題 |
| 時區正規化 | 所有 DatetimeIndex 統一為 tz-naive UTC | 消除跨市場時區問題 |
| 時間因果性 | Context 包裝 DataFeed，截斷至 `current_time` | 防止回測中的未來數據洩漏 |
| T+N 交割 | Portfolio 支援 `pending_settlements` / `settled_cash` | 模擬真實交割制度 |
| Alpha 層獨立於 strategy/ | `src/alpha/` 而非擴展 `research.py` | 避免 research.py 膨脹，Alpha 研究是獨立關注點 |

### 2.4 API 架構

- **路由**: 8 個模組 (`auth`, `admin`, `portfolio`, `strategies`, `orders`, `backtest`, `risk`, `system`)
- **前綴**: `/api/v1`
- **認證**: JWT + API Key 雙模式
- **授權**: 角色層級 `viewer < researcher < trader < risk_manager < admin`
- **限流**: slowapi (60 req/min 預設, backtest 10 req/min)
- **WebSocket**: 4 頻道 (`portfolio`, `alerts`, `orders`, `market`)
- **監控**: Prometheus `/metrics` 端點
- **審計**: AuditMiddleware 記錄所有變更操作

---

## 3. 模組清單與程式碼統計

### 3.1 後端程式碼量

| 模組 | 檔案數 | 行數 (LOC) | 說明 |
|------|--------|-----------|------|
| `src/api/` | 16 | ~2,264 | REST API + WebSocket + 中介層 |
| `src/backtest/` | 6 | ~2,106 | 回測引擎、分析、報表、驗證 |
| `src/data/` | 12 | ~1,719 | 數據源、快取、品質檢查 |
| `src/alpha/` | 8 | ~1,300 | Alpha 研究層 (Pipeline、中性化、組合建構) |
| `src/strategy/` | 7 | ~1,081 | 策略引擎、因子庫、最佳化器 |
| `src/domain/` | 3 | ~534 | 領域模型、持久化倉庫 |
| `src/risk/` | 4 | ~477 | 風險引擎、規則、監控 |
| `src/execution/` | 4 | ~374 | 模擬券商、OMS |
| `src/cli/` | 2 | ~283 | CLI 命令 |
| `src/notifications/` | 6 | ~246 | 通知渠道 |
| `src/config.py` | 1 | ~172 | 配置管理 |
| `src/scheduler/` | 2 | ~112 | 排程任務 |
| `src/logging_config.py` | 1 | ~44 | 日誌設定 |
| **後端合計** | **75** | **~8,600** | |

### 3.2 前端程式碼量

| 套件 | 檔案數 | 行數 (LOC) | 說明 |
|------|--------|-----------|------|
| `apps/web/` | ~107 | ~7,024 | React Web 儀表板 |
| `apps/mobile/` | ~40 | ~2,957 | React Native 行動端 |
| `apps/shared/` | ~11 | ~1,038 | 共享型別、API、工具 |
| **前端合計** | **~158** | **~11,019** | |

### 3.3 測試程式碼量

| 分類 | 檔案數 | 行數 (LOC) | 框架 |
|------|--------|-----------|------|
| Python 單元測試 | 34 | ~6,200 | pytest |
| Python 整合測試 | 2 | ~808 | pytest |
| Web 單元測試 | 18 | ~1,363 | Vitest + jsdom |
| Mobile 單元測試 | 14 | ~1,069 | Jest + React Native |
| Shared 單元測試 | 4 | ~413 | Vitest |
| Web E2E 測試 | 3 | ~182 | Playwright |
| **測試合計** | **75** | **~10,035** | |

### 3.4 其他

| 分類 | 檔案數 | 行數 (LOC) |
|------|--------|-----------|
| 策略插件 (`strategies/`) | 8 | ~615 |
| 資料庫遷移 (`migrations/`) | 5 | ~316 |
| 配置/基建檔 | ~15 | ~400 |

### 3.5 總計

| 類別 | 行數 |
|------|------|
| 業務程式碼 (後端 + 前端 + 策略) | ~20,234 |
| 測試程式碼 | ~10,035 |
| 測試佔比 | ~33% |
| **專案總計** | **~31,600** |

---

## 4. 後端模組詳細盤點

### 4.1 Alpha 研究層 (`src/alpha/`)

| 檔案 | 功能 |
|------|------|
| `universe.py` | `UniverseFilter`：流動性/市值/上市天數/數據完整性/產業篩選，支援逐日時序篩選 |
| `neutralize.py` | `winsorize()` + `standardize()` + `neutralize()`：4 種方法 (MARKET/INDUSTRY/SIZE/INDUSTRY_SIZE) |
| `cross_section.py` | `quantile_backtest()` → `QuantileResult`：N 分位收益、多空價差、單調性、Sharpe |
| `turnover.py` | `analyze_factor_turnover()` → `TurnoverResult`：換手率、成本侵蝕、盈虧平衡、淨 IC |
| `orthogonalize.py` | `orthogonalize_sequential()` (Gram-Schmidt) + `orthogonalize_symmetric()` (PCA/ZCA) |
| `construction.py` | `construct_portfolio()`：換手率懲罰 + 最大換手率約束 + `blend_with_decay()` 信號衰減混合 |
| `pipeline.py` | `AlphaPipeline`：`research()` 產出 `AlphaReport`，`generate_weights()` 產出即時權重 |
| `strategy.py` | `AlphaStrategy(Strategy)`：Pipeline 適配器，已註冊至 registry (`"alpha"`) |

### 4.2 領域模型 (`src/domain/`)

**models.py** — 核心值物件與聚合根：

| 類別 | 名稱 | 說明 |
|------|------|------|
| 列舉 | `Side`, `AssetClass`, `OrderStatus`, `OrderType`, `Severity` | 交易方向、資產類型、訂單狀態等 |
| 值物件 | `Instrument` (frozen) | 金融工具（代碼、名稱、資產類型） |
| 值物件 | `Bar` (frozen) | OHLCV K線數據 |
| 聚合 | `Position` | 持倉（數量、成本、未實現損益） |
| 聚合 | `Order` | 訂單（生命週期管理） |
| 聚合 | `Trade` | 成交紀錄 |
| 聚合根 | `Portfolio` | 投資組合（現金、持倉、T+N 交割、NAV） |

**repository.py** — `PortfolioRepository`：SQLAlchemy 實作，單 JOIN 查詢，支援 PostgreSQL 與 SQLite。

### 4.3 策略引擎 (`src/strategy/`)

| 檔案 | 功能 |
|------|------|
| `base.py` | `Strategy` ABC，`Context` 包裝器 |
| `engine.py` | `StrategyEngine`，`weights_to_orders()` 轉換 |
| `factors.py` | 因子庫：SMA, EMA, RSI, Bollinger, PE, PB, ROE, 量價趨勢 |
| `optimizer.py` | 最佳化器：等權重、信號權重、風險平價 |
| `registry.py` | 策略集中註冊（含 `alpha` 策略） |
| `research.py` | 因子研究：IC 分析、因子衰減、因子合成 (被 Alpha 層消費並擴展) |

### 4.4 風險管理 (`src/risk/`)

| 檔案 | 功能 |
|------|------|
| `engine.py` | `RiskEngine`：依序執行規則，首個 REJECT 即停止 |
| `rules.py` | 規則工廠：`max_position_weight`, `max_sector_weight`, `max_daily_drawdown`, `kill_switch` (5% 日損失熔斷) |
| `monitor.py` | `RiskMonitor`：持倉/訂單/組合指標追蹤，閾值告警 |

### 4.5 執行層 (`src/execution/`)

| 檔案 | 功能 |
|------|------|
| `sim.py` | `SimBroker`：固定/根號滑點模型、手續費/稅、價格限制、成交量檢查、T+N 交割 |
| `oms.py` | OMS：訂單生命週期管理 (pending → submitted → filled/rejected)，部分成交 |
| `broker.py` | `Broker` ABC 介面與工廠方法 |

### 4.6 回測引擎 (`src/backtest/`)

| 檔案 | 功能 |
|------|------|
| `engine.py` | 核心編排器：下載數據 → 逐交易日迭代 → 策略調用 → 風控 → 執行 → 更新。7 個輔助方法 |
| `analytics.py` | 40+ 績效指標：Sharpe, Sortino, Calmar, 最大回撤, 勝率, VaR, CVaR, Hurst 指數 |
| `report.py` | 報表生成：HTML 報告、基準比較、CSV 匯出、淨值曲線、收益歸因 |
| `validation.py` | 數據因果性檢查、確定性測試、敏感度分析 |
| `walk_forward.py` | 步進分析：滾動訓練/測試窗口、樣本外評估 |

### 4.7 數據層 (`src/data/`)

| 檔案 | 功能 |
|------|------|
| `feed.py` | `DataFeed` ABC |
| `store.py` | `HistoricalFeed`：OHLCV 載入、時間因果性、ffill 限制 |
| `user_store.py` | `UserDataStore`：用戶上傳 CSV 數據的本地 SQLite 持久化 |
| `fundamentals.py` | `FundamentalsProvider` ABC |
| `quality.py` | 數據品質檢查：NaN 偵測、OHLC 邏輯驗證、成交量一致性 |
| `sources/yahoo.py` | Yahoo Finance 數據源 (yfinance) |
| `sources/finmind.py` | FinMind 台灣股市數據源 |
| `sources/finmind_fundamentals.py` | 台灣基本面數據 (PE/PB/ROE/營收/股利/產業) |
| `sources/finmind_common.py` | FinMind 共用工具 |
| `sources/parquet_cache.py` | Parquet 磁碟快取 (LRU) |
| `sources/__init__.py` | `create_feed()` 數據源工廠 |

### 4.8 API 層 (`src/api/`)

**路由模組**:

| 路由 | 端點數 | 主要功能 |
|------|--------|---------|
| `auth.py` | 5 | 登入、註冊、登出、Token 刷新、密碼重設 |
| `admin.py` | 5+ | 用戶 CRUD、API Key 管理、角色分配 |
| `portfolio.py` | 6+ | 組合 CRUD、再平衡預覽、交易歷史、NAV |
| `backtest.py` | 3+ | 回測執行、步進分析、參數最佳化 |
| `strategies.py` | 2+ | 策略列表、參數描述 |
| `orders.py` | 3 | 建單、取消、歷史查詢 |
| `risk.py` | 3+ | 規則切換、熔斷控制、風險指標 |
| `system.py` | 3 | 健康檢查、版本、指標 |

**基建層**: `app.py` (應用工廠), `auth.py` (JWT/API Key), `middleware.py` (審計日誌), `schemas.py` (Pydantic 模型), `state.py` (AppState), `ws.py` (WebSocket), `password.py` (PBKDF2-SHA256)

### 4.9 其他後端模組

| 模組 | 說明 |
|------|------|
| `src/notifications/` | Discord / LINE / Telegram 多渠道通知，交易/再平衡/告警模板 |
| `src/scheduler/` | APScheduler：每日組合快照、每週再平衡檢查 |
| `src/cli/` | Typer CLI：`backtest`, `server`, `status`, `factors` 命令 |

---

## 5. 前端模組詳細盤點

### 5.1 共享套件 (`apps/shared/`)

| 模組 | 說明 |
|------|------|
| `types/index.ts` | TypeScript 介面 (對應後端 Pydantic schemas) |
| `api/client.ts` | 平台無關 HTTP 客戶端 (ClientAdapter 注入) |
| `api/endpoints.ts` | 型別化 API 端點定義 (25+ 端點) |
| `api/ws.ts` | WSManager (自動重連、指數退避、頻道訂閱) |
| `hooks/pollBacktestResult.ts` | 回測結果輪詢工具 |
| `utils/format.ts` | 數字/貨幣/日期格式化 |

### 5.2 Web 儀表板 (`apps/web/`)

**8 個功能頁面：**

| 頁面 | 路徑 | 說明 |
|------|------|------|
| Dashboard | `/` | MarketTicker, NavChart, PositionTable |
| Backtest | `/backtest` | UniversePicker, ParamsEditor, ResultChart, MonthlyHeatmap, CompareTable |
| Portfolio | `/portfolio` | 組合 CRUD、再平衡預覽 |
| Orders | `/orders` | OrderForm, 訂單歷史 |
| Strategies | `/strategies` | 策略列表、啟停控制 |
| Risk | `/risk` | 風險規則、告警、熔斷開關 |
| Settings | `/settings` | SystemMetrics, API Key, 密碼修改 |
| Admin | `/admin` | 用戶管理、審計日誌、配置 |

**核心基建**：Auth Context, API 適配器, `useApi`/`useWs` hooks, i18n (英文/繁體中文), 深色/淺色模式

**共享 UI 元件** (18+)：Card, MetricCard, StatusBadge, ErrorAlert, ErrorBoundary, Skeleton, Modal, DataTable, ConnectionBanner, ExportButton, InfoTooltip, Toast, Sidebar

### 5.3 行動端 App (`apps/mobile/`)

**元件**: MetricCard, PositionRow, OrderRow, OrderForm, StrategyRow, AlertItem, NavChart, BacktestChart, PositionPieChart, OfflineBanner, ErrorBoundary, Skeleton

**Hooks**：`useAuth`, `usePortfolio`, `useOrders`, `useBacktest`, `useAlerts`, `useRealtimeData`

**平台特性**：Expo SecureStore 安全儲存、Victory Native 圖表、離線偵測

### 5.4 前端設計模式

| 模式 | 說明 |
|------|------|
| 平台適配器 | 共享套件定義介面，各平台注入實作 |
| 桶形匯出 | 每個功能資料夾有 `index.ts`，特性代碼從 `@core/*` 匯入 |
| Context 狀態管理 | Auth, Theme, I18n 用 React Context，無 Redux |
| 角色門控 | UI 功能根據 JWT 角色動態顯示/隱藏 |
| 虛擬捲動 | TanStack React Virtual 處理大數據表格 |
| 國際化 | 支援英文/繁體中文，語言偏好持久化 |

---

## 6. 策略庫盤點

| 策略 | 檔案 | LOC | 邏輯摘要 |
|------|------|-----|---------|
| 動量 | `momentum.py` | 48 | 價格趨勢跟隨 |
| 均線交叉 | `ma_crossover.py` | 46 | 快慢均線交叉信號 |
| 均值回歸 | `mean_reversion.py` | 41 | 超買賣出/超賣買入 |
| RSI 超賣 | `rsi_oversold.py` | 48 | RSI < 30 買入信號 |
| 多因子 | `multi_factor.py` | 192 | 動量+價值+品質因子組合，風險平價加權 |
| 配對交易 | `pairs_trading.py` | 79 | 相關性統計套利 |
| 板塊輪動 | `sector_rotation.py` | 161 | 相對動量跨板塊輪動 |
| Alpha 策略 | `src/alpha/strategy.py` | 70 | Pipeline 驅動，配置定義因子組合 |
| **合計** | **8 策略** | **~685** | |

**新增策略流程**：在 `strategies/` 建立檔案 → 繼承 `Strategy` → 實作 `name()` 和 `on_bar()` → 在 `src/strategy/registry.py` 中註冊。

---

## 7. 基礎設施與部署

### 7.1 資料庫

| 項目 | 內容 |
|------|------|
| 生產環境 | PostgreSQL 16 (docker-compose) |
| 開發環境 | SQLite |
| ORM | SQLAlchemy 2.0 |
| 遷移工具 | Alembic (4 個版本) |
| 遷移歷史 | ① 初始 schema → ② 用戶表 → ③ Token 撤銷 → ④ 組合持久化 |

### 7.2 Docker

- **Dockerfile**: 多階段建置 (build + runtime), python:3.12-slim, 非 root 用戶 (appuser), 端口 8000
- **docker-compose.yml**: `api` 服務 (Uvicorn 2 workers) + `db` 服務 (PostgreSQL 16 Alpine), volumes `pg_data` / `cache_data`

### 7.3 配置管理

- Pydantic Settings 驅動，`QUANT_` 前綴環境變數，`.env` 支援
- 測試中透過 `override_config()` 覆寫

### 7.4 腳本

| 腳本 | 用途 |
|------|------|
| `scripts/benchmark.py` | 回測效能基準測試 (quick/full 模式) |
| `scripts/start.bat` | Windows 一鍵啟動 (後端 + 前端) |

---

## 8. 測試覆蓋現況

### 8.1 後端測試 (pytest)

**既有模組測試** (25 檔, 325 測試函式)：

回測引擎、股利、配置、數據源、執行、因子、ffill、FinMind、領域模型、策略、通知、密碼、組合 API、持久化、研究、風險、排程、SimBroker、驗證、步進分析、權重轉換、WebSocket、整合 API

**Alpha 層測試** (7 檔, 72 測試函式)：

| 測試檔 | 測試數 | 覆蓋 |
|--------|--------|------|
| `test_alpha_universe.py` | 8 | 所有篩選條件 + 時間因果性 |
| `test_alpha_neutralize.py` | 9 | winsorize/standardize/4 種 neutralize |
| `test_alpha_cross_section.py` | 7 | 有效因子單調性、隨機因子、多空分析 |
| `test_alpha_turnover.py` | 10 | 換手率計算、成本扣除 |
| `test_alpha_orthogonalize.py` | 9 | Sequential/Symmetric 降相關 |
| `test_alpha_construction.py` | 11 | 權重約束、換手率限制、衰減混合 |
| `test_alpha_pipeline.py` | 18 | Pipeline 端到端 + AlphaStrategy |

**後端測試合計**: 36 檔, ~397 測試函式

### 8.2 前端測試

- **Web (Vitest + jsdom)**: 18 測試檔 — 涵蓋所有頁面、核心元件、工具函式
- **Mobile (Jest)**: 14 測試檔 — 涵蓋所有元件、hooks
- **Shared (Vitest)**: 4 測試檔 — API 客戶端、WebSocket、格式化
- **E2E (Playwright)**: 3 測試檔 — 登入流程、訂單操作、回測提交

### 8.3 測試缺口

| 缺口 | 影響 | 優先級 |
|------|------|--------|
| 無測試覆蓋率報告 | 無法量化哪些路徑未被測試 | 高 |
| 無效能/壓力測試 | 不確定大數據量下的表現 | 中 |
| 無安全性測試 | 認證/授權邊界未自動驗證 | 高 |
| E2E 僅 3 個場景 | 關鍵用戶流程覆蓋不足 | 中 |
| 無行動端 E2E | 行動端整合未驗證 | 低 |

---

## 9. CI/CD 流水線

### 9.1 流水線結構

```
觸發: push to master / PR to master
           │
    ┌──────┼──────────────┐
    ▼      ▼              ▼
backend  backend     web-typecheck    shared-test   mobile-typecheck   mobile-test
 -lint    -test           │
                    ┌─────┼─────┐
                    ▼           ▼
                web-test    web-build
                    │
                    ▼
                e2e-test
```

### 9.2 各 Job 詳情

| Job | 環境 | 相依性 | 執行內容 |
|-----|------|--------|---------|
| `backend-lint` | Ubuntu, Python 3.12 | 無 | ruff check + mypy strict |
| `backend-test` | Ubuntu, Python 3.12 | 無 | pytest tests/ -v |
| `web-typecheck` | Ubuntu, bun | 無 | tsc --noEmit |
| `web-test` | Ubuntu, bun | web-typecheck | vitest |
| `web-build` | Ubuntu, bun | web-typecheck | vite build |
| `shared-test` | Ubuntu, bun | 無 | vitest |
| `mobile-typecheck` | Ubuntu, bun | 無 | tsc --noEmit |
| `mobile-test` | Ubuntu, bun | 無 | jest |
| `e2e-test` | Ubuntu, bun + Playwright | 無 | Playwright chromium |

### 9.3 CI 缺口

| 缺口 | 說明 |
|------|------|
| 無覆蓋率上報 | 無法在 PR 中看到覆蓋率變化 |
| 無 Docker 建置驗證 | Dockerfile 變更不會被 CI 驗證 |
| 無自動部署 | 僅有建置/測試，無 CD 流程 |
| 無安全掃描 | 未整合 dependabot / CodeQL / Trivy |
| 無效能回歸 | 回測效能無基準對比 |

---

## 10. 安全機制現況

### 10.1 已實作

| 機制 | 實作方式 | 狀態 |
|------|---------|------|
| JWT 認證 | python-jose + HS256 | ✅ |
| API Key 認證 | 請求頭驗證 | ✅ |
| 角色授權 | 5 級層級 (viewer → admin) | ✅ |
| 密碼雜湊 | PBKDF2-SHA256 | ✅ |
| Token 撤銷 | `valid_after` 時間戳 | ✅ |
| 帳號鎖定 | 失敗次數限制 (預設 5 次 / 15 分鐘鎖定) | ✅ |
| 限流 | slowapi (60/min, backtest 10/min) | ✅ |
| CORS | 可配置 `QUANT_ALLOWED_ORIGINS` | ✅ |
| 審計日誌 | AuditMiddleware 記錄變更操作 | ✅ |
| 非 root 容器 | Docker appuser | ✅ |
| 安全儲存 (行動端) | Expo SecureStore | ✅ |

### 10.2 安全缺口

| 缺口 | 風險等級 | 說明 |
|------|---------|------|
| JWT 使用 HS256 | 中 | 單一密鑰，建議升級為 RS256 非對稱簽章 |
| 無 HTTPS 強制 | 高 | 生產環境需在反向代理層強制 HTTPS |
| 無 CSP 標頭 | 中 | Web 應用缺乏 Content-Security-Policy |
| 無依賴掃描 | 中 | 未整合 Dependabot 或 Snyk |
| 無 SQL 注入防護測試 | 低 | 雖使用 ORM 參數化，但無自動安全測試 |
| 無速率限制持久化 | 低 | slowapi 使用記憶體存儲，重啟後重置 |
| API Key 明文環境變數 | 低 | 建議生產環境使用 secret manager |

---

## 11. 已知缺陷與待辦事項

### 11.1 代碼中的 TODO

| 位置 | 內容 |
|------|------|
| `src/api/ws.py:80` | `TODO: market channel broadcasting requires a market data feed integration.` |

### 11.2 功能缺陷

| 編號 | 分類 | 說明 | 嚴重度 |
|------|------|------|--------|
| B-01 | WebSocket | market 頻道尚未接入即時數據源 | 中 |
| B-02 | 數據源 | `.env.example` 列出 `fubon`/`twse` 但未實作 | 低 |
| B-03 | 排程器 | 排程任務依賴 API 進程存活，無獨立 worker | 中 |

---

## 12. 功能完成度評估

### 12.1 後端功能矩陣

| 功能領域 | 子功能 | 完成度 | 備註 |
|---------|--------|--------|------|
| **回測引擎** | 單策略回測 | ✅ | |
| | 步進分析 | ✅ | |
| | 回測驗證 | ✅ | 因果性、確定性、敏感度 |
| | 績效分析 | ✅ | 40+ 指標 |
| | 報表生成 | ✅ | HTML + CSV |
| **數據源** | Yahoo Finance | ✅ | |
| | FinMind (台灣) | ✅ | 含基本面 |
| | 數據快取 | ✅ | Parquet + LRU |
| | 數據品質檢查 | ✅ | |
| | 即時行情串流 | ❌ | 未實作 |
| **策略** | 7 種預建策略 | ✅ | |
| | 因子庫 | ✅ | 技術 6 + 基本面 4 |
| | 最佳化器 | ✅ | 等權重、信號、風險平價 |
| | 因子研究基礎 | ✅ | IC/衰減/合成 |
| | 自訂策略框架 | ✅ | 插件式載入 |
| **Alpha 研究** | 股票池篩選 | ✅ | 流動性/市值/上市天數/數據完整性/產業 |
| | 因子中性化 | ✅ | 市場/行業/規模/行業+規模 |
| | 因子正交化 | ✅ | Sequential (Gram-Schmidt) + Symmetric (PCA/ZCA) |
| | 分位數組合回測 | ✅ | N 分位、多空價差、單調性分數 |
| | 換手率/交易成本 | ✅ | 成本侵蝕、盈虧平衡成本、淨 IC |
| | 成本感知組合建構 | ✅ | 換手率懲罰、最大換手率約束、衰減混合 |
| | Alpha Pipeline | ✅ | 配置驅動、完整報告、AlphaStrategy 適配器 |
| **風險管理** | 持倉/板塊限制 | ✅ | |
| | 回撤熔斷 | ✅ | 5% 日損失 |
| | 風險監控 + 規則動態切換 | ✅ | API 支援 |
| **執行** | 模擬券商 | ✅ | |
| | 真實券商對接 | ❌ | 未實作 |
| | 訂單管理 | ✅ | |
| **投資組合** | CRUD / 再平衡 / T+N / NAV | ✅ | |
| **用戶系統** | JWT + 角色 + 管理 | ✅ | 5 級 |
| **通知** | Discord / LINE / Telegram | ✅ | |
| **API** | REST (30+) + Prometheus | ✅ | |
| | WebSocket | ⚠️ | market 頻道未接入 |

### 12.2 前端功能矩陣

| 頁面 | Web | Mobile | 備註 |
|------|-----|--------|------|
| 儀表板 | ✅ | ✅ | 即時更新 (WebSocket) |
| 回測 | ✅ | ✅ | 完整回測 + 比較 + 熱力圖 |
| 投資組合 | ✅ | ✅ | CRUD + 再平衡 |
| 訂單 | ✅ | ✅ | 下單表單 + 歷史 |
| 策略 | ✅ | ✅ | 列表 + 啟停 |
| 風險 | ✅ | ✅ | 規則 + 告警 + 熔斷 |
| 設定 | ✅ | ⚠️ | Mobile 部分 |
| 管理後台 | ✅ | ❌ | 僅 Web |
| 深色/淺色模式 | ✅ | ⚠️ | Mobile 部分 |
| 國際化 | ✅ | ✅ | 英文 + 繁體中文 |
| 離線支援 | — | ✅ | 離線偵測 + 狀態提示 |

---

## 13. 差距分析

### 13.1 Alpha 研究能力 — 已完成

第一階段全部 P0/P1 項目已完成 (2026-03-24)。剩餘為 P2 擴展：

| 優先級 | 差距 | 說明 |
|--------|------|------|
| 🟢 P2 | 事件驅動 Alpha | 財報發佈、除權息、法人買賣超等事件因子 |
| 🟢 P2 | 另類數據整合 | 市場情緒、資金流向等非傳統因子 |
| 🟢 P2 | Alpha 研究前端 | IC 時序圖、分位數收益圖、因子相關矩陣等視覺化 |

### 13.2 實盤交易能力差距

| 優先級 | 差距 | 說明 |
|--------|------|------|
| 🔴 **P0** | 真實券商對接 | 僅有 SimBroker，需對接至少一家券商 API (如永豐 Shioaji) |
| 🔴 **P0** | 即時行情串流 | WebSocket market 頻道為空殼，無 real-time feed |
| 🔴 **P0** | Paper Trading 模式 | `QUANT_MODE=paper` 存在但無完整流程 |
| 🟡 **P1** | 通知事件串接 | 通知模組已建好，但未與交易/再平衡事件串接 |
| 🟡 **P1** | 排程器獨立化 | 排程任務依賴 API 進程，需獨立 worker |

### 13.3 基礎設施差距

| 優先級 | 差距 | 說明 |
|--------|------|------|
| 🟡 **P1** | 測試覆蓋率追蹤 | 無 pytest-cov / istanbul |
| 🟡 **P1** | HTTPS / TLS | 無反向代理配置 |
| 🟢 **P2** | 生產部署方案 | 無 CD 流程 (自用階段可手動) |
| 🟢 **P2** | 資料庫備份 | 無自動備份策略 |
| 🟢 **P2** | 效能監控 | Prometheus 已暴露但無 Grafana |

### 13.4 遠期商業化差距（暫不優先）

用戶引導/教學、多帳戶支援、PDF 報表、訂閱/授權管理、行動端發佈、合規文件

---

## 14. 開發路線圖

基於「先有 Alpha → 再有實盤 → 最後商業化」的策略：

### 第一階段：Alpha 研究層 ✅ 已完成 (2026-03-24)

| # | 任務 | 產出 | 狀態 |
|---|------|------|------|
| 1 | 股票池篩選框架 | `src/alpha/universe.py` | ✅ |
| 2 | 因子中性化 | `src/alpha/neutralize.py` — 4 種方法 + winsorize + standardize | ✅ |
| 3 | 分位數組合回測 | `src/alpha/cross_section.py` — QuantileResult + 多空分析 | ✅ |
| 4 | 換手率分析 | `src/alpha/turnover.py` — TurnoverResult + 成本調整 | ✅ |
| 5 | 因子正交化 | `src/alpha/orthogonalize.py` — Sequential + Symmetric | ✅ |
| 6 | 成本感知組合建構 | `src/alpha/construction.py` — 換手率懲罰 + 衰減混合 | ✅ |
| 7 | Alpha Pipeline | `src/alpha/pipeline.py` — AlphaConfig + AlphaReport | ✅ |
| 8 | AlphaStrategy 適配器 | `src/alpha/strategy.py` — 註冊至 registry | ✅ |

**測試**: 7 個測試檔，72 個測試函式，全部通過。

### 第二階段：實盤交易能力（當前目標）

| # | 任務 | 說明 |
|---|------|------|
| 9 | **券商 API 對接** | 實作 `Broker` 介面，對接永豐 Shioaji 或其他券商 |
| 10 | **即時行情串流** | 接入即時報價，填補 WebSocket market 頻道 |
| 11 | **Paper Trading** | 完整紙上交易循環：即時信號 → 模擬下單 → 損益追蹤 |
| 12 | **通知事件串接** | 將交易/再平衡/風控事件接入通知系統 |
| 13 | **HTTPS + 安全** | 反向代理、TLS 配置 |

**完成標誌**: 能用 Alpha 研究層產出的策略，透過 Paper Trading 驗證後切換到實盤執行。

### 第三階段：穩固與商業化（遠期）

| # | 任務 |
|---|------|
| 14 | 測試覆蓋率工具 |
| 15 | Alpha 研究前端 (IC 圖表、分位數可視化) |
| 16 | 多帳戶/家族管理 |
| 17 | PDF 報表、用戶引導 |
| 18 | 訂閱授權、合規、部署 |

---

> **文件維護說明**: 本報告應在每次重大功能變更、架構調整或里程碑完成後更新。
