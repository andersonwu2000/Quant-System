"""FinMind Fundamentals 測試 — mock DataLoader，不呼叫真實 API。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data.sources.finmind_fundamentals import FinMindFundamentals


# ── Helpers ──

def _make_per_response() -> pd.DataFrame:
    """Fake TaiwanStockPER response."""
    return pd.DataFrame({
        "date": ["2024-03-01", "2024-03-02", "2024-03-03"],
        "stock_id": ["2330"] * 3,
        "PER": [25.5, 26.0, 25.8],
        "PBR": [6.2, 6.3, 6.1],
    })


def _make_financial_statement_response() -> pd.DataFrame:
    """Fake TaiwanStockFinancialStatement response."""
    return pd.DataFrame({
        "date": ["2024-01-01", "2024-01-01", "2024-04-01", "2024-04-01"],
        "stock_id": ["2330"] * 4,
        "type": ["EPS", "ROE", "EPS", "ROE"],
        "value": [5.2, 18.5, 5.8, 20.1],
    })


def _make_stock_info_response() -> pd.DataFrame:
    """Fake TaiwanStockInfo response."""
    return pd.DataFrame({
        "stock_id": ["2330", "2317", "2454"],
        "stock_name": ["TSMC", "Hon Hai", "MediaTek"],
        "industry_category": ["半導體業", "其他電子業", "半導體業"],
    })


def _make_revenue_response() -> pd.DataFrame:
    """Fake TaiwanStockMonthRevenue response."""
    return pd.DataFrame({
        "date": ["2023-01-01", "2023-02-01", "2024-01-01", "2024-02-01"],
        "stock_id": ["2330"] * 4,
        "revenue": [200_000, 180_000, 230_000, 210_000],
    })


def _make_dividend_response() -> pd.DataFrame:
    """Fake TaiwanStockDividend response."""
    return pd.DataFrame({
        "date": ["2024-06-15", "2024-09-15"],
        "stock_id": ["2330"] * 2,
        "CashEarningsDistribution": [3.5, 3.5],
        "StockEarningsDistribution": [0.0, 0.0],
    })


# ── get_financials ──

class TestGetFinancials:
    @patch("src.data.sources.finmind_fundamentals.FinMindFundamentals._get_dataloader")
    def test_get_financials_returns_metrics(self, mock_dl):
        loader = MagicMock()
        loader.taiwan_stock_per.return_value = _make_per_response()
        loader.taiwan_stock_financial_statement.return_value = (
            _make_financial_statement_response()
        )
        mock_dl.return_value = loader

        provider = FinMindFundamentals(token="test-token")
        result = provider.get_financials("2330.TW", date="2024-03-03")

        assert "pe_ratio" in result
        assert "pb_ratio" in result
        assert "eps" in result
        assert "roe" in result
        assert result["pe_ratio"] == pytest.approx(25.8, rel=0.01)
        assert result["pb_ratio"] == pytest.approx(6.1, rel=0.01)

    @patch("src.data.sources.finmind_fundamentals.FinMindFundamentals._get_dataloader")
    def test_missing_data_returns_empty(self, mock_dl):
        loader = MagicMock()
        loader.taiwan_stock_per.return_value = pd.DataFrame()
        loader.taiwan_stock_financial_statement.return_value = pd.DataFrame()
        mock_dl.return_value = loader

        provider = FinMindFundamentals()
        result = provider.get_financials("9999.TW")

        assert result == {}


# ── get_sector ──

class TestGetSector:
    @patch("src.data.sources.finmind_fundamentals.FinMindFundamentals._get_dataloader")
    def test_get_sector_returns_category(self, mock_dl):
        loader = MagicMock()
        loader.taiwan_stock_info.return_value = _make_stock_info_response()
        mock_dl.return_value = loader

        provider = FinMindFundamentals()
        sector = provider.get_sector("2330.TW")

        assert sector == "半導體業"

    @patch("src.data.sources.finmind_fundamentals.FinMindFundamentals._get_dataloader")
    def test_get_sector_unknown_symbol(self, mock_dl):
        loader = MagicMock()
        loader.taiwan_stock_info.return_value = _make_stock_info_response()
        mock_dl.return_value = loader

        provider = FinMindFundamentals()
        sector = provider.get_sector("9999.TW")

        assert sector == ""


# ── get_revenue ──

class TestGetRevenue:
    @patch("src.data.sources.finmind_fundamentals.FinMindFundamentals._get_dataloader")
    def test_get_revenue_with_yoy_growth(self, mock_dl):
        loader = MagicMock()
        loader.taiwan_stock_month_revenue.return_value = _make_revenue_response()
        mock_dl.return_value = loader

        provider = FinMindFundamentals()
        result = provider.get_revenue("2330.TW", start="2024-01-01", end="2024-12-31")

        assert not result.empty
        assert "revenue" in result.columns
        assert "yoy_growth" in result.columns
        # 2024-01 vs 2023-01: (230000/200000 - 1) * 100 = 15%
        jan_row = result[result["date"] == pd.Timestamp("2024-01-01")]
        if not jan_row.empty:
            assert jan_row.iloc[0]["yoy_growth"] == pytest.approx(15.0, rel=0.01)


# ── Cache TTL ──

class TestCacheTtl:
    @patch("src.data.sources.finmind_fundamentals.FinMindFundamentals._get_dataloader")
    def test_cache_ttl(self, mock_dl):
        """Cached data is returned on second call; expired data triggers re-fetch."""
        loader = MagicMock()
        loader.taiwan_stock_per.return_value = _make_per_response()
        loader.taiwan_stock_financial_statement.return_value = (
            _make_financial_statement_response()
        )
        mock_dl.return_value = loader

        provider = FinMindFundamentals()

        # First call
        result1 = provider.get_financials("2330.TW")
        call_count_1 = mock_dl.call_count

        # Second call — should use cache
        result2 = provider.get_financials("2330.TW")
        call_count_2 = mock_dl.call_count

        assert result1 == result2
        assert call_count_2 == call_count_1  # No additional DataLoader creation

    @patch("src.data.sources.finmind_fundamentals.FinMindFundamentals._get_dataloader")
    def test_expired_cache_refetches(self, mock_dl):
        """Manually expire cache to verify re-fetch."""
        loader = MagicMock()
        loader.taiwan_stock_per.return_value = _make_per_response()
        loader.taiwan_stock_financial_statement.return_value = (
            _make_financial_statement_response()
        )
        mock_dl.return_value = loader

        provider = FinMindFundamentals()

        # First call
        provider.get_financials("2330.TW")

        # Manually expire the cache entry
        for key in list(provider._cache.keys()):
            ts, data = provider._cache[key]
            provider._cache[key] = (ts - 8 * 24 * 3600, data)  # 8 days ago

        # Second call — should re-fetch
        provider.get_financials("2330.TW")
        assert mock_dl.call_count >= 2
