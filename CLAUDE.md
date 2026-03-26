# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Release Rules

- **GitHub Release 必須包含 APK**：每次建立 GitHub Release 時，一定要建置 Android debug APK (`apps/android` → `./gradlew.bat assembleDebug`) 並上傳為 release asset，命名格式為 `quant-trading-v{VERSION}.apk`。

## Maintenance Rules

After completing any feature addition, bug fix, refactoring, architecture change, or dependency update, **update `docs/dev/SYSTEM_STATUS_REPORT.md`** to reflect the changes. Sections to check and update:
- **Module inventory** (§3–§5): file counts, LOC, new/removed modules
- **Strategy list** (§6): if strategies were added/removed
- **Test coverage** (§8): new test files, updated test counts
- **CI/CD** (§9): pipeline changes
- **Known defects** (§11): resolved or newly discovered issues
- **Feature matrix** (§12): completion status changes
- **Gap analysis** (§13–§14): items that have been addressed

Keep updates minimal — only touch sections affected by the change.

## Project Overview

Multi-asset portfolio research and optimization system covering TW stocks, US stocks, ETFs (incl. bond/commodity ETF proxies), TW futures, US futures. Bond/commodity exposure via ETFs, not direct trading. No retail FX (Taiwan regulatory restriction). Current stage: equity alpha research layer complete, expanding to multi-asset architecture. Long-term goal: platform for individual investors and family asset management.

Monorepo: Python backend + React web + Android native (Kotlin/Compose). Targets Taiwan stock market defaults (commission 0.1425%, sell tax 0.3%) but works with any market via Yahoo Finance or FinMind.

**Monorepo structure:**
- `src/`, `tests/`, `strategies/`, `migrations/` — Python backend (~150 files, ~27,000 LOC)
- `apps/web/` — React 18 + Vite + Tailwind dashboard (incl. Alpha Research page)
- `apps/android/` — Android native (Kotlin + Jetpack Compose + Material 3)
- `apps/shared/` — `@quant/shared` TypeScript package (types, API client, WS manager, format utils)

Frontend workspace managed by bun (`apps/package.json` workspaces).

**Documentation:**
- `docs/dev/SYSTEM_STATUS_REPORT.md` — System status report (module inventory, feature matrix, gap analysis)
- `docs/dev/DEVELOPMENT_PLAN.md` — Development plan (Phase A~I + R1-R4: multi-asset infra → cross-asset alpha → optimizer → backtest → live → auto-alpha → academic → alpha expansion → refactoring)
- `docs/dev/DEVELOPMENT_LOG.md` — Development log (5-day history, key decisions, milestones)
- `docs/dev/architecture/MULTI_ASSET_ARCHITECTURE.md` — Multi-asset architecture design
- `docs/dev/architecture/AUTOMATED_ALPHA_ARCHITECTURE.md` — Auto-alpha system design
- `docs/dev/evaluations/BROKER_API_EVALUATION.md` — Broker API comparison (Shioaji chosen)
- `docs/dev/archive/Project Requirements (Archived).md` — Archived project requirements
- `docs/api-reference-zh.md` — API reference (Traditional Chinese)
- `docs/developer-guide-zh.md` — Developer guide (Traditional Chinese)
- `docs/user-guide-zh.md` — User guide (Traditional Chinese)

## Commands

```bash
# === Backend ===
make test                    # pytest tests/ -v (1243 tests)
make lint                    # ruff check + mypy strict
make dev                     # API with hot reload (port 8000)
make api                     # production API
make backtest ARGS="--strategy momentum -u AAPL -u MSFT --start 2023-01-01 --end 2024-12-31"
make migrate                 # alembic upgrade head
make seed                    # python scripts/seed_data.py

# Single test
pytest tests/unit/test_risk.py -v
pytest tests/unit/test_risk.py::TestMaxPositionWeight::test_approve_within_limit -v

# CLI
python -m src.cli.main backtest --strategy momentum -u AAPL --start 2023-01-01 --end 2024-12-31
python -m src.cli.main server
python -m src.cli.main status
python -m src.cli.main factors

# === Frontend ===
make install-apps            # bun install (all frontend packages)
make web                     # web dev server (port 3000)
cd apps/android && ./gradlew assembleDebug  # Android debug APK
make web-build               # production build
make web-typecheck           # tsc --noEmit
make web-test                # vitest
cd apps/android && ./gradlew lintDebug  # Android lint

# === Full stack ===
make start                   # backend + web in parallel
scripts/start.bat            # Windows: backend + web in separate windows

# === Docker ===
docker compose up -d         # API (port 8000) + PostgreSQL
docker compose down          # stop all services
```

