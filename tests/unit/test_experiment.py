"""Tests for src.backtest.experiment — experiment grid framework."""

from __future__ import annotations

import pandas as pd

from src.backtest.experiment import (
    DEFAULT_PERIODS,
    ExperimentResult,
    analyze_results,
    generate_coarse_grid,
    summarize_results,
)


class TestGenerateCoarseGrid:
    """Tests for generate_coarse_grid."""

    def test_produces_256_configs(self) -> None:
        configs = generate_coarse_grid()
        assert len(configs) == 256

    def test_all_configs_have_names(self) -> None:
        configs = generate_coarse_grid()
        names = [c.name for c in configs]
        assert all(n for n in names)
        # All names should be unique
        assert len(set(names)) == 256

    def test_config_fields_populated(self) -> None:
        configs = generate_coarse_grid()
        for c in configs:
            assert isinstance(c.factors, list)
            assert len(c.factors) >= 1
            assert c.rebalance_freq in ("weekly", "monthly")
            assert c.holding_period in (10, 20)
            assert c.max_weight in (0.05, 0.15)
            assert c.kill_switch_pct in (0.05, None)
            assert c.neutralize in ("none", "market")
            assert c.construction in ("equal_weight", "risk_parity")

    def test_universe_names_in_config_names(self) -> None:
        configs = generate_coarse_grid()
        tw50_count = sum(1 for c in configs if "TW50" in c.name)
        tw300_count = sum(1 for c in configs if "TW300" in c.name)
        assert tw50_count == 128
        assert tw300_count == 128


class TestExperimentResult:
    """Tests for ExperimentResult dataclass."""

    def test_creation(self) -> None:
        r = ExperimentResult(
            config_name="test",
            period_id="P1",
            total_return=0.1,
            annual_return=0.08,
            sharpe=1.5,
            sortino=2.0,
            calmar=1.0,
            max_drawdown=0.10,
            total_trades=100,
            total_commission=5000.0,
            win_rate=0.55,
            var_95=0.02,
            cvar_95=0.03,
        )
        assert r.config_name == "test"
        assert r.sharpe == 1.5


class TestAnalyzeResults:
    """Tests for analyze_results."""

    @staticmethod
    def _make_raw_df() -> pd.DataFrame:
        """Create a synthetic raw results DataFrame."""
        rows = []
        for period in ["P1", "P2", "P3", "P4", "FULL"]:
            rows.append(
                {
                    "config_name": "good_config",
                    "period_id": period,
                    "total_return": 0.20 if period == "FULL" else 0.05,
                    "annual_return": 0.10 if period == "FULL" else 0.05,
                    "sharpe": 1.2 if period == "FULL" else 0.8,
                    "sortino": 1.5,
                    "calmar": 1.0,
                    "max_drawdown": 0.10,
                    "total_trades": 500 if period == "FULL" else 100,
                    "total_commission": 5000.0,
                    "win_rate": 0.55,
                    "var_95": 0.02,
                    "cvar_95": 0.03,
                    "success": True,
                    "error": "",
                }
            )
        # Add a bad config that fails consistency
        for period in ["P1", "P2", "P3", "P4", "FULL"]:
            rows.append(
                {
                    "config_name": "bad_config",
                    "period_id": period,
                    "total_return": -0.10 if period == "FULL" else -0.05,
                    "annual_return": -0.05 if period == "FULL" else -0.03,
                    "sharpe": -0.5 if period == "FULL" else -0.3,
                    "sortino": -0.4,
                    "calmar": -0.2,
                    "max_drawdown": 0.30,
                    "total_trades": 200,
                    "total_commission": 3000.0,
                    "win_rate": 0.40,
                    "var_95": 0.04,
                    "cvar_95": 0.05,
                    "success": True,
                    "error": "",
                }
            )
        return pd.DataFrame(rows)

    def test_computes_dsr_and_consistency(self) -> None:
        df = self._make_raw_df()
        summary = analyze_results(df)
        assert not summary.empty
        assert "dsr" in summary.columns
        assert "consistency" in summary.columns
        assert "passes" in summary.columns

    def test_good_config_passes(self) -> None:
        df = self._make_raw_df()
        summary = analyze_results(df, total_trials=2)
        good = summary[summary["config_name"] == "good_config"]
        assert len(good) == 1
        assert good.iloc[0]["passes"] == True  # noqa: E712

    def test_bad_config_fails(self) -> None:
        df = self._make_raw_df()
        summary = analyze_results(df, total_trials=2)
        bad = summary[summary["config_name"] == "bad_config"]
        assert len(bad) == 1
        assert bad.iloc[0]["passes"] == False  # noqa: E712

    def test_sorted_by_sharpe_desc(self) -> None:
        df = self._make_raw_df()
        summary = analyze_results(df)
        sharpes = summary["full_sharpe"].tolist()
        assert sharpes == sorted(sharpes, reverse=True)

    def test_empty_df_returns_empty(self) -> None:
        df = pd.DataFrame(
            {
                "config_name": ["x"],
                "period_id": ["P1"],
                "success": [False],
                "error": ["fail"],
            }
        )
        summary = analyze_results(df)
        assert summary.empty


class TestSummarizeResults:
    """Tests for summarize_results."""

    def test_produces_readable_string(self) -> None:
        summary = pd.DataFrame(
            [
                {
                    "config_name": "cfg_a",
                    "full_return": 0.20,
                    "full_annual": 0.10,
                    "full_sharpe": 1.5,
                    "full_sortino": 2.0,
                    "full_calmar": 1.0,
                    "full_max_dd": 0.08,
                    "full_trades": 500,
                    "full_commission": 5000.0,
                    "full_win_rate": 0.55,
                    "positive_periods": 4,
                    "total_periods": 4,
                    "consistency": "4/4",
                    "worst_dd": 0.08,
                    "dsr": 0.90,
                    "passes": True,
                },
            ]
        )
        text = summarize_results(summary)
        assert "EXPERIMENT GRID RESULTS" in text
        assert "cfg_a" in text
        assert "Sharpe=1.50" in text

    def test_no_passes_shows_warning(self) -> None:
        summary = pd.DataFrame(
            [
                {
                    "config_name": "cfg_b",
                    "full_return": -0.05,
                    "full_annual": -0.03,
                    "full_sharpe": -0.5,
                    "full_sortino": -0.4,
                    "full_calmar": -0.2,
                    "full_max_dd": 0.30,
                    "full_trades": 200,
                    "full_commission": 3000.0,
                    "full_win_rate": 0.40,
                    "positive_periods": 1,
                    "total_periods": 4,
                    "consistency": "1/4",
                    "worst_dd": 0.30,
                    "dsr": 0.01,
                    "passes": False,
                },
            ]
        )
        text = summarize_results(summary)
        assert "NO CONFIGURATIONS PASSED" in text


class TestDefaultPeriods:
    """Tests for DEFAULT_PERIODS."""

    def test_five_periods(self) -> None:
        assert len(DEFAULT_PERIODS) == 5

    def test_full_period_present(self) -> None:
        ids = [p.period_id for p in DEFAULT_PERIODS]
        assert "FULL" in ids

    def test_period_dates_valid(self) -> None:
        for p in DEFAULT_PERIODS:
            start = pd.Timestamp(p.start)
            end = pd.Timestamp(p.end)
            assert end > start
