"""FinMind Feed 測試 — mock DataLoader，不呼叫真實 API。"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd

from src.data.sources.finmind import FinMindFeed
from src.data.sources.finmind_common import strip_tw_suffix, ensure_tw_suffix


# ── Helper ──

def _make_finmind_response(n: int = 10) -> pd.DataFrame:
    """Build a fake FinMind taiwan_stock_daily response."""
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "stock_id": ["2330"] * n,
        "Trading_Volume": [1_000_000 + i * 1000 for i in range(n)],
        "Trading_money": [50_000_000] * n,
        "open": [580.0 + i for i in range(n)],
        "max": [585.0 + i for i in range(n)],
        "min": [575.0 + i for i in range(n)],
        "close": [582.0 + i for i in range(n)],
        "spread": [2.0] * n,
        "Trading_turnover": [5000] * n,
    })


def _make_empty_response() -> pd.DataFrame:
    return pd.DataFrame()


# ── Suffix handling ──

class TestTwSuffixHandling:
    def test_strip_tw(self):
        assert strip_tw_suffix("2330.TW") == "2330"

    def test_strip_two(self):
        assert strip_tw_suffix("6510.TWO") == "6510"

    def test_strip_no_suffix(self):
        assert strip_tw_suffix("2330") == "2330"

    def test_strip_case_insensitive(self):
        assert strip_tw_suffix("2330.tw") == "2330"

    def test_ensure_bare_number(self):
        assert ensure_tw_suffix("2330") == "2330.TW"

    def test_ensure_already_suffixed(self):
        assert ensure_tw_suffix("2330.TW") == "2330.TW"
        assert ensure_tw_suffix("6510.TWO") == "6510.TWO"

    def test_ensure_non_numeric(self):
        assert ensure_tw_suffix("AAPL") == "AAPL"


# ── Column mapping ──

class TestColumnMapping:
    @patch("src.data.sources.finmind.FinMindFeed._get_dataloader")
    @patch("src.data.sources.parquet_cache.ParquetDiskCache.load", return_value=None)
    @patch("src.data.sources.parquet_cache.ParquetDiskCache.save")
    def test_finmind_columns_to_standard_ohlcv(
        self, mock_save, mock_load_cache, mock_dl
    ):
        """FinMind columns (max, min, Trading_Volume) mapped to standard OHLCV."""
        raw = _make_finmind_response(5)
        loader = MagicMock()
        loader.taiwan_stock_daily.return_value = raw
        mock_dl.return_value = loader

        feed = FinMindFeed(universe=["2330"], cache_size=64)
        df = feed.get_bars("2330.TW", start="2024-01-01", end="2024-12-31")

        assert not df.empty
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        # Verify the mapping: max -> high, min -> low
        assert df["high"].iloc[0] == 585.0
        assert df["low"].iloc[0] == 575.0
        assert df["volume"].iloc[0] == 1_000_000

    @patch("src.data.sources.finmind.FinMindFeed._get_dataloader")
    @patch("src.data.sources.parquet_cache.ParquetDiskCache.load", return_value=None)
    @patch("src.data.sources.parquet_cache.ParquetDiskCache.save")
    def test_index_is_datetimeindex(
        self, mock_save, mock_load_cache, mock_dl
    ):
        raw = _make_finmind_response(5)
        loader = MagicMock()
        loader.taiwan_stock_daily.return_value = raw
        mock_dl.return_value = loader

        feed = FinMindFeed(universe=["2330"], cache_size=64)
        df = feed.get_bars("2330", start="2024-01-01", end="2024-12-31")

        assert isinstance(df.index, pd.DatetimeIndex)
        assert df.index.tz is None  # tz-naive


# ── Empty response ──

class TestEmptyResponse:
    @patch("src.data.sources.finmind.FinMindFeed._get_dataloader")
    @patch("src.data.sources.parquet_cache.ParquetDiskCache.load", return_value=None)
    @patch("src.data.sources.parquet_cache.ParquetDiskCache.save")
    def test_empty_response_returns_empty_df(
        self, mock_save, mock_load_cache, mock_dl
    ):
        loader = MagicMock()
        loader.taiwan_stock_daily.return_value = _make_empty_response()
        mock_dl.return_value = loader

        feed = FinMindFeed(universe=["9999"], cache_size=64)
        df = feed.get_bars("9999.TW")

        assert df.empty
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]

    @patch("src.data.sources.finmind.FinMindFeed._get_dataloader")
    @patch("src.data.sources.parquet_cache.ParquetDiskCache.load", return_value=None)
    @patch("src.data.sources.parquet_cache.ParquetDiskCache.save")
    def test_empty_response_latest_price_is_zero(
        self, mock_save, mock_load_cache, mock_dl
    ):
        loader = MagicMock()
        loader.taiwan_stock_daily.return_value = _make_empty_response()
        mock_dl.return_value = loader

        feed = FinMindFeed(universe=["9999"], cache_size=64)
        price = feed.get_latest_price("9999.TW")
        assert price == Decimal("0")


# ── Cache ──

class TestCache:
    @patch("src.data.sources.finmind.FinMindFeed._get_dataloader")
    @patch("src.data.sources.parquet_cache.ParquetDiskCache.load", return_value=None)
    @patch("src.data.sources.parquet_cache.ParquetDiskCache.save")
    def test_cache_hit_skips_api_call(
        self, mock_save, mock_load_cache, mock_dl
    ):
        """Second call to get_bars with same range should use in-memory LRU cache."""
        raw = _make_finmind_response(5)
        loader = MagicMock()
        loader.taiwan_stock_daily.return_value = raw
        mock_dl.return_value = loader

        feed = FinMindFeed(universe=["2330"], cache_size=64)

        # First call — downloads
        df1 = feed.get_bars("2330.TW")
        assert not df1.empty
        assert loader.taiwan_stock_daily.call_count == 1

        # Second call (no start/end) — cache hit, no additional API call
        df2 = feed.get_bars("2330.TW")
        assert not df2.empty
        assert loader.taiwan_stock_daily.call_count == 1  # Still 1


# ── Universe ──

class TestUniverse:
    def test_universe_normalizes_suffixes(self):
        feed = FinMindFeed(universe=["2330", "2317.TW", "6510.TWO"], cache_size=64)
        universe = feed.get_universe()
        assert "2330.TW" in universe
        assert "2317.TW" in universe
        assert "6510.TWO" in universe

    @patch("src.data.sources.finmind.FinMindFeed._get_dataloader")
    @patch("src.data.sources.parquet_cache.ParquetDiskCache.load", return_value=None)
    @patch("src.data.sources.parquet_cache.ParquetDiskCache.save")
    def test_bare_id_sent_to_api(
        self, mock_save, mock_load_cache, mock_dl
    ):
        """FinMind API should receive bare stock ID without .TW suffix."""
        raw = _make_finmind_response(3)
        loader = MagicMock()
        loader.taiwan_stock_daily.return_value = raw
        mock_dl.return_value = loader

        feed = FinMindFeed(universe=["2330.TW"], cache_size=64)
        feed.get_bars("2330.TW", start="2024-01-01", end="2024-12-31")

        # Verify the API was called with bare ID
        call_kwargs = loader.taiwan_stock_daily.call_args
        assert call_kwargs.kwargs["stock_id"] == "2330"
