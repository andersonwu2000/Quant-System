"""Shared trading pipeline — one-bar processing logic used by both backtest and live.

This module extracts the common strategy → orders → risk → broker → apply_trades
flow so that BacktestEngine and any future live execution path share one code path.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from src.core.models import Instrument, Portfolio, Trade
from src.execution.broker.simulated import SimBroker
from src.execution.oms import apply_trades
from src.risk.engine import RiskEngine
from src.risk.rules import MarketState
from src.strategy.base import Context, Strategy
from src.strategy.engine import weights_to_orders

logger = logging.getLogger(__name__)


def execute_one_bar(
    strategy: Strategy,
    ctx: Context,
    portfolio: Portfolio,
    risk_engine: RiskEngine,
    prices: dict[str, Decimal],
    volumes: dict[str, Decimal] | None = None,
    current_bars: dict[str, dict[str, Any]] | None = None,
    sim_broker: SimBroker | None = None,
    instruments: dict[str, Instrument] | None = None,
    available_cash: Decimal | None = None,
    market_lot_sizes: dict[str, int] | None = None,
    fractional_shares: bool = False,
    timestamp: Any = None,
) -> list[Trade]:
    """Execute one bar of the trading loop.

    Shared by BacktestEngine (and potentially live scheduler in the future).

    Flow: strategy.on_bar() → weights_to_orders() → risk_engine.check_orders()
          → sim_broker.execute() → apply_trades()

    Args:
        strategy: Strategy instance.
        ctx: Context with data feed + portfolio.
        portfolio: Current portfolio (mutated in place via apply_trades).
        risk_engine: Risk engine for pre-trade checks.
        prices: {symbol: Decimal price} for order generation.
        volumes: {symbol: Decimal volume} for risk engine MarketState.
        current_bars: {symbol: bar_dict} for SimBroker (backtest mode).
        sim_broker: SimBroker instance (backtest mode). If None, returns [].
        instruments: Instrument registry lookup.
        available_cash: Cash cap for buy orders (T+N settlement).
        market_lot_sizes: Symbol suffix → lot size mapping.
        fractional_shares: If True, allow fractional share orders.
        timestamp: Bar timestamp passed to SimBroker.execute().

    Returns:
        List of executed trades (empty if no action taken).
    """
    # 1. Strategy produces target weights
    target_weights = strategy.on_bar(ctx)
    if not target_weights:
        return []

    # 2. Convert weights to orders
    orders = weights_to_orders(
        target_weights,
        portfolio,
        prices,
        instruments=instruments,
        available_cash=available_cash,
        market_lot_sizes=market_lot_sizes,
        fractional_shares=fractional_shares,
    )
    if not orders:
        return []

    # 3. Risk check
    market_state = MarketState(
        prices=prices,
        daily_volumes=volumes if volumes is not None else {},
    )
    approved = risk_engine.check_orders(orders, portfolio, market_state)
    if not approved:
        return []

    # 4. Execute via SimBroker (backtest) or return empty (no broker)
    if sim_broker is not None and current_bars is not None:
        trades = sim_broker.execute(approved, current_bars, timestamp)
    else:
        # No broker provided — caller is responsible for execution
        return []

    # 5. Apply trades to portfolio
    if trades:
        apply_trades(portfolio, trades)

    return trades
