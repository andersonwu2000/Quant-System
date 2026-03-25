"""Tests for Kakushadze 101 selected alpha factors and helpers."""

import numpy as np
import pandas as pd

from src.strategy.factors import (
    _decay_linear,
    _rank,
    _ts_rank,
    kakushadze_alpha_2,
    kakushadze_alpha_3,
    kakushadze_alpha_6,
    kakushadze_alpha_12,
    kakushadze_alpha_33,
    kakushadze_alpha_34,
    kakushadze_alpha_38,
    kakushadze_alpha_44,
    kakushadze_alpha_53,
    kakushadze_alpha_101,
)


def _make_bars(n: int = 30, seed: int = 42) -> pd.DataFrame:
    """Create a realistic test DataFrame with OHLCV data."""
    rng = np.random.RandomState(seed)
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    close = 100.0 + np.cumsum(rng.randn(n) * 0.5)
    high = close + rng.uniform(0.1, 1.0, n)
    low = close - rng.uniform(0.1, 1.0, n)
    open_ = close + rng.randn(n) * 0.3
    volume = rng.randint(500_000, 2_000_000, n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


def _make_constant_bars(n: int = 30) -> pd.DataFrame:
    """Create bars with constant price and volume (edge case)."""
    dates = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "open": [100.0] * n,
            "high": [100.0] * n,
            "low": [100.0] * n,
            "close": [100.0] * n,
            "volume": [1_000_000.0] * n,
        },
        index=dates,
    )


# ── Helper tests ────────────────────────────────────────────────────────


class TestRank:
    def test_basic_ranking(self):
        s = pd.Series([3, 1, 4, 1, 5])
        result = _rank(s)
        assert result.iloc[-1] == 1.0  # 5 is the largest
        assert result.iloc[1] in (0.2, 0.3)  # one of the 1s

    def test_all_equal(self):
        s = pd.Series([5.0, 5.0, 5.0, 5.0])
        result = _rank(s)
        # All same value -> all get the same rank (average of 1,2,3,4 / 4 = 0.625)
        assert result.nunique() == 1


class TestTsRank:
    def test_ts_rank_monotone(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        result = _ts_rank(s, 5)
        # Last value (10) is max in its window -> ts_rank = 1.0
        assert result.iloc[-1] == 1.0


class TestDecayLinear:
    def test_decay_linear_weighted_average(self):
        s = pd.Series([0.0, 0.0, 0.0, 0.0, 10.0])
        result = _decay_linear(s, 5)
        # weights = [1,2,3,4,5]/15; only last element is 10
        # result = 10 * 5/15 = 10/3 ≈ 3.333
        assert abs(result.iloc[-1] - 10 * 5 / 15) < 1e-6


# ── Alpha function tests ────────────────────────────────────────────────


class TestKakushadzeAlpha2:
    def test_returns_correct_key(self):
        bars = _make_bars(30)
        result = kakushadze_alpha_2(bars)
        assert "alpha_2" in result

    def test_insufficient_data(self):
        bars = _make_bars(5)
        result = kakushadze_alpha_2(bars)
        assert result == {}


class TestKakushadzeAlpha3:
    def test_returns_correct_key(self):
        bars = _make_bars(30)
        result = kakushadze_alpha_3(bars)
        assert "alpha_3" in result

    def test_insufficient_data(self):
        bars = _make_bars(5)
        result = kakushadze_alpha_3(bars)
        assert result == {}


class TestKakushadzeAlpha6:
    def test_returns_correct_key(self):
        bars = _make_bars(30)
        result = kakushadze_alpha_6(bars)
        assert "alpha_6" in result


class TestKakushadzeAlpha12:
    def test_returns_correct_key(self):
        bars = _make_bars(30)
        result = kakushadze_alpha_12(bars)
        assert "alpha_12" in result

    def test_insufficient_data(self):
        bars = _make_bars(2)
        result = kakushadze_alpha_12(bars)
        assert result == {}


class TestKakushadzeAlpha33:
    def test_returns_correct_key(self):
        bars = _make_bars(30)
        result = kakushadze_alpha_33(bars)
        assert "alpha_33" in result


class TestKakushadzeAlpha34:
    def test_returns_correct_key(self):
        bars = _make_bars(30)
        result = kakushadze_alpha_34(bars)
        assert "alpha_34" in result


class TestKakushadzeAlpha38:
    def test_returns_correct_key(self):
        bars = _make_bars(30)
        result = kakushadze_alpha_38(bars)
        assert "alpha_38" in result


class TestKakushadzeAlpha44:
    def test_returns_correct_key(self):
        bars = _make_bars(30)
        result = kakushadze_alpha_44(bars)
        assert "alpha_44" in result


class TestKakushadzeAlpha53:
    def test_returns_correct_key(self):
        bars = _make_bars(30)
        result = kakushadze_alpha_53(bars)
        assert "alpha_53" in result


class TestKakushadzeAlpha101:
    def test_returns_correct_key(self):
        bars = _make_bars(30)
        result = kakushadze_alpha_101(bars)
        assert "alpha_101" in result

    def test_single_bar(self):
        bars = _make_bars(1)
        result = kakushadze_alpha_101(bars)
        assert "alpha_101" in result

    def test_value_range(self):
        """Alpha 101 = (close-open)/((high-low)+0.001), should be in [-1, 1] approx."""
        bars = _make_bars(30)
        result = kakushadze_alpha_101(bars)
        assert -2.0 <= result["alpha_101"] <= 2.0


class TestConstantData:
    """Edge case: constant prices/volume should not crash."""

    def test_alpha_2_constant(self):
        bars = _make_constant_bars(30)
        result = kakushadze_alpha_2(bars)
        # May return {} (NaN correlation) or a value; should not raise
        assert isinstance(result, dict)

    def test_alpha_101_constant(self):
        bars = _make_constant_bars(30)
        result = kakushadze_alpha_101(bars)
        # high == low == close == open => (0)/(0+0.001) = 0
        if result:
            assert result["alpha_101"] == 0.0
