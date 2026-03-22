"""因子測試。"""

import numpy as np
import pandas as pd
import pytest

from src.strategy.factors import (
    mean_reversion,
    momentum,
    moving_average_crossover,
    rsi,
    volatility,
)


def _make_bars(prices: list[float]) -> pd.DataFrame:
    """建立測試用 DataFrame。"""
    dates = pd.date_range("2020-01-01", periods=len(prices), freq="B")
    return pd.DataFrame(
        {
            "open": prices,
            "high": [p * 1.01 for p in prices],
            "low": [p * 0.99 for p in prices],
            "close": prices,
            "volume": [1000000] * len(prices),
        },
        index=dates,
    )


class TestMomentum:
    def test_positive_momentum(self):
        # 股價從 100 上漲到 150
        prices = list(np.linspace(100, 150, 260))
        bars = _make_bars(prices)
        result = momentum(bars, lookback=252, skip=5)
        assert not result.empty
        assert result["momentum"] > 0

    def test_negative_momentum(self):
        # 股價從 150 下跌到 100
        prices = list(np.linspace(150, 100, 260))
        bars = _make_bars(prices)
        result = momentum(bars, lookback=252, skip=5)
        assert result["momentum"] < 0

    def test_insufficient_data(self):
        bars = _make_bars([100, 101, 102])
        result = momentum(bars, lookback=252)
        assert result.empty


class TestMeanReversion:
    def test_below_mean(self):
        # 股價在 100 附近，最後突然跌到 80
        prices = [100.0] * 30 + [80.0]
        bars = _make_bars(prices)
        result = mean_reversion(bars, lookback=20)
        assert result["z_score"] > 0  # 偏低→正的回歸信號

    def test_above_mean(self):
        prices = [100.0] * 30 + [120.0]
        bars = _make_bars(prices)
        result = mean_reversion(bars, lookback=20)
        assert result["z_score"] < 0  # 偏高→負的回歸信號


class TestVolatility:
    def test_nonzero(self):
        prices = list(np.random.RandomState(42).normal(100, 2, 50))
        bars = _make_bars(prices)
        result = volatility(bars, lookback=20)
        assert result["volatility"] > 0

    def test_zero_vol_constant_price(self):
        prices = [100.0] * 30
        bars = _make_bars(prices)
        result = volatility(bars, lookback=20)
        assert result["volatility"] == 0.0


class TestRSI:
    def test_overbought(self):
        # 連續上漲
        prices = list(range(100, 130))
        bars = _make_bars(prices)
        result = rsi(bars, period=14)
        assert result["rsi"] > 70  # 超買

    def test_oversold(self):
        # 連續下跌
        prices = list(range(130, 100, -1))
        bars = _make_bars(prices)
        result = rsi(bars, period=14)
        assert result["rsi"] < 30  # 超賣


class TestMACrossover:
    def test_bullish(self):
        # 快線在慢線之上
        prices = list(np.linspace(100, 150, 60))
        bars = _make_bars(prices)
        result = moving_average_crossover(bars, fast=10, slow=50)
        assert result["ma_cross"] > 0

    def test_insufficient_data(self):
        bars = _make_bars([100, 101])
        result = moving_average_crossover(bars, fast=10, slow=50)
        assert result.empty
