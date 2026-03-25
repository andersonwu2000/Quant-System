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
from src.config import get_config
from src.data.feed import HistoricalFeed
from src.data.sources import create_feed
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

    cfg = get_config()
    source = cfg.data_source
    source_kwargs: dict[str, object] = {}
    if source == "finmind":
        source_kwargs["token"] = cfg.finmind_token

    warmup_days = 400
    warmup_start = (
        pd.Timestamp(base_config.start) - pd.tseries.offsets.BDay(warmup_days)
    ).strftime("%Y-%m-%d")

    data_feed = create_feed(source, base_config.universe, **source_kwargs)

    # Load raw bar data for all symbols
    raw_bars: dict[str, pd.DataFrame] = {}
    for symbol in base_config.universe:
        df = data_feed.get_bars(symbol, start=warmup_start, end=base_config.end)
        if not df.empty:
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
    """
    from decimal import Decimal

    from src.backtest.analytics import compute_analytics
    from src.domain.models import Instrument, Portfolio
    from src.execution.oms import apply_trades
    from src.execution.sim import SimBroker, SimConfig
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
