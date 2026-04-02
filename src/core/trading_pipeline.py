"""Shared trading pipeline — one-bar processing logic used by both backtest and live.

U1: 統一 execution 路徑。BacktestEngine 和 paper/live pipeline 共用同一條代碼路徑。
- execute_one_bar: 策略 → 權重 → 訂單 → 風控 → 執行 → 更新持倉
- execute_from_weights: 接受已計算的權重（pipeline 需要先 log 權重再執行）
"""

from __future__ import annotations

import logging
import math
from decimal import Decimal
from typing import Any

from src.core.models import Instrument, Portfolio, Trade, TradingInvariantError
from src.execution.broker.base import OrderExecutor
from src.execution.broker.simulated import SimBroker
from src.execution.oms import apply_trades
from src.portfolio.overlay import OverlayConfig, apply_overlay
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
    broker: OrderExecutor | None = None,
    sim_broker: SimBroker | None = None,  # deprecated, use broker=
    instruments: dict[str, Instrument] | None = None,
    available_cash: Decimal | None = None,
    market_lot_sizes: dict[str, int] | None = None,
    fractional_shares: bool = False,
    timestamp: Any = None,
    check_invariants: bool = False,
    overlay_config: OverlayConfig | None = None,
    market_returns: Any = None,
    sector_map: dict[str, str] | None = None,
) -> list[Trade]:
    """Execute one bar: strategy → weights → orders → risk → broker → apply_trades.

    Used by BacktestEngine (with broker=SimBroker) and paper/live pipeline
    (with broker=ExecutionService).
    """
    # Backward compatibility: sim_broker → broker
    if sim_broker is not None and broker is None:
        broker = sim_broker

    # 1. Strategy produces target weights
    try:
        target_weights = strategy.on_bar(ctx)
    except Exception:
        logger.exception("strategy.on_bar() crashed — skipping bar")
        return []
    if not target_weights:
        return []

    # Filter NaN/inf
    target_weights = {
        k: v for k, v in target_weights.items()
        if isinstance(v, (int, float)) and math.isfinite(v)
    }

    return execute_from_weights(
        target_weights=target_weights,
        portfolio=portfolio,
        risk_engine=risk_engine,
        prices=prices,
        volumes=volumes,
        current_bars=current_bars,
        broker=broker,
        instruments=instruments,
        available_cash=available_cash,
        market_lot_sizes=market_lot_sizes,
        fractional_shares=fractional_shares,
        timestamp=timestamp,
        check_invariants=check_invariants,
        overlay_config=overlay_config,
        market_returns=market_returns,
        sector_map=sector_map,
    )


def execute_from_weights(
    target_weights: dict[str, float],
    portfolio: Portfolio,
    risk_engine: RiskEngine,
    prices: dict[str, Decimal],
    volumes: dict[str, Decimal] | None = None,
    current_bars: dict[str, dict[str, Any]] | None = None,
    broker: OrderExecutor | None = None,
    instruments: dict[str, Instrument] | None = None,
    available_cash: Decimal | None = None,
    market_lot_sizes: dict[str, int] | None = None,
    fractional_shares: bool = False,
    timestamp: Any = None,
    check_invariants: bool = False,
    overlay_config: OverlayConfig | None = None,
    market_returns: Any = None,
    sector_map: dict[str, str] | None = None,
) -> list[Trade]:
    """Execute from pre-computed weights: orders → risk → broker → apply_trades.

    Used by paper/live pipeline when weights need to be logged before execution.
    Also called internally by execute_one_bar().

    Args:
        target_weights: {symbol: weight} from strategy.
        broker: Any object with execute(orders, current_bars, timestamp) → list[Trade].
                SimBroker (backtest), ExecutionService (paper/live), or None.
        overlay_config: If provided, apply portfolio overlay before weights_to_orders.
        market_returns: Market index daily returns for beta calculation.
        sector_map: {symbol: sector} for sector cap enforcement.
    """
    if not target_weights:
        return []

    # 0. Portfolio overlay (after weights, before orders)
    if overlay_config is not None:
        target_weights = apply_overlay(
            weights=target_weights,
            prices=prices,
            market_returns=market_returns,
            sector_map=sector_map,
            config=overlay_config,
        )
        if not target_weights:
            return []

    # 1. Convert weights to orders
    orders = weights_to_orders(
        target_weights,
        portfolio,
        prices,
        instruments=instruments,
        available_cash=available_cash,
        market_lot_sizes=market_lot_sizes,
        fractional_shares=fractional_shares,
        volumes=volumes,
    )
    if not orders:
        return []

    # AL-3 I14: 訂單數量不得超過持倉股票數 × 2 + 5（防止訂單爆炸）
    if len(orders) > len(target_weights) * 2 + 5:
        raise TradingInvariantError(
            f"I14: Order count {len(orders)} >> weight count {len(target_weights)}"
        )

    # 2. Risk check (batch with projected portfolio)
    market_state = MarketState(
        prices=prices,
        daily_volumes=volumes if volumes is not None else {},
    )
    approved = risk_engine.check_orders(orders, portfolio, market_state)
    if not approved:
        return []

    # 3. Execute via broker (SimBroker, ExecutionService, or None)
    if broker is None:
        return []

    # H2: SimBroker 需要 current_bars，ExecutionService 不需要
    from src.execution.broker.simulated import SimBroker as _SimBroker
    if isinstance(broker, _SimBroker) and current_bars is None:
        logger.error("SimBroker requires current_bars but got None")
        return []

    trades = broker.execute(approved, current_bars, timestamp)

    # 4. Apply trades to portfolio
    if trades:
        apply_trades(portfolio, trades, check_invariants=check_invariants)

    return trades
