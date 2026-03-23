# 開發計畫書 v2.0

**日期**: 2026-03-24
**目標**: 從「回測研究平台」進化為「個人可用的投資輔助工具」
**資料源決策**: FinMind（免費，未來可擴充 EODHD/TEJ）
**參考文件**: `PERSONAL_USE_GAP_REPORT.md`, `PLAN_VS_REALITY.md`, `DATA_SOURCE_EVALUATION.md`

---

## 總覽

```
Phase 0  回測可信度修復        ─── 不被假數字誤導
Phase 1  FinMind 整合          ─── 台股基本面 + 產業分類
Phase 2  回測引擎強化          ─── 台股市場模擬 + 測試補全
Phase 3  實用化基礎設施        ─── 持久化 + 建議交易 + 通知
Phase 4  進階功能              ─── 績效追蹤 + 排程 + 多組合
```

完成 Phase 0-1 後，回測結果可信且支援基本面策略。
完成 Phase 0-3 後，系統可每月產生交易建議、推播通知、追蹤持倉。

---

## Phase 0 — 回測可信度修復

> **目的**: 目前回測報酬偏高 3-10%，修復後結果才可信。

### 0-1. 次日開盤價成交

**問題**: 策略在 Day N 收盤價計算訊號，卻在 Day N 收盤價成交。現實中最快 Day N+1 開盤才能交易。

**變更**:

| 檔案 | 修改 |
|------|------|
| `src/backtest/engine.py` | `BacktestConfig` 加 `execution_delay: int = 1`（預設次日成交） |
| `src/backtest/engine.py` | 主迴圈改為：Day N 產生訊號 → 暫存 `pending_orders` → Day N+1 用開盤價執行 |
| `src/execution/sim.py` | `SimBroker.execute()` 支援以 `open` 價為基準成交（新增 `fill_on: Literal["close", "open"]` 參數） |
| `src/backtest/engine.py` | `_build_matrices()` 額外建立 `_open_matrix` |
| `tests/unit/test_backtest_engine.py` | 驗證延遲 1 日 vs 0 日的結果差異 |

**設計細節**:

```python
# engine.py 主迴圈（概念）
pending_orders: list[Order] = []

for i, bar_date in enumerate(trading_dates):
    # 1. 先執行前一日的 pending orders（用今日開盤價）
    if pending_orders:
        open_prices = self._get_open_prices(universe, bar_date)
        trades = sim_broker.execute(pending_orders, open_bars, bar_date)
        portfolio = apply_trades(portfolio, trades)
        pending_orders = []

    # 2. 再算今日訊號
    if self._is_rebalance_day(bar_date, i, config.rebalance_freq):
        target_weights = strategy.on_bar(ctx)
        orders = weights_to_orders(target_weights, portfolio, prices)
        approved = risk_engine.check_orders(orders, portfolio, market_state)
        if config.execution_delay == 0:
            trades = sim_broker.execute(approved, close_bars, bar_date)
            portfolio = apply_trades(portfolio, trades)
        else:
            pending_orders = approved  # 延遲到次日
```

### 0-2. 滑價模型升級

**問題**: 固定 5bps 滑價不考慮訂單大小。大單實際滑價可達 20-50bps。

**變更**:

| 檔案 | 修改 |
|------|------|
| `src/execution/sim.py` | `SimConfig` 加 `impact_model: Literal["fixed", "sqrt"] = "sqrt"` |
| `src/execution/sim.py` | `SimBroker.execute()` 新增 `_calc_slippage()` 方法 |
| `tests/unit/test_sim_broker.py` | 新增滑價模型測試（固定 vs sqrt） |

**滑價公式** (square-root impact model):

```
slippage_bps = base_bps + impact_coeff × sqrt(order_qty / adv)
```

- `base_bps`: 基礎滑價（預設 2bps）
- `impact_coeff`: 衝擊係數（預設 50）
- `adv`: 20 日平均日成交量
- 小單（< 1% ADV）幾乎等於 base_bps
- 大單（10% ADV）約 2 + 50 × sqrt(0.1) ≈ 18bps

### 0-3. Kill Switch 串接回測

**問題**: `RiskEngine.kill_switch()` 存在但回測主迴圈從未呼叫。

**變更**:

