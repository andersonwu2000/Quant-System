"""Tests for src/alpha/regime.py — 市場環境分類與條件 IC。"""

import numpy as np
import pandas as pd

from src.alpha.regime import (
    MarketRegime,
    RegimeDefinition,
    classify_regimes,
    compute_regime_ic,
)


def _make_market_returns(pattern: str, n: int = 120) -> pd.Series:
    """產生模擬市場報酬序列。"""
    dates = pd.bdate_range("2020-01-01", periods=n)
    if pattern == "bull":
        # 持續正報酬 → 年化 > 10%
        returns = np.full(n, 0.001)  # ~25% annualized
    elif pattern == "bear":
        returns = np.full(n, -0.001)  # ~-25% annualized
    elif pattern == "sideways":
        returns = np.full(n, 0.0001)  # ~2.5% annualized, within threshold
    else:
        returns = np.random.RandomState(42).normal(0, 0.01, n)
    return pd.Series(returns, index=dates)


class TestClassifyRegimes:
    def test_bull_regime(self):
        mkt = _make_market_returns("bull")
        regimes = classify_regimes(mkt)
        assert not regimes.empty
        # Most dates after warmup should be BULL
        assert (regimes == MarketRegime.BULL).sum() > 0

    def test_bear_regime(self):
        mkt = _make_market_returns("bear")
        regimes = classify_regimes(mkt)
        assert (regimes == MarketRegime.BEAR).sum() > 0

    def test_sideways_regime(self):
        mkt = _make_market_returns("sideways")
        regimes = classify_regimes(mkt)
        assert (regimes == MarketRegime.SIDEWAYS).sum() > 0

    def test_insufficient_data(self):
        mkt = pd.Series([0.01] * 10, index=pd.bdate_range("2020-01-01", periods=10))
        regimes = classify_regimes(mkt, RegimeDefinition(lookback=60))
        assert regimes.empty

    def test_custom_thresholds(self):
        mkt = _make_market_returns("sideways")
        # Very tight thresholds → sideways becomes bull
        config = RegimeDefinition(lookback=60, bull_threshold=0.0, bear_threshold=-0.50)
        regimes = classify_regimes(mkt, config)
        assert (regimes == MarketRegime.BULL).sum() > 0


class TestComputeRegimeIC:
    def _make_factor_data(self, n_symbols: int = 10, n_days: int = 120):
        np.random.seed(42)
        dates = pd.bdate_range("2020-01-01", periods=n_days)
        symbols = [f"S{i:03d}" for i in range(n_symbols)]
        factor_values = pd.DataFrame(
            np.random.randn(n_days, n_symbols), index=dates, columns=symbols
        )
        forward_returns = pd.DataFrame(
            np.random.randn(n_days, n_symbols) * 0.02, index=dates, columns=symbols
        )
        return factor_values, forward_returns

    def test_regime_ic_per_regime(self):
        fv, fr = self._make_factor_data()
        mkt = pd.Series(np.random.RandomState(42).normal(0, 0.01, len(fv)), index=fv.index)
        regimes = classify_regimes(mkt)
        result = compute_regime_ic(fv, fr, regimes, factor_name="test")
        assert result.factor_name == "test"
        # Should have results for regimes that exist
        assert len(result.ic_by_regime) > 0

    def test_regime_counts_sum(self):
        fv, fr = self._make_factor_data()
        mkt = pd.Series(np.random.RandomState(42).normal(0, 0.01, len(fv)), index=fv.index)
        regimes = classify_regimes(mkt)
        result = compute_regime_ic(fv, fr, regimes, factor_name="test")
        # Counts should be non-negative
        for count in result.regime_counts.values():
            assert count >= 0
