# 多資產架構設計

> **目標**: 涵蓋台股、美股、ETF、期貨的投資組合研究與優化系統
> **不納入**: 直接債券交易（OTC）、實體商品、零售外匯
> **狀態**: Phase A~F 已實作（E1/E4 程式碼完成，待券商整合測試；F1~F4 核心完成）
> **券商**: 台股 — 永豐金 Shioaji SDK；美股 — Interactive Brokers（待實作）

---

## 1. 架構總覽

```
┌──────────────────────────────────────────────────────────────────────┐
│                       投資組合研究與交易平台                            │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │              第四層：交易執行 (src/execution/) Phase E             │ │
│  │  ExecutionService (模式路由: backtest/paper/live)                │ │
│  │  SinopacBroker (Shioaji SDK) ← → 即時行情 + 成交回報             │ │
│  │  StopOrderManager │ 交易時段管理 │ EOD 對帳                      │ │
│  └────────────────────────────┬──────────────────────────────────┘ │
│                               │                                      │
│  ┌────────────────────────────┼──────────────────────────────────┐ │
│  │              第三層：組合最佳化 (src/portfolio/) ✅                │ │
│  │  PortfolioOptimizer (14 methods: EW→HRP→CVaR→Robust→SemiVar)   │ │
│  │  RiskModel (LW/GARCH/Factor + VaR/CVaR + James-Stein)         │ │
│  │  CurrencyHedger (分級對沖)                                      │ │
│  └────────────────────────────┬──────────────────────────────────┘ │
│                               │                                      │
│  ┌────────────────────────────┼──────────────────────────────────┐ │
│  │              第二層：Alpha 信號                                   │ │
│  │  資產內 Alpha (src/alpha/) ✅    資產間 Alpha (src/allocation/) ✅│ │
│  │  16 因子 + Pipeline              宏觀四因子 + 跨資產信號          │ │
│  │  中性化/正交化/Rolling IC/建構    戰術配置引擎 + regime            │ │
│  └────────────────────────────┬──────────────────────────────────┘ │
│                               │                                      │
│  ┌────────────────────────────┼──────────────────────────────────┐ │
│  │              第一層：數據 + 標的                                   │ │
│  │  InstrumentRegistry (src/instrument/) ✅                         │ │
│  │  DataFeed: Yahoo + FinMind + FRED + Shioaji (src/data/) ✅      │ │
│  │  Scanner: 動態 universe + 處置股排除                              │ │
│  │  台股 │ 美股 │ ETF (債券/商品代理) │ 台灣期貨 │ 美國期貨          │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ╔══════════════════════════════════════════════════════════════╗   │
│  ║  基礎設施                                                      ║   │
│  ║  BacktestEngine │ RiskEngine(10規則) │ SimBroker │ API(14路由) ║   │
│  ║  Web(10頁) │ Mobile(7tabs) │ 通知 │ 排程 │ JWT/RBAC 認證      ║   │
│  ║  Auto-Alpha 閉環 (Phase F): 排程→研究→決策→執行→回饋          ║   │
│  ╚══════════════════════════════════════════════════════════════╝   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. 模組設計

### 2.1 Instrument Registry (`src/instrument/`)

統一標的模型：

```python
@dataclass(frozen=True)
class Instrument:
    symbol: str                      # "2330.TW", "ES=F", "TLT"
    asset_class: AssetClass          # EQUITY / ETF / FUTURE / OPTION
    sub_class: SubClass              # STOCK / ETF_BOND / ETF_COMMODITY / FUTURE / ...
    market: Market                   # TW / US
    currency: str                    # "TWD" / "USD"
    multiplier: Decimal              # 期貨合約乘數（股票=1）
    commission_rate: Decimal         # per-instrument 手續費
    tax_rate: Decimal                # per-instrument 稅率
