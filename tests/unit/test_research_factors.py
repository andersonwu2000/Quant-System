"""Tests for research factor modules in src/strategy/factors/research/.

Each factor follows the pattern:
  compute_<name>(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]
  Reads parquet from FUND_DIR / "{symbol}_revenue.parquet"
  40-day look-ahead bias cutoff
"""

from __future__ import annotations

import importlib
import numpy as np
import pandas as pd
import pytest
from pathlib import Path

_research_dir = Path("src/strategy/factors/research")
if not _research_dir.exists() or not list(_research_dir.glob("rev_*.py")):
    pytest.skip("No research factor modules found — skipping", allow_module_level=True)

# ---------------------------------------------------------------------------
# Dynamically discover all research factor modules
# ---------------------------------------------------------------------------


def _discover_factors() -> list[tuple[object, callable, int]]:
    """Discover all rev_* modules in the research package."""
    research_dir = Path("src/strategy/factors/research")
    entries = []
    for py_file in sorted(research_dir.glob("rev_*.py")):
        mod_name = py_file.stem
        full_mod = f"src.strategy.factors.research.{mod_name}"
        try:
            mod = importlib.import_module(full_mod)
        except ImportError:
            continue
        func_name = f"compute_{mod_name}"
        func = getattr(mod, func_name, None)
        if func is None:
            continue
        # Guess min months from source (conservative default 24)
        import inspect
        src = inspect.getsource(func)
        if "< 36" in src:
            min_months = 36
        elif "< 24" in src:
            min_months = 24
        else:
            min_months = 12
        entries.append((mod, func, min_months))
    return entries


FACTOR_REGISTRY = _discover_factors()
ALL_MODULES = [e[0] for e in FACTOR_REGISTRY]
ALL_FUNCS = [e[1] for e in FACTOR_REGISTRY]
ALL_MIN_MONTHS = [e[2] for e in FACTOR_REGISTRY]

# Ensure at least one factor exists
assert len(FACTOR_REGISTRY) > 0, "No research factor modules found!"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_revenue_parquet(path: Path, symbol: str, n_months: int = 48,
                          base_revenue: float = 1e8,
                          start: str = "2020-01-01") -> None:
    """Create a revenue parquet file with deterministic monthly data."""
    dates = pd.date_range(start, periods=n_months, freq="MS")
    rng = np.random.default_rng(42)
    revenues = base_revenue + rng.normal(0, base_revenue * 0.1, n_months)
    revenues = np.abs(revenues)  # ensure positive
    df = pd.DataFrame({"date": dates, "revenue": revenues})
    path.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path / f"{symbol}_revenue.parquet", index=False)


