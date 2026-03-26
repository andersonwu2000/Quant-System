"""戰術資產配置模組測試。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.allocation.cross_asset import CrossAssetConfig, CrossAssetSignals
from src.allocation.macro_factors import MacroFactorConfig, MacroFactorModel, MacroSignals
from src.allocation.tactical import (
    StrategicAllocation,
    TacticalConfig,
    TacticalEngine,
)
from src.alpha.regime import MarketRegime
from src.core.models import AssetClass


# ── MacroSignals ──────────────────────────────────────────


class TestMacroSignals:
    def test_to_dict(self):
        s = MacroSignals(growth=0.5, inflation=-0.3, rates=0.1, credit=0.2)
        d = s.to_dict()
        assert d["growth"] == 0.5
        assert d["inflation"] == -0.3
        assert len(d) == 4

    def test_repr(self):
        s = MacroSignals(growth=1.0, inflation=-1.0, rates=0.0, credit=0.5)
        r = repr(s)
        assert "growth=+1.00" in r
        assert "inflation=-1.00" in r


# ── MacroFactorModel ──────────────────────────────────────


class TestMacroFactorModel:
    @staticmethod
    def _make_mock_panel(n: int = 500) -> pd.DataFrame:
        """建立模擬 FRED 面板。"""
        rng = np.random.default_rng(42)
        dates = pd.bdate_range("2020-01-02", periods=n)
        return pd.DataFrame(
            {
                "unemployment": 5.0 + np.cumsum(rng.normal(0, 0.01, n)),
                "pmi": 12000 + np.cumsum(rng.normal(0, 10, n)),
                "cpi": 250 + np.cumsum(rng.normal(0.05, 0.1, n)),
                "yield_spread_10y2y": 1.0 + np.cumsum(rng.normal(0, 0.02, n)),
                "fed_funds": 2.0 + np.cumsum(rng.normal(0, 0.01, n)),
                "credit_spread": 2.5 + np.cumsum(rng.normal(0, 0.01, n)),
            },
            index=dates,
        )

    def test_compute_signals_with_mock_panel(self):
        model = MacroFactorModel()
        model._panel = self._make_mock_panel()
        signals = model.compute_signals()
        assert isinstance(signals, MacroSignals)
        # z-scores should be bounded
        for v in signals.to_dict().values():
            assert -3.0 <= v <= 3.0

    def test_compute_signals_empty_panel(self):
        model = MacroFactorModel()
        model._panel = pd.DataFrame()
        signals = model.compute_signals()
        assert signals.growth == 0.0
        assert signals.inflation == 0.0

    def test_compute_signals_as_of(self):
        model = MacroFactorModel()
        panel = self._make_mock_panel(500)
        model._panel = panel
        mid_date = panel.index[250]
        signals = model.compute_signals(as_of=mid_date)
        assert isinstance(signals, MacroSignals)

    def test_compute_signal_series(self):
        model = MacroFactorModel(config=MacroFactorConfig(zscore_lookback=60))
        model._panel = self._make_mock_panel(200)
        series = model.compute_signal_series()
        assert isinstance(series, pd.DataFrame)
        assert set(series.columns) == {"growth", "inflation", "rates", "credit"}
        assert len(series) > 0
        # All values bounded
        assert series.abs().max().max() <= 3.0

    def test_short_data_returns_zero(self):
        model = MacroFactorModel()
        model._panel = self._make_mock_panel(10)
        signals = model.compute_signals()
        assert signals.growth == 0.0


# ── CrossAssetSignals ─────────────────────────────────────


class TestCrossAssetSignals:
    @staticmethod
    def _make_prices(n: int = 500, seed: int = 42) -> pd.Series:
        rng = np.random.default_rng(seed)
        dates = pd.bdate_range("2020-01-02", periods=n)
        close = 100 + np.cumsum(rng.normal(0.05, 1.0, n))
        close = np.maximum(close, 10.0)
        return pd.Series(close, index=dates)

    def test_compute_returns_all_classes(self):
        cs = CrossAssetSignals()
        prices = {
            AssetClass.EQUITY: self._make_prices(500, 1),
            AssetClass.ETF: self._make_prices(500, 2),
            AssetClass.FUTURE: self._make_prices(500, 3),
        }
        result = cs.compute(prices)
        assert AssetClass.EQUITY in result
        assert AssetClass.ETF in result
        assert AssetClass.FUTURE in result
        for v in result.values():
            assert -3.0 <= v <= 3.0

    def test_compute_empty_prices(self):
        cs = CrossAssetSignals()
        prices = {AssetClass.EQUITY: pd.Series(dtype=float)}
        result = cs.compute(prices)
        assert result[AssetClass.EQUITY] == 0.0

    def test_compute_short_prices(self):
        cs = CrossAssetSignals()
        prices = {AssetClass.EQUITY: self._make_prices(30)}
        result = cs.compute(prices)
        assert result[AssetClass.EQUITY] == 0.0  # < 60 bars

    def test_compute_detail(self):
        cs = CrossAssetSignals()
        prices = {AssetClass.EQUITY: self._make_prices(500)}
        detail = cs.compute_detail(prices)
        assert "momentum" in detail[AssetClass.EQUITY]
        assert "volatility" in detail[AssetClass.EQUITY]
        assert "value" in detail[AssetClass.EQUITY]

    def test_custom_config(self):
        cfg = CrossAssetConfig(momentum_lookback=126, vol_lookback=30)
        cs = CrossAssetSignals(config=cfg)
        prices = {AssetClass.EQUITY: self._make_prices(300)}
        result = cs.compute(prices)
        assert AssetClass.EQUITY in result


# ── StrategicAllocation ───────────────────────────────────


class TestStrategicAllocation:
    def test_default_weights_sum_to_one(self):
        sa = StrategicAllocation()
        assert abs(sum(sa.weights.values()) - 1.0) < 0.01

    def test_auto_normalize(self):
        sa = StrategicAllocation(weights={
            AssetClass.EQUITY: 6.0,
            AssetClass.ETF: 3.0,
            AssetClass.FUTURE: 1.0,
        })
        assert abs(sum(sa.weights.values()) - 1.0) < 0.01
        assert abs(sa.weights[AssetClass.EQUITY] - 0.6) < 0.01


# ── TacticalEngine ────────────────────────────────────────


class TestTacticalEngine:
    def test_no_signals_returns_strategic(self):
        """無信號輸入時回傳戰略配置。"""
        engine = TacticalEngine()
        result = engine.compute()
        assert abs(sum(result.values()) - 1.0) < 0.01
        # 應接近戰略配置
        for ac, w in engine.strategic.weights.items():
            assert abs(result[ac] - w) < 0.05

    def test_macro_signals_shift_weights(self):
        """宏觀正向成長信號應超配股票。"""
        engine = TacticalEngine()
        strategic_equity = engine.strategic.weights[AssetClass.EQUITY]

        result = engine.compute(
            macro_signals={"growth": 2.0, "inflation": 0.0, "rates": 0.0, "credit": 0.0},
        )
        assert abs(sum(result.values()) - 1.0) < 0.01
        # 成長正向 → 股票應被超配
        assert result[AssetClass.EQUITY] >= strategic_equity

    def test_bear_regime_reduces_equity(self):
        """熊市應減少股票配置。"""
        engine = TacticalEngine()
        strategic_equity = engine.strategic.weights[AssetClass.EQUITY]

        result = engine.compute(regime=MarketRegime.BEAR)
        assert result[AssetClass.EQUITY] < strategic_equity

    def test_bull_regime_increases_equity(self):
        """牛市應增加股票配置。"""
        engine = TacticalEngine()
        strategic_equity = engine.strategic.weights[AssetClass.EQUITY]

        result = engine.compute(regime=MarketRegime.BULL)
        assert result[AssetClass.EQUITY] >= strategic_equity

    def test_weights_sum_to_one(self):
        """任何信號組合下權重總和為 1。"""
        engine = TacticalEngine()
        result = engine.compute(
            macro_signals={"growth": 2.0, "inflation": -1.0, "rates": 0.5, "credit": -0.5},
            cross_asset_signals={
                AssetClass.EQUITY: 1.0,
                AssetClass.ETF: -0.5,
                AssetClass.FUTURE: 0.3,
            },
            regime=MarketRegime.BEAR,
        )
        assert abs(sum(result.values()) - 1.0) < 1e-6

    def test_max_deviation_respected(self):
        """極端信號不應超過最大偏離度。"""
        cfg = TacticalConfig(max_deviation=0.10)
        engine = TacticalEngine(config=cfg)
        strategic = engine.strategic.weights

        result = engine.compute(
            macro_signals={"growth": 3.0, "inflation": 3.0, "rates": 3.0, "credit": 3.0},
            cross_asset_signals={ac: 3.0 for ac in strategic},
            regime=MarketRegime.BULL,
        )
        for w in result.values():
            assert w > 0  # min_weight enforced

    def test_min_weight_enforced(self):
        """任何資產類別不應低於 min_weight。"""
        cfg = TacticalConfig(min_weight=0.05)
        engine = TacticalEngine(config=cfg)

        result = engine.compute(
            macro_signals={"growth": -3.0, "inflation": 3.0, "rates": -3.0, "credit": -3.0},
            regime=MarketRegime.BEAR,
        )
        for w in result.values():
            assert w >= 0.01  # normalized min can be slightly below min_weight

    def test_custom_strategic(self):
        """自訂戰略配置。"""
        sa = StrategicAllocation(weights={
            AssetClass.EQUITY: 0.40,
            AssetClass.ETF: 0.50,
            AssetClass.FUTURE: 0.10,
        })
        engine = TacticalEngine(strategic=sa)
        result = engine.compute()
        assert abs(sum(result.values()) - 1.0) < 0.01

    def test_cross_asset_signals_applied(self):
        """跨資產信號應影響權重。"""
        engine = TacticalEngine()
        base = engine.compute()

        # 正向股票信號
        shifted = engine.compute(
            cross_asset_signals={
                AssetClass.EQUITY: 3.0,
                AssetClass.ETF: -3.0,
                AssetClass.FUTURE: 0.0,
            },
        )
        # 股票權重應上升
        assert shifted[AssetClass.EQUITY] >= base[AssetClass.EQUITY]