```

`InstrumentRegistry.get_or_create()` 自動從 symbol pattern 推斷屬性（`.TW` → TW stock, `=F` → futures, 已知 ETF 列表）。

### 2.2 數據層 (`src/data/`)

```
sources/
├── yahoo.py      — YahooFeed (全球市場, 日線為主)
├── finmind.py    — FinMindFeed (台股, 支援基本面)
├── fred.py       — FredDataSource (宏觀經濟數據)
├── shioaji_feed.py — ShioajiFeed (台股 1 分鐘 K 棒 / tick / snapshot)
└── __init__.py   — create_feed() 工廠

scanner.py        — ShioajiScanner (動態 universe / 漲跌排行 / 處置股排除)
store.py          — ParquetDiskCache
```

**數據源選擇策略**:
| 場景 | 建議數據源 | 理由 |
|------|----------|------|
| 日線回測 | Yahoo / FinMind | 免費 + 歷史深度 |
| 分鐘級回測 | Shioaji | 2020 起 1 分鐘 K 棒 |
| 即時行情 | Shioaji tick/bidask | broker 原生 + 低延遲 |
| 宏觀因子 | FRED | 美國經濟指標 |
| 基本面 | FinMind | 台股財報/營收 |
| 動態選股 | Shioaji Scanner | 成交量/漲跌排行 |

### 2.3 戰術配置層 (`src/allocation/`)

```
macro_factors.py  → MacroSignals (growth/inflation/rates/credit z-score)
cross_asset.py    → dict[AssetClass, float] (momentum/vol/value per class)
tactical.py       → dict[AssetClass, float] (戰術權重)
```

宏觀資料頻率處理：FRED 月度/季度資料以 `.ffill(limit=66)` 前向填補。

### 2.4 組合最佳化層 (`src/portfolio/`)

```
optimizer.py   → OptimizationResult (weights + return/risk/Sharpe/RC)
risk_model.py  → 共變異數矩陣 (歷史/EWM/Ledoit-Wolf) + 風險貢獻
currency.py    → HedgeRecommendation (暴露/比例/成本)
```

### 2.5 兩層配置整合 (`src/strategy/multi_asset.py`)

MultiAssetStrategy 串接完整流程：

```
1. 分類 universe → dict[AssetClass, list[str]]
2. 跨資產信號 → dict[AssetClass, float]
3. 市場狀態 → MarketRegime
4. 戰術配置 → dict[AssetClass, float]
5. 各類別內等權/Alpha → dict[str, float]
6. 組合最佳化 (Risk Parity 等) → final weights
```

### 2.6 交易執行層 (`src/execution/`)

Phase E 新增的核心模組：

```
execution_service.py   — 模式路由 (backtest → SimBroker, paper/live → SinopacBroker)
sinopac_broker.py      — SinopacBroker(BrokerAdapter): Shioaji SDK 封裝
sinopac_quote.py       — SinopacQuoteManager: tick/bidask 訂閱 + 回調轉發
market_hours.py        — 台股交易時段 (盤前/盤中/零股/定盤) + 盤外佇列
reconcile.py           — EOD 持倉對帳 (系統 vs 券商) + 自動修正
stop_order.py          — StopOrderManager: 軟體觸價委託 (stop-loss/profit)
sim.py                 — SimBroker: 回測模擬撮合 (滑點/費率/漲跌停)
broker.py              — BrokerAdapter ABC + PaperBroker
oms.py                 — OrderManager: 訂單生命週期管理
```

**執行模式路由**:
```
config.mode = "backtest" → SimBroker (離線模擬)
config.mode = "paper"    → SinopacBroker(simulation=True) (Shioaji 模擬環境)
config.mode = "live"     → SinopacBroker(simulation=False) (實盤交易)
```

**Shioaji SDK 認證**:
```python
api = sj.Shioaji(simulation=True)
api.login(api_key="YOUR_KEY", secret_key="YOUR_SECRET")
api.activate_ca(ca_path="Sinopac.pfx", ca_passwd="PASSWORD")
```

**委託回報流程**:
```
SinopacBroker.submit_order(order)
  → api.place_order(contract, sj_order, timeout=0)  # 非阻塞 (~12ms)
    → set_order_callback(stat, msg)
      → stat == StockOrder  → 委託確認/拒絕
      → stat == StockDeal   → 成交回報 → Order 狀態更新
