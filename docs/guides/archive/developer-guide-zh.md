# 量化交易系統 — 開發者指南

## 1. 架構概覽

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│  DataFeed   │────>│   Strategy   │────>│ RiskEngine  │────>│  SimBroker   │
│  (數據層)    │     │ (on_bar →    │     │  (盤前風控   │     │  (撮合模擬)   │
│             │     │  目標權重)    │     │   檢查)     │     │              │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
                          │                                        │
                    ┌─────┴─────┐                           ┌──────┴──────┐
                    │  Context  │                           │ apply_trades│
                    │ (因果性    │                           │ (更新持倉)   │
                    │  屏障)    │                           │             │
                    └───────────┘                           └─────────────┘
```

**數據流：** DataFeed → Strategy.on_bar(ctx) → 目標權重 dict → weights_to_orders() → RiskEngine.check_orders() → SimBroker.execute() → apply_trades() → Portfolio 更新

**設計原則：**
- 策略回傳目標權重 dict（`dict[str, float]`），不是訂單
- 風控規則是純函式工廠 — 不需要繼承
- 所有金額使用 `Decimal`，不使用 `float`
- 時間因果性在 Context 層強制執行（回測數據截斷至當前模擬時間）
- 全系統統一使用 tz-naive UTC（所有 DatetimeIndex 在載入時即正規化）

### 技術棧

| 類別 | 技術 |
|------|------|
| 語言/執行 | Python 3.12+ |
| API 框架 | FastAPI 0.110+、Uvicorn 0.27+、WebSockets |
| 資料處理 | Pandas 2.0+、NumPy 1.26+、yfinance |
| 資料庫 | PostgreSQL、SQLAlchemy 2.0+、Alembic |
| 最佳化 | cvxpy 1.4+、scipy 1.12+ |
| 認證 | JWT（python-jose）、API Key |
| CLI | Typer + Rich |
| 測試 | pytest 8.0+、pytest-asyncio、httpx |
| Web 前端 | React 18 + Vite + Tailwind CSS |
| Mobile 前端 | React Native 0.76 + Expo 52 + Expo Router 4 |
| Android 原生 | Kotlin + Jetpack Compose + Material 3 + Hilt DI |
| 前端共享 | `@quant/shared`（TypeScript 型別、API client、WS manager） |

## 2. 專案結構

```
src/
├── core/                     # 核心模組（canonical 位置）
│   ├── models.py             # 統一型別：Instrument, Bar, Position, Order, Portfolio, Trade, enums
│   ├── config.py             # Pydantic Settings，QUANT_ 前綴環境變數
│   ├── logging.py            # structlog 結構化日誌
│   ├── repository.py         # 資料庫存取層
│   ├── calendar.py           # TWTradingCalendar（台股交易日曆含國定假日）
│   └── trading_pipeline.py   # execute_one_bar()（回測/實盤共用交易流程）
├── instrument/               # InstrumentRegistry（get/search/by_market/by_asset_class）
├── alpha/                    # Alpha 研究層（within-asset 選股）
│   ├── pipeline.py           # 端到端流程：universe → factor → neutralization → composite → quantile backtest
│   ├── strategy.py           # AlphaStrategy adapter（包裝 pipeline 為 Strategy）
│   ├── filter_strategy.py    # 條件式選股（FilterCondition + 13 built-in 因子計算器）
│   ├── regime.py             # 市場狀態分類（與 allocation 共用）
│   └── auto/                 # 自動 Alpha 研究（9 檔案：Config, Researcher, DecisionEngine, Executor, Scheduler 等）
├── allocation/               # 戰術資產配置（between-asset 層）
│   ├── macro_factors.py      # 4 個總經因子（成長/通膨/利率/信用）from FRED z-scores
│   ├── cross_asset.py        # 跨資產因子：momentum/volatility/value per AssetClass
│   └── tactical.py           # TacticalEngine：strategic + macro + cross-asset + regime → 配置權重
├── portfolio/                # 多資產投資組合優化
│   ├── optimizer.py          # 14 種方法（EW/InverseVol/RiskParity/MVO/BL/HRP/Robust/CVaR 等）
│   ├── risk_model.py         # 共變異數估計（historical/EWM/Ledoit-Wolf/GARCH/PCA）
│   └── currency.py           # CurrencyHedger（分層避險比率 + HedgeRecommendation）
├── data/
│   ├── feed.py               # DataFeed ABC + HistoricalFeed
│   ├── store.py              # SQLAlchemy Core 持久化（SQLite/PostgreSQL）
│   ├── quality.py            # 數據驗證（欄位、NaN、異常值）
│   └── sources/              # yahoo.py, finmind.py, fred.py, local_market.py
├── strategy/
│   ├── base.py               # Strategy ABC + Context
│   ├── engine.py             # weights_to_orders() 權重轉訂單
│   ├── factors/              # 因子套件（83 個因子）
│   │   ├── technical.py      # 66 個技術因子（價量）
│   │   ├── fundamental.py    # 17 個基本面因子
│   │   └── kakushadze.py     # Kakushadze 101 Formulaic Alphas 子集
│   ├── optimizers/           # equal_weight, signal_weight, risk_parity
│   ├── registry.py           # 策略自動發現（strategies/ + alpha strategy）
│   ├── multi_asset.py        # 兩層策略：tactical allocation → within-class selection → optimization
│   └── research/             # IC 分析、factor decay
├── risk/
│   ├── engine.py             # RiskEngine：依序執行規則
│   ├── rules.py              # 宣告式風控規則工廠
│   └── monitor.py            # RiskMonitor + RealtimeRiskMonitor（tick-level 盤中回撤分層警報）
├── execution/
│   ├── broker/               # 券商子套件
│   │   ├── base.py           # BrokerAdapter ABC + PaperBroker
│   │   ├── simulated.py      # SimBroker（滑價/手續費/稅金/T+N 交割模擬）
│   │   └── sinopac.py        # SinopacBroker（Shioaji SDK wrapper）
│   ├── quote/sinopac.py      # SinopacQuoteManager（tick/bidask subscription）
│   ├── service.py            # ExecutionService（mode-aware routing: backtest/paper/live）
│   ├── smart_order.py        # TWAP 拆單
│   └── oms.py                # OrderManager + apply_trades()
├── backtest/
│   ├── engine.py             # BacktestEngine（InstrumentRegistry 整合、多幣別偵測）
│   ├── analytics.py          # 40+ 績效指標計算
│   ├── validation.py         # 回測合理性檢查
│   ├── experiment.py         # 平行網格回測
│   └── validator.py          # StrategyValidator（11 項強制驗證閘門）
├── api/
│   ├── app.py                # FastAPI 應用工廠（CORS、路由、WebSocket）
│   ├── auth.py               # API Key + JWT + 角色存取控制
│   ├── middleware.py         # AuditMiddleware（記錄所有 mutation 請求）
│   ├── ws.py                 # WebSocket ConnectionManager
│   └── routes/               # 14 個路由模組（auth, admin, portfolio, strategies, orders,
│                             #   backtest, risk, system, allocation, alpha, auto_alpha,
│                             #   execution, strategy_center 等）
├── notifications/            # Discord / LINE / Telegram 通知
├── scheduler/                # APScheduler（三條排程路徑：General / Auto-Alpha / Monthly Revenue）
└── cli/main.py               # Typer CLI：backtest, server, status, factors
#
# 注意：src/config.py 和 src/domain/models.py 為向後相容的 re-export，
# canonical 位置分別在 src/core/config.py 和 src/core/models.py

