"""Tests for AlphaResearcher with mock pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.alpha.auto.config import AutoAlphaConfig, FactorScore, ResearchSnapshot
from src.alpha.auto.researcher import AlphaResearcher
from src.alpha.pipeline import AlphaConfig, AlphaReport, FactorSpec
from src.alpha.regime import MarketRegime
from src.strategy.research import DecayResult, ICResult


def _make_ohlcv(days: int = 300) -> pd.DataFrame:
    dates = pd.bdate_range(end="2026-03-25", periods=days)
    rng = np.random.default_rng(42)
    close = 100 + rng.standard_normal(days).cumsum()
    return pd.DataFrame(
        {
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.98,
            "close": close,
            "volume": rng.uniform(500_000, 1_500_000, days),
        },
        index=dates,
    )


def _make_data(symbols: list[str], days: int = 300) -> dict[str, pd.DataFrame]:
    return {s: _make_ohlcv(days) for s in symbols}


def _make_ic_result(name: str, ic_mean: float, icir: float, hit_rate: float) -> ICResult:
    return ICResult(
        factor_name=name,
        ic_mean=ic_mean,
        ic_std=abs(ic_mean / icir) if icir != 0 else 1.0,
        icir=icir,
        hit_rate=hit_rate,
    )


def _make_mock_report(
    factor_names: list[str] | None = None,
) -> AlphaReport:
    """Create a mock AlphaReport with sample IC results."""
    if factor_names is None:
        factor_names = ["momentum", "volatility"]

    factor_ics = {}
    factor_turnovers = {}
    factor_decays = {}
    quantile_results = {}

    for name in factor_names:
        factor_ics[name] = _make_ic_result(name, 0.04, 0.8, 0.55)

        to = MagicMock()
        to.avg_turnover = 0.15
        to.cost_drag_annual_bps = 100.0
        factor_turnovers[name] = to

        factor_decays[name] = DecayResult(
            factor_name=name,
            horizons=[1, 5, 10, 20],
            ic_by_horizon={1: 0.05, 5: 0.04, 10: 0.02, 20: 0.01},
        )

        qr = MagicMock()
        qr.long_short_sharpe = 1.5
        quantile_results[name] = qr

    return AlphaReport(
        config=AlphaConfig(),
        universe_counts={"avg": 50, "min": 45, "max": 55},
        factor_ics=factor_ics,
        factor_turnovers=factor_turnovers,
        factor_decays=factor_decays,
        quantile_results=quantile_results,
        composite_weights={n: 1.0 / len(factor_names) for n in factor_names},
    )


class TestAlphaResearcherReportToScores:
    """Test _report_to_scores conversion logic."""

    def test_basic_conversion(self) -> None:
        cfg = AutoAlphaConfig(
            alpha_config=AlphaConfig(factors=[
                FactorSpec(name="momentum"),
                FactorSpec(name="volatility"),
            ]),
        )
        researcher = AlphaResearcher(cfg)
        report = _make_mock_report(["momentum", "volatility"])
        scores = researcher._report_to_scores(report)

        assert "momentum" in scores
        assert "volatility" in scores
        assert isinstance(scores["momentum"], FactorScore)
        assert scores["momentum"].ic == pytest.approx(0.04)
        assert scores["momentum"].icir == pytest.approx(0.8)
        assert scores["momentum"].hit_rate == pytest.approx(0.55)

    def test_eligibility_pass(self) -> None:
        """Factors meeting all thresholds should be eligible."""
        cfg = AutoAlphaConfig()
        researcher = AlphaResearcher(cfg)
        report = _make_mock_report(["momentum"])
        scores = researcher._report_to_scores(report)

        # ic=0.04, icir=0.8 > 0.3, hit_rate=0.55 > 0.52, cost=100 < 200
        assert scores["momentum"].eligible is True

    def test_eligibility_fail_icir(self) -> None:
        """Factor with low ICIR should not be eligible."""
        cfg = AutoAlphaConfig()
        researcher = AlphaResearcher(cfg)

        report = _make_mock_report(["weak"])
        report.factor_ics["weak"] = _make_ic_result("weak", 0.01, 0.1, 0.55)
        scores = researcher._report_to_scores(report)

        assert scores["weak"].eligible is False

    def test_eligibility_fail_hit_rate(self) -> None:
        cfg = AutoAlphaConfig()
        researcher = AlphaResearcher(cfg)

        report = _make_mock_report(["low_hit"])
        report.factor_ics["low_hit"] = _make_ic_result("low_hit", 0.04, 0.8, 0.45)
        scores = researcher._report_to_scores(report)

        assert scores["low_hit"].eligible is False

    def test_eligibility_fail_cost(self) -> None:
        cfg = AutoAlphaConfig()
        researcher = AlphaResearcher(cfg)

        report = _make_mock_report(["costly"])
        to = MagicMock()
        to.avg_turnover = 0.5
        to.cost_drag_annual_bps = 300.0
        report.factor_turnovers["costly"] = to
        scores = researcher._report_to_scores(report)

        assert scores["costly"].eligible is False

    def test_decay_half_life_estimation(self) -> None:
        cfg = AutoAlphaConfig()
        researcher = AlphaResearcher(cfg)
        report = _make_mock_report(["mom"])
        # IC: {1: 0.05, 5: 0.04, 10: 0.02, 20: 0.01}
        # max_ic = 0.05, threshold = 0.025
        # h=10: |0.02| < 0.025 => half_life = 10
        scores = researcher._report_to_scores(report)
        assert scores["mom"].decay_half_life == 10


class TestAlphaResearcherRun:
    """Test the full run() method with mocked pipeline."""

    @patch("src.alpha.auto.researcher.AlphaPipeline")
    @patch("src.alpha.auto.researcher.classify_regimes")
    @patch("src.alpha.auto.researcher.compute_market_returns")
    def test_run_with_data(
        self,
        mock_mkt_ret: MagicMock,
        mock_classify: MagicMock,
        mock_pipeline_cls: MagicMock,
    ) -> None:
        # Setup mocks
        mock_report = _make_mock_report(["momentum"])
        mock_pipeline = MagicMock()
        mock_pipeline.research.return_value = mock_report
        mock_pipeline_cls.return_value = mock_pipeline

        regime_series = pd.Series([MarketRegime.BULL])
        mock_classify.return_value = regime_series
        mock_mkt_ret.return_value = pd.Series([0.01, 0.02])

        cfg = AutoAlphaConfig()
        researcher = AlphaResearcher(cfg)
        data = _make_data(["AAPL", "MSFT"])
        snapshot = researcher.run(universe=["AAPL", "MSFT"], data=data)

        assert isinstance(snapshot, ResearchSnapshot)
        assert snapshot.regime == MarketRegime.BULL
        assert snapshot.universe == ["AAPL", "MSFT"]
        assert snapshot.universe_size == 2
        assert "momentum" in snapshot.factor_scores
        mock_pipeline.research.assert_called_once()

    @patch("src.alpha.auto.researcher.AlphaPipeline")
    @patch("src.alpha.auto.researcher.classify_regimes")
    @patch("src.alpha.auto.researcher.compute_market_returns")
    def test_run_regime_failure_defaults_sideways(
        self,
        mock_mkt_ret: MagicMock,
        mock_classify: MagicMock,
        mock_pipeline_cls: MagicMock,
    ) -> None:
        mock_report = _make_mock_report(["momentum"])
        mock_pipeline = MagicMock()
        mock_pipeline.research.return_value = mock_report
        mock_pipeline_cls.return_value = mock_pipeline

        mock_mkt_ret.side_effect = ValueError("Not enough data")

        cfg = AutoAlphaConfig()
        researcher = AlphaResearcher(cfg)
        data = _make_data(["AAPL"])
        snapshot = researcher.run(universe=["AAPL"], data=data)

        assert snapshot.regime == MarketRegime.SIDEWAYS

    def test_run_empty_data(self) -> None:
        cfg = AutoAlphaConfig()
        researcher = AlphaResearcher(cfg)
        snapshot = researcher.run(universe=["AAPL"], data={})

        assert snapshot.universe == ["AAPL"]
        assert snapshot.factor_scores == {}

    def test_run_filters_data_to_universe(self) -> None:
        """Data for symbols not in universe should be excluded."""
        cfg = AutoAlphaConfig()
        researcher = AlphaResearcher(cfg)

        with patch("src.alpha.auto.researcher.AlphaPipeline") as mock_cls:
            mock_report = _make_mock_report([])
            mock_report.factor_ics = {}
            mock_pipeline = MagicMock()
            mock_pipeline.research.return_value = mock_report
            mock_cls.return_value = mock_pipeline

            with patch("src.alpha.auto.researcher.classify_regimes") as mock_cr:
                mock_cr.return_value = pd.Series(dtype=object)
                with patch("src.alpha.auto.researcher.compute_market_returns") as mock_mr:
                    mock_mr.return_value = pd.Series(dtype=float)

                    data = _make_data(["AAPL", "MSFT", "EXTRA"])
                    researcher.run(universe=["AAPL", "MSFT"], data=data)

            # Pipeline should only receive AAPL and MSFT data
            call_args = mock_pipeline.research.call_args
            data_passed = call_args[0][0]
            assert "EXTRA" not in data_passed