```

### 2.7 自動化 Alpha 閉環 (`src/alpha/auto/`)

Phase F 新增的自動化研究與執行模組：

```
config.py             — AutoAlphaConfig + DecisionConfig (排程/篩選/安全閾值)
universe.py           — UniverseSelector (Scanner × 靜態約束 × 處置股排除)
researcher.py         — AlphaResearcher (AlphaPipeline + Regime + 持久化)
decision.py           — AlphaDecisionEngine (ICIR/Hit Rate 篩選 + Regime 調適)
executor.py           — AlphaExecutor (weights→orders→risk→execution→performance)
scheduler.py          — AlphaScheduler (7 個排程 job: 08:30~13:35)
store.py              — AlphaStore (DB 持久化: ResearchSnapshot + FactorScore)
alerts.py             — AlertManager (Regime 變化 / IC 反轉 / 回撤告警)
safety.py             — SafetyChecker (回撤熔斷 5% + 連續虧損暫停 5 天)
factor_tracker.py     — FactorPerformanceTracker (累計 IC + 回撤 per factor)
dynamic_pool.py       — DynamicFactorPool (ICIR 排名自動新增/移除因子)
```

**每日流程**: Scanner → 動態 Universe → 全因子 IC → ICIR 篩選 + Regime 調適 → 目標權重 → 風控 → 自動下單 → EOD 對帳 → 歸因 → 績效通知 → 回饋下一日

---

## 3. 資料流程

### 3.1 回測模式

```
DataFeed (Yahoo/FinMind/FRED/Shioaji)
     ↓
Strategy.on_bar(ctx) → target weights: dict[str, float]
     ↓
weights_to_orders() — 含乘數、lot_size、總權重驗證
     ↓
RiskEngine — 10 規則（含 asset_class/currency/leverage）
     ↓
SimBroker — per-instrument 費率、sqrt 滑點、漲跌停
     ↓
Portfolio — 多幣別 NAV (per-bar FX rate)
```

### 3.2 Paper/Live Trading 模式

```
排程觸發 / 手動 API 呼叫
     ↓
Strategy.on_bar(ctx) → target weights
     ↓
weights_to_orders() + RiskEngine 檢查
     ↓
ExecutionService → 交易時段驗證
     ↓  (盤外 → 佇列暫存)
SinopacBroker.submit_order() [timeout=0 非阻塞]
     ↓
Shioaji 模擬/實盤環境
     ↓
成交回報 callback → Order 狀態更新 → Portfolio 同步
     ↓
EOD reconcile() → 對帳 → auto_correct() → 通知
```

### 3.3 即時行情流程

```
SinopacQuoteManager.subscribe("2330", "tick")
     ↓
Shioaji SDK tick callback (背景執行緒)
     ↓
TickData 標準化 → StopOrderManager.on_tick() 檢查觸價
     ↓
