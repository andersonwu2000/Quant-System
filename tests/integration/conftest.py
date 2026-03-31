"""Shared fixtures for AK integration tests.

Session-scoped: synthetic market data (expensive to build, reused across tests)
Function-scoped: mutable state (Portfolio, mock broker) that needs isolation
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from src.core.models import Instrument, Portfolio, Position


# ── Session-scoped: synthetic data ──────────────────────────────────


@pytest.fixture(scope="session")
def synthetic_symbols() -> list[str]:
    """100 synthetic TW stock symbols."""
    return [f"{i}.TW" for i in range(2301, 2401)]


@pytest.fixture(scope="session")
def synthetic_bars(synthetic_symbols) -> dict[str, pd.DataFrame]:
    """Deterministic OHLCV bars: 100 symbols x 500 trading days."""
    rng = np.random.default_rng(42)
    bars = {}
    dates = pd.bdate_range("2020-01-02", periods=500, freq="B")
    for sym in synthetic_symbols:
        base = 50 + rng.random() * 200
        returns = rng.normal(0.0003, 0.02, size=500)
        close = base * np.cumprod(1 + returns)
        volume = rng.integers(100_000, 5_000_000, size=500).astype(float)
        df = pd.DataFrame({
            "open": close * (1 + rng.normal(0, 0.005, 500)),
            "high": close * (1 + abs(rng.normal(0, 0.01, 500))),
            "low": close * (1 - abs(rng.normal(0, 0.01, 500))),
            "close": close,
            "volume": volume,
        }, index=dates)
        bars[sym] = df
    return bars


@pytest.fixture(scope="session")
def synthetic_revenue(synthetic_symbols) -> dict[str, pd.DataFrame]:
    """Monthly revenue for 100 symbols, 60 months with yoy_growth."""
    rng = np.random.default_rng(123)
    revenue = {}
    dates = pd.date_range("2016-01-10", periods=60, freq="MS")
    for sym in synthetic_symbols:
        base = 1e8 * (1 + rng.random() * 5)
        growth = rng.normal(0.05, 0.15, size=60)
        rev = base * np.cumprod(1 + growth / 12)
        df = pd.DataFrame({"date": dates, "revenue": rev})
        df["yoy_growth"] = df["revenue"].pct_change(periods=12) * 100
        revenue[sym] = df
    return revenue


@pytest.fixture(scope="session")
def synthetic_per(synthetic_symbols) -> dict[str, pd.DataFrame]:
    """Daily PER/PBR for 100 symbols, 500 days."""
    rng = np.random.default_rng(456)
    per_history = {}
    dates = pd.bdate_range("2020-01-02", periods=500, freq="B")
    for sym in synthetic_symbols:
        per = 10 + rng.random() * 30 + rng.normal(0, 1, 500).cumsum() * 0.1
        per = np.clip(per, 1, 100)
        pbr = 0.5 + rng.random() * 3 + rng.normal(0, 0.05, 500).cumsum() * 0.01
        pbr = np.clip(pbr, 0.1, 20)
        per_history[sym] = pd.DataFrame({
            "date": dates, "PER": per, "PBR": pbr,
        })
    return per_history


@pytest.fixture(scope="session")
def synthetic_institutional(synthetic_symbols) -> dict[str, pd.DataFrame]:
    """Daily institutional data for 50 symbols."""
    rng = np.random.default_rng(789)
    inst = {}
    dates = pd.bdate_range("2020-01-02", periods=500, freq="B")
    for sym in synthetic_symbols[:50]:
        inst[sym] = pd.DataFrame({
            "date": dates,
            "trust_net": rng.integers(-500, 500, size=500).astype(float),
            "foreign_net": rng.integers(-1000, 1000, size=500).astype(float),
        })
    return inst


@pytest.fixture(scope="session")
def synthetic_margin(synthetic_symbols) -> dict[str, pd.DataFrame]:
    """Daily margin data for 30 symbols."""
    rng = np.random.default_rng(101)
    margin = {}
    dates = pd.bdate_range("2020-01-02", periods=500, freq="B")
    for sym in synthetic_symbols[:30]:
        margin[sym] = pd.DataFrame({
            "date": dates,
            "margin_usage": rng.uniform(0.1, 0.9, size=500),
        })
    return margin


@pytest.fixture(scope="session")
def full_data_dict(
    synthetic_bars, synthetic_revenue, synthetic_per,
    synthetic_institutional, synthetic_margin,
) -> dict:
    """Complete data dict matching evaluate.py _mask_data format."""
    return {
        "bars": synthetic_bars,
        "revenue": synthetic_revenue,
        "institutional": synthetic_institutional,
        "per_history": synthetic_per,
        "margin": synthetic_margin,
        "pe": {},
        "pb": {},
        "roe": {},
    }


# ── Function-scoped: mutable state ──────────────────────────────────


@pytest.fixture
def mock_portfolio() -> Portfolio:
    """Portfolio with 10 positions for testing."""
    p = Portfolio()
    for i in range(2301, 2311):
        sym = f"{i}.TW"
        p.positions[sym] = Position(
            instrument=Instrument(symbol=sym),
            quantity=Decimal("1000"),
            avg_cost=Decimal("100"),
        )
    return p
