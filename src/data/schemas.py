"""Data schemas — validation rules for each dataset type.

Uses plain pandas assertions (no Pandera dependency).
Each schema is a function that validates a DataFrame and raises ValueError on failure.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Callable

import pandas as pd

logger = logging.getLogger(__name__)

SchemaValidator = Callable[[pd.DataFrame, str], None]


def _assert_columns(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"[{name}] Missing columns: {missing}")


def _assert_no_all_nan(df: pd.DataFrame, columns: list[str], name: str) -> None:
    for col in columns:
        if col in df.columns and df[col].isna().all():
            raise ValueError(f"[{name}] Column '{col}' is entirely NaN")


def _assert_positive(df: pd.DataFrame, columns: list[str], name: str, allow_zero: bool = False) -> None:
    for col in columns:
        if col not in df.columns:
            continue
        check = (df[col] >= 0) if allow_zero else (df[col] > 0)
        bad = (~check & df[col].notna()).sum()
        if bad > len(df) * 0.10:
            raise ValueError(f"[{name}] Column '{col}' has {bad}/{len(df)} non-positive values (>10%)")


# ── Per-dataset validators ───────────────────────────────────────────

def validate_ohlcv(df: pd.DataFrame, symbol: str = "") -> None:
    """Validate OHLCV price data."""
    name = f"ohlcv:{symbol}" if symbol else "ohlcv"
    if df.empty:
        raise ValueError(f"[{name}] Empty DataFrame")

    _assert_columns(df, {"open", "high", "low", "close", "volume"}, name)

    _assert_positive(df, ["open", "high", "low", "close"], name)
    _assert_positive(df, ["volume"], name, allow_zero=True)

    # high >= low
    if "high" in df.columns and "low" in df.columns:
        violations = (df["high"] < df["low"]).sum()
        if violations > len(df) * 0.01:
            raise ValueError(f"[{name}] {violations} rows with high < low")


def validate_revenue(df: pd.DataFrame, symbol: str = "") -> None:
    """Validate monthly revenue data."""
    name = f"revenue:{symbol}" if symbol else "revenue"
    if df.empty:
        raise ValueError(f"[{name}] Empty DataFrame")
    _assert_columns(df, {"date", "revenue"}, name)
    _assert_no_all_nan(df, ["revenue"], name)


def validate_institutional(df: pd.DataFrame, symbol: str = "") -> None:
    """Validate institutional investor data."""
    name = f"institutional:{symbol}" if symbol else "institutional"
    if df.empty:
        raise ValueError(f"[{name}] Empty DataFrame")
    _assert_columns(df, {"date"}, name)
    # Should have at least one of these
    expected = {"Foreign_Investor_buy", "Foreign_Investor_sell",
                "Investment_Trust_buy", "Investment_Trust_sell"}
    if not expected & set(df.columns):
        # Try alternate names
        alt = {"foreign_net", "trust_net", "dealer_net"}
        if not alt & set(df.columns):
            logger.warning("[%s] No recognizable institutional columns", name)


def validate_margin(df: pd.DataFrame, symbol: str = "") -> None:
    """Validate margin trading data."""
    name = f"margin:{symbol}" if symbol else "margin"
    if df.empty:
        raise ValueError(f"[{name}] Empty DataFrame")
    _assert_columns(df, {"date"}, name)


def validate_generic(df: pd.DataFrame, symbol: str = "") -> None:
    """Generic validator for datasets without specific rules."""
    name = f"generic:{symbol}" if symbol else "generic"
    if df.empty:
        raise ValueError(f"[{name}] Empty DataFrame")
    if "date" not in df.columns and not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(f"[{name}] No date column or DatetimeIndex")


# ── Schema registry ──────────────────────────────────────────────────

SCHEMA_VALIDATORS: dict[str, SchemaValidator] = {
    "price": validate_ohlcv,
    "revenue": validate_revenue,
    "institutional": validate_institutional,
    "margin": validate_margin,
    "per": validate_generic,
    "financial_statement": validate_generic,
    "cash_flows": validate_generic,
    "balance_sheet": validate_generic,
    "securities_lending": validate_generic,
    "shareholding": validate_generic,
    "day_trading": validate_generic,
    "dividend": validate_generic,
}


def validate(dataset: str, df: pd.DataFrame, symbol: str = "") -> bool:
    """Validate a DataFrame against its dataset schema.

    Returns True if valid, raises ValueError if invalid.
    """
    validator = SCHEMA_VALIDATORS.get(dataset, validate_generic)
    validator(df, symbol)
    return True


# ── PIT (Point-in-Time) helpers ──────────────────────────────────────

# Quarterly report deadlines (Taiwan regulations):
# Q1: 5/15, Q2: 8/14 (conservative; legal max 9/14), Q3: 11/14, Q4: next year 3/31
QUARTERLY_DEADLINES: dict[str, tuple[int, int]] = {
    "Q1": (5, 15),
    "Q2": (8, 14),   # Legal max is 9/14, but most companies publish by 8/14
    "Q3": (11, 14),
    "Q4": (3, 31),   # Next year
}


def conservative_announcement_date(report_date: date, quarter: str) -> date:
    """Conservative estimate of when a quarterly report becomes public.

    Uses the legal deadline (latest possible date). Actual announcement_date
    from FinLab upload_date panel would be more precise.
    """
    month, day = QUARTERLY_DEADLINES[quarter]
    year = report_date.year + (1 if quarter == "Q4" else 0)
    return date(year, month, day)


# ── Actual upload date lookup ────────────────────────────────────────

_upload_date_cache: pd.DataFrame | None = None


def _load_upload_dates() -> pd.DataFrame:
    """Load FinLab financial statement upload dates (cached)."""
    global _upload_date_cache
    if _upload_date_cache is not None:
        return _upload_date_cache

    from pathlib import Path
    path = Path("data/finlab/fundamental/upload_date.parquet")
    if not path.exists():
        _upload_date_cache = pd.DataFrame()
        return _upload_date_cache

    try:
        _upload_date_cache = pd.read_parquet(path)
    except Exception:
        _upload_date_cache = pd.DataFrame()
    return _upload_date_cache


def actual_announcement_date(symbol: str, quarter: str) -> date | None:
    """Look up the actual financial statement upload date for a symbol+quarter.

    Returns the real upload date if available, None otherwise.
    Caller should fall back to conservative_announcement_date() when None.
    """
    upload_dates = _load_upload_dates()
    if upload_dates.empty:
        return None

    bare = symbol.replace(".TW", "").replace(".TWO", "")
    if bare not in upload_dates.columns or quarter not in upload_dates.index:
        return None

    val = upload_dates.loc[quarter, bare]
    if pd.isna(val):
        return None
    try:
        return pd.Timestamp(val).date()
    except Exception:
        return None


def pit_filter(
    df: pd.DataFrame,
    as_of: date,
    date_col: str = "date",
    pit_delay_days: int = 0,
    symbol: str = "",
) -> pd.DataFrame:
    """Filter DataFrame to only include rows available as of a given date.

    For daily data (pit_delay_days=0): return rows where date <= as_of.
    For monthly data (pit_delay_days=40): return rows where date <= as_of - 40 days.
    For quarterly data (pit_delay_days>=45): uses actual upload dates from FinLab
    when available, falls back to conservative delay.
    """
    if df.empty:
        return df

    if date_col in df.columns:
        dates = pd.to_datetime(df[date_col])
    elif isinstance(df.index, pd.DatetimeIndex):
        dates = df.index
        date_col = None
    else:
        return df

    # For quarterly data (delay >= 45 days), try actual upload dates first.
    # This provides ~10-30 days more precise PIT than conservative deadlines.
    if pit_delay_days >= 45 and symbol:
        filtered = _pit_filter_quarterly(df, dates, as_of, symbol, date_col)
        if filtered is not None:
            return filtered

    # Default: simple delay-based cutoff
    cutoff = pd.Timestamp(as_of) - pd.Timedelta(days=pit_delay_days)

    if date_col:
        return df[dates <= cutoff].copy()
    else:
        return df[dates <= cutoff].copy()


def _pit_filter_quarterly(
    df: pd.DataFrame, dates: pd.Series | pd.DatetimeIndex,
    as_of: date, symbol: str, date_col: str | None,
) -> pd.DataFrame | None:
    """PIT filter using actual upload dates for quarterly data.

    For each row, determines which quarter it belongs to and checks if that
    quarter's financial statement was uploaded before as_of.

    Returns None if upload_date data is unavailable (caller should use fallback).
    """
    upload_dates = _load_upload_dates()
    if upload_dates.empty:
        return None

    bare = symbol.replace(".TW", "").replace(".TWO", "")
    if bare not in upload_dates.columns:
        return None

    symbol_uploads = upload_dates[bare].dropna()
    if symbol_uploads.empty:
        return None

    # Build a mapping: quarter → actual upload date
    quarter_available: dict[str, date] = {}
    for q_label, upload_ts in symbol_uploads.items():
        try:
            quarter_available[str(q_label)] = pd.Timestamp(upload_ts).date()
        except Exception:
            continue

    if not quarter_available:
        return None

    # For each row date, determine which quarter it could be from and whether
    # that quarter's data was uploaded before as_of.
    # Simple approach: find the latest quarter whose upload_date <= as_of
    available_quarters = sorted(
        [q for q, d in quarter_available.items() if d <= as_of],
        reverse=True,
    )
    if not available_quarters:
        # No quarterly data available as of this date
        if date_col:
            return df.iloc[:0].copy()
        else:
            return df.iloc[:0].copy()

    # The latest available quarter tells us how far back data is usable
    latest_q = available_quarters[0]
    # Parse quarter end date (e.g. "2018-Q3" → 2018-09-30)
    try:
        year = int(latest_q.split("-")[0])
        qnum = int(latest_q.split("Q")[1])
        q_end_month = {1: 3, 2: 6, 3: 9, 4: 12}[qnum]
        from calendar import monthrange
        q_end_day = monthrange(year, q_end_month)[1]
        cutoff = pd.Timestamp(date(year, q_end_month, q_end_day))
    except Exception:
        return None  # can't parse, let caller use fallback

    if date_col:
        return df[dates <= cutoff].copy()
    else:
        return df[dates <= cutoff].copy()