WebSocket broadcast("market", payload) → 前端即時更新
```

### 層間資料契約

| 步驟 | 輸出型別 |
|------|---------|
| 戰術配置 | `dict[AssetClass, float]`（sum ≈ 1.0） |
| 資產內選標 | `dict[str, float]`（各 symbol 權重） |
| 組合最佳化 | `OptimizationResult.weights: dict[str, float]` |
| 最終 | `weights_to_orders() → list[Order]` |
| 執行 | `ExecutionService.submit_orders() → list[Trade]` |
| 對帳 | `reconcile() → ReconcileResult` |

---

## 4. 風控架構

| 規則 | 層級 | 說明 |
|------|------|------|
| max_position_weight | 個股 | 單一標的權重上限 |
| max_order_notional | 個股 | 單筆金額上限 |
| fat_finger | 個股 | 價格偏離檢查 |
| daily_drawdown | 組合 | 日回撤上限 |
| max_daily_trades | 組合 | 交易次數上限 |
| max_order_vs_adv | 個股 | 流動性限制 |
| price_circuit_breaker | 個股 | 價格熔斷 |
| **max_asset_class_weight** | **跨資產** | 資產類別權重上限 |
| **max_currency_exposure** | **跨資產** | 幣別暴露上限 |
| **max_gross_leverage** | **跨資產** | 總槓桿上限 |

### 4.1 執行層風控（Phase E 新增）

| 機制 | 說明 |
|------|------|
| 交易時段驗證 | 盤外自動佇列，開盤送出 |
| 交易額度預檢 | `api.trading_limits()` 可用額度 vs 委託金額 |
| 處置股排除 | `api.punish()` 自動排除受限標的 |
| 注意股警告 | `api.notice()` 產生告警但不阻擋 |
| Kill switch | stop order → 即時平倉（tick callback 觸發） |
| Kill switch 恢復 | 3 天冷靜期 → 50%~100% 漸進恢復（5 天 ramp） |
| 回測閘門 | auto-alpha 須通過近 60 天 lookback 回測方可執行 |
| EOD 對帳 | `reconcile()` 比對 → 差異告警 → 可選自動修正 |

---

## 5. 委託模型

### 5.1 Order 擴展

```python
@dataclass
class Order:
    instrument: Instrument
    side: Side                           # BUY / SELL
    order_type: OrderType                # MARKET / LIMIT
    quantity: Decimal
    price: Decimal | None
    status: OrderStatus                  # PENDING → SUBMITTED → FILLED/CANCELLED/REJECTED
    order_cond: OrderCondition = CASH    # CASH / MARGIN_TRADING / SHORT_SELLING / DAY_TRADE
    order_lot: StockOrderLot = COMMON    # COMMON / INTRADAY_ODD / ODD / FIXING
    ...
