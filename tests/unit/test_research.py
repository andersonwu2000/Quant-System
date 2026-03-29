"""因子研究框架單元測試。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.strategy.research import (
    FACTOR_REGISTRY,
    DecayResult,
    ICResult,
    analyze_factor,
    compute_factor_values,
    compute_forward_returns,
    compute_ic,
    factor_decay,
)


# ── 測試資料工廠 ───────────────────────────────────────────────


def _make_ohlcv(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """產生模擬 OHLCV 資料。"""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2022-01-03", periods=n)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    close = np.maximum(close, 1.0)  # 確保正值
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
    n_symbols: int = 5, n_bars: int = 300
) -> dict[str, pd.DataFrame]:
    """產生多檔標的資料。"""
    return {f"SYM{i}": _make_ohlcv(n_bars, seed=i) for i in range(n_symbols)}


# ── FACTOR_REGISTRY ────────────────────────────────────────────


class TestFactorRegistry:
    def test_known_factors(self):
        expected = {
            # Original technical
            "momentum", "mean_reversion", "volatility", "rsi", "ma_cross", "vpt",
            "reversal", "illiquidity", "ivol", "skewness", "max_ret",
            # New technical indicators
            "bollinger_pos", "macd_hist", "obv_trend", "adx", "cci",
            "williams_r", "stochastic_k", "atr_ratio", "price_accel",
            "vol_momentum", "hl_range", "close_to_high", "gap",
            "intraday_ret", "overnight_ret",
            # Academic factors
            "momentum_1m", "momentum_6m", "momentum_12m", "lt_reversal",
            "beta", "idio_skew", "max_daily_ret", "turnover_vol",
            "price_delay", "zero_days",
            # Original Kakushadze
            "alpha_2", "alpha_3", "alpha_6", "alpha_12", "alpha_33",
            "alpha_34", "alpha_38", "alpha_44", "alpha_53", "alpha_101",
            # New Kakushadze
            "alpha_1", "alpha_4", "alpha_7", "alpha_8", "alpha_9",
            "alpha_10", "alpha_13", "alpha_14", "alpha_15", "alpha_16",
            "alpha_17", "alpha_18", "alpha_19", "alpha_20", "alpha_22",
            "alpha_23", "alpha_24", "alpha_30", "alpha_35", "alpha_40",
        }
        assert expected == set(FACTOR_REGISTRY.keys())

    def test_entries_have_required_keys(self):
        for name, entry in FACTOR_REGISTRY.items():
            assert "fn" in entry, f"{name} missing fn"
            assert "key" in entry, f"{name} missing key"
            assert "min_bars" in entry, f"{name} missing min_bars"
            assert callable(entry["fn"]), f"{name} fn not callable"


# ── compute_factor_values ──────────────────────────────────────


class TestComputeFactorValues:
    def test_returns_dataframe(self):
        data = _make_multi_stock_data()
        fv = compute_factor_values(data, "rsi")
        assert isinstance(fv, pd.DataFrame)
        assert not fv.empty

    def test_columns_are_symbols(self):
        data = _make_multi_stock_data(3)
        fv = compute_factor_values(data, "rsi")
        for col in fv.columns:
            assert col in data

    def test_unknown_factor_raises(self):
        data = _make_multi_stock_data(3)
        with pytest.raises(ValueError, match="Unknown factor"):
            compute_factor_values(data, "nonexistent_factor")

    def test_insufficient_data_returns_empty(self):
        # Only 5 bars — not enough for any factor
        data = _make_multi_stock_data(3, n_bars=5)
        fv = compute_factor_values(data, "momentum")
        assert fv.empty

    def test_custom_dates(self):
        data = _make_multi_stock_data(3, n_bars=300)
        all_dates = list(data["SYM0"].index)
        subset = [all_dates[200], all_dates[250]]
        fv = compute_factor_values(data, "rsi", dates=subset)
        assert len(fv) <= 2


# ── compute_forward_returns ────────────────────────────────────


class TestComputeForwardReturns:
    def test_returns_dataframe(self):
        data = _make_multi_stock_data(3)
        fwd = compute_forward_returns(data, horizon=5)
        assert isinstance(fwd, pd.DataFrame)
        assert not fwd.empty

    def test_values_are_reasonable(self):
        data = _make_multi_stock_data(3)
        fwd = compute_forward_returns(data, horizon=5)
        # 5-day returns should be small
        assert fwd.abs().max().max() < 1.0  # < 100%

    def test_horizon_too_large(self):
        data = _make_multi_stock_data(3, n_bars=10)
        fwd = compute_forward_returns(data, horizon=20)
        assert fwd.empty


# ── compute_ic ─────────────────────────────────────────────────


class TestComputeIC:
    def _make_ic_inputs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        data = _make_multi_stock_data(35, n_bars=300)
        fv = compute_factor_values(data, "rsi")
        fwd = compute_forward_returns(data, horizon=5, dates=list(fv.index))
        return fv, fwd

    def test_returns_ic_result(self):
        fv, fwd = self._make_ic_inputs()
        result = compute_ic(fv, fwd)
        assert isinstance(result, ICResult)

    def test_ic_in_range(self):
        fv, fwd = self._make_ic_inputs()
        result = compute_ic(fv, fwd)
        assert -1.0 <= result.ic_mean <= 1.0

    def test_hit_rate_in_range(self):
        fv, fwd = self._make_ic_inputs()
        result = compute_ic(fv, fwd)
        assert 0.0 <= result.hit_rate <= 1.0

    def test_ic_series_length(self):
        fv, fwd = self._make_ic_inputs()
        result = compute_ic(fv, fwd)
        assert len(result.ic_series) > 0

    def test_perfect_correlation(self):
        """Perfect forward knowledge should give high IC."""
        dates = pd.bdate_range("2023-01-03", periods=10)
        symbols = [f"S{i}" for i in range(35)]
        rng = np.random.default_rng(0)
        fv = pd.DataFrame(rng.standard_normal((10, 35)), index=dates, columns=symbols)
        # Forward returns = same rank order as factor
        fwd = fv.copy()
        result = compute_ic(fv, fwd, method="rank")
        assert result.ic_mean > 0.8

    def test_empty_inputs(self):
        fv = pd.DataFrame()
        fwd = pd.DataFrame()
        result = compute_ic(fv, fwd)
        assert result.ic_mean == 0
        assert result.ic_std == 0

    def test_summary(self):
        fv, fwd = self._make_ic_inputs()
        result = compute_ic(fv, fwd)
        result.factor_name = "rsi"
        s = result.summary()
        assert "rsi" in s
        assert "IC Mean" in s


# ── factor_decay ───────────────────────────────────────────────


class TestFactorDecay:
    def test_returns_decay_result(self):
        data = _make_multi_stock_data(5, n_bars=300)
        result = factor_decay(data, "rsi", horizons=[1, 5, 10])
        assert isinstance(result, DecayResult)
        assert result.factor_name == "rsi"

    def test_all_horizons_present(self):
        data = _make_multi_stock_data(5, n_bars=300)
        horizons = [1, 5, 10]
        result = factor_decay(data, "rsi", horizons=horizons)
        for h in horizons:
            assert h in result.ic_by_horizon

    def test_summary(self):
        data = _make_multi_stock_data(5, n_bars=300)
        result = factor_decay(data, "rsi", horizons=[1, 5])
        s = result.summary()
        assert "rsi" in s
        assert "1d" in s


# ── analyze_factor ─────────────────────────────────────────────


class TestAnalyzeFactor:
    def test_returns_ic_result_with_name(self):
        data = _make_multi_stock_data(5, n_bars=300)
        result = analyze_factor(data, "rsi", horizon=5)
        assert isinstance(result, ICResult)
        assert result.factor_name == "rsi"

    def test_insufficient_data(self):
        data = _make_multi_stock_data(3, n_bars=5)
        result = analyze_factor(data, "rsi")
        assert result.ic_mean == 0