strategies/                   # 用戶自定義策略（13 個）
├── momentum.py               # 12-1 動量策略
├── mean_reversion.py         # 均值回歸策略
├── rsi_oversold.py           # RSI 超賣策略
├── ma_crossover.py           # 均線交叉策略
├── multi_factor.py           # 多因子複合策略（momentum + value + quality, risk-parity 加權）
├── pairs_trading.py          # 配對交易策略
├── sector_rotation.py        # 板塊輪動策略
├── revenue_momentum.py       # 月營收動量 + 價格確認（rev_yoy ICIR 0.037（修正前 0.674）））
├── revenue_momentum_hedged.py # = Revenue Momentum + 複合 regime hedge（Paper Trading 主策略）
├── trust_follow.py           # 投信跟單 + 營收成長
└── multi_strategy_combo.py   # 多策略逆波動率加權組合
# + src/alpha/strategy.py      # Alpha（可配置因子 pipeline）
# + src/strategy/multi_asset.py # Multi-Asset（兩層：戰術配置 → 類內選股 → 組合優化）

apps/
├── web/                      # React 18 + Vite + Tailwind 儀表板
├── mobile/                   # React Native + Expo 52 行動 App
├── android/                  # Android 原生（Kotlin + Jetpack Compose + Material 3 + Hilt DI）
└── shared/                   # @quant/shared TypeScript 共享套件
    └── src/
        ├── types/            # TypeScript 介面（對應後端 Pydantic schemas）
        ├── api/client.ts     # 平台無關 HTTP client（ClientAdapter 注入）
        ├── api/ws.ts         # WSManager（自動重連 + 指數退避）
        ├── api/endpoints.ts  # 型別安全 API 端點定義（25+ endpoints）
        └── utils/format.ts   # 數值/貨幣/日期格式化

