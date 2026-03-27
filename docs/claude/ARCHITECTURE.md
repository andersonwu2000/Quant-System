# Architecture Guide

> 從 CLAUDE.md 分拆，供 Claude Code 理解系統架構時參考。
> CLAUDE.md 保留行為規範和開發規則，本文件保留技術架構細節。

---

## Data Flow

DataFeed → Strategy.on_bar() → target weights → RiskEngine → SimBroker/Broker → Trade → Portfolio update

## Key Design Decisions

- **Strategy returns target weight dicts** (`dict[str, float]`), not orders. `weights_to_orders()` in `src/strategy/engine.py` handles the conversion.
- **Risk rules are pure function factories** in `src/risk/rules.py` — no inheritance. Each returns a `RiskRule` dataclass. The engine runs rules sequentially; first REJECT stops evaluation.
- **Time causality**: `Context` wraps `DataFeed` + `Portfolio` and truncates data to `current_time` during backtest. `HistoricalFeed.set_current_date()` enforces this at the feed level.
- **All monetary values use `Decimal`**, never `float`.
- **Timezone handling**: All DatetimeIndex data is normalized to tz-naive UTC. Both `HistoricalFeed.load()` and `YahooFeed._download()` strip timezone info.

## Module Boundaries

Detailed inventory in `docs/dev/SYSTEM_STATUS_REPORT.md` §4.

- `src/core/` — `models.py` (**Unified** Instrument, Bar, Position, Order, Portfolio, Trade, enums), `config.py` (Pydantic Settings), `logging.py` (structlog), `repository.py`, `calendar.py` (TWTradingCalendar — 台股交易日曆含國定假日), `trading_pipeline.py` (`execute_one_bar()` — 回測/實盤共用交易流程).
- `src/instrument/` — `InstrumentRegistry` (get/get_or_create/search/by_market/by_asset_class). Re-exports Instrument from domain. `_infer_instrument()` auto-detects asset type from symbol pattern. Cost templates (TW_STOCK_DEFAULTS, US_FUTURES_DEFAULTS, etc.).
- `src/alpha/` — Alpha research layer (within-asset selection). `pipeline.py` orchestrates end-to-end: universe filtering → factor computation → neutralization → orthogonalization → composite signal → quantile backtest → cost-aware portfolio construction. `AlphaStrategy` adapter wraps pipeline as `Strategy`. `filter_strategy.py` provides condition-based screening (`FilterCondition` + `FilterStrategyConfig` + `FilterStrategy`, 13 built-in factor calculators, pre-configured `revenue_momentum_filter()` / `trust_follow_filter()` factories). `regime.py` classifies market regimes (shared with allocation layer). `auto/` (9 files: AutoAlphaConfig, UniverseSelector, AlphaResearcher, AlphaDecisionEngine, AlphaExecutor, AlphaScheduler, AlphaStore, AlertManager, SafetyChecker, FactorPerformanceTracker, DynamicFactorPool).
- `src/allocation/` — Tactical asset allocation (between-asset selection). `macro_factors.py`: 4 macro factors (growth/inflation/rates/credit) from FRED z-scores. `cross_asset.py`: momentum/volatility/value per AssetClass. `tactical.py`: TacticalEngine combines strategic weights + macro + cross-asset + regime → `dict[AssetClass, float]`. API: `POST /api/v1/allocation`.
- `src/portfolio/` — Multi-asset portfolio optimization. `optimizer.py`: 14 methods (EW/InverseVol/RiskParity/MVO/BlackLitterman/HRP/Robust/Resampled/CVaR/MaxDrawdown/GlobalMinVariance/MaxSharpe/IndexTracking), `BLView` for views, `OptimizationResult` with risk/return/Sharpe/risk contributions. `risk_model.py`: covariance estimation (historical/EWM/Ledoit-Wolf shrinkage/GARCH/PCA factor model), correlation, volatilities, portfolio risk, marginal risk contribution. `currency.py`: `CurrencyHedger` with tiered hedge ratios, `HedgeRecommendation`.
- `src/strategy/` — Strategy ABC (`on_bar()` → weights), `factors/` package (technical.py + fundamental.py + kakushadze.py — 66 price-volume factors + 17 fundamental = 83 total, vectorized), optimizers (equal_weight, signal_weight, risk_parity), registry (auto-discovery from `strategies/` + `alpha` strategy), research (IC analysis, factor decay).
- `src/risk/` — RiskEngine executes declarative rules; `kill_switch()` at 5% daily drawdown. RiskMonitor tracks metrics. `RealtimeRiskMonitor` — tick-level intraday drawdown with tiered alerts (2%/3%/5%) and automatic kill switch.
- `src/execution/` — `broker/` subpackage: `base.py` (BrokerAdapter ABC, PaperBroker), `simulated.py` (SimBroker — slippage, per-instrument commission/tax, T+N settlement), `sinopac.py` (SinopacBroker — Shioaji SDK wrapper). `quote/` subpackage: `sinopac.py` (SinopacQuoteManager — tick/bidask subscription). `service.py` (ExecutionService — mode-aware routing: backtest/paper/live), `smart_order.py` (TWAP splitter), OMS (order lifecycle), market hours validation, EOD reconciliation.
- `src/backtest/` — BacktestEngine (InstrumentRegistry integration, multi-currency detection), 40+ analytics, HTML/CSV reports, walk-forward, validation, `experiment.py` (parallel grid backtesting), `validator.py` (**StrategyValidator — 13 項強制驗證閘門**: CAGR/Sharpe/MDD/Walk-Forward/PBO/DSR/Bootstrap/OOS/vs-1N/Cost/Factor-Decay).
- `src/data/` — DataFeed ABC (`get_bars`, `get_fx_rate`, `get_futures_chain`), YahooFeed (local-first: reads `data/market/*.parquet`, downloads only if missing), FinMindFeed, FredDataSource (macro data), LocalMarketData (permanent parquet store in `data/market/`).
- `src/api/` — FastAPI REST + WebSocket, 14 route modules (incl. `/alpha`, `/allocation`, `/execution`, `/auto-alpha`), JWT auth, Prometheus.
- `src/notifications/` — Discord / LINE / Telegram.
- `src/scheduler/` — APScheduler with three execution paths (see Scheduling section below).