| 檔案 | 修改 |
|------|------|
| `src/backtest/engine.py` | 主迴圈每日 NAV 更新後呼叫 `risk_engine.kill_switch(portfolio)` |
| `src/backtest/engine.py` | Kill switch 觸發 → 清空所有持倉（市價全賣）→ 停止交易直到月底 |
| `src/backtest/engine.py` | `BacktestConfig` 加 `enable_kill_switch: bool = True` |
| `tests/unit/test_backtest_engine.py` | 驗證 > 5% 日跌時觸發熔斷 |

### 0-4. 拒單記錄與報告

**問題**: SimBroker 拒絕訂單時只設 `REJECTED` 狀態，不記錄也不反映在結果中。

**變更**:

| 檔案 | 修改 |
|------|------|
| `src/execution/sim.py` | `SimBroker` 加 `rejected_log: list[Order]`，拒單時記錄 |
| `src/backtest/analytics.py` | `BacktestResult` 加 `rejected_orders: int`、`rejected_notional: float` |
| `src/backtest/engine.py` | 將 `sim_broker.rejected_log` 傳入 `compute_analytics()` |

### 0-5. 成交量為零不可交易

**問題**: 成交量為 0 的日期仍允許交易（停牌股）。

**變更**:

| 檔案 | 修改 |
|------|------|
| `src/execution/sim.py` | `execute()` 中 `volume == 0` → REJECT（新增檢查） |

---

## Phase 1 — FinMind 整合

> **目的**: 解決 `multi_factor` 缺基本面、`sector_rotation` 缺產業分類的問題。

### 1-1. FinMind 資料源（OHLCV）

**新增** `src/data/sources/finmind.py`:

```python
class FinMindFeed(DataFeed):
    """FinMind 台股數據源。支援日 OHLCV + 基本面查詢。"""

    def __init__(self, universe: list[str], token: str = ""):
        self._dl = DataLoader()
        if token:
            self._dl.login_by_token(api_token=token)
        ...

    def get_bars(self, symbol, start, end, freq="1d") -> pd.DataFrame:
        # FinMind 的 taiwan_stock_daily → 轉換為標準 OHLCV DataFrame
        ...

    def get_latest_price(self, symbol) -> Decimal:
        ...

    def get_universe(self) -> list[str]:
        ...
```

| 檔案 | 修改 |
|------|------|
| `src/data/sources/finmind.py` | 新增 `FinMindFeed` 實作 `DataFeed` ABC |
| `src/config.py` | `data_source` 加 `"finmind"` 選項；新增 `finmind_token: str = ""` |
| `pyproject.toml` | 加 `FinMind` 依賴 |
| `tests/unit/test_finmind_feed.py` | Mock DataLoader 測試欄位轉換、快取、錯誤處理 |

**FinMind 欄位對照**:

| FinMind 欄位 | 標準化 |
|-------------|--------|
| `date` | DatetimeIndex |
| `open` | `open` |
| `max` | `high` |
| `min` | `low` |
| `close` | `close` |
| `Trading_Volume` | `volume` |

### 1-2. 基本面資料介面

**新增** `src/data/fundamentals.py`:

```python
class FundamentalsProvider(ABC):
    """基本面數據的統一介面。"""

    @abstractmethod
    def get_financials(self, symbol: str, date: str | None = None) -> dict:
        """取得財報數據。回傳: {pe_ratio, pb_ratio, roe, eps, ...}"""

    @abstractmethod
    def get_sector(self, symbol: str) -> str:
        """取得產業分類。"""

    @abstractmethod
    def get_revenue(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """取得月營收歷史。"""

    @abstractmethod
    def get_institutional_investors(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """取得法人買賣超。"""
```

### 1-3. FinMind 基本面實作

**新增** `src/data/sources/finmind_fundamentals.py`:

| API 呼叫 | 用途 | FinMind dataset |
|----------|------|----------------|
| 財報三表 | P/E、P/B、ROE、EPS | `TaiwanStockFinancialStatement` |
| 月營收 | 營收成長率 | `TaiwanStockMonthRevenue` |
| 法人買賣超 | 資金流向因子 | `TaiwanStockInstitutionalInvestorsBuySell` |
| 產業分類 | sector_rotation | `TaiwanStockInfo` |
| 股利歷史 | 殖利率因子 | `TaiwanStockDividend` |
| PER/PBR 日頻 | 估值因子 | `TaiwanStockPER` |

