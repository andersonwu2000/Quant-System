"""Tests for the backtest verification gate (Stage 3.5)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from src.alpha.auto.backtest_gate import GateResult, verify_before_execution
from src.alpha.auto.config import AutoAlphaConfig
from src.alpha.auto.decision import DecisionResult
from src.alpha.regime import MarketRegime
from src.backtest.analytics import BacktestResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_decision(
    factors: list[str] | None = None,
    weights: dict[str, float] | None = None,
) -> DecisionResult:
    factors = factors or ["momentum"]
    weights = weights or {f: 1.0 / len(factors) for f in factors}
    return DecisionResult(
        selected_factors=factors,
        factor_weights=weights,
        regime=MarketRegime.SIDEWAYS,
        reason="test",
    )


def _make_data(symbols: list[str] | None = None, periods: int = 120) -> dict[str, pd.DataFrame]:
    symbols = symbols or ["AAPL", "MSFT"]
    dates = pd.date_range("2024-01-01", periods=periods, freq="B")
    result: dict[str, pd.DataFrame] = {}
    for sym in symbols:
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


def _mock_backtest_result(
    sharpe: float = 0.5,
    total_return: float = 0.05,
    max_drawdown: float = 0.03,
    total_commission: float = 50_000.0,
    total_trades: int = 20,
) -> BacktestResult:
    """Create a mock BacktestResult with the given metrics."""
    return BacktestResult(
        strategy_name="test",
        start_date="2024-01-01",
        end_date="2024-06-01",
        initial_cash=10_000_000.0,
        total_return=total_return,
        annual_return=total_return * 2,
        sharpe=sharpe,
        sortino=sharpe * 1.2,
        calmar=0.5,
        max_drawdown=max_drawdown,
        max_drawdown_duration=10,
        volatility=0.15,
        downside_vol=0.10,
        total_trades=total_trades,
        win_rate=0.55,
        avg_trade_return=0.005,
        total_commission=total_commission,
        turnover=0.1,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGatePassesOnProfitable:
    """Gate passes when backtest shows positive Sharpe and acceptable cost."""

    @patch("src.alpha.auto.backtest_gate.BacktestEngine")
    def test_gate_passes_positive_sharpe(self, mock_engine_cls: MagicMock) -> None:
        """Gate passes when Sharpe > 0 and costs are acceptable."""
        mock_engine = MagicMock()
        mock_engine.run.return_value = _mock_backtest_result(sharpe=0.8, total_commission=10_000.0)
        mock_engine_cls.return_value = mock_engine

        config = AutoAlphaConfig(backtest_gate_enabled=True)
        decision = _make_decision()
        data = _make_data()

        result = verify_before_execution(decision=decision, data=data, config=config)

        assert result.passed is True
        assert result.sharpe == 0.8
        assert "All checks passed" in result.reason


class TestGateBlocksNegativeSharpe:
    """Gate blocks when Sharpe < min threshold."""

    @patch("src.alpha.auto.backtest_gate.BacktestEngine")
    def test_gate_blocks_negative_sharpe(self, mock_engine_cls: MagicMock) -> None:
        """Gate blocks when Sharpe ratio is negative."""
        mock_engine = MagicMock()
        mock_engine.run.return_value = _mock_backtest_result(sharpe=-0.5, total_commission=10_000.0)
        mock_engine_cls.return_value = mock_engine

        config = AutoAlphaConfig(backtest_gate_enabled=True, backtest_gate_min_sharpe=0.0)
        decision = _make_decision()
        data = _make_data()

        result = verify_before_execution(decision=decision, data=data, config=config)

        assert result.passed is False
        assert result.sharpe == -0.5
        assert "Sharpe" in result.reason


class TestGateBlocksHighCost:
    """Gate blocks when estimated annual cost exceeds threshold."""

    @patch("src.alpha.auto.backtest_gate.BacktestEngine")
    def test_gate_blocks_excessive_cost(self, mock_engine_cls: MagicMock) -> None:
        """Gate blocks when annual cost pct > max_cost_pct."""
        # total_commission = 1_000_000 on 10M capital over ~120 days
        # annual cost = (1M / 10M) * (252 / ~120) ~ 21%
        mock_engine = MagicMock()
        mock_engine.run.return_value = _mock_backtest_result(
            sharpe=1.0, total_commission=1_000_000.0,
        )
        mock_engine_cls.return_value = mock_engine

        config = AutoAlphaConfig(
            backtest_gate_enabled=True,
            backtest_gate_max_cost_pct=0.05,
        )
        decision = _make_decision()
        data = _make_data()

        result = verify_before_execution(decision=decision, data=data, config=config)

        assert result.passed is False
        assert result.net_cost > 0.05
        assert "cost" in result.reason.lower()


class TestGateDisabled:
    """When gate is disabled in config, the scheduler skips it entirely.

    verify_before_execution itself always runs; the scheduler checks
    config.backtest_gate_enabled before calling it.  Here we test that
    the function still works correctly when called.
    """

    @patch("src.alpha.auto.backtest_gate.BacktestEngine")
    def test_gate_runs_regardless_of_config_flag(self, mock_engine_cls: MagicMock) -> None:
        """Function returns valid GateResult even when called with gate disabled."""
        mock_engine = MagicMock()
        mock_engine.run.return_value = _mock_backtest_result(sharpe=0.5, total_commission=10_000.0)
        mock_engine_cls.return_value = mock_engine

        config = AutoAlphaConfig(backtest_gate_enabled=False)
        decision = _make_decision()
        data = _make_data()

        result = verify_before_execution(decision=decision, data=data, config=config)

        assert isinstance(result, GateResult)
        assert result.passed is True


class TestGateResultFields:
    """GateResult fields are populated correctly."""

    @patch("src.alpha.auto.backtest_gate.BacktestEngine")
    def test_all_fields_populated(self, mock_engine_cls: MagicMock) -> None:
        """All GateResult fields reflect backtest output."""
        mock_engine = MagicMock()
        mock_engine.run.return_value = _mock_backtest_result(
            sharpe=1.2, total_return=0.08, max_drawdown=0.04, total_commission=30_000.0,
        )
        mock_engine_cls.return_value = mock_engine

        config = AutoAlphaConfig(backtest_gate_enabled=True)
        decision = _make_decision()
        data = _make_data()

        result = verify_before_execution(decision=decision, data=data, config=config)

        assert result.sharpe == 1.2
        assert result.total_return == 0.08
        assert result.max_drawdown == 0.04
        assert result.net_cost > 0.0
        assert isinstance(result.reason, str)

    def test_empty_decision_fails(self) -> None:
        """Empty decision (no factors) returns failed gate."""
        config = AutoAlphaConfig(backtest_gate_enabled=True)
        decision = DecisionResult(
            selected_factors=[],
            factor_weights={},
            regime=MarketRegime.SIDEWAYS,
            reason="none",
        )
        data = _make_data()

        result = verify_before_execution(decision=decision, data=data, config=config)

        assert result.passed is False
        assert "No factors" in result.reason

    def test_empty_data_fails(self) -> None:
        """Empty data dict returns failed gate."""
        config = AutoAlphaConfig(backtest_gate_enabled=True)
        decision = _make_decision()

        result = verify_before_execution(decision=decision, data={}, config=config)

        assert result.passed is False
        assert "No data" in result.reason

    @patch("src.alpha.auto.backtest_gate.BacktestEngine")
    def test_engine_exception_returns_failed(self, mock_engine_cls: MagicMock) -> None:
        """If BacktestEngine.run() raises, gate returns failure."""
        mock_engine = MagicMock()
        mock_engine.run.side_effect = ValueError("bad data")
        mock_engine_cls.return_value = mock_engine

        config = AutoAlphaConfig(backtest_gate_enabled=True)
        decision = _make_decision()
        data = _make_data()

        result = verify_before_execution(decision=decision, data=data, config=config)

        assert result.passed is False
        assert "error" in result.reason.lower()