## Architecture

**Data flow**: DataFeed → Strategy.on_bar() → target weights → RiskEngine → SimBroker/Broker → Trade → Portfolio update

Key design decisions:
- **Strategy returns target weight dicts** (`dict[str, float]`), not orders. `weights_to_orders()` in `src/strategy/engine.py` handles the conversion.
- **Risk rules are pure function factories** in `src/risk/rules.py` — no inheritance. Each returns a `RiskRule` dataclass. The engine runs rules sequentially; first REJECT stops evaluation.
- **Time causality**: `Context` wraps `DataFeed` + `Portfolio` and truncates data to `current_time` during backtest. `HistoricalFeed.set_current_date()` enforces this at the feed level.
- **All monetary values use `Decimal`**, never `float`.
- **Timezone handling**: All DatetimeIndex data is normalized to tz-naive UTC. Both `HistoricalFeed.load()` and `YahooFeed._download()` strip timezone info.

**Module boundaries** (detailed inventory in `docs/dev/SYSTEM_STATUS_REPORT.md` §4):
- `src/core/` — `models.py` (**Unified** Instrument, Bar, Position, Order, Portfolio, Trade, enums), `config.py` (Pydantic Settings), `logging.py` (structlog), `repository.py`, `calendar.py` (TWTradingCalendar — 台股交易日曆含國定假日), `trading_pipeline.py` (`execute_one_bar()` — 回測/實盤共用交易流程). (`src/domain/models.py` re-exports for backward compat.)
- `src/instrument/` — `InstrumentRegistry` (get/get_or_create/search/by_market/by_asset_class). Re-exports Instrument from domain. `_infer_instrument()` auto-detects asset type from symbol pattern. Cost templates (TW_STOCK_DEFAULTS, US_FUTURES_DEFAULTS, etc.).
- `src/alpha/` — Alpha research layer (within-asset selection). `pipeline.py` orchestrates end-to-end: universe filtering → factor computation → neutralization → orthogonalization → composite signal → quantile backtest → cost-aware portfolio construction. `AlphaStrategy` adapter wraps pipeline as `Strategy`. `regime.py` classifies market regimes (shared with allocation layer). `auto/` (9 files: AutoAlphaConfig, UniverseSelector, AlphaResearcher, AlphaDecisionEngine, AlphaExecutor, AlphaScheduler, AlphaStore, AlertManager, SafetyChecker, FactorPerformanceTracker, DynamicFactorPool).
- `src/allocation/` — Tactical asset allocation (between-asset selection). `macro_factors.py`: 4 macro factors (growth/inflation/rates/credit) from FRED z-scores. `cross_asset.py`: momentum/volatility/value per AssetClass. `tactical.py`: TacticalEngine combines strategic weights + macro + cross-asset + regime → `dict[AssetClass, float]`. API: `POST /api/v1/allocation`.
- `src/portfolio/` — Multi-asset portfolio optimization. `optimizer.py`: 14 methods (EW/InverseVol/RiskParity/MVO/BlackLitterman/HRP/Robust/Resampled/CVaR/MaxDrawdown/GlobalMinVariance/MaxSharpe/IndexTracking), `BLView` for views, `OptimizationResult` with risk/return/Sharpe/risk contributions. `risk_model.py`: covariance estimation (historical/EWM/Ledoit-Wolf shrinkage/GARCH/PCA factor model), correlation, volatilities, portfolio risk, marginal risk contribution. `currency.py`: `CurrencyHedger` with tiered hedge ratios, `HedgeRecommendation`.
- `src/strategy/` — Strategy ABC (`on_bar()` → weights), `factors/` package (technical.py + fundamental.py + kakushadze.py — 66 price-volume factors + 9 fundamental = 75 total, vectorized), optimizers (equal_weight, signal_weight, risk_parity), registry (auto-discovery from `strategies/` + `alpha` strategy), research (IC analysis, factor decay).
- `src/risk/` — RiskEngine executes declarative rules; `kill_switch()` at 5% daily drawdown. RiskMonitor tracks metrics. `RealtimeRiskMonitor` — tick-level intraday drawdown with tiered alerts (2%/3%/5%) and automatic kill switch.
- `src/execution/` — `broker/` subpackage: `base.py` (BrokerAdapter ABC, PaperBroker), `simulated.py` (SimBroker — slippage, per-instrument commission/tax, T+N settlement), `sinopac.py` (SinopacBroker — Shioaji SDK wrapper). `quote/` subpackage: `sinopac.py` (SinopacQuoteManager — tick/bidask subscription). `service.py` (ExecutionService — mode-aware routing: backtest/paper/live), `smart_order.py` (TWAP splitter), OMS (order lifecycle), market hours validation, EOD reconciliation.
- `src/backtest/` — BacktestEngine (InstrumentRegistry integration, multi-currency detection), 40+ analytics, HTML/CSV reports, walk-forward, validation, `experiment.py` (parallel grid backtesting — 256+ configs × 5 periods, 12-core ProcessPoolExecutor).
- `src/data/` — DataFeed ABC (`get_bars`, `get_fx_rate`, `get_futures_chain`), YahooFeed (local-first: reads `data/market/*.parquet`, downloads only if missing), FinMindFeed, FredDataSource (macro data), LocalMarketData (permanent parquet store in `data/market/`).
- `src/api/` — FastAPI REST + WebSocket, 14 route modules (incl. `/alpha`, `/allocation`, `/execution`, `/auto-alpha`), JWT auth, Prometheus.
- `src/notifications/` — Discord / LINE / Telegram.
- `src/scheduler/` — APScheduler (daily snapshots, weekly rebalance).

