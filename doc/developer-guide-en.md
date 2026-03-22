# Quant Trading System — Developer Guide

## 1. Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│  DataFeed   │────>│   Strategy   │────>│ RiskEngine  │────>│  SimBroker   │
│ (data layer)│     │ (on_bar →    │     │ (pre-trade  │     │ (execution   │
│             │     │  weights)    │     │  checks)    │     │  simulation) │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
                          │                                        │
                    ┌─────┴─────┐                           ┌──────┴──────┐
                    │  Context  │                           │ apply_trades│
                    │ (causality│                           │ (portfolio  │
                    │  barrier) │                           │  update)    │
                    └───────────┘                           └─────────────┘
```

**Data flow:** DataFeed → Strategy.on_bar(ctx) → target weight dict → weights_to_orders() → RiskEngine.check_orders() → SimBroker.execute() → apply_trades() → Portfolio update

**Design principles:**
- Strategies return target weight dicts (`dict[str, float]`), not orders
- Risk rules are pure function factories — no inheritance required
- All monetary values use `Decimal`, never `float`
- Time causality is enforced at the Context layer (backtest data is truncated to current simulation time)
- Timezone-naive UTC throughout (all DatetimeIndex data is normalized on ingestion)

## 2. Project Structure

```
src/
├── domain/models.py      # Core types: Instrument, Order, Portfolio, Position, Trade
├── config.py             # Pydantic Settings with QUANT_ env prefix
├── data/
│   ├── feed.py           # DataFeed ABC + HistoricalFeed
│   ├── store.py          # SQLite/PostgreSQL persistence
│   ├── quality.py        # Data validation (schema, NaN, outliers)
│   └── sources/yahoo.py  # Yahoo Finance connector
├── strategy/
│   ├── base.py           # Strategy ABC + Context
│   ├── engine.py         # weights_to_orders() conversion
│   ├── factors.py        # Pure function factor library
│   └── optimizer.py      # Portfolio optimizers (equal_weight, signal_weight, risk_parity)
├── risk/
│   ├── engine.py         # RiskEngine: sequential rule execution
│   ├── rules.py          # Declarative risk rule factories
│   └── monitor.py        # Alert tracking with cooldown
├── execution/
│   ├── sim.py            # SimBroker: fill simulation with slippage/commission/tax
│   ├── oms.py            # OrderManager + apply_trades()
│   └── broker.py         # BrokerAdapter ABC + PaperBroker
├── backtest/
│   ├── engine.py         # BacktestEngine: event-driven simulation loop
│   ├── analytics.py      # Performance metric computation
│   └── validation.py     # Backtest sanity checks
├── api/
│   ├── app.py            # FastAPI app factory with CORS, routes, WebSocket
│   ├── auth.py           # API Key + JWT + role-based access control
│   ├── schemas.py        # Pydantic request/response models (→ OpenAPI)
│   ├── state.py          # AppState singleton
│   ├── ws.py             # WebSocket ConnectionManager
│   └── routes/           # REST endpoints (portfolio, strategies, orders, backtest, risk, system)
└── cli/main.py           # Typer CLI: backtest, server, status, factors

strategies/               # User-defined strategy implementations
├── momentum.py           # 12-1 momentum strategy
└── mean_reversion.py     # Mean reversion strategy

tests/
├── unit/                 # Unit tests (54 tests)
└── integration/          # Integration tests
```

## 3. Development Commands

```bash
# Run all tests
make test                    # pytest tests/ -v

# Run specific tests
pytest tests/unit/test_risk.py -v                              # single file
pytest tests/unit/test_risk.py::TestMaxPositionWeight -v       # single class
pytest tests/unit/test_risk.py::TestMaxPositionWeight::test_approve_within_limit -v  # single test

# Linting
make lint                    # ruff check + mypy strict
ruff check src/ tests/       # ruff only
mypy src/                    # mypy only

# Run API server
make dev                     # development with hot reload
make api                     # production

