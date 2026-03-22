# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Quantitative trading system — single-process Python monolith for backtesting and paper/live trading. Targets Taiwan stock market defaults (commission 0.1425%, sell tax 0.3%) but works with any market via Yahoo Finance.

## Commands

```bash
# Testing
make test                    # pytest tests/ -v
pytest tests/unit/test_risk.py -v          # single test file
pytest tests/unit/test_risk.py::TestMaxPositionWeight -v  # single class
pytest tests/unit/test_risk.py::TestMaxPositionWeight::test_approve_within_limit -v  # single test

# Linting
make lint                    # ruff check + mypy strict
ruff check src/ tests/       # ruff only
mypy src/                    # mypy only

# Running
make dev                     # API with hot reload (port 8000)
make api                     # production API
make backtest ARGS="--strategy momentum -u AAPL -u MSFT --start 2023-01-01 --end 2024-12-31"

# CLI entry point
python -m src.cli.main backtest --strategy momentum -u AAPL --start 2023-01-01 --end 2024-12-31
python -m src.cli.main server
python -m src.cli.main status
python -m src.cli.main factors

# Database
make migrate                 # alembic upgrade head
```

## Architecture

**Data flow**: DataFeed → Strategy.on_bar() → target weights → RiskEngine → SimBroker/Broker → Trade → Portfolio update

Key design decisions:
- **Strategy returns target weight dicts** (`dict[str, float]`), not orders. `weights_to_orders()` in `src/strategy/engine.py` handles the conversion.
- **Risk rules are pure function factories** in `src/risk/rules.py` — no inheritance. Each returns a `RiskRule` dataclass. The engine runs rules sequentially; first REJECT stops evaluation.
- **Time causality**: `Context` wraps `DataFeed` + `Portfolio` and truncates data to `current_time` during backtest. `HistoricalFeed.set_current_date()` enforces this at the feed level.
- **All monetary values use `Decimal`**, never `float`.
- **Timezone handling**: All DatetimeIndex data is normalized to tz-naive UTC. Both `HistoricalFeed.load()` and `YahooFeed._download()` strip timezone info.

**Module boundaries**:
- `src/domain/models.py` — Frozen value objects (Instrument, Bar) + mutable aggregates (Position, Order, Portfolio, Trade)
- `src/strategy/` — Strategy ABC (`on_bar()` → weights), factor library (pure functions), optimizers (equal_weight, signal_weight, risk_parity)
- `src/risk/` — RiskEngine executes declarative rules; `check_order()` for singles, `check_orders()` for batch filtering, `kill_switch()` at 5% daily drawdown
- `src/execution/` — SimBroker (slippage/commission/tax simulation), `apply_trades()` updates Portfolio from Trade list
- `src/backtest/engine.py` — Orchestrates: download data → iterate trading dates → call strategy → risk check → execute → update portfolio
- `src/api/` — FastAPI REST + WebSocket. `AppState` singleton holds runtime state. JWT auth with role hierarchy (viewer < researcher < trader < risk_manager < admin)

**Adding a new strategy**: Create a file in `strategies/`, subclass `Strategy` from `src/strategy/base.py`, implement `name()` and `on_bar(ctx) -> dict[str, float]`. Register it in `src/backtest/engine.py:_resolve_strategy()`.

## Configuration

All config via `QUANT_` prefixed env vars or `.env` file (see `.env.example`). Defined in `src/config.py` as Pydantic Settings. Access via `get_config()` singleton; use `override_config()` in tests.