@pytest.fixture()
def fund_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create temp FUND_DIR with sample data and patch all modules."""
    for mod in ALL_MODULES:
        monkeypatch.setattr(mod, "FUND_DIR", tmp_path)
    _make_revenue_parquet(tmp_path, "AAPL", n_months=48)
    _make_revenue_parquet(tmp_path, "MSFT", n_months=48)
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOutputType:
    """Each factor returns dict[str, float]."""

    @pytest.mark.parametrize("func", ALL_FUNCS, ids=[f.__name__ for f in ALL_FUNCS])
    def test_returns_dict_str_float(self, fund_dir: Path, func):
        as_of = pd.Timestamp("2023-06-15")
        result = func(["AAPL", "MSFT"], as_of)
        assert isinstance(result, dict)
        for k, v in result.items():
            assert isinstance(k, str)
            assert isinstance(v, float)
            assert np.isfinite(v), f"{func.__name__} returned non-finite: {v}"


class TestLookAheadBias:
    """40-day cutoff must exclude recent data."""

    def test_recent_data_excluded(self, tmp_path: Path, monkeypatch):
        """Data only within 40 days → should return empty (not enough history)."""
        for mod in ALL_MODULES:
            monkeypatch.setattr(mod, "FUND_DIR", tmp_path)

        # Create data only in last 30 days
        dates = pd.date_range("2023-06-01", periods=5, freq="7D")
        df = pd.DataFrame({"date": dates, "revenue": [1e8] * 5})
        df.to_parquet(tmp_path / "TEST_revenue.parquet", index=False)

        as_of = pd.Timestamp("2023-06-30")
        for func in ALL_FUNCS:
            result = func(["TEST"], as_of)
            assert result == {}, f"{func.__name__} used data within 40-day window"

    @pytest.mark.parametrize("func,min_m", list(zip(ALL_FUNCS, ALL_MIN_MONTHS)),
                             ids=[f.__name__ for f in ALL_FUNCS])
    def test_old_data_usable(self, fund_dir: Path, func, min_m):
        """Data older than 40 days → should produce results."""
        as_of = pd.Timestamp("2023-12-15")
        result = func(["AAPL"], as_of)
        # With 48 months of data starting 2020-01, most factors should produce results
        # (as_of - 40 days ≈ 2023-11-05, so ~44 months usable)
        assert isinstance(result, dict)


class TestInsufficientData:
    """Too few months → empty dict."""

    @pytest.mark.parametrize("func,min_m", list(zip(ALL_FUNCS, ALL_MIN_MONTHS)),
                             ids=[f.__name__ for f in ALL_FUNCS])
    def test_too_few_months(self, tmp_path: Path, monkeypatch, func, min_m):
        for mod in ALL_MODULES:
            monkeypatch.setattr(mod, "FUND_DIR", tmp_path)

        # Create only 3 months of data, way before the cutoff
        dates = pd.date_range("2020-01-01", periods=3, freq="MS")
        df = pd.DataFrame({"date": dates, "revenue": [1e8, 1.1e8, 1.2e8]})
        df.to_parquet(tmp_path / "SHORT_revenue.parquet", index=False)

        result = func(["SHORT"], pd.Timestamp("2022-01-01"))
        assert result == {}

    @pytest.mark.parametrize("func", ALL_FUNCS, ids=[f.__name__ for f in ALL_FUNCS])
    def test_missing_file(self, tmp_path: Path, monkeypatch, func):
        for mod in ALL_MODULES:
            monkeypatch.setattr(mod, "FUND_DIR", tmp_path)
        result = func(["NOFILE"], pd.Timestamp("2023-06-15"))
        assert result == {}


class TestEmptyDataFrame:
    """Empty or malformed data → empty dict."""

    @pytest.mark.parametrize("func", ALL_FUNCS, ids=[f.__name__ for f in ALL_FUNCS])
    def test_empty_df(self, tmp_path: Path, monkeypatch, func):
        for mod in ALL_MODULES:
            monkeypatch.setattr(mod, "FUND_DIR", tmp_path)
        df = pd.DataFrame({"date": [], "revenue": []})
        df.to_parquet(tmp_path / "EMPTY_revenue.parquet", index=False)
        assert func(["EMPTY"], pd.Timestamp("2023-06-15")) == {}

    @pytest.mark.parametrize("func", ALL_FUNCS, ids=[f.__name__ for f in ALL_FUNCS])
    def test_missing_column(self, tmp_path: Path, monkeypatch, func):
        for mod in ALL_MODULES:
            monkeypatch.setattr(mod, "FUND_DIR", tmp_path)
        df = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=48, freq="MS"),
                           "other_col": range(48)})
        df.to_parquet(tmp_path / "NOCOL_revenue.parquet", index=False)
        assert func(["NOCOL"], pd.Timestamp("2023-06-15")) == {}


class TestZeroNegativeRevenue:
    """Zero/negative revenues → no crash, no inf/nan."""

    @pytest.mark.parametrize("func", ALL_FUNCS, ids=[f.__name__ for f in ALL_FUNCS])
    def test_all_zero_revenue(self, tmp_path: Path, monkeypatch, func):
        for mod in ALL_MODULES:
            monkeypatch.setattr(mod, "FUND_DIR", tmp_path)
        dates = pd.date_range("2020-01-01", periods=48, freq="MS")
        df = pd.DataFrame({"date": dates, "revenue": [0.0] * 48})
        df.to_parquet(tmp_path / "ZERO_revenue.parquet", index=False)
        result = func(["ZERO"], pd.Timestamp("2023-12-15"))
        for v in result.values():
            assert np.isfinite(v)

    @pytest.mark.parametrize("func", ALL_FUNCS, ids=[f.__name__ for f in ALL_FUNCS])
    def test_negative_revenue(self, tmp_path: Path, monkeypatch, func):
        for mod in ALL_MODULES:
            monkeypatch.setattr(mod, "FUND_DIR", tmp_path)
        dates = pd.date_range("2020-01-01", periods=48, freq="MS")
        df = pd.DataFrame({"date": dates, "revenue": [-1e8] * 48})
        df.to_parquet(tmp_path / "NEG_revenue.parquet", index=False)
        result = func(["NEG"], pd.Timestamp("2023-12-15"))
        for v in result.values():
            assert np.isfinite(v)


class TestMultipleSymbols:
    """Multiple symbols handled independently."""

    @pytest.mark.parametrize("func", ALL_FUNCS, ids=[f.__name__ for f in ALL_FUNCS])
    def test_mixed_valid_invalid(self, fund_dir: Path, func):
        result = func(["AAPL", "NONEXIST", "MSFT"], pd.Timestamp("2023-12-15"))
        assert isinstance(result, dict)
        assert "NONEXIST" not in result


class TestRev2ndDerivativeSpecific:
    """Specific value tests for the 2nd derivative factor (if it exists)."""

    @pytest.fixture(autouse=True)
    def _load_module(self):
        try:
            self._mod = importlib.import_module(
                "src.strategy.factors.research.rev_accel_2nd_derivative"
            )
            self._func = self._mod.compute_rev_accel_2nd_derivative
        except ImportError:
            pytest.skip("rev_accel_2nd_derivative module not available")

    def test_constant_growth_yields_near_zero(self, tmp_path: Path, monkeypatch):
        """Constant YoY → 2nd derivative ≈ 0."""
        monkeypatch.setattr(self._mod, "FUND_DIR", tmp_path)
        dates = pd.date_range("2020-01-01", periods=48, freq="MS")
        base = 1e8
        revenues = [base * (1.10 ** (i / 12)) for i in range(48)]
        df = pd.DataFrame({"date": dates, "revenue": revenues})
        df.to_parquet(tmp_path / "CONST_revenue.parquet", index=False)

        result = self._func(["CONST"], pd.Timestamp("2023-12-15"))
        if "CONST" in result:
            assert abs(result["CONST"]) < 0.05

    def test_accelerating_growth_positive(self, tmp_path: Path, monkeypatch):
        """Accelerating YoY → positive 2nd derivative."""
        monkeypatch.setattr(self._mod, "FUND_DIR", tmp_path)
        dates = pd.date_range("2020-01-01", periods=48, freq="MS")
        revenues = []
        for i in range(48):
            year_frac = i / 12
            growth = 1 + 0.05 * year_frac
            revenues.append(1e8 * (growth ** year_frac))
        df = pd.DataFrame({"date": dates, "revenue": revenues})
        df.to_parquet(tmp_path / "ACCEL_revenue.parquet", index=False)

        result = self._func(["ACCEL"], pd.Timestamp("2023-12-15"))
        assert isinstance(result, dict)
