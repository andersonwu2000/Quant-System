"""AlphaExecutor — convert decisions to orders, run risk checks, and submit."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal

import pandas as pd

from src.alpha.auto.config import AutoAlphaConfig
from src.alpha.auto.decision import DecisionResult
from src.alpha.pipeline import AlphaConfig, AlphaPipeline, FactorSpec
from src.domain.models import Portfolio, Trade
from src.execution.execution_service import ExecutionService
from src.execution.oms import apply_trades
from src.risk.engine import RiskEngine
from src.strategy.engine import weights_to_orders

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Outcome of an alpha execution cycle."""

    trades_count: int = 0
    turnover: float = 0.0
    orders_submitted: int = 0
    orders_rejected: int = 0
    target_weights: dict[str, float] = field(default_factory=dict)


class AlphaExecutor:
    """Execute a DecisionResult through the trading pipeline.

    Steps:
        1. Build an AlphaPipeline using the decision's factors + weights.
        2. Call ``pipeline.generate_weights`` to get target weights.
        3. Convert weights to orders via ``weights_to_orders``.
        4. Run risk checks.
        5. Submit approved orders via the execution service.
    """

    def __init__(self, config: AutoAlphaConfig) -> None:
        self._config = config

    def execute(
        self,
        decision: DecisionResult,
        data: dict[str, pd.DataFrame],
        portfolio: Portfolio,
        execution_service: ExecutionService,
        risk_engine: RiskEngine,
        current_date: pd.Timestamp | None = None,
    ) -> ExecutionResult:
        """Run the full execution cycle.

        Parameters
        ----------
        decision:
            Output from ``AlphaDecisionEngine.decide()``.
        data:
            Historical OHLCV data keyed by symbol.
        portfolio:
            Current portfolio state.
        execution_service:
            Mode-aware order routing service.
        risk_engine:
            Pre-trade risk engine.
        current_date:
            Date for weight generation (defaults to last date in data).
        """
        if not decision.selected_factors or not decision.factor_weights:
            logger.info("No factors selected — skipping execution")
            return ExecutionResult()

        # 1. Build pipeline with decision factors + custom weights
        factor_specs = [
            FactorSpec(name=name) for name in decision.selected_factors
        ]
        alpha_cfg = AlphaConfig(
            factors=factor_specs,
            combine_method="custom",
            combine_weights=decision.factor_weights,
        )
        pipeline = AlphaPipeline(alpha_cfg)

        # 2. Determine current date
        if current_date is None:
            some_df = next(iter(data.values()))
            current_date = some_df.index[-1]

        # Current weights from portfolio
        current_weights: pd.Series | None = None
        if portfolio.positions and portfolio.nav > 0:
            w = {
                sym: float(pos.market_value / portfolio.nav)
                for sym, pos in portfolio.positions.items()
            }
            current_weights = pd.Series(w)

        # 3. Generate target weights
        target_weights = pipeline.generate_weights(
            data=data,
            current_date=current_date,
            current_weights=current_weights,
        )

        if not target_weights:
            logger.info("Pipeline produced empty weights — skipping execution")
            return ExecutionResult(target_weights={})

        # 4. Convert to orders
        prices: dict[str, Decimal] = {}
        for sym, df in data.items():
            if not df.empty:
                prices[sym] = Decimal(str(float(df["close"].iloc[-1])))

        orders = weights_to_orders(
            target_weights=target_weights,
            portfolio=portfolio,
            prices=prices,
        )

        if not orders:
            return ExecutionResult(target_weights=target_weights)

        # 5. Risk check
        approved = risk_engine.check_orders(orders, portfolio)
        rejected_count = len(orders) - len(approved)

        if not approved:
            logger.warning("All %d orders rejected by risk engine", len(orders))
            return ExecutionResult(
                orders_submitted=0,
                orders_rejected=rejected_count,
                target_weights=target_weights,
            )

        # 6. Submit orders (skip in backtest mode — no current_bars available)
        trades: list[Trade] = []
        if execution_service.mode != "backtest":
            trades = execution_service.submit_orders(approved, portfolio)
        else:
            logger.info("Backtest mode — skipping actual order submission (%d orders)", len(approved))

        # 7. Apply trades to portfolio
        if trades:
            apply_trades(portfolio, trades)

        # Compute turnover
        turnover = 0.0
        if portfolio.nav > 0:
            trade_notional = sum(float(t.price * t.quantity) for t in trades)
            turnover = trade_notional / float(portfolio.nav)

        return ExecutionResult(
            trades_count=len(trades),
            turnover=turnover,
            orders_submitted=len(approved),
            orders_rejected=rejected_count,
            target_weights=target_weights,
        )
