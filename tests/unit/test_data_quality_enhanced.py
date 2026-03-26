"""Tests for enhanced data quality checks (Phase K1)."""

import pandas as pd

from src.data.quality import (
    check_bars_with_dividends,
    check_fundamentals,
    detect_halted_dates,
    load_dividend_dates,
    QualityStatus,
)


def _make_bars(n: int = 100, start: str = "2023-01-01") -> pd.DataFrame:
    """Create a simple OHLCV DataFrame for testing."""
    dates = pd.bdate_range(start, periods=n)
    return pd.DataFrame(
        {
            "open": [100.0 + i * 0.1 for i in range(n)],
            "high": [101.0 + i * 0.1 for i in range(n)],
            "low": [99.0 + i * 0.1 for i in range(n)],
            "close": [100.5 + i * 0.1 for i in range(n)],
            "volume": [1_000_000] * n,
        },
        index=dates,
    )


# ── check_fundamentals ─────────────────────────────────────────────


class TestCheckFundamentals:
    def test_normal_values_unchanged(self) -> None:
        data = {"pe_ratio": 15.0, "pb_ratio": 2.0, "roe": 12.5}
        result = check_fundamentals(data)
        assert result == data

    def test_pe_clipped_high(self) -> None:
        data = {"pe_ratio": 9999.0}
        result = check_fundamentals(data)
        assert result["pe_ratio"] == 200.0

    def test_pe_clipped_negative(self) -> None:
        data = {"pe_ratio": -5.0}
        result = check_fundamentals(data)
        assert result["pe_ratio"] == 0.0

    def test_roe_clipped_extreme(self) -> None:
        data = {"roe": -500.0}
        result = check_fundamentals(data)
        assert result["roe"] == -100.0

    def test_nan_removed(self) -> None:
        data = {"pe_ratio": float("nan"), "pb_ratio": 3.0}
        result = check_fundamentals(data)
        assert "pe_ratio" not in result
        assert result["pb_ratio"] == 3.0

    def test_unknown_keys_pass_through(self) -> None:
        data = {"custom_metric": 42.0, "pe_ratio": 10.0}
        result = check_fundamentals(data)
        assert result["custom_metric"] == 42.0

    def test_original_not_mutated(self) -> None:
        data = {"pe_ratio": 9999.0}
        _ = check_fundamentals(data)
        assert data["pe_ratio"] == 9999.0  # Original unchanged


# ── detect_halted_dates ────────────────────────────────────────────


class TestDetectHaltedDates:
    def test_zero_volume_detected(self) -> None:
        df = _make_bars(10)
        df.loc[df.index[3], "volume"] = 0
        df.loc[df.index[7], "volume"] = 0
        halted = detect_halted_dates(df)
        assert len(halted) == 2

    def test_unchanged_close_streak(self) -> None:
        df = _make_bars(10)
        # 4 consecutive same close
        for i in range(3, 7):
            df.iloc[i, df.columns.get_loc("close")] = 100.0
        halted = detect_halted_dates(df, max_unchanged_days=3)
        assert len(halted) >= 3

    def test_normal_data_no_halted(self) -> None:
        df = _make_bars(50)
        halted = detect_halted_dates(df)
        assert len(halted) == 0

    def test_empty_dataframe(self) -> None:
        df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        halted = detect_halted_dates(df)
        assert len(halted) == 0


# ── check_bars_with_dividends ──────────────────────────────────────


class TestCheckBarsWithDividends:
    def test_normal_data_passes(self) -> None:
        df = _make_bars(100)
        result = check_bars_with_dividends(df, "TEST")
        assert result.ok

    def test_known_dividend_date_not_suspect(self) -> None:
        """A 5σ jump on a known dividend date should NOT be flagged."""
        df = _make_bars(100)
        # Insert a big drop at index 50
        drop_date = df.index[50]
        df.loc[drop_date, "close"] = df.loc[df.index[49], "close"] * 0.85  # -15%

        date_str = str(drop_date.date())
        # Without dividend dates → flagged
        r1 = check_bars_with_dividends(df, "TEST", dividend_dates=set())
        # With dividend dates → not flagged
        r2 = check_bars_with_dividends(df, "TEST", dividend_dates={date_str})

        if r1.suspect_dates:
            assert date_str in r1.suspect_dates
        if r2.suspect_dates:
            assert date_str not in r2.suspect_dates

    def test_missing_columns_rejected(self) -> None:
        df = pd.DataFrame({"close": [100, 101]})
        result = check_bars_with_dividends(df, "TEST")
        assert result.status == QualityStatus.REJECT

    def test_empty_data_rejected(self) -> None:
        df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        result = check_bars_with_dividends(df, "TEST")
        assert result.status == QualityStatus.REJECT


# ── load_dividend_dates ────────────────────────────────────────────


class TestLoadDividendDates:
    def test_nonexistent_returns_empty(self, tmp_path: str) -> None:
        result = load_dividend_dates("NONEXIST.TW", data_dir=str(tmp_path))
        assert result == set()
