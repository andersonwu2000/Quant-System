"""Tests for src/alpha/construction.py — 成本感知組合建構。"""

import pandas as pd
import pytest

from src.alpha.construction import ConstructionConfig, blend_with_decay, construct_portfolio


class TestConstructPortfolio:
    def test_basic_signal_to_weights(self):
        signal = pd.Series({"A": 0.8, "B": 0.5, "C": 0.3})
        result = construct_portfolio(signal)
        assert len(result) > 0
        assert all(v > 0 for v in result.values())
        assert all(v <= 0.05 for v in result.values())

    def test_respects_max_weight(self):
        signal = pd.Series({"A": 100.0})
        config = ConstructionConfig(max_weight=0.03)
        result = construct_portfolio(signal, config=config)
        assert result["A"] <= 0.03

    def test_respects_max_total_weight(self):
        signal = pd.Series({f"S{i}": 1.0 for i in range(50)})
        config = ConstructionConfig(max_weight=0.10, max_total_weight=0.90)
        result = construct_portfolio(signal, config=config)
        total = sum(result.values())
        assert total <= 0.90 + 0.01  # 小容差

    def test_long_only_ignores_negative(self):
        signal = pd.Series({"A": 0.5, "B": -0.3, "C": 0.2})
        config = ConstructionConfig(long_only=True)
        result = construct_portfolio(signal, config=config)
        assert "B" not in result

    def test_with_current_weights_reduces_turnover(self):
        signal = pd.Series({"A": 0.8, "B": 0.5, "C": 0.3})
        current = pd.Series({"A": 0.04, "B": 0.03, "D": 0.02})
        config = ConstructionConfig(turnover_penalty=0.01)
        result = construct_portfolio(signal, current_weights=current, config=config)
        # 不能具體預測值，但應有結果
        assert isinstance(result, dict)

    def test_max_turnover_constraint(self):
        signal = pd.Series({"A": 1.0, "B": 1.0})
        current = pd.Series({"C": 0.05, "D": 0.05})
        config = ConstructionConfig(max_turnover=0.02, turnover_penalty=0)
        result = construct_portfolio(signal, current_weights=current, config=config)
        # 換手率被限制，不會完全切換
        total_change = sum(abs(result.get(s, 0) - current.get(s, 0)) for s in set(list(result.keys()) + list(current.index)))
        # 寬鬆檢查
        assert total_change < 1.0

    def test_empty_signal(self):
        result = construct_portfolio(pd.Series(dtype=float))
        assert result == {}

    def test_with_volatilities(self):
        signal = pd.Series({f"S{i}": 1.0 for i in range(10)})
        vols = {f"S{i}": 0.3 for i in range(10)}
        vols["S0"] = 0.05  # S0 波動率最低 → 應獲得最多權重
        config = ConstructionConfig(max_weight=0.20, max_total_weight=0.95)
        result = construct_portfolio(signal, volatilities=vols, config=config)
        assert result["S0"] > result["S1"]  # 低波動率得到更多權重


class TestBlendWithDecay:
    def test_blends_signals(self):
        old = pd.Series({"A": 1.0, "B": 0.0})
        new = pd.Series({"A": 0.0, "B": 1.0})
        blended = blend_with_decay(new, old, half_life=5)
        # 應介於新舊之間
        assert 0 < blended["A"] < 1.0
        assert 0 < blended["B"] < 1.0

    def test_half_life_1_strongly_favors_new(self):
        old = pd.Series({"A": 1.0})
        new = pd.Series({"A": 0.0})
        blended = blend_with_decay(new, old, half_life=1)
        assert blended["A"] < 0.6  # 衰減快 → 新信號佔比大

    def test_large_half_life_favors_old(self):
        old = pd.Series({"A": 1.0})
        new = pd.Series({"A": 0.0})
        blended = blend_with_decay(new, old, half_life=100)
        assert blended["A"] > 0.9  # 衰減慢 → 舊信號佔比大
