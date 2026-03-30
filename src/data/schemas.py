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

    # Check columns (may be in index or columns)
    if isinstance(df.index, pd.DatetimeIndex):
        _assert_columns(df, {"open", "high", "low", "close", "volume"}, name)
    else:
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
    from MOPS would be more precise but requires scraping.
    """
    month, day = QUARTERLY_DEADLINES[quarter]
    year = report_date.year + (1 if quarter == "Q4" else 0)
    return date(year, month, day)


def quarter_from_date(d: date) -> str:
    """Determine fiscal quarter from a report date."""
    if d.month <= 3:
        return "Q4"  # Q4 of previous year
    elif d.month <= 6:
        return "Q1"
    elif d.month <= 9:
        return "Q2"
    else:
        return "Q3"


def pit_filter(
    df: pd.DataFrame,
    as_of: date,
    date_col: str = "date",
    pit_delay_days: int = 0,
) -> pd.DataFrame:
    """Filter DataFrame to only include rows available as of a given date.

    For daily data (pit_delay_days=0): return rows where date <= as_of.
    For delayed data (pit_delay_days>0): return rows where date <= as_of - delay.
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

    cutoff = pd.Timestamp(as_of) - pd.Timedelta(days=pit_delay_days)

    if date_col:
        return df[dates <= cutoff].copy()
    else:
        return df[dates <= cutoff].copy()