# Run backtest
make backtest ARGS="--strategy momentum -u AAPL --start 2023-01-01 --end 2024-12-31"
```

## 4. Writing a New Strategy

### Step 1: Create a strategy file

Create `strategies/my_strategy.py`:

```python
from src.strategy.base import Context, Strategy
from src.strategy.factors import momentum, rsi
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
                # Combine factors: buy momentum winners with RSI < 70
                if r["rsi"] < 70:
                    signals[symbol] = mom["momentum"]

        return signal_weight(
            signals,
            OptConstraints(max_weight=0.08, max_total_weight=0.90),
        )
```

### Step 2: Register the strategy

Add it to `src/cli/main.py` in `_resolve_strategy()`:

```python
def _resolve_strategy(name: str):
    from strategies.momentum import MomentumStrategy
    from strategies.mean_reversion import MeanReversionStrategy
    from strategies.my_strategy import MyStrategy   # <-- add import

    mapping = {
        "momentum": MomentumStrategy,
        "mean_reversion": MeanReversionStrategy,
        "my_strategy": MyStrategy,                  # <-- add entry
    }
    ...
```

### Step 3: Run the backtest

```bash
python -m src.cli.main backtest --strategy my_strategy -u AAPL -u MSFT --start 2023-01-01 --end 2024-12-31
```

### Strategy ABC Reference

```python
class Strategy(ABC):
    @abstractmethod
    def name(self) -> str:
        """Unique strategy identifier."""

    @abstractmethod
    def on_bar(self, ctx: Context) -> dict[str, float]:
        """
        Called on each bar. Returns target portfolio weights.

        Returns:
            {"symbol": weight, ...}
            weight = fraction of NAV (positive = long, negative = short)
            Symbols not in dict → target weight 0 (close position)
        """

    def on_start(self, ctx: Context) -> None:     # optional
    def on_stop(self) -> None:                     # optional
    def on_fill(self, symbol, side, qty, price):   # optional
