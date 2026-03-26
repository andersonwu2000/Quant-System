"""數據源工廠測試。"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.data.sources import create_feed, create_fundamentals
from src.data.feed import DataFeed
from src.data.fundamentals import FundamentalsProvider


class TestCreateFeed:
    def test_create_feed_yahoo(self):
        feed = create_feed("yahoo", ["AAPL", "MSFT"])
        assert isinstance(feed, DataFeed)
        assert feed.get_universe() == ["AAPL", "MSFT"]

    @patch("src.data.sources.finmind.FinMindFeed._get_dataloader")
    def test_create_feed_finmind(self, mock_dl):
        feed = create_feed("finmind", ["2330", "2317"], token="test-token")
        assert isinstance(feed, DataFeed)
        universe = feed.get_universe()
        # FinMindFeed normalizes bare IDs to .TW
        assert "2330.TW" in universe
        assert "2317.TW" in universe

    def test_create_feed_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown data source"):
            create_feed("nonexistent", ["AAPL"])

    def test_create_feed_unknown_message_lists_available(self):
        with pytest.raises(ValueError, match="Available: yahoo, finmind"):
            create_feed("polygon", ["AAPL"])


class TestCreateFundamentals:
    def test_create_fundamentals_finmind(self):
        provider = create_fundamentals("finmind", token="test-token")
        assert provider is not None
        assert isinstance(provider, FundamentalsProvider)

    def test_create_fundamentals_yahoo_may_return_finmind(self):
        """Yahoo mode returns FinMind fundamentals if token is available, None otherwise."""
        provider = create_fundamentals("yahoo")
        # If QUANT_FINMIND_TOKEN is set, returns FinMindFundamentals; else None
        if provider is not None:
            assert isinstance(provider, FundamentalsProvider)

    def test_create_fundamentals_unknown_returns_none(self):
        provider = create_fundamentals("polygon")
        assert provider is None
