"""Tests for SafetyChecker — drawdown circuit breaker and loss streak detection."""

from __future__ import annotations

import uuid
from datetime import date

from src.alpha.auto.config import AutoAlphaConfig, ResearchSnapshot
from src.alpha.auto.safety import SafetyChecker
from src.alpha.auto.store import AlphaStore
from src.alpha.regime import MarketRegime


def _make_config(**overrides: object) -> AutoAlphaConfig:
    """Create an AutoAlphaConfig, bypassing AlphaConfig import."""
    from src.alpha.pipeline import AlphaConfig

    defaults = {
        "alpha_config": AlphaConfig(),
        "emergency_stop_drawdown": 0.05,
        "max_consecutive_losses": 5,
    }
    defaults.update(overrides)
    return AutoAlphaConfig(**defaults)  # type: ignore[arg-type]


def _make_snapshot(snap_date: str, daily_pnl: float | None = None) -> ResearchSnapshot:
    return ResearchSnapshot(
        id=str(uuid.uuid4()),
        date=date.fromisoformat(snap_date),
        regime=MarketRegime.SIDEWAYS,
        daily_pnl=daily_pnl,
    )


# ------------------------------------------------------------------
# Normal operation
# ------------------------------------------------------------------


class TestNormalOperation:
    def test_no_danger(self, tmp_path: object) -> None:
        """When NAV is healthy and no loss streak, should_pause is False."""
        store = AlphaStore(db_path=str(tmp_path / "s.json"))  # type: ignore[operator]
        # Some winning days
        for i in range(3):
            store.save_snapshot(_make_snapshot(f"2026-03-{20 + i:02d}", daily_pnl=100.0))

        checker = SafetyChecker(_make_config(), store)
        result = checker.check(portfolio_nav=1_050_000, initial_nav=1_000_000)

        assert result.should_pause is False
        assert result.alerts == []
        assert result.drawdown < 0  # NAV above initial means negative drawdown
        assert result.consecutive_losses == 0


# ------------------------------------------------------------------
# Drawdown triggers
# ------------------------------------------------------------------


class TestDrawdownTrigger:
    def test_drawdown_triggers_pause(self, tmp_path: object) -> None:
        """Drawdown >= 5% should trigger emergency stop."""
        store = AlphaStore(db_path=str(tmp_path / "s.json"))  # type: ignore[operator]
        checker = SafetyChecker(_make_config(emergency_stop_drawdown=0.05), store)

        # NAV dropped 6% from initial
        result = checker.check(portfolio_nav=940_000, initial_nav=1_000_000)

        assert result.should_pause is True
        assert result.drawdown == 0.06
        assert len(result.alerts) == 1
        assert result.alerts[0].level == "critical"
        assert result.alerts[0].category == "drawdown"

    def test_drawdown_just_below_threshold(self, tmp_path: object) -> None:
        """Drawdown just below threshold should NOT trigger pause."""
        store = AlphaStore(db_path=str(tmp_path / "s.json"))  # type: ignore[operator]
        checker = SafetyChecker(_make_config(emergency_stop_drawdown=0.05), store)

        result = checker.check(portfolio_nav=960_000, initial_nav=1_000_000)

        assert result.should_pause is False
        assert result.drawdown == 0.04


# ------------------------------------------------------------------
# Consecutive losses
# ------------------------------------------------------------------


class TestConsecutiveLosses:
    def test_consecutive_losses_warning(self, tmp_path: object) -> None:
        """5+ consecutive loss days should generate a warning alert."""
        store = AlphaStore(db_path=str(tmp_path / "s.json"))  # type: ignore[operator]
        # 6 consecutive loss days
        for i in range(6):
            store.save_snapshot(
                _make_snapshot(f"2026-03-{20 + i:02d}", daily_pnl=-50.0)
            )

        checker = SafetyChecker(
            _make_config(max_consecutive_losses=5, emergency_stop_drawdown=0.99),
            store,
        )
        result = checker.check(portfolio_nav=999_000, initial_nav=1_000_000)

        assert result.consecutive_losses == 6
        assert len(result.alerts) == 1
        assert result.alerts[0].level == "warning"
        assert result.alerts[0].category == "execution"

    def test_loss_streak_broken_by_win(self, tmp_path: object) -> None:
        """A winning day should break the loss streak."""
        store = AlphaStore(db_path=str(tmp_path / "s.json"))  # type: ignore[operator]
        # 3 losses, then 1 win, then 2 losses (most recent first when listed)
        store.save_snapshot(_make_snapshot("2026-03-20", daily_pnl=-50.0))
        store.save_snapshot(_make_snapshot("2026-03-21", daily_pnl=-50.0))
        store.save_snapshot(_make_snapshot("2026-03-22", daily_pnl=-50.0))
        store.save_snapshot(_make_snapshot("2026-03-23", daily_pnl=100.0))
        store.save_snapshot(_make_snapshot("2026-03-24", daily_pnl=-50.0))
        store.save_snapshot(_make_snapshot("2026-03-25", daily_pnl=-50.0))

        checker = SafetyChecker(
            _make_config(max_consecutive_losses=5, emergency_stop_drawdown=0.99),
            store,
        )
        result = checker.check(portfolio_nav=999_000, initial_nav=1_000_000)

        # Only 2 consecutive losses from most recent
        assert result.consecutive_losses == 2
        assert result.alerts == []


# ------------------------------------------------------------------
# Both triggers
# ------------------------------------------------------------------


class TestBothTriggers:
    def test_drawdown_and_losses_together(self, tmp_path: object) -> None:
        """Both drawdown and consecutive losses can fire simultaneously."""
        store = AlphaStore(db_path=str(tmp_path / "s.json"))  # type: ignore[operator]
        for i in range(6):
            store.save_snapshot(
                _make_snapshot(f"2026-03-{20 + i:02d}", daily_pnl=-100.0)
            )

        checker = SafetyChecker(
            _make_config(emergency_stop_drawdown=0.05, max_consecutive_losses=5),
            store,
        )
        # 7% drawdown + 6 consecutive losses
        result = checker.check(portfolio_nav=930_000, initial_nav=1_000_000)

        assert result.should_pause is True
        assert result.drawdown == 0.07
        assert result.consecutive_losses == 6
        assert len(result.alerts) == 2
        levels = {a.level for a in result.alerts}
        assert "critical" in levels
        assert "warning" in levels