## Adding Components

**Adding a new strategy**: Create a file in `strategies/`, subclass `Strategy` from `src/strategy/base.py`, implement `name()` and `on_bar(ctx) -> dict[str, float]`. Register it in `_resolve_strategy()` in both `src/api/routes/backtest.py` and `src/cli/main.py`.

**Adding a new data source**: Create a file in `src/data/sources/`, subclass `DataFeed` from `src/data/feed.py`, implement `get_bars()`, `get_latest_price()`, `get_universe()`. Output: `DataFrame[open, high, low, close, volume]` + tz-naive `DatetimeIndex`. Register in `create_feed()` factory in `src/data/sources/__init__.py`.

## API Layer

**Routes** (`src/api/routes/`): auth, admin, portfolio, strategies, orders, backtest, risk, system — all mounted under `/api/v1`.

**Key endpoints**: See `docs/api-reference-zh.md` for full list. Core endpoints:
- `POST /api/v1/auth/login` — JWT token
- `POST /api/v1/backtest` — Run backtest
- `POST /api/v1/strategy/rebalance` — One-click rebalance
- `GET /api/v1/execution/paper-trading/status` — Paper trading status
- `POST /api/v1/auto-alpha/start` — Start auto-alpha scheduler
- `GET /api/v1/system/health` — Health check

**Middleware**: AuditMiddleware, JWT auth, rate limiting (slowapi), CORS, Prometheus.

**WebSocket** (`src/api/ws.py`): channels — `portfolio`, `alerts`, `orders`, `market`. Token-based auth.

## Frontend Architecture

**Shared package** (`apps/shared/`): TypeScript types, API client, WS manager, format utils.

**Web** (`apps/web/`): React 18 + Vite + Tailwind, 11 pages (Dashboard, Trading, Strategies, Research, Auto-Alpha, Risk, Guide, Settings, Admin). Path aliases: `@core`, `@feat`, `@shared`.

**Android** (`apps/android/`): Kotlin + Jetpack Compose + Material 3 + Hilt DI.

**i18n**: English + Traditional Chinese.

## Strategies

13 strategies (11 built-in + 2 pipeline):

| Strategy | File | Logic |
|----------|------|-------|
| Revenue Momentum Hedged | `strategies/revenue_momentum_hedged.py` | **Paper Trading 主策略** — revenue_acceleration + regime hedge |
| Revenue Momentum | `strategies/revenue_momentum.py` | Sort by revenue_acceleration (3M/12M) |
| Alpha | `src/alpha/strategy.py` | Configurable factor pipeline |
| Multi-Asset | `src/strategy/multi_asset.py` | Tactical allocation → selection → optimization |
| + 9 others | `strategies/*.py` | Momentum, MA, Mean Reversion, RSI, Multi-Factor, Pairs, Sector, Trust Follow, Combo |

## Scheduling

Three independent execution paths — **should not run simultaneously**:

| Path | Trigger | Cron | Config |
|------|---------|------|--------|
| **Unified Pipeline** | APScheduler | `QUANT_TRADING_PIPELINE_CRON` (default: 11th 08:30) | `QUANT_SCHEDULER_ENABLED` |
| **Auto-Alpha** | `/auto-alpha/start` API | 8 stages 08:30~13:35 | Manual |
| **Alpha Research** | `scripts/alpha_research_agent.py` | Manual / background | -- |

## Infrastructure

- **DB**: PostgreSQL 16 (SQLite for dev). Alembic migrations.
- **Docker**: Multi-stage, non-root. `docker-compose.yml` = api + db.
- **CI/CD**: 9 jobs (lint, test, typecheck, build, e2e, release+APK).

## Configuration

All config via `QUANT_` env vars or `.env`. See `src/core/config.py` and `.env.example`.

## Security

JWT (HS256) + API Key, 5-level roles, PBKDF2 passwords, token revocation, account lockout, rate limiting, audit logging, non-root container.