**Adding a new strategy**: Create a file in `strategies/`, subclass `Strategy` from `src/strategy/base.py`, implement `name()` and `on_bar(ctx) -> dict[str, float]`. Register it in `_resolve_strategy()` in both `src/api/routes/backtest.py` and `src/cli/main.py`.

**Adding a new data source**: Create a file in `src/data/sources/`, subclass `DataFeed` from `src/data/feed.py`, implement `get_bars()`, `get_latest_price()`, `get_universe()`. Output: `DataFrame[open, high, low, close, volume]` + tz-naive `DatetimeIndex`. Register in `create_feed()` factory in `src/data/sources/__init__.py`.

## API Layer

**Routes** (`src/api/routes/`): auth, admin, portfolio, strategies, orders, backtest, risk, system — all mounted under `/api/v1`.

**Key endpoints**:
- `POST /api/v1/auth/login` — JWT token issuance
- `POST /api/v1/auth/register` — User registration
- `POST /api/v1/backtest` — Run backtest
- `POST /api/v1/backtest/walk-forward` — Walk-forward analysis
- `GET/POST/DELETE /api/v1/portfolio/saved` — Persisted portfolio CRUD
- `POST /api/v1/portfolio/saved/{id}/rebalance-preview` — Suggested trades via `weights_to_orders()`
- `GET /api/v1/portfolio/saved/{id}/trades` — Trade history
- `GET /api/v1/strategies` — List available strategies
- `POST /api/v1/orders` — Create order
- `PUT /api/v1/orders/{id}` — Modify order (price/quantity)
- `DELETE /api/v1/orders/{id}` — Cancel order
- `GET /api/v1/risk/rules` — Risk rule status
- `POST /api/v1/risk/kill-switch` — Kill switch control
- `GET /api/v1/risk/realtime` — Real-time intraday drawdown + alerts
- `GET /api/v1/system/health` — Health check
- `GET /api/v1/execution/status` — Execution service status
- `GET /api/v1/execution/market-hours` — Current trading session
- `POST /api/v1/execution/reconcile` — EOD position reconciliation
- `GET /api/v1/execution/paper-trading/status` — Paper trading status
- `GET /api/v1/auto-alpha/status` — Auto-alpha running state
- `POST /api/v1/auto-alpha/start` — Start auto-alpha scheduler
- `POST /api/v1/auto-alpha/run-now` — Execute one cycle immediately

**Middleware & cross-cutting concerns**:
- `src/api/middleware.py` — AuditMiddleware logs all mutation requests (POST/PUT/DELETE) with user, path, status, duration
- `src/api/auth.py` — JWT token issuance + API key verification; role hierarchy enforcement
- `src/api/password.py` — PBKDF2-SHA256 password hashing (standard library, zero deps)
- Rate limiting via slowapi (60 requests/minute default, 10/minute for backtest)
- CORS configured via `QUANT_ALLOWED_ORIGINS`
- Prometheus metrics via `/metrics` endpoint

