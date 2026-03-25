"""Tests for momentum crash detection and related decision engine changes."""

import numpy as np
import pandas as pd

from src.alpha.auto.decision import REGIME_FACTOR_BIAS
from src.alpha.auto.safety import check_momentum_crash
from src.alpha.regime import MarketRegime


def _make_returns(n: int, daily_mean: float = 0.0, daily_std: float = 0.01, seed: int = 42) -> pd.Series:
    """Create a synthetic daily return series."""
    rng = np.random.RandomState(seed)
    returns = rng.normal(daily_mean, daily_std, n)
    dates = pd.date_range("2019-01-01", periods=n, freq="B")
    return pd.Series(returns, index=dates)


class TestCheckMomentumCrash:
    def test_crash_detected_when_both_conditions_met(self):
        """Crash: market down >20% AND recent vol > 2x long-term vol."""
        # Build returns: first 232 days normal, then 20 days of high-vol crash
        normal = _make_returns(232, daily_mean=0.0, daily_std=0.01, seed=1)
        # Crash period: large negative returns with high volatility
        crash_dates = pd.date_range(normal.index[-1] + pd.offsets.BDay(1), periods=20, freq="B")
        crash = pd.Series(
            np.random.RandomState(2).normal(-0.03, 0.05, 20),
            index=crash_dates,
        )
        market = pd.concat([normal, crash])
        assert check_momentum_crash(market, market_threshold=-0.20, vol_multiplier=2.0)

    def test_not_detected_normal_market(self):
        """Normal bull market: neither condition should trigger."""
        returns = _make_returns(300, daily_mean=0.0005, daily_std=0.01)
        assert not check_momentum_crash(returns)

    def test_not_detected_only_drawdown(self):
        """Market is down but volatility is normal (not elevated)."""
        # Steady small negative returns (low vol, large cumulative loss)
        n = 300
        dates = pd.date_range("2019-01-01", periods=n, freq="B")
        returns = pd.Series([-0.002] * n, index=dates)
        # Cumulative return ~ (0.998)^252 - 1 ~ -0.395 (< -0.20)
        # But vol is ~0 (constant returns), so condition 2 fails
        assert not check_momentum_crash(returns)

    def test_not_detected_only_high_vol(self):
        """High recent vol but market is up overall."""
        normal = _make_returns(232, daily_mean=0.001, daily_std=0.005, seed=3)
        # Spike in vol but not enough cumulative loss
        spike_dates = pd.date_range(normal.index[-1] + pd.offsets.BDay(1), periods=20, freq="B")
        spike = pd.Series(
            np.random.RandomState(4).normal(0.0, 0.08, 20),
            index=spike_dates,
        )
        market = pd.concat([normal, spike])
        # Cumulative return likely positive from the normal period
        assert not check_momentum_crash(market, market_threshold=-0.20)

    def test_insufficient_data(self):
        """With too few data points, should return False."""
        short = _make_returns(50)
        assert not check_momentum_crash(short)

    def test_zero_longterm_vol(self):
        """If long-term vol is zero, should not crash (division guard)."""
        n = 300
        dates = pd.date_range("2019-01-01", periods=n, freq="B")
        returns = pd.Series([0.0] * n, index=dates)
        assert not check_momentum_crash(returns)


class TestRegimeFactorBiasMomentumBear:
    def test_bear_momentum_weight_is_low(self):
        """BEAR regime momentum bias should be 0.1 (not 0.5) per I4 spec."""
        bear_bias = REGIME_FACTOR_BIAS[MarketRegime.BEAR]
        assert bear_bias["momentum"] == 0.1

    def test_bull_momentum_unchanged(self):
        """BULL regime momentum bias should remain 1.5."""
        bull_bias = REGIME_FACTOR_BIAS[MarketRegime.BULL]
        assert bull_bias["momentum"] == 1.5
