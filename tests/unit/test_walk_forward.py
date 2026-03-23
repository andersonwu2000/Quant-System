"""Walk-Forward Analysis 測試。"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest

from src.backtest.analytics import BacktestResult
from src.backtest.walk_forward import (
    WalkForwardAnalyzer,
    WFAConfig,
    WFAFold,
    WFAResult,
)


def _make_mock_result(
    sharpe: float = 1.0,
    total_return: float = 0.05,
    max_drawdown: float = 0.10,
) -> BacktestResult:
    """建立 mock BacktestResult。"""
    return BacktestResult(
        strategy_name="test",
        start_date="2023-01-01",
        end_date="2023-06-30",
        initial_cash=10_000_000.0,
        total_return=total_return,
        annual_return=total_return * 2,
        sharpe=sharpe,
        sortino=sharpe * 1.2,
        calmar=sharpe * 0.8,
        max_drawdown=max_drawdown,
        max_drawdown_duration=30,
        volatility=0.15,
        downside_vol=0.10,
        total_trades=50,
        win_rate=0.55,
        avg_trade_return=100.0,
        total_commission=5000.0,
        turnover=2.0,
        nav_series=pd.Series([10_000_000.0, 10_500_000.0]),
        daily_returns=pd.Series([0.0, 0.05]),
        drawdown_series=pd.Series([0.0, 0.0]),
        trades=[],
    )


class TestWalkForwardAnalyzer:
    """Walk-Forward Analysis 測試。"""

    def test_basic_two_fold_produces_results(self) -> None:
        """基本 2-fold WFA 應產生結果。"""
        analyzer = WalkForwardAnalyzer()
        config = WFAConfig(
            train_days=60,
            test_days=30,
            step_days=30,
            universe=["AAPL"],
            initial_cash=1_000_000.0,
        )

        mock_result = _make_mock_result(sharpe=1.5, total_return=0.03)

        with patch.object(analyzer, "_run_backtest", return_value=mock_result):
            result = analyzer.run(
                strategy_name="momentum",
                universe=["AAPL"],
                start="2023-01-01",
                end="2023-12-31",
                config=config,
            )

        assert isinstance(result, WFAResult)
        assert len(result.folds) >= 2
        assert result.oos_total_return != 0.0
        assert result.oos_sharpe != 0.0

        # Verify fold structure
        for fold in result.folds:
            assert isinstance(fold, WFAFold)
            assert fold.train_start < fold.train_end
            assert fold.test_start < fold.test_end
            assert fold.train_end < fold.test_start

    def test_param_grid_produces_optimized_results(self) -> None:
        """提供 param_grid 時應進行參數優化。"""
        analyzer = WalkForwardAnalyzer()
        config = WFAConfig(
            train_days=60,
            test_days=30,
            step_days=30,
            universe=["AAPL"],
            initial_cash=1_000_000.0,
        )

        call_count = 0

        def mock_run_backtest(
            strategy_name: str,
            universe: list[str],
            start: str,
            end: str,
            config: WFAConfig,
            params: dict[str, Any] | None,
        ) -> BacktestResult:
            nonlocal call_count
            call_count += 1
            # Vary sharpe based on params to test grid search
            if params and params.get("lookback") == 20:
                return _make_mock_result(sharpe=2.0, total_return=0.08)
            return _make_mock_result(sharpe=1.0, total_return=0.03)

        with patch.object(analyzer, "_run_backtest", side_effect=mock_run_backtest):
            result = analyzer.run(
                strategy_name="momentum",
                universe=["AAPL"],
                start="2023-01-01",
                end="2023-12-31",
                config=config,
                param_grid={"lookback": [10, 20, 30]},
            )

        assert isinstance(result, WFAResult)
        assert len(result.folds) >= 2

        # With param_grid, best_params should be set on each fold
        for fold in result.folds:
            assert fold.best_params is not None
            assert "lookback" in fold.best_params

        # param_stability should contain lookback info
        assert "lookback" in result.param_stability

    def test_insufficient_date_range_raises_error(self) -> None:
        """日期範圍不足時應拋出 ValueError。"""
        analyzer = WalkForwardAnalyzer()
        config = WFAConfig(
            train_days=252,
            test_days=126,
            step_days=63,
            universe=["AAPL"],
        )

        with pytest.raises(ValueError, match="Insufficient date range"):
            analyzer.run(
                strategy_name="momentum",
                universe=["AAPL"],
                start="2023-01-01",
                end="2023-03-01",  # Only ~40 business days — not enough
                config=config,
            )

    def test_fold_dates_no_test_overlap(self) -> None:
        """測試視窗之間不應重疊。"""
        analyzer = WalkForwardAnalyzer()
        config = WFAConfig(
            train_days=60,
            test_days=30,
            step_days=30,
            universe=["AAPL"],
            initial_cash=1_000_000.0,
        )

        mock_result = _make_mock_result()

        with patch.object(analyzer, "_run_backtest", return_value=mock_result):
            result = analyzer.run(
                strategy_name="momentum",
                universe=["AAPL"],
                start="2022-01-01",
                end="2023-12-31",
                config=config,
            )

        assert len(result.folds) >= 2

        # Verify no overlap between consecutive test windows
        # Adjacent windows may share a boundary date (test_end == next test_start)
        # but actual test ranges must not overlap (test_start_i+1 >= test_end_i)
        for i in range(len(result.folds) - 1):
            current_test_end = pd.Timestamp(result.folds[i].test_end)
            next_test_start = pd.Timestamp(result.folds[i + 1].test_start)
            assert current_test_end <= next_test_start, (
                f"Fold {i} test_end ({current_test_end}) should not be after "
                f"fold {i+1} test_start ({next_test_start})"
            )