```

### Context API

| Method | Returns | Description |
|--------|---------|-------------|
| `ctx.bars(symbol, lookback=252)` | `pd.DataFrame` | OHLCV bars, auto-truncated to current time in backtest |
| `ctx.universe()` | `list[str]` | Available trading symbols |
| `ctx.portfolio()` | `Portfolio` | Current portfolio snapshot |
| `ctx.now()` | `datetime` | Current simulation time |
| `ctx.latest_price(symbol)` | `Decimal` | Latest price for a symbol |
| `ctx.log(msg)` | `None` | Strategy-level logging |

## 5. Writing a Custom Factor

Factors are pure functions in `src/strategy/factors.py`:

```python
def my_factor(prices: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """
    Custom factor.

    Args:
        prices: DataFrame with columns [open, high, low, close, volume]
        lookback: Number of bars to look back

    Returns:
        pd.Series with named values, or empty Series if insufficient data
    """
    close = prices["close"]
    if len(close) < lookback:
        return pd.Series(dtype=float)

    # Your calculation here
    value = close.iloc[-1] / close.iloc[-lookback] - 1

    return pd.Series({"my_factor": float(value)})
```

Conventions:
- Accept a `pd.DataFrame` with OHLCV columns, return a `pd.Series` with named values
- Return empty `pd.Series(dtype=float)` when insufficient data
- No side effects, no state — pure functions only

## 6. Writing a Custom Risk Rule

Risk rules are function factories in `src/risk/rules.py`:

```python
from src.risk.rules import RiskRule, MarketState
from src.domain.models import Order, Portfolio, RiskDecision


def max_sector_exposure(threshold: float = 0.30) -> RiskRule:
    """Limit total exposure to any single sector."""
    def check(order: Order, portfolio: Portfolio, market: MarketState) -> RiskDecision:
        # Your check logic here
        if some_condition_violated:
            return RiskDecision.REJECT("Sector exposure too high")
        return RiskDecision.APPROVE()

    return RiskRule(f"max_sector_exposure_{threshold}", check)
```

To activate a custom rule, add it to `default_rules()` in `src/risk/rules.py` or pass a custom rule list to `RiskEngine`:

```python
from src.risk.engine import RiskEngine
engine = RiskEngine(rules=[max_sector_exposure(0.30), ...])
```

### RiskDecision API

```python
RiskDecision.APPROVE()                          # allow the order
RiskDecision.REJECT("reason")                   # block the order
RiskDecision.MODIFY(new_qty, "reason")          # allow with modified quantity
```

## 7. Portfolio Optimization

Three optimizers are available in `src/strategy/optimizer.py`:

### equal_weight(signals, constraints)
Distributes weight equally among all positive signals. Simplest approach.

### signal_weight(signals, constraints)
Weights proportional to signal magnitude. Stronger signals get more capital.

### risk_parity(signals, volatilities, constraints)
Weights by inverse volatility — each position contributes equal risk.

```python
from src.strategy.optimizer import OptConstraints

constraints = OptConstraints(
    max_weight=0.10,          # 10% max per position
    max_total_weight=0.95,    # 95% max total (5% cash reserve)
    min_weight=0.001,         # positions below 0.1% are dropped
    long_only=True,           # no short positions
)
```

## 8. Backtest Engine Internals

The backtest loop (`src/backtest/engine.py`) follows this sequence for each trading day:

1. **Set visible time** — `feed.set_current_date(bar_date)` prevents look-ahead bias
2. **Update market prices** — portfolio positions are marked to market
3. **Check rebalance** — based on frequency (daily/weekly on Monday/monthly on day 1-3)
4. **Strategy signal** — `strategy.on_bar(ctx)` produces target weights
5. **Order generation** — `weights_to_orders()` computes the delta vs current holdings
6. **Risk check** — `risk_engine.check_orders()` filters rejected orders
7. **Execution** — `sim_broker.execute()` simulates fills with slippage/commission/tax
8. **Portfolio update** — `apply_trades()` adjusts positions and cash
9. **Record NAV** — daily NAV is appended to the history

## 9. Data Layer

### DataFeed ABC

```python
class DataFeed(ABC):
    def get_bars(self, symbol, start, end, freq) -> pd.DataFrame:
        """Returns DataFrame with columns: [open, high, low, close, volume], DatetimeIndex (UTC)"""

    def get_latest_price(self, symbol) -> Decimal: ...
    def get_universe(self) -> list[str]: ...
```

### Adding a New Data Source

1. Create `src/data/sources/my_source.py`
2. Subclass `DataFeed` from `src/data/feed.py`
3. Implement `get_bars()`, `get_latest_price()`, `get_universe()`
4. Normalize all DatetimeIndex to tz-naive UTC
5. Ensure column names are lowercase: `open, high, low, close, volume`

### Data Quality

`src/data/quality.py` validates incoming data:
- Required columns present
- No NaN values
- Prices > 0, high >= low, volume >= 0
- Monotonic timestamps
- No 5-sigma price jumps

## 10. Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage (if pytest-cov installed)
pytest tests/ --cov=src --cov-report=term-missing
```

### Test Structure

- `tests/unit/test_models.py` — Domain model tests (Position, Portfolio, Order)
- `tests/unit/test_factors.py` — Factor computation tests
- `tests/unit/test_risk.py` — Risk engine and rule tests
- `tests/unit/test_execution.py` — SimBroker and trade application tests
- `tests/unit/test_strategy.py` — Strategy ABC, Context, optimizer tests

### Writing Tests

```python
from decimal import Decimal
from src.domain.models import Instrument, Order, Portfolio, Position, Side

def test_example():
    portfolio = Portfolio(cash=Decimal("1000000"))
    order = Order(
        instrument=Instrument(symbol="AAPL"),
        side=Side.BUY,
        quantity=Decimal("100"),
        price=Decimal("150"),
    )
    # assertions...
```

## 11. Configuration System

`src/config.py` uses Pydantic Settings with singleton pattern:

```python
from src.config import get_config, override_config, TradingConfig

# Read config (loads once, cached)
config = get_config()
print(config.mode)              # "backtest"
print(config.commission_rate)   # 0.001425

# Override in tests
test_config = TradingConfig(mode="backtest", commission_rate=0.0)
override_config(test_config)
```

Priority: Environment variables > `.env` file > Defaults

## 12. Code Conventions

- **Language:** Code comments and docstrings are in Traditional Chinese
- **Type safety:** `Decimal` for all prices/quantities, strict mypy
- **Line length:** 100 characters (ruff)
- **Target Python:** 3.12+
- **Imports:** Use `from __future__ import annotations` in every module