**快取策略**: 基本面數據更新頻率低（季報/月營收），使用 Parquet 磁碟快取 + 7 天 TTL。

| 檔案 | 修改 |
|------|------|
| `src/data/fundamentals.py` | 新增 ABC |
| `src/data/sources/finmind_fundamentals.py` | 新增 `FinMindFundamentals` 實作 |
| `tests/unit/test_finmind_fundamentals.py` | Mock API 測試各查詢 |

### 1-4. 策略升級：真實基本面因子

**改造** `multi_factor` 和 `sector_rotation`:

| 檔案 | 修改 |
|------|------|
| `src/strategy/base.py` | `Context` 新增 `fundamentals(symbol) -> dict` 和 `sector(symbol) -> str` 方法 |
| `src/strategy/base.py` | `Context.__init__` 接受可選 `fundamentals_provider: FundamentalsProvider` |
| `src/backtest/engine.py` | 初始化 `FundamentalsProvider` 並傳入 `Context` |
| `strategies/multi_factor.py` | 加入真實 P/E、P/B、ROE 因子（取代純技術因子代理） |
| `strategies/sector_rotation.py` | 加入產業分類功能，支援按產業輪動 |
| `src/strategy/factors.py` | 新增 `value_pe()`, `value_pb()`, `quality_roe()` 基本面因子函式 |

**multi_factor 改造前後對比**:

```python
# 之前（純技術因子代理 value）
value_score = -z_score  # 用價格均值回歸代替估值

# 之後（真實基本面）
fundamentals = ctx.fundamentals(symbol)
if fundamentals:
    pe_score = -fundamentals.get("pe_ratio", 0)   # 低 PE 高分
    pb_score = -fundamentals.get("pb_ratio", 0)    # 低 PB 高分
    roe_score = fundamentals.get("roe", 0)         # 高 ROE 高分
    value_score = normalize(pe_score * 0.4 + pb_score * 0.3 + roe_score * 0.3)
```

### 1-5. 資料源切換機制

| 檔案 | 修改 |
|------|------|
| `src/data/sources/__init__.py` | 新增 `create_feed(source: str, universe: list[str]) -> DataFeed` 工廠函式 |
| `src/backtest/engine.py` | `_load_data()` 改用工廠，根據 `config.data_source` 自動選源 |
| `src/config.py` | `data_source` 加 `"finmind"` |

```python
# src/data/sources/__init__.py
def create_feed(source: str, universe: list[str], **kwargs) -> DataFeed:
    if source == "yahoo":
        return YahooFeed(universe)
    elif source == "finmind":
        from src.data.sources.finmind import FinMindFeed
        return FinMindFeed(universe, token=kwargs.get("token", ""))
    else:
        raise ValueError(f"Unknown data source: {source}")
```

---

## Phase 2 — 回測引擎強化

> **目的**: 台股市場模擬 + 測試覆蓋 + 回測品質驗證。

### 2-1. 回測引擎單元測試

**問題**: 引擎核心邏輯目前只有間接測試（ffill、dividends），缺少直接測試。

**新增** `tests/unit/test_backtest_engine.py`:

| 測試 | 驗證內容 |
|------|---------|
| `test_basic_run_produces_result` | 基本回測流程跑完，結果結構正確 |
| `test_nav_starts_at_initial_cash` | 第一日 NAV = initial_cash |
| `test_rebalance_freq_daily` | 每日再平衡都觸發策略 |
| `test_rebalance_freq_monthly` | 月頻率只在月初觸發 |
| `test_suspect_dates_skipped` | 品質可疑日不交易 |
| `test_commission_and_tax_deducted` | 手續費+交易稅從 cash 扣除 |
| `test_execution_delay_one_day` | 次日成交（Phase 0-1 完成後） |
| `test_kill_switch_stops_trading` | 熔斷後停止交易（Phase 0-3 完成後） |
| `test_empty_universe_raises` | 空標的池拋出 ValueError |
| `test_deterministic_same_result` | 相同輸入 → 相同輸出 |

### 2-2. 回測品質驗證模組

**新增** `src/backtest/validation.py`（原規劃中有但未實作）:

| 功能 | 說明 |
|------|------|
| `check_causality()` | 打亂時間軸跑回測 → 結果應不同（驗證沒有未來資料洩漏） |
| `check_determinism()` | 同參數跑兩次 → 結果完全相同 |
| `check_sensitivity()` | 微調滑價 ±50% → 結果不應崩潰（穩健性） |

### 2-3. 台股整股交易單位

**問題**: `lot_size` 預設 1，但台股整張 = 1000 股。

**變更**:

| 檔案 | 修改 |
|------|------|
| `src/domain/models.py` | `Instrument` 加 `market: str = ""` 欄位 |
| `src/strategy/engine.py` | `weights_to_orders()` 根據 symbol 後綴（`.TW`/`.TWO`）自動設 `lot_size=1000` |
| `src/config.py` | 新增 `tw_lot_size: int = 1000`（可配置，支援零股模式設 1） |
| `tests/unit/test_weights_to_orders.py` | 測試台股取整行為 |

**邏輯**:

```python
# 根據 symbol 判斷市場
if symbol.endswith(('.TW', '.TWO')):
    lot_size = config.tw_lot_size  # 預設 1000（整張）
else:
    lot_size = 1  # 美股 1 股
```

### 2-4. 台股漲跌幅限制模擬

**問題**: 回測中股票可以無限漲跌，但台股有 ±10% 限制。

**變更**:

| 檔案 | 修改 |
|------|------|
| `src/execution/sim.py` | `SimConfig` 加 `price_limit_pct: float = 0.0`（0 = 不限制） |
| `src/execution/sim.py` | `execute()` 中加漲跌停檢查：成交價超出限制 → REJECT |
| `src/config.py` | 新增 `tw_price_limit_pct: float = 0.10` |

### 2-5. T+2 交割模擬

**問題**: 回測中同一筆現金當日可反覆使用，實際需 T+2 才可用。

**變更**:

| 檔案 | 修改 |
|------|------|
| `src/domain/models.py` | `Portfolio` 加 `settled_cash: Decimal`、`pending_settlements: list` |
| `src/backtest/engine.py` | 每日開始前結算到期的 pending → settled_cash |
| `src/strategy/engine.py` | `weights_to_orders()` 用 `settled_cash` 而非 `cash` 計算可用金額 |
| `src/backtest/engine.py` | `BacktestConfig` 加 `settlement_days: int = 0`（0 = 不模擬） |

---

## Phase 3 — 實用化基礎設施

> **目的**: 讓系統能真正管理投資組合，不只是跑回測。

### 3-1. Portfolio 持久化

**問題**: 重啟伺服器 = 所有持倉歸零。

**變更**:

| 檔案 | 修改 |
|------|------|
| `migrations/versions/004_portfolio_persistence.py` | 新增 `portfolios` + `position_snapshots` 表 |
| `src/domain/repository.py` | 新增 `PortfolioRepository`（CRUD） |
| `src/api/app.py` | 啟動時從 DB 載入 Portfolio |
| `src/api/routes/portfolio.py` | 修改為讀寫 DB |

**Schema**:

```sql
CREATE TABLE portfolios (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    cash DECIMAL NOT NULL,
    initial_cash DECIMAL NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE position_snapshots (
    id SERIAL PRIMARY KEY,
    portfolio_id TEXT REFERENCES portfolios(id),
    symbol TEXT NOT NULL,
    quantity DECIMAL NOT NULL,
    avg_cost DECIMAL NOT NULL,
    market_price DECIMAL NOT NULL,
    snapshot_date DATE NOT NULL,
    UNIQUE (portfolio_id, symbol, snapshot_date)
);
```

### 3-2. 「建議交易」API

**目的**: 輸入「目前持倉 + 策略」→ 輸出「該買什麼、賣什麼」。

| 檔案 | 修改 |
|------|------|
| `src/api/routes/portfolio.py` | `POST /api/v1/portfolio/{id}/rebalance-preview` |
| `src/api/schemas.py` | `RebalancePreviewRequest`、`RebalancePreviewResponse` |

**Response 格式**:

```json
{
  "strategy": "momentum",
  "target_weights": {"2330.TW": 0.20, "2317.TW": 0.15},
  "current_weights": {"2330.TW": 0.18, "2454.TW": 0.12},
  "suggested_trades": [
    {"symbol": "2330.TW", "side": "BUY", "quantity": 2000, "est_cost": 140000},
    {"symbol": "2454.TW", "side": "SELL", "quantity": 3000, "est_proceeds": 45000},
    {"symbol": "2317.TW", "side": "BUY", "quantity": 5000, "est_cost": 75000}
  ],
  "estimated_commission": 3500,
  "estimated_tax": 1350
}
```

### 3-3. 交易通知（Telegram Bot）

**目的**: 策略產生建議時推播到手機。

| 檔案 | 修改 |
|------|------|
| `src/notifications/__init__.py` | `NotificationProvider` ABC |
| `src/notifications/telegram.py` | `TelegramNotifier`（用 `python-telegram-bot`） |
| `src/config.py` | `telegram_bot_token: str = ""`、`telegram_chat_id: str = ""` |
| `pyproject.toml` | 加 `python-telegram-bot` 依賴 |

**通知格式**:

```
📊 動量策略 月度再平衡建議
━━━━━━━━━━━━━━━━━━━━━
🟢 買進 台積電(2330) 2張 ≈$140,000
🟢 買進 鴻海(2317) 5張 ≈$75,000
🔴 賣出 聯發科(2454) 3張 ≈$45,000
━━━━━━━━━━━━━━━━━━━━━
預估手續費: $3,500 | 交易稅: $1,350
```

### 3-4. 策略排程

**目的**: 每月自動跑策略、產生建議、推播通知。

| 檔案 | 修改 |
|------|------|
| `src/scheduler/__init__.py` | `SchedulerService`（基於 APScheduler） |
| `src/scheduler/jobs.py` | `rebalance_job()` — 跑策略 → 產生建議 → 發通知 |
| `src/api/app.py` | 啟動時初始化 scheduler |
| `src/config.py` | `scheduler_enabled: bool = False`、`rebalance_cron: str = "0 9 1 * *"`（每月1日 09:00） |
| `pyproject.toml` | 加 `apscheduler` 依賴 |

---

## Phase 4 — 進階功能

> **目的**: 提升使用體驗，接近半自動化投資。

### 4-1. 多投資組合

- `Portfolio` 加 ID，支援多組合 CRUD
- API: `GET/POST/DELETE /api/v1/portfolios`
- 每個組合可綁定不同策略和參數

### 4-2. 實際績效追蹤

- 新增 `actual_trades` 表：記錄在券商實際執行的交易
- 手動輸入 API: `POST /api/v1/portfolio/{id}/actual-trades`
- 績效比較: 回測建議 vs 實際執行的差異分析

### 4-3. 手動交易記錄

- Web UI: 在 OrdersPage 新增「記錄已執行交易」功能
- Mobile: OrderForm 增加「記錄模式」（記錄已完成的交易，非下新單）

### 4-4. 券商 API 介接（Fugle）

- 新增 `src/execution/fugle.py` 實作 `BrokerAdapter`
- 支援查詢持倉、下單、撤單
- 需要 Fugle 交易 API 帳戶

---

## 依賴關係

```
Phase 0-1 (次日成交) ──┐
Phase 0-2 (滑價升級) ──┤
Phase 0-3 (Kill Switch)┼── Phase 2-1 (引擎測試，需先有 0-1/0-3 才能測)
Phase 0-4 (拒單記錄) ──┤
Phase 0-5 (零量檢查) ──┘

Phase 1-1 (FinMind Feed) ──→ Phase 1-5 (切換機制)
Phase 1-2 (基本面 ABC) ───→ Phase 1-3 (FinMind 基本面)
Phase 1-3 ─────────────────→ Phase 1-4 (策略升級)

Phase 2-3 (整股單位) ──┐
Phase 2-4 (漲跌幅)  ──┼── 獨立，可平行
Phase 2-5 (T+2)     ──┘

Phase 3-1 (持久化) ───→ Phase 3-2 (建議交易 API)
Phase 3-2 ────────────→ Phase 3-3 (通知)
Phase 3-2 + 3-3 ──────→ Phase 3-4 (排程)

Phase 3-1 ────────────→ Phase 4-1 (多組合)
Phase 3-1 ────────────→ Phase 4-2 (績效追蹤)
```

---

## 新增依賴

