"""Tests for kill switch recovery mechanism in SafetyChecker."""

from __future__ import annotations

from src.alpha.auto.config import AutoAlphaConfig
from src.alpha.auto.safety import RecoveryResult, SafetyChecker
from src.alpha.auto.store import AlphaStore
from src.alpha.pipeline import AlphaConfig


def _make_config(**overrides: object) -> AutoAlphaConfig:
    """Create an AutoAlphaConfig with sensible defaults."""
    defaults: dict[str, object] = {
        "alpha_config": AlphaConfig(),
    }
    defaults.update(overrides)
    return AutoAlphaConfig(**defaults)  # type: ignore[arg-type]


def _make_checker(config: AutoAlphaConfig | None = None) -> SafetyChecker:
    """Create a SafetyChecker with an empty store."""
    if config is None:
        config = _make_config()
    return SafetyChecker(config, AlphaStore())


# ------------------------------------------------------------------
# Default config values
# ------------------------------------------------------------------


class TestDefaultConfig:
    def test_default_cooldown_days(self) -> None:
        """Default kill_switch_cooldown_days is 3."""
        cfg = _make_config()
        assert cfg.kill_switch_cooldown_days == 3

    def test_default_recovery_position_pct(self) -> None:
        """Default kill_switch_recovery_position_pct is 0.50."""
        cfg = _make_config()
        assert cfg.kill_switch_recovery_position_pct == 0.50

    def test_default_ramp_days(self) -> None:
        """Default kill_switch_recovery_ramp_days is 5."""
        cfg = _make_config()
        assert cfg.kill_switch_recovery_ramp_days == 5


# ------------------------------------------------------------------
# During cooldown
# ------------------------------------------------------------------


class TestCooldownPeriod:
    def test_day_0_cannot_resume(self) -> None:
        """Day 0 after pause: still in cooldown, cannot resume."""
        checker = _make_checker()
        result = checker.check_recovery(days_since_pause=0)

        assert result.can_resume is False
        assert result.position_scale == 0.0
        assert "Cooldown" in result.reason
        assert "0/3" in result.reason

    def test_day_1_cannot_resume(self) -> None:
        """Day 1 after pause: still in cooldown."""
        checker = _make_checker()
        result = checker.check_recovery(days_since_pause=1)

        assert result.can_resume is False
        assert result.position_scale == 0.0

    def test_day_2_cannot_resume(self) -> None:
        """Day 2 after pause: last day of cooldown, still cannot resume."""
        checker = _make_checker()
        result = checker.check_recovery(days_since_pause=2)

        assert result.can_resume is False
        assert result.position_scale == 0.0


# ------------------------------------------------------------------
# After cooldown — ramp period
# ------------------------------------------------------------------


class TestRecoveryRamp:
    def test_first_day_after_cooldown(self) -> None:
        """Day 3 (first day after 3-day cooldown): can resume at 50%."""
        checker = _make_checker()
        result = checker.check_recovery(days_since_pause=3)

        assert result.can_resume is True
        assert result.position_scale == 0.50

    def test_mid_ramp(self) -> None:
        """Mid-ramp: scale between 0.5 and 1.0."""
        checker = _make_checker()
        # Day 5: cooldown=3, so days_in_ramp=2, ramp_days=5
        # scale = 0.5 + 0.5 * (2/5) = 0.5 + 0.2 = 0.7
        result = checker.check_recovery(days_since_pause=5)

        assert result.can_resume is True
        assert 0.5 < result.position_scale < 1.0
        assert abs(result.position_scale - 0.7) < 1e-9

    def test_last_ramp_day(self) -> None:
        """Last day of ramp: scale approaching 1.0 but not quite."""
        checker = _make_checker()
        # Day 7: cooldown=3, days_in_ramp=4, ramp_days=5
        # scale = 0.5 + 0.5 * (4/5) = 0.5 + 0.4 = 0.9
        result = checker.check_recovery(days_since_pause=7)

        assert result.can_resume is True
        assert abs(result.position_scale - 0.9) < 1e-9

    def test_full_ramp_complete(self) -> None:
        """After full ramp period: scale = 1.0."""
        checker = _make_checker()
        # Day 8: cooldown=3, days_in_ramp=5 >= ramp_days=5
        result = checker.check_recovery(days_since_pause=8)

        assert result.can_resume is True
        assert result.position_scale == 1.0

    def test_well_past_ramp(self) -> None:
        """Well past ramp period: scale stays at 1.0."""
        checker = _make_checker()
        result = checker.check_recovery(days_since_pause=30)

        assert result.can_resume is True
        assert result.position_scale == 1.0


# ------------------------------------------------------------------
# Custom config
# ------------------------------------------------------------------


class TestCustomConfig:
    def test_custom_cooldown(self) -> None:
        """Custom cooldown of 7 days: day 6 cannot resume, day 7 can."""
        cfg = _make_config(kill_switch_cooldown_days=7)
        checker = _make_checker(cfg)

        result_day6 = checker.check_recovery(days_since_pause=6)
        assert result_day6.can_resume is False

        result_day7 = checker.check_recovery(days_since_pause=7)
        assert result_day7.can_resume is True

    def test_custom_recovery_pct(self) -> None:
        """Custom recovery_position_pct of 0.30: starts at 30%."""
        cfg = _make_config(
            kill_switch_cooldown_days=3,
            kill_switch_recovery_position_pct=0.30,
            kill_switch_recovery_ramp_days=5,
        )
        checker = _make_checker(cfg)

        result = checker.check_recovery(days_since_pause=3)
        assert result.can_resume is True
        assert abs(result.position_scale - 0.30) < 1e-9

    def test_custom_ramp_days(self) -> None:
        """Custom ramp_days of 10: full recovery at cooldown + 10."""
        cfg = _make_config(
            kill_switch_cooldown_days=2,
            kill_switch_recovery_position_pct=0.50,
            kill_switch_recovery_ramp_days=10,
        )
        checker = _make_checker(cfg)

        # Day 2: first ramp day, scale = 0.5
        result = checker.check_recovery(days_since_pause=2)
        assert result.position_scale == 0.50

        # Day 7: days_in_ramp=5, scale = 0.5 + 0.5*(5/10) = 0.75
        result = checker.check_recovery(days_since_pause=7)
        assert abs(result.position_scale - 0.75) < 1e-9

        # Day 12: days_in_ramp=10 >= ramp_days=10, scale = 1.0
        result = checker.check_recovery(days_since_pause=12)
        assert result.position_scale == 1.0


# ------------------------------------------------------------------
# RecoveryResult dataclass
# ------------------------------------------------------------------


class TestRecoveryResultDataclass:
    def test_fields(self) -> None:
        """RecoveryResult has all expected fields."""
        r = RecoveryResult(can_resume=True, position_scale=0.75, reason="test")
        assert r.can_resume is True
        assert r.position_scale == 0.75
        assert r.reason == "test"
