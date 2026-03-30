"""Tests for src.data.refresh — incremental data refresh engine."""

from __future__ import annotations

import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import date

from src.data.refresh import (
    RefreshReport,
    refresh_dataset_sync,
    _atomic_write,
    _last_date,
    _normalize_ohlcv,
    _parquet_path,
    _read_existing,
)
from src.data.registry import REGISTRY


# ── Helpers ──────────────────────────────────────────────────────────

def _make_ohlcv(days: int = 5, start: str = "2026-01-01") -> pd.DataFrame:
    """Create a minimal valid OHLCV DataFrame."""
    dates = pd.bdate_range(start, periods=days)
    return pd.DataFrame(
        {
            "open": [100.0] * days,
            "high": [105.0] * days,
            "low": [95.0] * days,
            "close": [102.0] * days,
            "volume": [1000.0] * days,
        },
        index=dates,
    )


# ── Unit tests ───────────────────────────────────────────────────────

class TestAtomicWrite:
    def test_writes_parquet(self, tmp_path: Path):
        df = _make_ohlcv()
        target = tmp_path / "test.parquet"
        _atomic_write(df, target)
        assert target.exists()
        result = pd.read_parquet(target)
        assert len(result) == len(df)

    def test_no_tmp_left_on_success(self, tmp_path: Path):
        df = _make_ohlcv()
        target = tmp_path / "test.parquet"
        _atomic_write(df, target)
        assert not (tmp_path / "test.tmp.parquet").exists()

    def test_creates_parent_dirs(self, tmp_path: Path):
        df = _make_ohlcv()
        target = tmp_path / "sub" / "dir" / "test.parquet"
        _atomic_write(df, target)
        assert target.exists()


class TestLastDate:
    def test_datetime_index(self):
        df = _make_ohlcv(3, "2026-03-01")
        result = _last_date(df)
        # bdate_range("2026-03-01", periods=3) = [3/2, 3/3, 3/4] (Mon-Wed)
        assert result == date(2026, 3, 4)

    def test_date_column(self):
        df = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "value": [1, 2]})
        result = _last_date(df)
        assert result == date(2026, 1, 2)

    def test_empty_returns_none(self):
        df = pd.DataFrame()
        assert _last_date(df) is None


class TestNormalizeOhlcv:
    def test_lowercase_columns(self):
        df = pd.DataFrame({"Open": [100], "High": [105], "Low": [95], "Close": [102], "Volume": [1000]},
                          index=pd.DatetimeIndex(["2026-01-01"]))
        result = _normalize_ohlcv(df)
        assert list(result.columns) == ["open", "high", "low", "close", "volume"]

    def test_removes_tz(self):
        idx = pd.DatetimeIndex(["2026-01-01"], tz="US/Eastern")
        df = pd.DataFrame({"open": [100], "high": [105], "low": [95], "close": [102], "volume": [1000]}, index=idx)
        result = _normalize_ohlcv(df)
        assert result.index.tz is None

    def test_removes_zero_prices(self):
        df = pd.DataFrame(
            {"open": [100, 0], "high": [105, 0], "low": [95, 0], "close": [102, 0], "volume": [1000, 0]},
            index=pd.DatetimeIndex(["2026-01-01", "2026-01-02"]),
        )
        result = _normalize_ohlcv(df)
        assert len(result) == 1


class TestParquetPath:
    def test_price_dataset(self):
        p = _parquet_path("2330.TW", "price")
        # Primary source for price is twse (or yahoo/finmind if file exists there)
        assert p.name == "2330.TW_1d.parquet"
        assert p.parent.name in ("twse", "yahoo", "finmind")

    def test_fundamental_dataset(self):
        p = _parquet_path("2330.TW", "revenue")
        assert p.name == "2330.TW_revenue.parquet"
        assert p.parent.name == "finmind"


class TestReadExisting:
    def test_nonexistent_returns_none(self):
        assert _read_existing(Path("/nonexistent/file.parquet")) is None

    def test_reads_valid_parquet(self, tmp_path: Path):
        df = _make_ohlcv()
        path = tmp_path / "test.parquet"
        df.to_parquet(path)
        result = _read_existing(path)
        assert result is not None
        assert len(result) == len(df)


class TestRefreshReport:
    def test_ok_when_no_errors(self):
        r = RefreshReport(dataset="price", total_symbols=10, updated=5, skipped=5)
        assert r.ok

    def test_not_ok_when_error(self):
        r = RefreshReport(dataset="price", error="boom")
        assert not r.ok

    def test_not_ok_when_majority_failed(self):
        r = RefreshReport(dataset="price", total_symbols=10, failed=["a"] * 6)
        assert not r.ok

    def test_summary_format(self):
        r = RefreshReport(dataset="price", total_symbols=10, updated=8, skipped=1,
                          failed=["x"], new_rows=100, duration_seconds=5.3, provider_used="yahoo")
        s = r.summary()
        assert "[price]" in s
        assert "8 updated" in s
        assert "+100 rows" in s


class TestDatasetRegistry:
    def test_all_datasets_have_required_fields(self):
        for name, ds in REGISTRY.items():
            assert ds.suffix, f"{name} missing suffix"
            assert ds.source_dirs, f"{name} missing source_dirs"
            assert ds.finmind_method, f"{name} missing finmind_method"
            assert ds.frequency, f"{name} missing frequency"


class TestRefreshDatasetSync:
    @patch("src.data.refresh._discover_symbols", return_value=[])
    def test_no_symbols_returns_error(self, mock_discover):
        report = refresh_dataset_sync("price")
        assert not report.ok
        assert "No symbols" in report.error

    def test_unknown_dataset(self):
        report = refresh_dataset_sync("nonexistent")
        assert not report.ok
        assert "Unknown" in report.error

    @patch("src.data.refresh._fetch_yahoo")
    @patch("src.data.refresh._discover_symbols")
    def test_skips_fresh_symbols(self, mock_discover, mock_yahoo, tmp_path, monkeypatch):
        from dataclasses import replace
        from datetime import datetime, timedelta
        # Setup: create a parquet with last bar = today (definitely fresh)
        today = datetime.now().strftime("%Y-%m-%d")
        df = pd.DataFrame(
            {"open": [100], "high": [105], "low": [95], "close": [102], "volume": [1000.0]},
            index=pd.DatetimeIndex([today]),
        )
        sym = "TEST.TW"
        patched_price = replace(REGISTRY["price"], source_dirs=(tmp_path,))
        patched_registry = {**REGISTRY, "price": patched_price}
        monkeypatch.setattr("src.data.refresh.REGISTRY", patched_registry)
        monkeypatch.setattr("src.data.registry.REGISTRY", patched_registry)
        path = tmp_path / f"{sym}_1d.parquet"
        df.to_parquet(path)

        mock_discover.return_value = [sym]
        report = refresh_dataset_sync("price", [sym])
        assert report.skipped == 1
        assert report.updated == 0
        mock_yahoo.assert_not_called()