**WebSocket** (`src/api/ws.py`): channels — `portfolio`, `alerts`, `orders`, `market`. Token-based auth (optional in dev mode). Ping/pong keep-alive. Broadcast uses `asyncio.gather` with 5s timeout and dead connection cleanup. `market` channel connected to SinopacQuoteManager tick/bidask in paper/live mode. `RealtimeRiskMonitor` monitors intraday drawdown via tick callbacks.

**Logging** (`src/core/logging.py`): Structured logging via structlog. Supports `text` and `json` output formats, configured by `QUANT_LOG_FORMAT`. (`src/logging_config.py` re-exports for backward compat.)

## Frontend Architecture

**Shared package** (`apps/shared/`):
- `src/types/` — TypeScript interfaces matching backend Pydantic schemas (UserRole hierarchy, Portfolio, BacktestResult, etc.)
- `src/api/client.ts` — Platform-agnostic HTTP client with `ClientAdapter` injection (each platform provides its own auth/storage)
- `src/api/ws.ts` — `WSManager` with auto-reconnect and exponential backoff; URL builder injected via `initWs()`
- `src/api/endpoints.ts` — Typed API endpoint definitions (25+ endpoints, 1:1 with backend routes)
- `src/hooks/pollBacktestResult.ts` — Backtest result polling utility
- `src/utils/format.ts` — Number/currency/date formatters

**Platform adapters** (keep platform-specific code out of shared):
- Web: `apps/web/src/core/api/client.ts` — localStorage for API key, browser-relative URLs, Vite proxy
- Android: `apps/android/` — Kotlin + Jetpack Compose + Hilt DI + OkHttp

**Key pattern**: Web barrel files (`@core/api/index.ts`, etc.) re-export from `@quant/shared`. Feature code imports from `@core/*` — never directly from `@quant/shared`.

**Web pages** (11 feature pages):
- Dashboard (`/`) — MarketTicker, NavChart, PositionTable (WebSocket real-time)
- Trading (`/trading`) — Portfolio + Orders + Paper Trading (consolidated)
- Strategies (`/strategies`) — List + start/stop controls
- Research (`/research`) — Alpha + Backtest + Allocation (consolidated)
- Auto-Alpha (`/auto-alpha`) — Auto-Alpha Dashboard + factor allocation + performance
- Risk (`/risk`) — Rules, alerts, kill switch
- Guide (`/guide`) — 7-chapter interactive guide
- Settings (`/settings`) — API key, password, Getting Started
- Admin (`/admin`) — User CRUD, audit logs

**Web UI patterns**:
- Shared `<Card>` component for consistent card styling across all pages
- JWT role extracted from token (not localStorage) via `extractRoleFromJwt()`
- `PageSkeleton` for loading states
- `DataTable` with TanStack React Virtual for virtual scrolling
- `Toast` notification system
- `ErrorBoundary` + `RouteErrorBoundary` for error handling
- Path aliases: `@core`, `@feat`, `@shared`, `@test`

**Android app** (`apps/android/`):
- Kotlin + Jetpack Compose + Material 3
- Hilt DI + OkHttp + Retrofit
- Screens: Dashboard, Backtest, Strategies, Orders, Risk, Settings
- SecureStorage for credentials, WebSocket real-time updates

**Internationalization**: English + Traditional Chinese (en/zh). Context-based i18n with `useT` hook (web). Language preference persisted to localStorage.

**Web frontend tests**: Vitest with jsdom (`apps/web/vitest.config.ts`). Test files colocated (e.g. `BacktestPage.test.tsx`, `RiskPage.test.tsx`, `AdminPage.test.tsx`). E2E tests via Playwright (`apps/web/e2e/`).

## Strategies

11 strategies (9 built-in + 2 pipeline):

