# Quant Trading System — User Guide

## 1. Introduction

The Quant Trading System is a Python-based quantitative trading platform supporting backtesting, paper trading, and live trading. It features a modular architecture with built-in risk management, a factor library, and a REST/WebSocket API.

**Key features:**
- Event-driven backtesting engine with realistic slippage, commission, and tax simulation
- Built-in technical factor library (momentum, mean reversion, RSI, MA crossover, etc.)
- Declarative risk management with pre-trade checks and kill switch
- REST API + WebSocket for real-time monitoring
- CLI for backtesting, factor analysis, and system management

## 2. Installation

### Prerequisites

- Python 3.12+
- PostgreSQL (optional, for persistent storage)
- Docker (optional, for database setup)

### Setup

```bash
# Clone and install
cd Finance
pip install -e ".[dev]"

# Copy and edit configuration
cp .env.example .env
# Edit .env with your settings

# (Optional) Start database
docker compose up -d db
make migrate
```

### Configuration

All settings are controlled by environment variables with the `QUANT_` prefix. Copy `.env.example` and edit as needed:

| Variable | Default | Description |
|----------|---------|-------------|
| `QUANT_MODE` | `backtest` | Operating mode: `backtest`, `paper`, `live` |
| `QUANT_DATABASE_URL` | `postgresql://...` | Database connection string |
| `QUANT_DATA_SOURCE` | `yahoo` | Data source: `yahoo`, `fubon`, `twse` |
| `QUANT_API_KEY` | `dev-key` | API authentication key |
| `QUANT_LOG_LEVEL` | `INFO` | Logging level |
| `QUANT_COMMISSION_RATE` | `0.001425` | Broker commission (0.1425%) |
| `QUANT_DEFAULT_SLIPPAGE_BPS` | `5.0` | Slippage in basis points |
| `QUANT_MAX_POSITION_PCT` | `0.05` | Max single position weight |
| `QUANT_MAX_DAILY_DRAWDOWN_PCT` | `0.03` | Daily drawdown limit |

## 3. Quick Start

### Run a Backtest

```bash
# Momentum strategy on US tech stocks, weekly rebalance
python -m src.cli.main backtest \
    --strategy momentum \
    -u AAPL -u MSFT -u GOOGL -u AMZN -u META \
    --start 2023-01-01 \
    --end 2024-12-31 \
    --rebalance weekly \
    --validate
```

**Options:**

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--strategy` | `-s` | `momentum` | Strategy name |
| `--universe` | `-u` | AAPL, MSFT, GOOGL, AMZN, META | Stock symbols (repeat for multiple) |
| `--start` | | `2020-01-01` | Start date |
| `--end` | | `2024-12-31` | End date |
| `--cash` | `-c` | `10000000` | Initial capital |
| `--rebalance` | `-r` | `weekly` | Rebalance frequency: `daily`, `weekly`, `monthly` |
| `--slippage` | | `5.0` | Slippage in basis points |
| `--validate` | `-v` | `False` | Run backtest validation checks |
| `--log-level` | `-l` | `INFO` | Log verbosity |

### Example Output

```
═══ momentum_12_1 Backtest Result ═══
Period:        2023-01-03 ~ 2024-12-30
Initial Cash:  $10,000,000
Final NAV:     $11,694,031

Total Return:  +16.94%
Annual Return: +8.19%
Volatility:    7.73%
Sharpe Ratio:  1.06
Sortino Ratio: 0.99
Calmar Ratio:  1.02

Max Drawdown:  8.04%
Max DD Days:   87