| 套件 | Phase | 用途 |
|------|:-----:|------|
| `FinMind` | 1 | 台股數據 + 基本面 |
| `python-telegram-bot` | 3 | 通知推播 |
| `apscheduler` | 3 | 策略排程 |

---

## 新增 / 修改檔案清單

### Phase 0

| 動作 | 檔案 |
|:----:|------|
| 改 | `src/backtest/engine.py` — 次日成交、kill switch、拒單、成交量零 |
| 改 | `src/execution/sim.py` — 滑價模型、開盤價成交、漲跌幅、零量 |
| 改 | `src/backtest/analytics.py` — 拒單統計 |
| 新 | `tests/unit/test_sim_broker.py` — 滑價模型測試 |

### Phase 1

| 動作 | 檔案 |
|:----:|------|
| 新 | `src/data/sources/finmind.py` — FinMind OHLCV Feed |
| 新 | `src/data/fundamentals.py` — 基本面 ABC |
| 新 | `src/data/sources/finmind_fundamentals.py` — FinMind 基本面實作 |
| 改 | `src/data/sources/__init__.py` — 工廠函式 |
| 改 | `src/strategy/base.py` — Context 加 fundamentals |
| 改 | `src/config.py` — finmind 配置 |
| 改 | `strategies/multi_factor.py` — 真實基本面因子 |
| 改 | `strategies/sector_rotation.py` — 產業分類 |
| 改 | `src/strategy/factors.py` — 基本面因子函式 |
| 新 | `tests/unit/test_finmind_feed.py` |
| 新 | `tests/unit/test_finmind_fundamentals.py` |

### Phase 2

| 動作 | 檔案 |
|:----:|------|
| 新 | `tests/unit/test_backtest_engine.py` — 引擎核心測試 |
| 新 | `src/backtest/validation.py` — 因果性/確定性/穩健性檢查 |
| 改 | `src/domain/models.py` — lot_size 邏輯、settled_cash |
| 改 | `src/strategy/engine.py` — 台股整股取整 |

### Phase 3

| 動作 | 檔案 |
|:----:|------|
| 新 | `migrations/versions/004_portfolio_persistence.py` |
| 新 | `src/domain/repository.py` |
| 新 | `src/notifications/telegram.py` |
| 新 | `src/scheduler/jobs.py` |
| 改 | `src/api/routes/portfolio.py` — 建議交易 API |
| 改 | `src/api/schemas.py` — 新 schemas |
| 改 | `src/api/app.py` — 啟動載入 + scheduler |

---

## 測試計畫

| Phase | 新增測試檔 | 預估測試數 |
|:-----:|-----------|:---------:|
| 0 | `test_sim_broker.py`, `test_backtest_engine.py`（部分） | ~15 |
| 1 | `test_finmind_feed.py`, `test_finmind_fundamentals.py` | ~12 |
| 2 | `test_backtest_engine.py`（完整）, `test_validation.py`, `test_weights_to_orders.py` | ~20 |
| 3 | `test_repository.py`, `test_telegram.py`, `test_scheduler.py` | ~12 |
| **合計** | | **~59** |

---

## 執行順序建議

```
1. Phase 0 全部（獨立，可全部平行開發）
2. Phase 1-1 ~ 1-3（FinMind 基礎整合）
3. Phase 2-1（引擎測試，依賴 Phase 0 完成）
4. Phase 1-4 ~ 1-5（策略升級 + 切換機制）
5. Phase 2-2 ~ 2-5（台股模擬 + 驗證，獨立可平行）
6. Phase 3-1 → 3-2 → 3-3 → 3-4（串行依賴）
7. Phase 4（按需求）
```

---

## 里程碑

| 里程碑 | 完成條件 | 效果 |
|--------|---------|------|
| **M1: 可信回測** | Phase 0 全部 | 回測報酬不再虛高，有 kill switch 保護 |
| **M2: 基本面策略** | Phase 1 全部 | multi_factor 用真實 P/E、P/B、ROE；sector_rotation 用真實產業分類 |
| **M3: 台股精確模擬** | Phase 2 全部 | 整股交易、漲跌停、T+2、引擎測試 100% |
| **M4: 投資輔助工具** | Phase 3 全部 | 系統每月推播交易建議到 Telegram，持倉持久化 |
| **M5: 半自動化** | Phase 4 全部 | 多組合、績效追蹤、券商介接 |
