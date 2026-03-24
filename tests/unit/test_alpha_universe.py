"""Tests for src/alpha/universe.py — 股票池篩選。"""

import pandas as pd
import pytest

from src.alpha.universe import UniverseConfig, UniverseFilter


def _make_ohlcv(n_days: int, base_price: float = 100.0, volume: float = 1000.0) -> pd.DataFrame:
    """產生 n 天的假 OHLCV 數據。"""
    dates = pd.bdate_range("2020-01-01", periods=n_days)
    return pd.DataFrame(
        {
            "open": base_price,
            "high": base_price * 1.01,
            "low": base_price * 0.99,
            "close": base_price,
            "volume": volume,
        },
        index=dates,
    )


class TestUniverseFilter:
    def test_default_config_passes_all(self):
        data = {"A": _make_ohlcv(300), "B": _make_ohlcv(300)}
        uf = UniverseFilter()
        result = uf.filter(data, pd.Timestamp("2021-03-01"))
        assert result == ["A", "B"]

    def test_min_listing_days_filters_short(self):
        data = {"A": _make_ohlcv(300), "B": _make_ohlcv(100)}
        uf = UniverseFilter(UniverseConfig(min_listing_days=252))
        result = uf.filter(data, pd.Timestamp("2021-03-01"))
        assert result == ["A"]

    def test_min_avg_volume_filters_low(self):
        data = {
            "A": _make_ohlcv(300, volume=10000.0),
            "B": _make_ohlcv(300, volume=50.0),
        }
        uf = UniverseFilter(UniverseConfig(min_avg_volume=1000.0, min_listing_days=1))
        result = uf.filter(data, pd.Timestamp("2021-03-01"))
        assert result == ["A"]

    def test_min_avg_turnover_filters_low(self):
        data = {
            "A": _make_ohlcv(300, base_price=100, volume=10000),  # turnover = 1M
            "B": _make_ohlcv(300, base_price=10, volume=10),  # turnover = 100
        }
        uf = UniverseFilter(UniverseConfig(min_avg_turnover=50000.0, min_listing_days=1))
        result = uf.filter(data, pd.Timestamp("2021-03-01"))
        assert result == ["A"]

    def test_max_missing_pct_filters_incomplete(self):
        df = _make_ohlcv(300)
        # 注入大量 NaN
        df.loc[df.index[-30:], "close"] = float("nan")
        data = {"A": _make_ohlcv(300), "B": df}
        uf = UniverseFilter(UniverseConfig(max_missing_pct=0.05, min_listing_days=1))
        result = uf.filter(data, pd.Timestamp("2021-03-01"))
        assert result == ["A"]

    def test_time_causality(self):
        """篩選只看到 date 之前的數據。"""
        data = {"A": _make_ohlcv(300)}
        uf = UniverseFilter(UniverseConfig(min_listing_days=252))
        # 太早 → 不夠天數
        early = uf.filter(data, pd.Timestamp("2020-06-01"))
        assert early == []
        # 夠晚 → 通過
        late = uf.filter(data, pd.Timestamp("2021-03-01"))
        assert late == ["A"]

    def test_filter_timeseries(self):
        data = {"A": _make_ohlcv(300)}
        uf = UniverseFilter(UniverseConfig(min_listing_days=1))
        dates = [pd.Timestamp("2020-01-10"), pd.Timestamp("2020-06-01")]
        result = uf.filter_timeseries(data, dates)
        assert len(result) == 2
        assert "A" in result[dates[0]]

    def test_empty_data(self):
        uf = UniverseFilter()
        result = uf.filter({}, pd.Timestamp("2021-01-01"))
        assert result == []
