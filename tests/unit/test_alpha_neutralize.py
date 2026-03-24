"""Tests for src/alpha/neutralize.py — 因子中性化。"""

import numpy as np
import pandas as pd
import pytest

from src.alpha.neutralize import (
    NeutralizeMethod,
    neutralize,
    standardize,
    winsorize,
)


def _make_factor_df() -> pd.DataFrame:
    """產生測試用因子 DataFrame。"""
    dates = pd.bdate_range("2020-01-01", periods=10)
    np.random.seed(42)
    return pd.DataFrame(
        np.random.randn(10, 5),
        index=dates,
        columns=["A", "B", "C", "D", "E"],
    )


class TestWinsorize:
    def test_clips_extremes(self):
        df = _make_factor_df()
        # 注入極端值
        df.iloc[0, 0] = 100.0
        df.iloc[0, 1] = -100.0
        result = winsorize(df, 0.1, 0.9)
        assert result.iloc[0, 0] < 100.0
        assert result.iloc[0, 1] > -100.0

    def test_no_change_within_bounds(self):
        df = pd.DataFrame({"A": [1.0, 2.0, 3.0], "B": [1.0, 2.0, 3.0]}, index=pd.bdate_range("2020-01-01", periods=3))
        result = winsorize(df, 0.0, 1.0)
        pd.testing.assert_frame_equal(result, df)


class TestStandardize:
    def test_zscore_mean_zero(self):
        df = _make_factor_df()
        result = standardize(df, "zscore")
        for dt in result.index:
            row = result.loc[dt].dropna()
            assert abs(row.mean()) < 1e-10

    def test_rank_between_0_1(self):
        df = _make_factor_df()
        result = standardize(df, "rank")
        assert result.min().min() > 0
        assert result.max().max() <= 1.0

    def test_rank_zscore(self):
        df = _make_factor_df()
        result = standardize(df, "rank_zscore")
        for dt in result.index:
            row = result.loc[dt].dropna()
            assert abs(row.mean()) < 1e-10


class TestNeutralize:
    def test_market_neutral_mean_zero(self):
        df = _make_factor_df()
        result = neutralize(df, NeutralizeMethod.MARKET)
        for dt in result.index:
            row = result.loc[dt].dropna()
            assert abs(row.mean()) < 1e-10

    def test_industry_neutral(self):
        df = _make_factor_df()
        industry_map = {"A": "tech", "B": "tech", "C": "fin", "D": "fin", "E": "fin"}
        result = neutralize(df, NeutralizeMethod.INDUSTRY, industry_map=industry_map)
        # 每個行業內均值應接近 0
        for dt in result.index:
            tech = result.loc[dt, ["A", "B"]].dropna()
            fin = result.loc[dt, ["C", "D", "E"]].dropna()
            if len(tech) >= 2:
                assert abs(tech.mean()) < 1e-10
            if len(fin) >= 2:
                assert abs(fin.mean()) < 1e-10

    def test_size_neutral(self):
        df = _make_factor_df()
        # 構造市值（大小不一）
        caps = pd.DataFrame(
            np.random.uniform(1e8, 1e10, (10, 5)),
            index=df.index,
            columns=df.columns,
        )
        result = neutralize(df, NeutralizeMethod.SIZE, market_caps=caps)
        assert result.shape == df.shape

    def test_industry_size_neutral(self):
        df = _make_factor_df()
        industry_map = {"A": "tech", "B": "tech", "C": "fin", "D": "fin", "E": "fin"}
        caps = pd.DataFrame(
            np.random.uniform(1e8, 1e10, (10, 5)),
            index=df.index,
            columns=df.columns,
        )
        result = neutralize(df, NeutralizeMethod.INDUSTRY_SIZE, industry_map=industry_map, market_caps=caps)
        assert result.shape == df.shape

    def test_industry_without_map_raises(self):
        df = _make_factor_df()
        with pytest.raises(ValueError, match="industry_map"):
            neutralize(df, NeutralizeMethod.INDUSTRY)

    def test_size_without_caps_raises(self):
        df = _make_factor_df()
        with pytest.raises(ValueError, match="market_caps"):
            neutralize(df, NeutralizeMethod.SIZE)