tests/
├── unit/                     # 單元測試（1,707 個）
└── integration/              # 整合測試
```

## 3. 開發指令

```bash
# === 後端 ===
make test                    # pytest tests/ -v
make lint                    # ruff check + mypy strict
make dev                     # 開發模式（含熱重載）
make api                     # 生產模式
make backtest ARGS="--strategy momentum -u AAPL --start 2023-01-01 --end 2024-12-31"

# 執行特定測試
pytest tests/unit/test_risk.py -v                              # 單一檔案
pytest tests/unit/test_risk.py::TestMaxPositionWeight -v       # 單一類別
pytest tests/unit/test_risk.py::TestMaxPositionWeight::test_approve_within_limit -v  # 單一測試

# 程式碼檢查
ruff check src/ tests/       # 僅 ruff
mypy src/                    # 僅 mypy

# === 前端 ===
make install-apps            # bun install（所有前端套件）
make web                     # web dev server (port 3000)
make mobile                  # expo dev server
make web-build               # production build
make web-typecheck           # tsc --noEmit
make web-test                # vitest
cd apps/android && ./gradlew assembleDebug  # Android debug APK
cd apps/android && ./gradlew lintDebug      # Android lint

# === 全端啟動 ===
make start                   # 後端 + web 並行
scripts/start.bat            # Windows：分別開啟視窗
```

## 4. 撰寫新策略

### 步驟一：建立策略檔案

建立 `strategies/my_strategy.py`：

```python
from src.strategy.base import Context, Strategy
from src.strategy.factors.technical import momentum, rsi
from src.strategy.optimizer import signal_weight, OptConstraints


class MyStrategy(Strategy):
    def name(self) -> str:
        return "my_strategy"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        signals: dict[str, float] = {}

        for symbol in ctx.universe():
            bars = ctx.bars(symbol, lookback=252)
            if len(bars) < 60:
                continue

            mom = momentum(bars, lookback=60, skip=5)
            r = rsi(bars, period=14)

            if not mom.empty and not r.empty:
                # 組合因子：買入 RSI < 70 的動量贏家
                if r["rsi"] < 70:
                    signals[symbol] = mom["momentum"]

        return signal_weight(
            signals,
            OptConstraints(max_weight=0.08, max_total_weight=0.90),
        )
```

### 步驟二：註冊策略

在 `src/api/routes/backtest.py` 的 `_resolve_strategy()` 和 `src/cli/main.py` 的 `_resolve_strategy()` 中加入：

```python
from strategies.my_strategy import MyStrategy   # <-- 新增 import

mapping = {
    "momentum": MomentumStrategy,
    "momentum_12_1": MomentumStrategy,
    "mean_reversion": MeanReversionStrategy,
    "rsi_oversold": RsiOversoldStrategy,
    "ma_crossover": MaCrossoverStrategy,
    "pairs_trading": PairsTradingStrategy,
    "multi_factor": MultiFactorStrategy,
    "sector_rotation": SectorRotationStrategy,
    "my_strategy": MyStrategy,                  # <-- 新增對應
}
```

### 步驟三：執行回測

```bash
python -m src.cli.main backtest --strategy my_strategy -u AAPL -u MSFT --start 2023-01-01 --end 2024-12-31
```

### Strategy ABC 參考

```python
class Strategy(ABC):
    @abstractmethod
    def name(self) -> str:
        """策略唯一識別碼。"""

    @abstractmethod
    def on_bar(self, ctx: Context) -> dict[str, float]:
        """
        收到新 bar 時呼叫，回傳目標持倉權重。

        Returns:
            {"symbol": weight, ...}
            weight = 佔 NAV 的比例（正=多頭，負=空頭）
            不在 dict 中的標的 → 目標權重 0（平倉）
        """

    def on_start(self, ctx: Context) -> None:     # 選用
    def on_stop(self) -> None:                     # 選用
    def on_fill(self, symbol, side, qty, price):   # 選用
