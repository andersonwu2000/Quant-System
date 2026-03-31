"""
Synthetic Data Stress Test — 對歷史數據施加壓力情境，測試策略韌性。

預定義情境：
- BEAR_MARKET: 隨機 20% 的交易日套用 -2x 報酬
- HIGH_VOLATILITY: 波動率放大 3 倍
- FLASH_CRASH: 在隨機時點注入 -10% 單日暴跌
- REGIME_CHANGE: 前半段正常，後半段反轉相關性
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from src.backtest.analytics import BacktestResult
from src.backtest.engine import BacktestConfig, BacktestEngine
from src.data.feed import HistoricalFeed
from src.strategy.base import Strategy

logger = logging.getLogger(__name__)


@dataclass
class StressScenario:
    """壓力情境定義。"""

    name: str
    returns_modifier: Callable[[pd.DataFrame, np.random.Generator], pd.DataFrame]


def _bear_market_modifier(
    df: pd.DataFrame, rng: np.random.Generator,
) -> pd.DataFrame:
    """隨機 20% 的交易日套用 -2x 報酬倍率。"""
    result = df.copy()
    n_rows = len(result)
    n_bear = max(1, int(n_rows * 0.2))
    bear_indices = rng.choice(n_rows, size=n_bear, replace=False)

    for col in ["open", "high", "low", "close"]:
        if col not in result.columns:
            continue
        returns = result[col].pct_change()
        # Apply -2x multiplier to selected days
        values = result[col].values.copy()
        ret_values = returns.values
        for idx in bear_indices:
            if idx == 0:
                continue
            original_ret = float(ret_values[idx])
            stressed_ret = original_ret * -2.0
            values[idx] = values[idx - 1] * (1.0 + stressed_ret)
        result[col] = values

    # Ensure no negative prices
    for col in ["open", "high", "low", "close"]:
        if col in result.columns:
            result[col] = result[col].clip(lower=0.01)

    return result


def _high_volatility_modifier(
    df: pd.DataFrame, rng: np.random.Generator,
) -> pd.DataFrame:
    """波動率放大 3 倍。"""
    result = df.copy()
    vol_multiplier = 3.0

    for col in ["open", "high", "low", "close"]:
        if col not in result.columns:
            continue
        returns = result[col].pct_change().fillna(0.0)
        mean_ret = returns.mean()
        # Scale deviations from mean by vol_multiplier
        stressed_returns = mean_ret + (returns - mean_ret) * vol_multiplier

        # Reconstruct prices from stressed returns
        prices = [float(result[col].iloc[0])]
        for ret in stressed_returns.iloc[1:]:
            prices.append(prices[-1] * (1.0 + ret))
        result[col] = prices

    for col in ["open", "high", "low", "close"]:
        if col in result.columns:
            result[col] = result[col].clip(lower=0.01)

    return result


def _flash_crash_modifier(
    df: pd.DataFrame, rng: np.random.Generator,
) -> pd.DataFrame:
    """在隨機時點注入 -10% 單日暴跌（約 3 次）。"""
    result = df.copy()
    n_rows = len(result)
    n_crashes = min(3, max(1, n_rows // 60))
    crash_indices = rng.choice(
        range(1, n_rows), size=n_crashes, replace=False,
    )

    for col in ["open", "high", "low", "close"]:
        if col not in result.columns:
            continue
        values = result[col].values.copy()
        for idx in crash_indices:
            values[idx] = values[idx - 1] * 0.90
        result[col] = values

    for col in ["open", "high", "low", "close"]:
        if col in result.columns:
            result[col] = result[col].clip(lower=0.01)

    return result


def _regime_change_modifier(
    df: pd.DataFrame, rng: np.random.Generator,
) -> pd.DataFrame:
    """前半段正常，後半段反轉報酬。"""
    result = df.copy()
    n_rows = len(result)
    mid = n_rows // 2

    for col in ["open", "high", "low", "close"]:
        if col not in result.columns:
            continue
        returns = result[col].pct_change().fillna(0.0)
        # Invert returns in second half
        inverted_returns = returns.copy()
        inverted_returns.iloc[mid:] = -returns.iloc[mid:]

        # Reconstruct prices
        prices = [float(result[col].iloc[0])]
        for ret in inverted_returns.iloc[1:]:
            prices.append(prices[-1] * (1.0 + ret))
        result[col] = prices

    for col in ["open", "high", "low", "close"]:
        if col in result.columns:
            result[col] = result[col].clip(lower=0.01)

    return result


# Predefined scenarios
BEAR_MARKET = StressScenario(
    name="bear_market",
    returns_modifier=_bear_market_modifier,
)

HIGH_VOLATILITY = StressScenario(
    name="high_volatility",
    returns_modifier=_high_volatility_modifier,
)

FLASH_CRASH = StressScenario(
    name="flash_crash",
    returns_modifier=_flash_crash_modifier,
)

REGIME_CHANGE = StressScenario(
    name="regime_change",
    returns_modifier=_regime_change_modifier,
)

ALL_SCENARIOS: list[StressScenario] = [
    BEAR_MARKET, HIGH_VOLATILITY, FLASH_CRASH, REGIME_CHANGE,
]


# ── Taiwan historical stress periods ──────────────────────────────
# These use REAL data (no modification) — just backtest within the crisis window.


@dataclass
class HistoricalStressPeriod:
    """A real historical crisis period for backtest."""
    name: str
    start: str
    end: str
    description: str
    benchmark: str = "0050.TW"  # compare against


TW_STRESS_PERIODS = [
    HistoricalStressPeriod("2008_financial_crisis", "2008-09-01", "2009-03-31", "金融海嘯 — 台股跌 46%"),
    HistoricalStressPeriod("2015_china_crash", "2015-06-01", "2015-08-31", "中國股災 — 急跌 28%"),
    HistoricalStressPeriod("2018_trade_war", "2018-10-01", "2018-12-31", "中美貿易戰 — 外資大量賣超"),
    HistoricalStressPeriod("2020_covid", "2020-02-01", "2020-04-30", "COVID 崩盤 — 跌 30% 後 V 轉"),
    HistoricalStressPeriod("2021_tw_outbreak", "2021-05-01", "2021-06-30", "本土疫情 — 單週跌 8.5%"),
    HistoricalStressPeriod("2022_rate_hike", "2022-01-01", "2022-10-31", "升息通膨 — 緩慢下跌 25%"),
]

# Cost sensitivity scenarios
COST_SCENARIOS = {
    "base":      {"commission_rate": 0.001425, "tax_rate": 0.003, "slippage_bps": 5},
    "2x_cost":   {"commission_rate": 0.00285,  "tax_rate": 0.003, "slippage_bps": 10},
    "3x_slip":   {"commission_rate": 0.001425, "tax_rate": 0.003, "slippage_bps": 15},
    "day_trade":  {"commission_rate": 0.001425, "tax_rate": 0.0015, "slippage_bps": 5},
    "worst":     {"commission_rate": 0.00285,  "tax_rate": 0.003, "slippage_bps": 20},
}


def run_stress_test(
    strategy_factory: Callable[[], Strategy],
    base_config: BacktestConfig,
    scenarios: list[StressScenario] | None = None,
    seed: int = 42,
) -> dict[str, BacktestResult]:
    """對每個壓力情境修改數據並執行回測。

    Args:
        strategy_factory: 零引數 callable，回傳新的 Strategy 實例。
        base_config: 基礎回測設定。
        scenarios: 壓力情境清單；None 則使用所有預定義情境。
        seed: 隨機種子。

    Returns:
        dict[scenario_name, BacktestResult]。
    """
    if scenarios is None:
        scenarios = ALL_SCENARIOS

    rng = np.random.default_rng(seed)
    results: dict[str, BacktestResult] = {}

    # First, load data once using the standard mechanism
    engine = BacktestEngine()

    # Load from DataCatalog (local parquets, no Yahoo download)
    from src.data.data_catalog import get_catalog
    catalog = get_catalog()

    raw_bars: dict[str, pd.DataFrame] = {}
    for symbol in base_config.universe:
        df = catalog.get("price", symbol)
        if not df.empty and "close" in df.columns:
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            raw_bars[symbol] = df

    if not raw_bars:
        logger.warning("No data loaded for stress test")
        return results

    for scenario in scenarios:
        logger.info("Running stress scenario: %s", scenario.name)

        try:
            # Build a HistoricalFeed with modified data
            feed = HistoricalFeed()
            for symbol, df in raw_bars.items():
                modified_df = scenario.returns_modifier(df.copy(), rng)
                feed.load(symbol, modified_df)

            # Run backtest using engine with modified feed
            strategy = strategy_factory()
            result = _run_with_feed(engine, strategy, base_config, feed)
            results[scenario.name] = result

            logger.info(
                "Scenario %s: sharpe=%.3f return=%.2f%% maxdd=%.2f%%",
                scenario.name, result.sharpe,
                result.annual_return * 100,
                result.max_drawdown * 100,
            )
        except Exception:
            logger.warning(
                "Stress scenario %s failed", scenario.name, exc_info=True,
            )
            continue

    return results


def run_historical_stress(
    strategy_factory: Callable[[], Strategy],
    universe: list[str],
    periods: list[HistoricalStressPeriod] | None = None,
    initial_cash: float = 10_000_000,
) -> dict[str, dict]:
    """Run strategy through real historical crisis periods.

    Uses actual market data (no synthetic modification).
    Compares against 0050.TW benchmark for each period.

    Returns {period_name: {strategy: BacktestResult, benchmark_return: float, ...}}
    """
    if periods is None:
        periods = TW_STRESS_PERIODS

    results: dict[str, dict] = {}
    engine = BacktestEngine()

    # Pre-check which symbols have data in each period
    from src.data.data_catalog import get_catalog
    catalog = get_catalog()

    for period in periods:
        logger.info("Historical stress: %s (%s to %s)", period.name, period.start, period.end)
        try:
            # Filter universe to symbols with data in this period
            period_universe = []
            for sym in universe:
                df = catalog.get("price", sym)
                if df.empty or "close" not in df.columns:
                    continue
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)
                period_data = df.loc[period.start:period.end]
                if len(period_data) >= 20:  # at least 20 trading days
                    period_universe.append(sym)

            if len(period_universe) < 20:
                results[period.name] = {
                    "description": period.description,
                    "error": f"Only {len(period_universe)} symbols with data in {period.start}~{period.end} (need 20)",
                }
                continue

            logger.info("  %d/%d symbols have data for %s", len(period_universe), len(universe), period.name)

            config = BacktestConfig(
                universe=period_universe,
                start=period.start,
                end=period.end,
                initial_cash=initial_cash,
                rebalance_freq="monthly",
            )
            strategy = strategy_factory()
            result = engine.run(strategy, config)

            # Benchmark: 0050.TW buy-and-hold return
            benchmark_ret = _benchmark_return(period.benchmark, period.start, period.end)

            results[period.name] = {
                "description": period.description,
                "start": period.start,
                "end": period.end,
                "cagr": result.annual_return,
                "sharpe": result.sharpe,
                "max_drawdown": result.max_drawdown,
                "total_return": float(result.nav_series.iloc[-1] / result.nav_series.iloc[0] - 1) if len(result.nav_series) > 1 else 0,
                "benchmark_return": benchmark_ret,
                "excess_return": (float(result.nav_series.iloc[-1] / result.nav_series.iloc[0] - 1) if len(result.nav_series) > 1 else 0) - benchmark_ret,
                "result": result,
            }
            logger.info("  %s: return=%.1f%% benchmark=%.1f%% MDD=%.1f%%",
                        period.name,
                        results[period.name]["total_return"] * 100,
                        benchmark_ret * 100,
                        result.max_drawdown * 100)
        except Exception as e:
            logger.warning("Historical stress %s failed: %s", period.name, e)
            results[period.name] = {"description": period.description, "error": str(e)}

    return results


def run_cost_sensitivity(
    strategy_factory: Callable[[], Strategy],
    universe: list[str],
    start: str = "2018-01-01",
    end: str = "2025-12-31",
    scenarios: dict[str, dict] | None = None,
    initial_cash: float = 10_000_000,
) -> dict[str, dict]:
    """Run strategy with different cost assumptions.

    Returns {scenario_name: {sharpe, cagr, max_drawdown, total_cost, cost_ratio}}
    """
    if scenarios is None:
        scenarios = COST_SCENARIOS

    results: dict[str, dict] = {}
    engine = BacktestEngine()

    for name, costs in scenarios.items():
        logger.info("Cost scenario: %s", name)
        try:
            config = BacktestConfig(
                universe=universe,
                start=start,
                end=end,
                initial_cash=initial_cash,
                commission_rate=costs["commission_rate"],
                tax_rate=costs["tax_rate"],
                slippage_bps=costs["slippage_bps"],
                rebalance_freq="monthly",
            )
            strategy = strategy_factory()
            result = engine.run(strategy, config)

            n_years = max(len(result.nav_series) / 252, 0.5)
            annual_cost = result.total_commission / initial_cash / n_years
            gross_alpha = result.annual_return + annual_cost
            cost_ratio = annual_cost / gross_alpha if gross_alpha > 0 else 1.0

            results[name] = {
                "sharpe": result.sharpe,
                "cagr": result.annual_return,
                "max_drawdown": result.max_drawdown,
                "annual_cost_pct": annual_cost * 100,
                "cost_ratio": cost_ratio,
                "result": result,
            }
            logger.info("  %s: Sharpe=%.3f CAGR=%.1f%% cost_ratio=%.0f%%",
                        name, result.sharpe, result.annual_return * 100, cost_ratio * 100)
        except Exception as e:
            logger.warning("Cost scenario %s failed: %s", name, e)
            results[name] = {"error": str(e)}

    return results


def _benchmark_return(symbol: str, start: str, end: str) -> float:
    """Get buy-and-hold return for a benchmark symbol."""
    try:
        from src.data.data_catalog import get_catalog
        catalog = get_catalog()
        from datetime import date
        df = catalog.get("price", symbol, start=date.fromisoformat(start), end=date.fromisoformat(end))
        if df.empty or "close" not in df.columns or len(df) < 2:
            return 0.0
        return float(df["close"].iloc[-1] / df["close"].iloc[0] - 1)
    except Exception:
        return 0.0


def generate_stress_report(
    historical: dict[str, dict],
    cost: dict[str, dict],
    output_path: str = "docs/research/stress_test_report.md",
) -> str:
    """Generate markdown stress test report."""
    from pathlib import Path
    import time

    lines = [
        "# Stress Test Report",
        "",
        f"> Generated: {time.strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 1. Historical Crisis Periods",
        "",
        "| Period | Description | Return | Benchmark | Excess | MDD | Sharpe |",
        "|--------|-------------|-------:|----------:|-------:|----:|-------:|",
    ]

    for name, data in historical.items():
        if "error" in data:
            lines.append(f"| {name} | {data['description']} | ERROR | — | — | — | — |")
            continue
        ret = data.get("total_return", 0) * 100
        bench = data.get("benchmark_return", 0) * 100
        excess = data.get("excess_return", 0) * 100
        mdd = data.get("max_drawdown", 0) * 100
        sharpe = data.get("sharpe", 0)
        lines.append(f"| {name} | {data['description']} | {ret:+.1f}% | {bench:+.1f}% | {excess:+.1f}% | {mdd:.1f}% | {sharpe:.2f} |")

    lines.extend([
        "",
        "## 2. Cost Sensitivity",
        "",
        "| Scenario | Sharpe | CAGR | MDD | Annual Cost | Cost/Alpha |",
        "|----------|-------:|-----:|----:|------------:|-----------:|",
    ])

    for name, data in cost.items():
        if "error" in data:
            lines.append(f"| {name} | ERROR | — | — | — | — |")
            continue
        lines.append(
            f"| {name} | {data['sharpe']:.3f} | {data['cagr']:+.1f}% | "
            f"{data['max_drawdown']:.1f}% | {data['annual_cost_pct']:.2f}% | "
            f"{data['cost_ratio']:.0f}% |"
        )

    lines.extend(["", "---", "*Auto-generated stress test report*"])

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def run_correlation_stress(
    universe: list[str],
    start: str = "2018-01-01",
    end: str = "2025-12-31",
    window: int = 60,
) -> dict[str, Any]:
    """Analyze rolling pairwise correlation of universe.

    Finds periods where correlation is highest (diversification fails).

    Returns {peak_date, peak_corr, avg_corr, min_corr, corr_series}
    """
    from src.data.data_catalog import get_catalog

    catalog = get_catalog()
    returns_dict: dict[str, pd.Series] = {}
    for sym in universe[:50]:  # cap at 50 for speed
        df = catalog.get("price", sym)
        if df.empty or "close" not in df.columns:
            continue
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        rets = df["close"].pct_change().dropna()
        rets = rets.loc[start:end]
        if len(rets) >= window:
            returns_dict[sym] = rets

    if len(returns_dict) < 10:
        return {"error": f"Only {len(returns_dict)} symbols with returns data"}

    ret_df = pd.DataFrame(returns_dict).dropna(how="all")

    # Rolling average pairwise correlation
    corr_series = []
    dates = ret_df.index[window:]
    for i in range(window, len(ret_df)):
        win = ret_df.iloc[i - window:i]
        corr_matrix = win.corr()
        # Average off-diagonal correlation
        n = len(corr_matrix)
        if n < 2:
            continue
        avg_corr = (corr_matrix.values.sum() - n) / (n * (n - 1))
        corr_series.append({"date": ret_df.index[i], "avg_corr": avg_corr})

    if not corr_series:
        return {"error": "Insufficient data for correlation analysis"}

    corr_df = pd.DataFrame(corr_series).set_index("date")
    peak_idx = corr_df["avg_corr"].idxmax()
    return {
        "peak_date": str(peak_idx.date()),
        "peak_corr": float(corr_df["avg_corr"].max()),
        "avg_corr": float(corr_df["avg_corr"].mean()),
        "min_corr": float(corr_df["avg_corr"].min()),
        "n_symbols": len(returns_dict),
    }


def _run_with_feed(
    engine: BacktestEngine,
    strategy: Strategy,
    config: BacktestConfig,
    feed: HistoricalFeed,
) -> BacktestResult:
    """用預載入的 feed 執行回測（繞過 engine 內部資料載入）。

    這是一個簡化版本：直接呼叫 engine.run()，
    因為 engine._load_data 會重新下載。
    我們改為直接使用 analytics 來處理。

    Note: rebalance_freq from config is intentionally ignored here.
    Stress tests call strategy.on_bar() every trading day to maximize
    stress exposure. The strategy itself controls rebalancing via its
    internal logic (e.g. monthly cache in trust_follow).
    """
    from decimal import Decimal

    from src.backtest.analytics import compute_analytics
    from src.core.models import Instrument, Portfolio
    from src.execution.oms import apply_trades
    from src.execution.broker.simulated import SimBroker, SimConfig
    from src.instrument.registry import InstrumentRegistry
    from src.risk.engine import RiskEngine
    from src.strategy.base import Context
    from src.strategy.engine import weights_to_orders

    # Build matrices
    universe = [s for s in config.universe if s in feed.get_universe()]
    if not universe:
        raise ValueError("No data loaded for any symbol in universe")

    # Trading dates
    all_dates: set[pd.Timestamp] = set()
    for symbol in universe:
        df = feed.get_bars(symbol)
        all_dates |= set(df.index)
    start = pd.Timestamp(config.start)
    end = pd.Timestamp(config.end)
    trading_dates = sorted(d for d in all_dates if start <= d <= end)

    if not trading_dates:
        raise ValueError("No trading dates in range")

    # Setup
    sim_broker = SimBroker(SimConfig(
        slippage_bps=config.slippage_bps,
        commission_rate=config.commission_rate,
        tax_rate=config.tax_rate,
    ))
    risk_engine = RiskEngine(config.risk_rules)
    portfolio = Portfolio(
        cash=Decimal(str(config.initial_cash)),
        initial_cash=Decimal(str(config.initial_cash)),
    )
    registry = InstrumentRegistry()
    instruments: dict[str, Instrument] = {}
    for sym in universe:
        instruments[sym] = registry.get_or_create(sym)

    # Build price matrix
    price_frames: dict[str, pd.Series] = {}
    for symbol in universe:
        df = feed.get_bars(symbol)
        if not df.empty:
            price_frames[symbol] = df["close"]
    price_matrix = pd.DataFrame(price_frames).sort_index().ffill(limit=config.max_ffill_days)

    nav_history: list[dict[str, object]] = []

    for bar_date in trading_dates:
        dt = bar_date.to_pydatetime() if hasattr(bar_date, "to_pydatetime") else bar_date
        feed.set_current_date(dt)

        # Get prices
        ts = pd.Timestamp(bar_date)
        idx = price_matrix.index.searchsorted(ts, side="right") - 1
        if idx < 0:
            continue
        row = price_matrix.iloc[idx]
        prices: dict[str, Decimal] = {}
        for sym in universe:
            if sym in row.index and not np.isnan(row[sym]):
                prices[sym] = Decimal(str(round(float(row[sym]), 4)))

        portfolio.update_market_prices(prices)
        portfolio.as_of = dt
        if portfolio.nav_sod == 0:
            portfolio.nav_sod = portfolio.nav

        ctx = Context(feed=feed, portfolio=portfolio, current_time=dt)
        target_weights = strategy.on_bar(ctx)

        if target_weights:
            orders = weights_to_orders(target_weights, portfolio, prices, instruments=instruments)
            from src.risk.rules import MarketState
            market_state = MarketState(prices=prices, daily_volumes={})
            approved = risk_engine.check_orders(orders, portfolio, market_state)
            bars_dict: dict[str, dict[str, object]] = {}
            for s, p in prices.items():
                bars_dict[s] = {"close": float(p), "volume": 1e8, "prev_close": None}
            trades = sim_broker.execute(approved, bars_dict, dt)
            if trades:
                portfolio = apply_trades(portfolio, trades)

        nav_history.append({
            "date": dt,
            "nav": float(portfolio.nav),
            "cash": float(portfolio.cash),
        })
        portfolio.nav_sod = portfolio.nav

    nav_df = pd.DataFrame(nav_history).set_index("date")
    return compute_analytics(
        nav_series=nav_df["nav"],
        initial_cash=config.initial_cash,
        trades=sim_broker.trade_log,
        strategy_name=strategy.name(),
        config=config,
    )