| Strategy | File | Logic |
|----------|------|-------|
| Momentum | `strategies/momentum.py` | Price trend-following |
| MA Crossover | `strategies/ma_crossover.py` | Fast/slow MA crossover signals |
| Mean Reversion | `strategies/mean_reversion.py` | Buy oversold, sell overbought |
| RSI Oversold | `strategies/rsi_oversold.py` | Buy when RSI < 30 |
| Multi-Factor | `strategies/multi_factor.py` | Momentum + value + quality, risk-parity weighted |
| Pairs Trading | `strategies/pairs_trading.py` | Statistical arbitrage on correlated instruments |
| Sector Rotation | `strategies/sector_rotation.py` | Rotate capital by relative momentum across sectors |
| Revenue Momentum | `strategies/revenue_momentum.py` | Monthly revenue momentum + price trend confirmation (FinLab-inspired, CAGR 33.5% benchmark) |
| Trust Follow | `strategies/trust_follow.py` | Investment trust net buy + revenue growth (FinLab-inspired, CAGR 31.7% benchmark) |
| Alpha | `src/alpha/strategy.py` | Configurable factor pipeline with neutralization + cost-aware construction |
| Multi-Asset | `src/strategy/multi_asset.py` | Two-layer: tactical allocation → within-class selection → portfolio optimization |

## Infrastructure

**Database**: PostgreSQL 16 (SQLite for development). Migrations managed by Alembic (`migrations/`). 4 migrations: initial schema, users, token revocation, portfolio persistence.

**Docker**: Multi-stage Dockerfile (Python 3.12-slim, non-root user `appuser`). `docker-compose.yml` runs `api` (Uvicorn 2 workers) + `db` (PostgreSQL 16 Alpine) services with health checks and persistent volumes (`pg_data`, `cache_data`).

**CI/CD** (`.github/workflows/ci.yml`) — 9 jobs:
- `backend-lint` — ruff check + mypy strict
- `backend-test` — pytest (1243 tests)
- `web-typecheck` — tsc --noEmit
- `web-test` — vitest (depends on web-typecheck)
- `web-build` — vite build (depends on web-typecheck)
- `shared-test` — vitest for @quant/shared
- `android-build` — Gradle assembleDebug
- `e2e-test` — Playwright chromium
- `release` — GitHub Release + APK artifact (on push to master)

**Scripts**:
- `scripts/benchmark.py` — Performance benchmarking for backtests (quick/full modes)
- `scripts/start.bat` — Windows one-click launcher (backend + web)

## Configuration

All config via `QUANT_` prefixed env vars or `.env` file (see `.env.example`). Defined in `src/core/config.py` as Pydantic Settings. Access via `get_config()` singleton; use `override_config()` in tests. (`src/config.py` re-exports for backward compat.)

Key config:
- `mode`: `"backtest"` (default), `"paper"`, or `"live"` — operating mode
- `data_source`: `"yahoo"` (default) or `"finmind"` — selects data feed
- `data_cache_size`: LRU cache size for in-memory bar data (default 128)
- `finmind_token`: FinMind API token (optional, increases rate limit)
- `tw_lot_size`: Taiwan stock lot size (default 1000 for round lots, set 1 for odd lots)
- `settlement_days`: T+N settlement simulation (default 0 = disabled)
- `max_ffill_days`: Forward-fill limit for missing data (default 5)
- `commission_rate`: Trading commission rate (default 0.001425)
- `default_slippage_bps`: Default slippage in basis points (default 5.0)
- `max_position_pct`: Max single position percentage (default 0.05)
- `max_daily_drawdown_pct`: Max daily drawdown percentage (default 0.03)
- `scheduler_enabled`, `rebalance_cron`: APScheduler config
- `api_key`, `jwt_secret`: Authentication secrets
- `allowed_origins`: CORS origins
- `max_failed_logins` (default 5), `lockout_minutes` (default 15): Account security
- Notification config: `discord_webhook_url`, `line_notify_token`, `telegram_bot_token`, `telegram_chat_id`
- `log_level`, `log_format`: Logging configuration

## Security

- **Authentication**: JWT (HS256) + API Key dual-mode
- **Authorization**: 5-level role hierarchy (viewer < researcher < trader < risk_manager < admin)
- **Password**: PBKDF2-SHA256 hashing
- **Token revocation**: `valid_after` timestamp per user
- **Account lockout**: Configurable failed login limit + lockout duration
- **Rate limiting**: slowapi (memory-backed)
- **Audit**: AuditMiddleware logs all mutations
- **Container**: Non-root Docker user
- **Android**: EncryptedSharedPreferences for credentials
