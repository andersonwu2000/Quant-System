"""Tests for AutoAlphaConfig, DecisionConfig, and supporting data models."""

from __future__ import annotations

from datetime import datetime

from src.alpha.auto.config import (
    ALERT_RULES,
    AlphaAlert,
    AutoAlphaConfig,
    DecisionConfig,
    FactorScore,
    ResearchSnapshot,
)
from src.alpha.pipeline import AlphaConfig
from src.alpha.regime import MarketRegime


class TestDecisionConfig:
    """DecisionConfig defaults and customization."""

    def test_defaults(self) -> None:
        cfg = DecisionConfig()
        assert cfg.min_icir == 0.3
        assert cfg.min_hit_rate == 0.52
        assert cfg.max_cost_drag == 200.0
        assert cfg.use_rolling_ic is True
        assert cfg.regime_aware is True

    def test_custom_values(self) -> None:
        cfg = DecisionConfig(min_icir=0.5, min_hit_rate=0.6, max_cost_drag=100.0)
        assert cfg.min_icir == 0.5
        assert cfg.min_hit_rate == 0.6
        assert cfg.max_cost_drag == 100.0


class TestAutoAlphaConfig:
    """AutoAlphaConfig defaults, nesting, and property accessors."""

    def test_defaults(self) -> None:
        cfg = AutoAlphaConfig()
        # Schedule
        assert cfg.schedule == "50 8 * * 1-5"
        assert cfg.eod_schedule == "00 14 * * 1-5"
        # Universe
        assert cfg.universe_count == 150
        assert cfg.min_adv == 500_000
        assert cfg.min_listing_days == 120
        assert cfg.exclude_disposition is True
        assert cfg.exclude_attention is False
        # Research
        assert cfg.lookback == 252
        assert isinstance(cfg.alpha_config, AlphaConfig)
        # Execution
        assert cfg.max_turnover == 0.30
        assert cfg.min_trade_value == 50_000
        # Safety
        assert cfg.max_consecutive_losses == 5
        assert cfg.ic_reversal_days == 10
        assert cfg.emergency_stop_drawdown == 0.05

    def test_decision_config_nested(self) -> None:
        cfg = AutoAlphaConfig()
        assert isinstance(cfg.decision, DecisionConfig)
        assert cfg.decision.min_icir == 0.3

    def test_convenience_properties(self) -> None:
        """Property accessors should delegate to nested DecisionConfig."""
        dc = DecisionConfig(min_icir=0.8, min_hit_rate=0.60)
        cfg = AutoAlphaConfig(decision=dc)
        assert cfg.min_icir == 0.8
        assert cfg.min_hit_rate == 0.60
        assert cfg.max_cost_drag == 200.0
        assert cfg.use_rolling_ic is True
        assert cfg.regime_aware is True

    def test_custom_alpha_config(self) -> None:
        ac = AlphaConfig(n_quantiles=10, holding_period=10)
        cfg = AutoAlphaConfig(alpha_config=ac)
        assert cfg.alpha_config.n_quantiles == 10
        assert cfg.alpha_config.holding_period == 10


class TestFactorScore:
    """FactorScore data model."""

    def test_creation(self) -> None:
        score = FactorScore(
            name="momentum",
            ic=0.045,
            icir=0.82,
            hit_rate=0.55,
            decay_half_life=10,
            turnover=0.15,
            cost_drag_bps=120.0,
            regime_ic={"bull": 0.06, "bear": -0.02},
            long_short_sharpe=1.2,
            eligible=True,
        )
        assert score.name == "momentum"
        assert score.ic == 0.045
        assert score.eligible is True
        assert score.regime_ic["bull"] == 0.06

    def test_defaults(self) -> None:
        score = FactorScore(
            name="test", ic=0.0, icir=0.0, hit_rate=0.0,
            decay_half_life=0, turnover=0.0, cost_drag_bps=0.0,
        )
        assert score.regime_ic == {}
        assert score.long_short_sharpe == 0.0
        assert score.eligible is False


class TestResearchSnapshot:
    """ResearchSnapshot data model."""

    def test_auto_universe_size(self) -> None:
        snap = ResearchSnapshot(universe=["AAPL", "MSFT", "GOOG"])
        assert snap.universe_size == 3

    def test_explicit_universe_size(self) -> None:
        snap = ResearchSnapshot(universe=["AAPL"], universe_size=5)
        assert snap.universe_size == 5

    def test_defaults(self) -> None:
        snap = ResearchSnapshot()
        assert snap.regime == MarketRegime.SIDEWAYS
        assert snap.universe == []
        assert snap.factor_scores == {}
        assert snap.selected_factors == []
        assert snap.daily_pnl is None
        assert snap.cumulative_return is None
        assert snap.trades_count == 0

    def test_uuid_generated(self) -> None:
        s1 = ResearchSnapshot()
        s2 = ResearchSnapshot()
        assert s1.id != s2.id
        assert len(s1.id) == 36  # UUID format


class TestAlphaAlert:
    """AlphaAlert data model."""

    def test_creation(self) -> None:
        alert = AlphaAlert(
            level="critical",
            category="drawdown",
            message="Drawdown reached 5.2%",
            details={"dd": 0.052},
        )
        assert alert.level == "critical"
        assert alert.category == "drawdown"
        assert isinstance(alert.timestamp, datetime)

    def test_defaults(self) -> None:
        alert = AlphaAlert()
        assert alert.level == "info"
        assert alert.category == ""
        assert alert.message == ""
        assert alert.details == {}


class TestAlertRules:
    """ALERT_RULES template dict."""

    def test_all_rules_present(self) -> None:
        expected_keys = {
            "regime_change", "factor_degraded", "ic_reversal",
            "high_turnover", "drawdown_warning", "emergency_stop",
            "no_eligible_factors", "disposition_added",
        }
        assert set(ALERT_RULES.keys()) == expected_keys

    def test_rules_are_strings(self) -> None:
        for key, val in ALERT_RULES.items():
            assert isinstance(val, str), f"{key} should be a string"
