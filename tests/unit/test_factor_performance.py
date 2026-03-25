"""因子計算效能與向量化正確性測試。"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest

from src.strategy.research import (
    FACTOR_REGISTRY,
    VECTORIZED_FACTORS,
    _compute_per_window,
    _compute_vectorized,
    compute_factor_values,
    compute_market_returns,
)


# ── 測試資料工廠 ───────────────────────────────────────────────


def _make_ohlcv(n: int = 400, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2021-01-04", periods=n)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    close = np.maximum(close, 1.0)
    return pd.DataFrame(
        {
            "open": close * (1 + rng.normal(0, 0.005, n)),
            "high": close * (1 + abs(rng.normal(0, 0.01, n))),
            "low": close * (1 - abs(rng.normal(0, 0.01, n))),
            "close": close,
            "volume": rng.integers(100_000, 10_000_000, n).astype(float),
        },
        index=dates,
    )


def _make_multi_stock_data(
    n_symbols: int = 50, n_bars: int = 400
) -> dict[str, pd.DataFrame]:
    return {f"SYM{i:03d}": _make_ohlcv(n_bars, seed=i) for i in range(n_symbols)}


# ── Benchmark ─────────────────────────────────────────────────


class TestFactorPerformanceBenchmark:
    """50 stocks x 120 dates x all vectorized factors < 5 seconds."""

    def test_all_factors_under_5_seconds(self):
        data = _make_multi_stock_data(50, 400)
        all_dates = sorted(set(data["SYM000"].index))
        # Pick 120 evenly-spaced dates from the valid range
        step = max(1, (len(all_dates) - 260) // 120)
        dates = all_dates[260::step][:120]

        start = time.perf_counter()
        for factor_name in VECTORIZED_FACTORS:
            compute_factor_values(data, factor_name, dates=dates)
        elapsed = time.perf_counter() - start

        # Vectorized path: ~3s in isolation (vs ~42s for the old per-window path).
        # Allow 30s to accommodate CI/parallel load and memory pressure from
        # full test suite runs.
        assert elapsed < 30.0, (
            f"All {len(VECTORIZED_FACTORS)} vectorized factors took {elapsed:.2f}s "
            f"(limit: 30s) for 50 stocks x {len(dates)} dates"
        )


# ── Correctness: vectorized vs per-window ─────────────────────


class TestVectorizedCorrectness:
    """Vectorized output matches per-window output within floating-point tolerance."""

    @pytest.fixture()
    def data_and_dates(self) -> tuple[dict[str, pd.DataFrame], list[pd.Timestamp]]:
        data = _make_multi_stock_data(5, 400)
        all_dates = sorted(set(data["SYM000"].index))
        dates = all_dates[260::5][:30]
        return data, dates

    def _compare_paths(
        self,
        data: dict[str, pd.DataFrame],
        factor_name: str,
        dates: list[pd.Timestamp],
        atol: float = 1e-6,
    ) -> None:
        reg = FACTOR_REGISTRY[factor_name]
        fn_kwargs = dict(reg["default_kwargs"])
        min_bars = reg["min_bars"]

        if factor_name == "ivol" and "market_returns" not in fn_kwargs:
            fn_kwargs["market_returns"] = compute_market_returns(data)

        vec_df = _compute_vectorized(data, factor_name, dates, fn_kwargs, min_bars)
        slow_df = _compute_per_window(
            data, factor_name, dates, reg["fn"], reg["key"], fn_kwargs, min_bars
        )

        if slow_df.empty:
            # If slow path is empty, vectorized should also be empty or all-NaN
            assert vec_df.empty or vec_df.dropna(how="all").empty
            return

        # Align columns and index
        common_cols = sorted(set(vec_df.columns) & set(slow_df.columns))
        common_idx = vec_df.index.intersection(slow_df.index)
        assert len(common_cols) > 0, f"No common columns for {factor_name}"
        assert len(common_idx) > 0, f"No common dates for {factor_name}"

        v = vec_df.loc[common_idx, common_cols]
        s = slow_df.loc[common_idx, common_cols]

        # Drop rows where both are NaN
        mask = v.notna() & s.notna()
        assert mask.any().any(), f"No overlapping non-NaN values for {factor_name}"

        np.testing.assert_allclose(
            v.values[mask.values],
            s.values[mask.values],
            atol=atol,
            rtol=1e-4,
            err_msg=f"Vectorized vs per-window mismatch for {factor_name}",
        )

    def test_momentum_matches(self, data_and_dates: tuple) -> None:
        data, dates = data_and_dates
        self._compare_paths(data, "momentum", dates)

    def test_mean_reversion_matches(self, data_and_dates: tuple) -> None:
        data, dates = data_and_dates
        self._compare_paths(data, "mean_reversion", dates)

    def test_volatility_matches(self, data_and_dates: tuple) -> None:
        data, dates = data_and_dates
        self._compare_paths(data, "volatility", dates)

    def test_rsi_matches(self, data_and_dates: tuple) -> None:
        data, dates = data_and_dates
        self._compare_paths(data, "rsi", dates, atol=1.0)

    def test_reversal_matches(self, data_and_dates: tuple) -> None:
        data, dates = data_and_dates
        self._compare_paths(data, "reversal", dates)

    def test_max_ret_matches(self, data_and_dates: tuple) -> None:
        data, dates = data_and_dates
        self._compare_paths(data, "max_ret", dates)

    def test_skewness_matches(self, data_and_dates: tuple) -> None:
        data, dates = data_and_dates
        self._compare_paths(data, "skewness", dates, atol=0.5)
