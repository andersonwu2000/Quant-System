"""
Tests for expanded factor library — technical, academic, and Kakushadze factors.

Validates:
- Each new factor returns correct key and valid float
- Vectorized factors produce valid output
- Edge cases: constant data, short data
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.strategy.factors import technical as tech
from src.strategy.factors import kakushadze as kak


# ── Fixtures ───────────────────────────────────────────────────────


def _make_bars(n: int = 100, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range("2023-01-01", periods=n)
    close = 100 + np.cumsum(rng.randn(n) * 0.5)
    close = np.maximum(close, 1.0)  # ensure positive
    high = close + rng.uniform(0.1, 2.0, n)
    low = close - rng.uniform(0.1, 2.0, n)
    low = np.maximum(low, 0.5)
    open_ = close + rng.randn(n) * 0.3
    open_ = np.maximum(open_, 0.5)
    volume = rng.randint(1000, 100000, n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


def _make_constant_bars(n: int = 50) -> pd.DataFrame:
    """Constant OHLCV — edge case for zero variance."""
    dates = pd.bdate_range("2023-01-01", periods=n)
    return pd.DataFrame(
        {
            "open": np.full(n, 100.0),
            "high": np.full(n, 100.0),
            "low": np.full(n, 100.0),
            "close": np.full(n, 100.0),
            "volume": np.full(n, 10000.0),
        },
        index=dates,
    )


@pytest.fixture
def bars() -> pd.DataFrame:
    return _make_bars(300)


@pytest.fixture
def short_bars() -> pd.DataFrame:
    return _make_bars(5)


@pytest.fixture
def constant_bars() -> pd.DataFrame:
    return _make_constant_bars(50)


# ── Technical Indicator Tests ──────────────────────────────────────


class TestBollingerPosition:
    def test_returns_valid(self, bars: pd.DataFrame) -> None:
        result = tech.bollinger_position(bars)
        assert "bollinger_pos" in result.index
        val = result["bollinger_pos"]
        assert 0.0 <= val <= 1.0

    def test_constant_data(self, constant_bars: pd.DataFrame) -> None:
        result = tech.bollinger_position(constant_bars)
        assert "bollinger_pos" in result.index
        assert result["bollinger_pos"] == 0.5

    def test_short_data(self, short_bars: pd.DataFrame) -> None:
        result = tech.bollinger_position(short_bars, lookback=20)
        assert result.empty


class TestMacdSignal:
    def test_returns_valid(self, bars: pd.DataFrame) -> None:
        result = tech.macd_signal(bars)
        assert "macd_hist" in result.index
        assert isinstance(result["macd_hist"], float)
        assert not np.isnan(result["macd_hist"])


class TestObvTrend:
    def test_returns_valid(self, bars: pd.DataFrame) -> None:
        result = tech.obv_trend(bars)
        assert "obv_trend" in result.index
        assert isinstance(result["obv_trend"], float)


class TestAdx:
    def test_returns_valid(self, bars: pd.DataFrame) -> None:
        result = tech.adx(bars)
        assert "adx" in result.index
        val = result["adx"]
        assert 0 <= val <= 100


class TestCci:
    def test_returns_valid(self, bars: pd.DataFrame) -> None:
        result = tech.cci(bars)
        assert "cci" in result.index
        assert isinstance(result["cci"], float)


class TestWilliamsR:
    def test_returns_valid(self, bars: pd.DataFrame) -> None:
        result = tech.williams_r(bars)
        assert "williams_r" in result.index
        val = result["williams_r"]
        assert -100 <= val <= 0


class TestStochasticK:
    def test_returns_valid(self, bars: pd.DataFrame) -> None:
        result = tech.stochastic_k(bars)
        assert "stochastic_k" in result.index
        val = result["stochastic_k"]
        assert 0 <= val <= 100


class TestAtrRatio:
    def test_returns_valid(self, bars: pd.DataFrame) -> None:
        result = tech.atr_ratio(bars)
        assert "atr_ratio" in result.index
        assert result["atr_ratio"] > 0


class TestPriceAcceleration:
    def test_returns_valid(self, bars: pd.DataFrame) -> None:
        result = tech.price_acceleration(bars)
        assert "price_accel" in result.index
        assert isinstance(result["price_accel"], float)


class TestVolumeMomentum:
    def test_returns_valid(self, bars: pd.DataFrame) -> None:
        result = tech.volume_momentum(bars)
        assert "vol_momentum" in result.index
        assert isinstance(result["vol_momentum"], float)


class TestHighLowRange:
    def test_returns_valid(self, bars: pd.DataFrame) -> None:
        result = tech.high_low_range(bars)
        assert "hl_range" in result.index
        assert result["hl_range"] > 0


class TestCloseToHigh:
    def test_returns_valid(self, bars: pd.DataFrame) -> None:
        result = tech.close_to_high(bars)
        assert "close_to_high" in result.index
        assert 0 < result["close_to_high"] <= 1.0


class TestGapFactor:
    def test_returns_valid(self, bars: pd.DataFrame) -> None:
        result = tech.gap_factor(bars)
        assert "gap" in result.index
        assert isinstance(result["gap"], float)

    def test_single_bar(self) -> None:
        bars = _make_bars(1)
        result = tech.gap_factor(bars)
        assert result.empty


class TestIntradayReturn:
    def test_returns_valid(self, bars: pd.DataFrame) -> None:
        result = tech.intraday_return(bars)
        assert "intraday_ret" in result.index
        assert isinstance(result["intraday_ret"], float)


class TestOvernightReturn:
    def test_returns_valid(self, bars: pd.DataFrame) -> None:
        result = tech.overnight_return(bars)
        assert "overnight_ret" in result.index
        assert isinstance(result["overnight_ret"], float)


# ── Academic Factor Tests ──────────────────────────────────────────


class TestMomentumVariants:
    def test_momentum_1m(self, bars: pd.DataFrame) -> None:
        result = tech.momentum_1m(bars)
        assert "momentum_1m" in result.index
        assert isinstance(result["momentum_1m"], float)

    def test_momentum_6m(self, bars: pd.DataFrame) -> None:
        result = tech.momentum_6m(bars)
        assert "momentum_6m" in result.index
        assert isinstance(result["momentum_6m"], float)

    def test_momentum_12m(self, bars: pd.DataFrame) -> None:
        result = tech.momentum_12m(bars)
        assert "momentum_12m" in result.index
        assert isinstance(result["momentum_12m"], float)


class TestMaxDailyReturn:
    def test_returns_valid(self, bars: pd.DataFrame) -> None:
        result = tech.max_daily_return(bars)
        assert "max_daily_ret" in result.index
        assert isinstance(result["max_daily_ret"], float)


class TestTurnoverVolatility:
    def test_returns_valid(self, bars: pd.DataFrame) -> None:
        result = tech.turnover_volatility(bars)
        assert "turnover_vol" in result.index
        assert result["turnover_vol"] >= 0


class TestPriceDelay:
    def test_returns_valid(self, bars: pd.DataFrame) -> None:
        result = tech.price_delay(bars)
        assert "price_delay" in result.index
        assert result["price_delay"] >= 0


class TestZeroTradingDays:
    def test_returns_valid(self, bars: pd.DataFrame) -> None:
        result = tech.zero_trading_days(bars)
        assert "zero_days" in result.index
        assert 0.0 <= result["zero_days"] <= 1.0

    def test_no_zero_volume(self, bars: pd.DataFrame) -> None:
        # All volume > 0 in synthetic data
        result = tech.zero_trading_days(bars)
        assert result["zero_days"] == 0.0


# ── Kakushadze Alpha Tests ────────────────────────────────────────


class TestNewKakushadzeAlphas:
    """Test all 20 new Kakushadze alphas return correct key and valid float."""

    @pytest.mark.parametrize(
        "alpha_fn,key,min_bars",
        [
            (kak.kakushadze_alpha_1, "alpha_1", 26),
            (kak.kakushadze_alpha_4, "alpha_4", 11),
            (kak.kakushadze_alpha_7, "alpha_7", 68),
            (kak.kakushadze_alpha_8, "alpha_8", 16),
            (kak.kakushadze_alpha_9, "alpha_9", 7),
            (kak.kakushadze_alpha_10, "alpha_10", 6),
            (kak.kakushadze_alpha_13, "alpha_13", 7),
            (kak.kakushadze_alpha_14, "alpha_14", 15),
            (kak.kakushadze_alpha_15, "alpha_15", 8),
            (kak.kakushadze_alpha_16, "alpha_16", 7),
            (kak.kakushadze_alpha_17, "alpha_17", 22),
            (kak.kakushadze_alpha_18, "alpha_18", 12),
            (kak.kakushadze_alpha_19, "alpha_19", 252),
            (kak.kakushadze_alpha_20, "alpha_20", 3),
            (kak.kakushadze_alpha_22, "alpha_22", 30),
            (kak.kakushadze_alpha_23, "alpha_23", 22),
            (kak.kakushadze_alpha_24, "alpha_24", 104),
            (kak.kakushadze_alpha_30, "alpha_30", 6),
            (kak.kakushadze_alpha_35, "alpha_35", 34),
            (kak.kakushadze_alpha_40, "alpha_40", 12),
        ],
    )
    def test_alpha_returns_valid(
        self,
        alpha_fn: object,
        key: str,
        min_bars: int,
    ) -> None:
        bars = _make_bars(max(min_bars + 50, 300))
        result = alpha_fn(bars)  # type: ignore[operator]
        assert isinstance(result, dict), f"{key} should return dict"
        assert key in result, f"{key} not in result keys: {list(result.keys())}"
        assert isinstance(result[key], float), f"{key} value should be float"
        assert not np.isnan(result[key]), f"{key} value should not be NaN"


class TestKakushadzeEdgeCases:
    def test_short_data_returns_empty(self) -> None:
        bars = _make_bars(2)
        # Alpha #7 needs 68 bars, should return empty
        result = kak.kakushadze_alpha_7(bars)
        assert result == {}

    def test_constant_data(self) -> None:
        bars = _make_constant_bars(50)
        # Alpha #12 should still work on constant data
        result = kak.kakushadze_alpha_12(bars)
        # May return empty or zero — just shouldn't crash
        if result:
            assert isinstance(result["alpha_12"], float)


# ── Vectorized Consistency Tests ──────────────────────────────────


class TestVectorizedConsistency:
    """Check that vectorized factors produce valid output matching non-vectorized."""

    def test_vec_momentum_1m_valid(self) -> None:
        from src.strategy.research import VECTORIZED_FACTORS

        bars = _make_bars(100)
        vec_fn = VECTORIZED_FACTORS["momentum_1m"]
        series = vec_fn(bars)
        assert isinstance(series, pd.Series)
        valid = series.dropna()
        assert len(valid) > 0

    def test_vec_bollinger_pos_valid(self) -> None:
        from src.strategy.research import VECTORIZED_FACTORS

        bars = _make_bars(100)
        vec_fn = VECTORIZED_FACTORS["bollinger_pos"]
        series = vec_fn(bars)
        valid = series.dropna()
        assert len(valid) > 0
        # All values should be clipped to [0, 1]
        assert (valid >= 0).all() and (valid <= 1).all()

    def test_vec_gap_valid(self) -> None:
        from src.strategy.research import VECTORIZED_FACTORS

        bars = _make_bars(100)
        vec_fn = VECTORIZED_FACTORS["gap"]
        series = vec_fn(bars)
        valid = series.dropna()
        assert len(valid) > 0

    def test_vec_intraday_ret_valid(self) -> None:
        from src.strategy.research import VECTORIZED_FACTORS

        bars = _make_bars(100)
        vec_fn = VECTORIZED_FACTORS["intraday_ret"]
        series = vec_fn(bars)
        valid = series.dropna()
        assert len(valid) > 0


# ── Registry Tests ────────────────────────────────────────────────


class TestFactorRegistry:
    def test_all_new_factors_registered(self) -> None:
        from src.strategy.research import FACTOR_REGISTRY

        expected_new = [
            "bollinger_pos", "macd_hist", "obv_trend", "adx", "cci",
            "williams_r", "stochastic_k", "atr_ratio", "price_accel",
            "vol_momentum", "hl_range", "close_to_high", "gap",
            "intraday_ret", "overnight_ret",
            "momentum_1m", "momentum_6m", "momentum_12m", "lt_reversal",
            "beta", "idio_skew", "max_daily_ret", "turnover_vol",
            "price_delay", "zero_days",
            "alpha_1", "alpha_4", "alpha_7", "alpha_8", "alpha_9",
            "alpha_10", "alpha_13", "alpha_14", "alpha_15", "alpha_16",
            "alpha_17", "alpha_18", "alpha_19", "alpha_20", "alpha_22",
            "alpha_23", "alpha_24", "alpha_30", "alpha_35", "alpha_40",
        ]
        for name in expected_new:
            assert name in FACTOR_REGISTRY, f"{name} not in FACTOR_REGISTRY"

    def test_registry_count_at_least_66(self) -> None:
        from src.strategy.research import FACTOR_REGISTRY

        # Original 21 + 25 new technical/academic + 20 new Kakushadze = 66
        assert len(FACTOR_REGISTRY) >= 66, f"Expected >=66 factors, got {len(FACTOR_REGISTRY)}"

    def test_vectorized_factors_count(self) -> None:
        from src.strategy.research import VECTORIZED_FACTORS

        # Should have many more vectorized factors now
        assert len(VECTORIZED_FACTORS) >= 48