```

### 5.2 委託映射（Order → Shioaji）

| 本專案 | Shioaji 常數 |
|--------|-------------|
| `OrderType.MARKET` | `sj.constant.StockPriceType.MKT` |
| `OrderType.LIMIT` | `sj.constant.StockPriceType.LMT` |
| `Side.BUY / SELL` | `sj.constant.Action.Buy / Sell` |
| `OrderCondition.CASH` | `sj.constant.StockOrderCond.Cash` |
| `OrderCondition.MARGIN_TRADING` | `sj.constant.StockOrderCond.MarginTrading` |
| `OrderCondition.SHORT_SELLING` | `sj.constant.StockOrderCond.ShortSelling` |
| `StockOrderLot.COMMON` | `sj.constant.StockOrderLot.Common` |
| `StockOrderLot.INTRADAY_ODD` | `sj.constant.StockOrderLot.IntradayOdd` |
| ROD/IOC/FOK | `sj.constant.OrderType.ROD/IOC/FOK` |

### 5.3 交易時段

| 時段 | 時間 (台灣) | 撮合方式 | StockOrderLot |
|------|------------|---------|---------------|
| 盤前試撮 | 08:30–09:00 | 僅接受委託 | Common |
| 盤中交易 | 09:00–13:25 | 逐筆撮合 | Common |
| 盤中零股 | 09:10–13:30 | 3 分鐘集合競價 | IntradayOdd |
| 收盤定價 | 13:40–14:30 | 收盤價撮合 | Fixing |
| 盤後零股 | 13:40–14:30 | 集合競價 | Odd |

---

## 6. 前端架構

| 頁面 | 路由 | 功能 |
|------|------|------|
| Dashboard | `/` | NAV/持倉/即時 |
| Portfolio | `/portfolio` | CRUD + 再平衡預覽 |
| Strategies | `/strategies` | 9 策略列表 + 啟停 |
| Orders | `/orders` | 下單 + 歷史 |
| Backtest | `/backtest` | 回測 + 比較 + 月報 |
| Alpha | `/alpha` | 因子研究 (16 因子) |
| Allocation | `/allocation` | 戰術配置計算 + 視覺化 |
| Risk | `/risk` | 10 規則 + 告警 + kill switch |
| Settings | `/settings` | API key + 語言 + 主題 |
| Admin | `/admin` | 用戶管理 + 審計 |

---

## 7. API 架構

### 7.1 REST 端點（14 路由模組, 68 端點）

| 模組 | 端點數 | 說明 |
|------|--------|------|
| auth | 2 | 登入 + 註冊 |
| admin | 3 | 用戶管理 + 審計 |
| portfolio | 5 | CRUD + 再平衡 + 交易歷史 |
| strategies | 2 | 策略列表 + 啟停 |
| orders | 2 | 下單 + 歷史 |
| backtest | 2 | 回測 + Walk-forward |
| risk | 2 | 規則狀態 + Kill switch |
| alpha | 2 | Alpha 研究 + 因子查詢 |
| allocation | 1 | 戰術配置 |
| execution | 6 | 執行狀態 + 交易時段 + 對帳 + Paper trading |
| auto_alpha | 10 | 自動 Alpha: config/start/stop/status/history/performance/alerts/run-now |
| system | 1 | 健康檢查 |

### 7.2 WebSocket 頻道

| 頻道 | 說明 | 數據來源 |
|------|------|---------|
| `portfolio` | 持倉 + NAV 更新 | 策略執行後推送 |
| `orders` | 訂單狀態變更 | OMS / 成交回報 |
| `alerts` | 風控告警 | RiskEngine / RiskMonitor |
| `market` | 即時行情 | SinopacQuoteManager → tick → broadcast |

---

## 8. 目錄結構

```
src/                          ~120 .py files
├── alpha/           ✅ 23 files — Alpha 研究 (14 因子 + Pipeline + regime + attribution) + auto/ (11 files: 自動化 Alpha 閉環)
├── allocation/      ✅  4 files — 戰術配置 (宏觀 + 跨資產 + 戰術)
├── portfolio/       ✅  4 files — 組合最佳化 (6 法 + LW + 對沖)
├── strategy/        ✅  8 files — 9 策略 + 因子庫 + MultiAssetStrategy
├── backtest/        ✅  6 files — 回測引擎 (多幣別 + FX 時序)
├── risk/            ✅  4 files — 10 規則 + kill switch
├── execution/       ✅ 10 files — SinopacBroker + ExecutionService + 對帳 + 觸價
├── data/            ✅ 15 files — Yahoo + FinMind + FRED + Shioaji + Scanner
├── instrument/      ✅  3 files — Registry + 自動推斷
├── domain/          ✅  3 files — 統一模型 (Order 含融資融券/零股欄位)
├── api/             ✅ 22 files — REST(14 路由) + WS + Auth + Middleware
├── cli/             ✅  2 files — backtest/server/status/factors
├── notifications/   ✅  6 files — Discord/LINE/Telegram
└── scheduler/       ✅  2 files — APScheduler

strategies/           7 files — 7 個內建策略
tests/               63 files — pytest (856 tests)
apps/web/                     — React 18 + Vite + Tailwind (10 頁)
apps/mobile/                  — React Native + Expo 52 (7 tabs)
apps/shared/                  — @quant/shared TypeScript 套件
```

---

## 9. 配置體系

所有配置透過 `QUANT_` 前綴環境變數或 `.env` 檔案設定。

### 9.1 Shioaji 券商配置（Phase E 新增）

| 環境變數 | 說明 | 預設 |
|---------|------|------|
| `QUANT_SINOPAC_API_KEY` | Shioaji API Key | `""` |
| `QUANT_SINOPAC_SECRET_KEY` | Shioaji Secret Key | `""` |
| `QUANT_SINOPAC_CA_PATH` | CA 憑證路徑 (.pfx) | `""` |
| `QUANT_SINOPAC_CA_PASSWORD` | CA 憑證密碼 | `""` |
| `QUANT_MODE` | 運行模式 | `"backtest"` |

### 9.2 模式切換

```
QUANT_MODE=backtest  → SimBroker (離線，無需任何券商配置)
QUANT_MODE=paper     → SinopacBroker(simulation=True) (需 API key + CA)
QUANT_MODE=live      → SinopacBroker(simulation=False) (需 API key + CA + 正式環境)
```
