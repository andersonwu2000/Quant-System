"""回測品質驗證測試。"""

from src.backtest.validation import (
    QualityValidationResult,
    check_determinism,
    check_sensitivity,
    run_all_quality_validations,
)


class TestQualityValidationResultStructure:
    def test_result_has_required_fields(self):
        r = QualityValidationResult(
            test_name="test", passed=True, details="ok"
        )
        assert r.test_name == "test"
        assert r.passed is True
        assert r.details == "ok"

    def test_result_failed(self):
        r = QualityValidationResult(
            test_name="fail_test", passed=False, details="something wrong"
        )
        assert r.passed is False
        assert "something wrong" in r.details


class TestDeterminism:
    """Determinism check with a trivial strategy that always returns empty weights."""

    def test_determinism_passes(self):
        """Same input = same output for a deterministic strategy."""
        import pandas as pd
        from src.backtest.engine import BacktestConfig
        from src.data.feed import HistoricalFeed
        from src.strategy.base import Context, Strategy

        class EmptyStrategy(Strategy):
            def name(self) -> str:
                return "empty"

            def on_bar(self, ctx: Context) -> dict[str, float]:
                return {}

        # We need to mock the data loading to avoid network calls.
        # Use monkey-patching on BacktestEngine._load_data.
        dates = pd.date_range("2024-01-01", "2024-06-30", freq="B")
        df = pd.DataFrame(
            {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 10000.0},
            index=dates,
        )

        from src.backtest.engine import BacktestEngine

        original_load = BacktestEngine._load_data

        def _mock_load(self, config):
            feed = HistoricalFeed()
            for symbol in config.universe:
                feed.load(symbol, df.copy())
            return feed, set(), None

        BacktestEngine._load_data = _mock_load
        try:
            strategy = EmptyStrategy()
            cfg = BacktestConfig(
                universe=["TEST.TW"],
                start="2024-01-01",
                end="2024-06-30",
                initial_cash=1_000_000.0,
            )
            result = check_determinism(strategy, cfg)
            assert result.passed is True
            assert result.test_name == "determinism"
        finally:
            BacktestEngine._load_data = original_load


class TestSensitivity:
    """Sensitivity check completes with different slippage values."""

    def test_sensitivity_completes(self):
        import pandas as pd
        from src.backtest.engine import BacktestConfig, BacktestEngine
        from src.data.feed import HistoricalFeed
        from src.strategy.base import Context, Strategy

        class SimpleStrategy(Strategy):
            def name(self) -> str:
                return "simple"

            def on_bar(self, ctx: Context) -> dict[str, float]:
                return {"TEST.TW": 0.5}

        dates = pd.date_range("2024-01-01", "2024-03-31", freq="B")
        df = pd.DataFrame(
            {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 100000.0},
            index=dates,
        )

        original_load = BacktestEngine._load_data

        def _mock_load(self, config):
            feed = HistoricalFeed()
            for symbol in config.universe:
                feed.load(symbol, df.copy())
            return feed, set(), None

        BacktestEngine._load_data = _mock_load
        try:
            strategy = SimpleStrategy()
            cfg = BacktestConfig(
                universe=["TEST.TW"],
                start="2024-01-01",
                end="2024-03-31",
                initial_cash=1_000_000.0,
                slippage_bps=5.0,
            )
            result = check_sensitivity(strategy, cfg, slippage_multipliers=(0.5, 2.0))
            assert result.test_name == "sensitivity"
            # Should pass since all runs complete and flat-price strategy won't flip sign
            assert result.passed is True
        finally:
            BacktestEngine._load_data = original_load


class TestRunAllQualityValidations:
    def test_returns_list_of_results(self):
        import pandas as pd
        from src.backtest.engine import BacktestConfig, BacktestEngine
        from src.data.feed import HistoricalFeed
        from src.strategy.base import Context, Strategy

        class EmptyStrategy(Strategy):
            def name(self) -> str:
                return "empty"

            def on_bar(self, ctx: Context) -> dict[str, float]:
                return {}

        dates = pd.date_range("2024-01-01", "2024-03-31", freq="B")
        df = pd.DataFrame(
            {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 10000.0},
            index=dates,
        )

        original_load = BacktestEngine._load_data

        def _mock_load(self, config):
            feed = HistoricalFeed()
            for symbol in config.universe:
                feed.load(symbol, df.copy())
            return feed, set(), None

        BacktestEngine._load_data = _mock_load
        try:
            strategy = EmptyStrategy()
            cfg = BacktestConfig(
                universe=["TEST.TW"],
                start="2024-01-01",
                end="2024-03-31",
                initial_cash=1_000_000.0,
            )
            results = run_all_quality_validations(strategy, cfg)
            assert len(results) == 3
            names = {r.test_name for r in results}
            assert names == {"causality", "determinism", "sensitivity"}
            for r in results:
                assert isinstance(r, QualityValidationResult)
        finally:
            BacktestEngine._load_data = original_load
