"""Tests for AlphaExecutor (F1e)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd

from src.alpha.auto.config import AutoAlphaConfig
from src.alpha.auto.decision import DecisionResult
from src.alpha.auto.executor import AlphaExecutor, ExecutionResult
from src.alpha.regime import MarketRegime
from src.core.models import Instrument, Order, Portfolio, Position, Side, Trade


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_portfolio(
    cash: Decimal = Decimal("1000000"),
    positions: dict[str, Position] | None = None,
) -> Portfolio:
    return Portfolio(cash=cash, positions=positions or {})


def _make_data() -> dict[str, pd.DataFrame]:
    """Return minimal OHLCV data for two symbols."""
    dates = pd.date_range("2024-01-01", periods=60, freq="B")
    result: dict[str, pd.DataFrame] = {}
    for sym in ["AAPL", "MSFT"]:
        df = pd.DataFrame(
            {
                "open": 100.0,
                "high": 105.0,
                "low": 95.0,
                "close": 102.0,
                "volume": 1_000_000,
            },
            index=dates,
        )
        result[sym] = df
    return result


def _make_decision(
    factors: list[str] | None = None,
    weights: dict[str, float] | None = None,
) -> DecisionResult:
    factors = factors or ["momentum"]
    weights = weights or {f: 1.0 / len(factors) for f in factors}
    return DecisionResult(
        selected_factors=factors,
        factor_weights=weights,
        regime=MarketRegime.BULL,
        reason="test",
    )


def _make_trade(symbol: str = "AAPL") -> Trade:
    from datetime import datetime, timezone

    return Trade(
        timestamp=datetime.now(timezone.utc),
        symbol=symbol,
        side=Side.BUY,
        quantity=Decimal("10"),
        price=Decimal("102"),
        commission=Decimal("0.14"),
        slippage_bps=Decimal("5"),
    )


def _make_order(symbol: str = "AAPL") -> Order:
    return Order(
        instrument=Instrument(symbol),
        side=Side.BUY,
        quantity=Decimal("10"),
        price=Decimal("102"),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAlphaExecutor:
    """AlphaExecutor integration tests with mocked dependencies."""

    def test_execute_with_mock_pipeline(self) -> None:
        """Full execution cycle with mocked risk + execution service."""
        cfg = AutoAlphaConfig()
        executor = AlphaExecutor(cfg)
        data = _make_data()
        portfolio = _make_portfolio()

        risk_engine = MagicMock()
        risk_engine.check_orders.return_value = [_make_order()]

        exec_service = MagicMock()
        exec_service.submit_orders.return_value = [_make_trade()]

        decision = _make_decision()

        with patch(
            "src.alpha.auto.executor.AlphaPipeline.generate_weights",
            return_value={"AAPL": 0.5, "MSFT": 0.5},
        ):
            result = executor.execute(
                decision=decision,
                data=data,
                portfolio=portfolio,
                execution_service=exec_service,
                risk_engine=risk_engine,
            )

        assert isinstance(result, ExecutionResult)
        assert result.trades_count == 1
        assert result.orders_submitted == 1

    def test_empty_weights_returns_empty(self) -> None:
        """When pipeline produces empty weights, no orders are submitted."""
        cfg = AutoAlphaConfig()
        executor = AlphaExecutor(cfg)
        data = _make_data()
        portfolio = _make_portfolio()

        risk_engine = MagicMock()
        exec_service = MagicMock()

        decision = _make_decision()

        with patch(
            "src.alpha.auto.executor.AlphaPipeline.generate_weights",
            return_value={},
        ):
            result = executor.execute(
                decision=decision,
                data=data,
                portfolio=portfolio,
                execution_service=exec_service,
                risk_engine=risk_engine,
            )

        assert result.trades_count == 0
        assert result.orders_submitted == 0
        exec_service.submit_orders.assert_not_called()

    def test_no_selected_factors_skips(self) -> None:
        """Empty decision factors → immediate skip."""
        cfg = AutoAlphaConfig()
        executor = AlphaExecutor(cfg)
        data = _make_data()
        portfolio = _make_portfolio()

        risk_engine = MagicMock()
        exec_service = MagicMock()

        decision = DecisionResult(selected_factors=[], factor_weights={})

        result = executor.execute(
            decision=decision,
            data=data,
            portfolio=portfolio,
            execution_service=exec_service,
            risk_engine=risk_engine,
        )

        assert result.trades_count == 0
        risk_engine.check_orders.assert_not_called()
        exec_service.submit_orders.assert_not_called()

    def test_all_orders_rejected(self) -> None:
        """When risk engine rejects all orders."""
        cfg = AutoAlphaConfig()
        executor = AlphaExecutor(cfg)
        data = _make_data()
        portfolio = _make_portfolio()

        risk_engine = MagicMock()
        risk_engine.check_orders.return_value = []  # all rejected

        exec_service = MagicMock()

        decision = _make_decision()

        with patch(
            "src.alpha.auto.executor.AlphaPipeline.generate_weights",
            return_value={"AAPL": 0.5, "MSFT": 0.5},
        ):
            result = executor.execute(
                decision=decision,
                data=data,
                portfolio=portfolio,
                execution_service=exec_service,
                risk_engine=risk_engine,
            )

        assert result.orders_submitted == 0
        assert result.orders_rejected > 0
        exec_service.submit_orders.assert_not_called()

    def test_turnover_calculation(self) -> None:
        """Turnover is computed from trades vs portfolio NAV."""
        cfg = AutoAlphaConfig()
        executor = AlphaExecutor(cfg)
        data = _make_data()
        portfolio = _make_portfolio(cash=Decimal("1000000"))

        trade = _make_trade()
        risk_engine = MagicMock()
        risk_engine.check_orders.return_value = [_make_order()]

        exec_service = MagicMock()
        exec_service.submit_orders.return_value = [trade]

        decision = _make_decision()

        with patch(
            "src.alpha.auto.executor.AlphaPipeline.generate_weights",
            return_value={"AAPL": 0.5},
        ):
            result = executor.execute(
                decision=decision,
                data=data,
                portfolio=portfolio,
                execution_service=exec_service,
                risk_engine=risk_engine,
            )

        # trade notional = 102 * 10 = 1020, nav ~1000000
        assert result.turnover > 0
        assert result.turnover < 0.01  # should be small relative to portfolio

    def test_target_weights_in_result(self) -> None:
        """Target weights from pipeline are included in result."""
        cfg = AutoAlphaConfig()
        executor = AlphaExecutor(cfg)
        data = _make_data()
        portfolio = _make_portfolio()

        risk_engine = MagicMock()
        risk_engine.check_orders.return_value = []

        exec_service = MagicMock()

        decision = _make_decision()
        expected = {"AAPL": 0.6, "MSFT": 0.4}

        with patch(
            "src.alpha.auto.executor.AlphaPipeline.generate_weights",
            return_value=expected,
        ):
            result = executor.execute(
                decision=decision,
                data=data,
                portfolio=portfolio,
                execution_service=exec_service,
                risk_engine=risk_engine,
            )

        assert result.target_weights == expected

    def test_execution_result_dataclass(self) -> None:
        """ExecutionResult has correct defaults."""
        result = ExecutionResult()
        assert result.trades_count == 0
        assert result.turnover == 0.0
        assert result.orders_submitted == 0
        assert result.orders_rejected == 0
        assert result.target_weights == {}

    def test_multiple_trades(self) -> None:
        """Multiple trades are counted correctly."""
        cfg = AutoAlphaConfig()
        executor = AlphaExecutor(cfg)
        data = _make_data()
        portfolio = _make_portfolio()

        orders = [_make_order("AAPL"), _make_order("MSFT")]
        trades = [_make_trade("AAPL"), _make_trade("MSFT")]

        risk_engine = MagicMock()
        risk_engine.check_orders.return_value = orders

        exec_service = MagicMock()
        exec_service.submit_orders.return_value = trades

        decision = _make_decision()

        with patch(
            "src.alpha.auto.executor.AlphaPipeline.generate_weights",
            return_value={"AAPL": 0.3, "MSFT": 0.3},
        ):
            result = executor.execute(
                decision=decision,
                data=data,
                portfolio=portfolio,
                execution_service=exec_service,
                risk_engine=risk_engine,
            )

        assert result.trades_count == 2
        assert result.orders_submitted == 2
        assert result.orders_rejected == 0
