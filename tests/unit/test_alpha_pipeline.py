"""Tests for src/alpha/pipeline.py + strategy.py — Pipeline 端到端 + 策略適配器。"""

import numpy as np
import pandas as pd
import pytest

from src.alpha.pipeline import AlphaConfig, AlphaPipeline, AlphaReport, FactorSpec
from src.alpha.universe import UniverseConfig
from src.alpha.construction import ConstructionConfig
from src.alpha.neutralize import NeutralizeMethod
from src.alpha.strategy import AlphaStrategy


def _make_market_data(n_symbols: int = 15, n_days: int = 300) -> dict[str, pd.DataFrame]:
    """產生模擬市場數據。"""
    np.random.seed(42)
    dates = pd.bdate_range("2019-01-01", periods=n_days)
    data = {}
    for i in range(n_symbols):
        prices = 100 * np.cumprod(1 + np.random.randn(n_days) * 0.02)
        volume = np.random.uniform(5000, 50000, n_days)
        data[f"S{i:03d}"] = pd.DataFrame(
            {
                "open": prices * 0.99,
                "high": prices * 1.01,
                "low": prices * 0.98,
                "close": prices,
                "volume": volume,
            },
            index=dates,
        )
    return data


def _make_config(**overrides) -> AlphaConfig:
    defaults = dict(
        universe=UniverseConfig(min_listing_days=60, min_avg_volume=1000),
        factors=[
            FactorSpec(name="momentum"),
            FactorSpec(name="mean_reversion"),
        ],
        neutralize_method=NeutralizeMethod.MARKET,
        combine_method="equal",
        holding_period=5,
        n_quantiles=5,
        construction=ConstructionConfig(max_weight=0.10, max_total_weight=0.90),
    )
    defaults.update(overrides)
    return AlphaConfig(**defaults)


class TestAlphaPipeline:
    def test_research_returns_report(self):
        data = _make_market_data()
        config = _make_config()
        pipeline = AlphaPipeline(config)
        report = pipeline.research(data)
        assert isinstance(report, AlphaReport)
        assert len(report.factor_ics) == 2
        assert "momentum" in report.factor_ics
        assert "mean_reversion" in report.factor_ics

    def test_research_factor_ic_populated(self):
        data = _make_market_data()
        config = _make_config()
        pipeline = AlphaPipeline(config)
        report = pipeline.research(data)
        for name, ic in report.factor_ics.items():
            assert ic.factor_name == name

    def test_research_quantile_results(self):
        data = _make_market_data()
        config = _make_config()
        pipeline = AlphaPipeline(config)
        report = pipeline.research(data)
        assert len(report.quantile_results) == 2
        for qr in report.quantile_results.values():
            assert qr.n_quantiles == 5

    def test_research_composite_alpha(self):
        data = _make_market_data()
        config = _make_config()
        pipeline = AlphaPipeline(config)
        report = pipeline.research(data)
        assert report.composite_ic is not None
        assert report.composite_quantile is not None

    def test_research_turnover_analysis(self):
        data = _make_market_data()
        config = _make_config()
        pipeline = AlphaPipeline(config)
        report = pipeline.research(data)
        assert len(report.factor_turnovers) == 2
        for to in report.factor_turnovers.values():
            assert to.avg_turnover >= 0

    def test_research_correlation_matrix(self):
        data = _make_market_data()
        config = _make_config()
        pipeline = AlphaPipeline(config)
        report = pipeline.research(data)
        assert report.factor_correlations.shape == (2, 2)

    def test_research_with_orthogonalization(self):
        data = _make_market_data()
        config = _make_config(orthogonalize=True, orthogonalize_method="sequential")
        pipeline = AlphaPipeline(config)
        report = pipeline.research(data)
        assert report.composite_ic is not None

    def test_research_ic_weighted_combine(self):
        data = _make_market_data()
        config = _make_config(combine_method="ic")
        pipeline = AlphaPipeline(config)
        report = pipeline.research(data)
        # IC 加權的權重不應等權
        if report.composite_weights:
            weights = list(report.composite_weights.values())
            assert not all(abs(w - weights[0]) < 1e-10 for w in weights) or len(weights) == 1

    def test_research_summary(self):
        data = _make_market_data()
        config = _make_config()
        pipeline = AlphaPipeline(config)
        report = pipeline.research(data)
        s = report.summary()
        assert "Alpha Pipeline Report" in s
        assert "momentum" in s

    def test_generate_weights(self):
        data = _make_market_data()
        config = _make_config()
        pipeline = AlphaPipeline(config)
        date = data["S000"].index[-1]
        weights = pipeline.generate_weights(data, pd.Timestamp(date))
        assert isinstance(weights, dict)
        # 應有一些持倉
        assert len(weights) > 0
        assert all(v > 0 for v in weights.values())

    def test_generate_weights_with_current(self):
        data = _make_market_data()
        config = _make_config()
        pipeline = AlphaPipeline(config)
        date = data["S000"].index[-1]
        current = pd.Series({"S000": 0.05, "S001": 0.03})
        weights = pipeline.generate_weights(data, pd.Timestamp(date), current_weights=current)
        assert isinstance(weights, dict)

    def test_empty_data(self):
        config = _make_config()
        pipeline = AlphaPipeline(config)
        report = pipeline.research({})
        assert report.universe_counts["avg"] == 0

    def test_single_factor(self):
        data = _make_market_data()
        config = _make_config(factors=[FactorSpec(name="momentum")])
        pipeline = AlphaPipeline(config)
        report = pipeline.research(data)
        assert len(report.factor_ics) == 1


class TestAlphaStrategy:
    def test_name_reflects_factors(self):
        strategy = AlphaStrategy(factors=["momentum", "rsi"])
        assert "momentum" in strategy.name()
        assert "rsi" in strategy.name()

    def test_default_factors(self):
        strategy = AlphaStrategy()
        name = strategy.name()
        assert "momentum" in name
        assert "mean_reversion" in name
        assert "volatility" in name

    def test_custom_config(self):
        config = _make_config()
        strategy = AlphaStrategy(config=config)
        assert strategy.name() == "alpha_momentum_mean_reversion"
