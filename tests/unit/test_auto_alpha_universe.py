"""Tests for UniverseSelector with mock scanner."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
from src.alpha.auto.config import AutoAlphaConfig
from src.alpha.auto.universe import UniverseResult, UniverseSelector


def _make_ohlcv(days: int = 300, avg_volume: float = 1_000_000) -> pd.DataFrame:
    """Create a synthetic OHLCV DataFrame."""
    dates = pd.bdate_range(end="2026-03-25", periods=days)
    rng = np.random.default_rng(42)
    close = 100 + rng.standard_normal(days).cumsum()
    return pd.DataFrame(
        {
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.98,
            "close": close,
            "volume": rng.uniform(avg_volume * 0.5, avg_volume * 1.5, days),
        },
        index=dates,
    )


def _make_data(
    symbols: list[str],
    days: int = 300,
    avg_volume: float = 1_000_000,
) -> dict[str, pd.DataFrame]:
    return {s: _make_ohlcv(days, avg_volume) for s in symbols}


class TestUniverseResultDataclass:
    def test_defaults(self) -> None:
        r = UniverseResult()
        assert r.symbols == []
        assert r.excluded_disposition == []
        assert r.excluded_attention == []
        assert r.total_candidates == 0


class TestUniverseSelectorNoScanner:
    """Fallback path — no scanner available."""

    def test_fallback_to_data_keys(self) -> None:
        cfg = AutoAlphaConfig(min_listing_days=10, min_adv=100)
        selector = UniverseSelector(cfg, scanner=None)
        data = _make_data(["AAPL", "MSFT", "GOOG"])
        result = selector.select(data=data)

        assert set(result.symbols) == {"AAPL", "MSFT", "GOOG"}
        assert result.total_candidates == 3
        assert result.excluded_disposition == []

    def test_no_data_no_scanner(self) -> None:
        cfg = AutoAlphaConfig()
        selector = UniverseSelector(cfg, scanner=None)
        result = selector.select(data=None)

        assert result.symbols == []
        assert result.total_candidates == 0

    def test_adv_filter_excludes_illiquid(self) -> None:
        cfg = AutoAlphaConfig(min_adv=5_000_000, min_listing_days=10)
        selector = UniverseSelector(cfg, scanner=None)
        data = _make_data(["AAPL", "MSFT"], avg_volume=100_000)
        result = selector.select(data=data)

        # Average volume ~100k, threshold 5M => all excluded
        assert result.symbols == []

    def test_listing_days_filter(self) -> None:
        cfg = AutoAlphaConfig(min_listing_days=500, min_adv=100)
        selector = UniverseSelector(cfg, scanner=None)
        data = _make_data(["AAPL"], days=100)  # only 100 days
        result = selector.select(data=data)

        assert result.symbols == []


class TestUniverseSelectorWithScanner:
    """Scanner integration path with mocks."""

    def _mock_scanner(
        self,
        volume_codes: list[str],
        disposition: set[str] | None = None,
        attention: set[str] | None = None,
    ) -> MagicMock:
        scanner = MagicMock()
        scanner.top_volume.return_value = [
            {"code": c, "name": c, "close": 100, "volume": 1000000,
             "total_volume": 1000000, "change_price": 1.0, "change_rate": 0.01}
            for c in volume_codes
        ]
        scanner.get_disposition_stocks.return_value = disposition or set()
        scanner.get_attention_stocks.return_value = attention or set()
        return scanner

    def test_scanner_basic(self) -> None:
        codes = ["2330", "2317", "2454"]
        scanner = self._mock_scanner(codes)
        cfg = AutoAlphaConfig(
            universe_count=50,
            min_listing_days=10,
            min_adv=100,
        )
        selector = UniverseSelector(cfg, scanner=scanner)
        data = _make_data(codes)
        result = selector.select(data=data)

        scanner.top_volume.assert_called_once_with(count=50)
        assert set(result.symbols) == set(codes)
        assert result.total_candidates == 3

    def test_disposition_exclusion(self) -> None:
        codes = ["2330", "2317", "2454"]
        scanner = self._mock_scanner(codes, disposition={"2317"})
        cfg = AutoAlphaConfig(
            exclude_disposition=True,
            min_listing_days=10,
            min_adv=100,
        )
        selector = UniverseSelector(cfg, scanner=scanner)
        data = _make_data(codes)
        result = selector.select(data=data)

        assert "2317" not in result.symbols
        assert "2317" in result.excluded_disposition
        assert len(result.symbols) == 2

    def test_attention_exclusion(self) -> None:
        codes = ["2330", "2317"]
        scanner = self._mock_scanner(codes, attention={"2330"})
        cfg = AutoAlphaConfig(
            exclude_attention=True,
            min_listing_days=10,
            min_adv=100,
        )
        selector = UniverseSelector(cfg, scanner=scanner)
        data = _make_data(codes)
        result = selector.select(data=data)

        assert "2330" not in result.symbols
        assert "2330" in result.excluded_attention

    def test_scanner_failure_falls_back(self) -> None:
        scanner = MagicMock()
        scanner.top_volume.side_effect = RuntimeError("API disconnected")
        cfg = AutoAlphaConfig(min_listing_days=10, min_adv=100)
        selector = UniverseSelector(cfg, scanner=scanner)
        data = _make_data(["AAPL", "MSFT"])
        result = selector.select(data=data)

        # Should fall back to data keys
        assert set(result.symbols) == {"AAPL", "MSFT"}

    def test_scanner_without_data_for_symbol(self) -> None:
        """Scanner returns codes not present in data dict — they should be filtered."""
        codes = ["2330", "9999"]
        scanner = self._mock_scanner(codes)
        cfg = AutoAlphaConfig(min_listing_days=10, min_adv=100)
        selector = UniverseSelector(cfg, scanner=scanner)
        data = _make_data(["2330"])  # only 2330 has data
        result = selector.select(data=data)

        assert "2330" in result.symbols
        assert "9999" not in result.symbols