Total Trades:  54
Win Rate:      64.7%
Total Comm.:   $25,962
```

### View Factor Values

```bash
python -m src.cli.main factors AAPL
```

Displays current factor values for a given symbol: momentum, mean reversion (Z-score), volatility, RSI, and MA crossover.

### Check System Status

```bash
python -m src.cli.main status
```

Shows current configuration: mode, data source, API endpoint, commission rate, and risk limits.

## 4. Built-in Strategies

### Momentum (12-1)

Classic cross-sectional momentum strategy.

- **Logic:** Buy stocks with the highest 12-month returns, skipping the most recent month (to avoid short-term reversal).
- **Parameters:** `lookback=252`, `skip=21`, `max_holdings=10`
- **Allocation:** Signal-weighted, max 10% per position, 95% total exposure.
- **Name:** `momentum` or `momentum_12_1`

### Mean Reversion

Statistical mean reversion strategy.

- **Logic:** Buy stocks whose price has deviated significantly below their 20-day moving average (Z-score > 1.5 standard deviations below).
- **Parameters:** `lookback=20`, `z_threshold=1.5`
- **Allocation:** Signal-weighted, max 8% per position, 90% total exposure, long only.
- **Name:** `mean_reversion`

## 5. Starting the API Server

```bash
# Development mode (with hot reload)
make dev

# Production mode
make api

# Or via CLI
python -m src.cli.main server --host 0.0.0.0 --port 8000
```

Once started:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Authentication

All API requests (except health check) require authentication:

```bash
# API Key authentication
curl -H "X-API-Key: dev-key" http://localhost:8000/api/v1/system/status
```

## 6. Risk Management

The system enforces the following risk rules on every order before execution:

| Rule | Default | Description |
|------|---------|-------------|
| Max Position Weight | 10% | Single position cannot exceed 10% of NAV |
| Max Order Notional | 10% | Single order value cannot exceed 10% of NAV |
| Daily Drawdown Limit | 3% | No new orders when daily loss exceeds 3% |
| Fat Finger Check | 5% | Rejects orders with price deviating >5% from market |
| Max Daily Trades | 100 | Maximum 100 trades per day |
| Max Order vs ADV | 10% | Order size cannot exceed 10% of average daily volume |

**Kill Switch:** Automatically triggered at 5% daily drawdown — cancels all pending orders and stops all strategies.

## 7. Performance Metrics

The backtest engine computes the following metrics:

| Metric | Description |
|--------|-------------|
| Total Return | Cumulative return over the backtest period |
| Annual Return | Annualized return (assuming 252 trading days/year) |
| Sharpe Ratio | Risk-adjusted return (annual return / volatility) |
| Sortino Ratio | Downside risk-adjusted return |
| Calmar Ratio | Annual return / max drawdown |
| Max Drawdown | Largest peak-to-trough decline |
| Max DD Duration | Longest drawdown period in days |
| Volatility | Annualized standard deviation of daily returns |
| Win Rate | Percentage of profitable round-trip trades |
| Turnover | Annualized portfolio turnover |

### Backtest Validation

When `--validate` is enabled, the following checks are performed:

- **Non-zero trades:** At least 1 trade was executed
- **NAV continuity:** No single-day NAV jump exceeds a reasonable threshold
- **Return sanity:** Annual return is within a believable range
- **Sharpe sanity:** Sharpe ratio is within a believable range
- **Cost impact:** Transaction costs are reasonable relative to returns

## 8. Factor Library

Available technical factors for strategy development:

| Factor | Function | Key Parameters | Output |
|--------|----------|----------------|--------|
| Momentum | `momentum()` | `lookback=252, skip=21` | 12-1 month return ratio |
| Mean Reversion | `mean_reversion()` | `lookback=20` | Z-score (inverted: low = buy) |
| Volatility | `volatility()` | `lookback=20` | Annualized volatility |
| RSI | `rsi()` | `period=14` | Relative Strength Index (0-100) |
| MA Crossover | `moving_average_crossover()` | `fast=10, slow=50` | Fast/slow MA ratio - 1 |
| Volume-Price Trend | `volume_price_trend()` | `lookback=20` | Price-volume correlation |

## 9. Transaction Cost Model

The simulation engine models Taiwan stock market costs by default:

| Cost Type | Default | Description |
|-----------|---------|-------------|
| Commission | 0.1425% | Applied to both buy and sell |
| Tax | 0.3% | Applied to sell orders only (Taiwan securities transaction tax) |
| Slippage | 5 bps | Buy price adjusted up, sell price adjusted down |

All costs are configurable via CLI flags or environment variables.