```

### Context API

| 方法 | 回傳型別 | 說明 |
|------|----------|------|
| `ctx.bars(symbol, lookback=252)` | `pd.DataFrame` | OHLCV K 線，回測時自動截斷至當前時間 |
| `ctx.universe()` | `list[str]` | 可交易標的清單 |
| `ctx.portfolio()` | `Portfolio` | 當前持倉快照 |
| `ctx.now()` | `datetime` | 當前模擬時間 |
| `ctx.latest_price(symbol)` | `Decimal` | 指定標的的最新價格 |
| `ctx.log(msg)` | `None` | 策略層級日誌 |

## 5. 撰寫自定義因子

因子位於 `src/strategy/factors/` 套件中（technical.py 66 個 + fundamental.py 17 個 + kakushadze.py = 共 83 個因子），皆為純函式：

```python
def my_factor(prices: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """
    自定義因子。

    Args:
        prices: 含 [open, high, low, close, volume] 欄位的 DataFrame
        lookback: 回看天數

    Returns:
        含命名值的 pd.Series，數據不足時回傳空 Series
    """
    close = prices["close"]
    if len(close) < lookback:
        return pd.Series(dtype=float)

    # 你的計算邏輯
    value = close.iloc[-1] / close.iloc[-lookback] - 1

    return pd.Series({"my_factor": float(value)})
```

慣例：
- 輸入 `pd.DataFrame`（OHLCV 欄位），輸出 `pd.Series`（命名值）
- 數據不足時回傳空 `pd.Series(dtype=float)`
- 無副作用、無狀態 — 僅限純函式

## 6. 撰寫自定義風控規則

風控規則是 `src/risk/rules.py` 中的函式工廠：

```python
from src.risk.rules import RiskRule, MarketState
from src.core.models import Order, Portfolio, RiskDecision


def max_sector_exposure(threshold: float = 0.30) -> RiskRule:
    """限制單一板塊的總曝險。"""
    def check(order: Order, portfolio: Portfolio, market: MarketState) -> RiskDecision:
        # 你的檢查邏輯
        if some_condition_violated:
            return RiskDecision.REJECT("板塊曝險過高")
        return RiskDecision.APPROVE()

    return RiskRule(f"max_sector_exposure_{threshold}", check)
```

啟用自定義規則的方式：加入 `src/risk/rules.py` 的 `default_rules()`，或傳入自定義規則列表給 `RiskEngine`：

```python
from src.risk.engine import RiskEngine
engine = RiskEngine(rules=[max_sector_exposure(0.30), ...])
```

### RiskDecision API

```python
RiskDecision.APPROVE()                          # 放行訂單
RiskDecision.REJECT("原因")                      # 拒絕訂單
RiskDecision.MODIFY(new_qty, "原因")             # 放行但修改數量
```

## 7. 投資組合優化

系統提供兩層優化：

### 策略層優化器（`src/strategy/optimizers/`）

簡單的權重分配方法，用於單一策略內部：

- **equal_weight** — 等權分配
- **signal_weight** — 按信號強度按比例分配
- **risk_parity** — 按波動率倒數分配

```python
from src.strategy.optimizer import OptConstraints

constraints = OptConstraints(
    max_weight=0.10,          # 單檔上限 10%
    max_total_weight=0.95,    # 總投資上限 95%（保留 5% 現金）
    min_weight=0.001,         # 低於 0.1% 的持倉會被捨棄
    long_only=True,           # 不允許放空
)
```

### 投資組合優化器（`src/portfolio/optimizer.py`）

14 種進階優化方法，用於多資產投資組合構建：

| 方法 | 說明 |
|------|------|
| EqualWeight | 等權分配 |
| InverseVolatility | 逆波動率加權 |
| RiskParity | 風險平價 |
| MVO | 均值-變異數最佳化 |
| BlackLitterman | Black-Litterman 模型（支援 `BLView` 觀點） |
| HRP | 層次風險平價 |
| Robust | 穩健最佳化 |
| Resampled | 重採樣效率前緣 |
| CVaR | 條件風險值最佳化 |
| MaxDrawdown | 最大回撤最佳化 |
| GlobalMinVariance | 全域最小變異數 |
| MaxSharpe | 最大 Sharpe 比率 |
| IndexTracking | 指數追蹤 |

搭配 `src/portfolio/risk_model.py`（共變異數估計：historical/EWM/Ledoit-Wolf/GARCH/PCA）和 `src/portfolio/currency.py`（CurrencyHedger 分層避險）。

## 8. 回測引擎內部機制

回測迴圈（`src/backtest/engine.py`）在每個交易日依序執行：

1. **設定可見時間** — `feed.set_current_date(bar_date)` 防止前視偏誤
2. **更新市場價格** — 持倉以市價重新估值
3. **檢查是否為再平衡日** — 依頻率判定（每日/每週一/每月初）
4. **策略訊號** — `strategy.on_bar(ctx)` 產出目標權重
5. **生成訂單** — `weights_to_orders()` 計算當前持倉與目標的差異
6. **風控檢查** — `risk_engine.check_orders()` 過濾被拒絕的訂單
7. **執行撮合** — `sim_broker.execute()` 模擬成交（含滑價/手續費/稅金）
8. **更新持倉** — `apply_trades()` 調整部位與現金
9. **記錄 NAV** — 每日 NAV 追加到歷史序列

## 9. 數據層

### DataFeed ABC

```python
class DataFeed(ABC):
    def get_bars(self, symbol, start, end, freq) -> pd.DataFrame:
        """回傳 DataFrame，欄位：[open, high, low, close, volume]，索引：DatetimeIndex (UTC)"""

    def get_latest_price(self, symbol) -> Decimal: ...
    def get_universe(self) -> list[str]: ...
```

### 新增數據源

1. 建立 `src/data/sources/my_source.py`
2. 繼承 `src/data/feed.py` 的 `DataFeed`
3. 實作 `get_bars()`、`get_latest_price()`、`get_universe()`
4. 將所有 DatetimeIndex 正規化為 tz-naive UTC
5. 確保欄位名稱為小寫：`open, high, low, close, volume`

### 數據品質

`src/data/quality.py` 驗證傳入的數據：
- 必要欄位是否存在
- 無 NaN 值
- 價格 > 0、high >= low、volume >= 0
- 時間戳遞增
- 無 5 sigma 價格跳躍

## 10. 前後端整合

### 前端架構模式

Web、Mobile、Android 共享 `@quant/shared` 套件，各平台透過 adapter 注入平台特定邏輯：

```
@quant/shared (types, API client, WS manager, formatters)
    ↑                    ↑                    ↑
apps/web/            apps/mobile/         apps/android/
  (localStorage)       (SecureStore)        (Kotlin + Hilt + OkHttp)
```

**匯入慣例：** Feature 程式碼從 `@core/*` 匯入（不直接匯入 `@quant/shared`），保持平台無關。

### 前後端連線對照

| 前端畫面 | 後端端點 | 協議 |
|---------|---------|------|
| Dashboard 即時 NAV | `GET /api/v1/portfolio` | REST + WebSocket `portfolio` |
| Positions 部位列表 | `GET /api/v1/portfolio/positions` | REST |
| Strategies 啟動/停止 | `POST /api/v1/strategies/{id}/start\|stop` | REST |
| Alerts 警報 Feed | `GET /api/v1/risk/alerts` | REST + WebSocket `alerts` |
| Alerts Kill Switch | `POST /api/v1/risk/kill-switch` | REST |
| Settings 系統狀態 | `GET /api/v1/system/status` | REST |
| Settings 風控規則 | `GET /api/v1/risk/rules` + `PUT /api/v1/risk/rules/{name}` | REST |
| Backtest 回測 | `POST /api/v1/backtest` + `GET /api/v1/backtest/{id}` | REST |

### WebSocket 頻道

| 頻道 | 推播內容 |
|------|---------|
| `portfolio` | 部位與 NAV 即時更新 |
| `alerts` | 風險警報 |
| `orders` | 訂單成交與狀態變更 |
| `market` | 行情資料更新 |

連線格式：`ws://{host}:{port}/ws/{channel}`

### 核心 TypeScript 型別

定義於 `apps/shared/src/types/`，對應後端 Pydantic schemas：

```typescript
Portfolio {
  nav: number
  cash: number
  daily_pnl: number
  daily_pnl_pct: number
  gross_exposure: number
  net_exposure: number
  positions_count: number
  positions: Position[]
  as_of: string              // ISO 時間戳
}

Position {
  symbol: string
  quantity: number
  avg_cost: number
  market_price: number
  market_value: number
  unrealized_pnl: number
  weight: number             // 佔 NAV 比例
}

StrategyInfo {
  name: string
  status: "running" | "stopped" | "error"
  pnl: number
}

OrderInfo {
  id: string
  symbol: string
  side: "BUY" | "SELL"
  quantity: number
  price: number | null
  status: string
  filled_qty: number
  filled_avg_price: number
  commission: number
  created_at: string
  strategy_id: string
}

RiskAlert {
  timestamp: string
  rule_name: string
  severity: "INFO" | "WARNING" | "CRITICAL"
  metric_value: number
  threshold: number
  action_taken: string
  message: string
}
```

### 版本相容性注意事項

| 項目 | 後端定義 | 前端使用 |
|------|---------|---------|
| API 前綴 | `/api/v1/` | `/api/v1/` |
| 金額型別 | `Decimal` → JSON 序列化為數字 | `number` 接收 |
| 訂單 Side | `BUY` / `SELL`（Python Enum） | `"BUY" \| "SELL"`（TypeScript） |
| 風險警報嚴重度 | INFO / WARNING / CRITICAL / EMERGENCY | INFO / WARNING / CRITICAL |

### 部署架構

```
[瀏覽器/行動裝置]              [伺服器/本機]
Web / Mobile /     ←HTTP→   FastAPI (Port 8000)
Android App        ←WS→     WebSocket (/ws/*)
                                    ↕
                             PostgreSQL (DB)
                                    ↕
                         Yahoo Finance / FinMind / FRED API
                                    ↕
                         Shioaji SDK（實盤/模擬券商）
```

## 11. 測試

```bash
# 執行所有測試
pytest tests/ -v

# 執行含覆蓋率（需安裝 pytest-cov）
pytest tests/ --cov=src --cov-report=term-missing
```

### 測試結構

後端共 1,707 個測試，涵蓋所有模組：

- `tests/unit/test_models.py` — 領域模型測試（Position, Portfolio, Order）
- `tests/unit/test_factors.py` — 因子計算測試
- `tests/unit/test_risk.py` — 風控引擎與規則測試
- `tests/unit/test_execution.py` — SimBroker 與交易更新測試
- `tests/unit/test_strategy.py` — Strategy ABC、Context、優化器測試
- `tests/unit/test_alpha*.py` — Alpha pipeline、filter strategy 測試
- `tests/unit/test_portfolio*.py` — 14 種優化器、risk model 測試
- `tests/unit/test_allocation*.py` — 戰術配置、總經因子測試
- `tests/unit/test_backtest*.py` — 回測引擎、validator 測試
- `tests/unit/test_api*.py` — API 路由測試
- 前端：Vitest（web）+ Playwright（e2e）

### 撰寫測試

```python
from decimal import Decimal
from src.core.models import Instrument, Order, Portfolio, Position, Side

def test_example():
    portfolio = Portfolio(cash=Decimal("1000000"))
    order = Order(
        instrument=Instrument(symbol="AAPL"),
        side=Side.BUY,
        quantity=Decimal("100"),
        price=Decimal("150"),
    )
    # 斷言...
```

## 12. 配置系統

`src/core/config.py` 使用 Pydantic Settings 搭配單例模式（`src/config.py` 為向後相容 re-export）：

```python
from src.core.config import get_config, override_config, TradingConfig

# 讀取配置（僅載入一次，之後快取）
config = get_config()
print(config.mode)              # "backtest"
print(config.commission_rate)   # 0.001425

# 在測試中覆寫
test_config = TradingConfig(mode="backtest", commission_rate=0.0)
override_config(test_config)
```

優先級：環境變數 > `.env` 檔案 > 預設值

## 13. 程式碼慣例

- **語言：** 程式碼註解與文件字串使用繁體中文
- **型別安全：** 所有價格/數量使用 `Decimal`，mypy 嚴格模式
- **行長度：** 100 字元（ruff）
- **目標 Python：** 3.12+
- **匯入：** 每個模組開頭使用 `from __future__ import annotations`
