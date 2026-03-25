"""Tests for AlertManager — rule-based alert generation."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from src.alpha.auto.alerts import AlertManager
from src.alpha.auto.config import FactorScore, ResearchSnapshot
from src.alpha.auto.store import AlphaStore
from src.alpha.regime import MarketRegime


def _make_factor_score(
    name: str, ic: float = 0.05, icir: float = 0.8
) -> FactorScore:
    return FactorScore(
        name=name,
        ic=ic,
        icir=icir,
        hit_rate=0.55,
        decay_half_life=5,
        turnover=0.1,
        cost_drag_bps=50.0,
        eligible=True,
    )


def _make_snapshot_with_ic(
    snap_date: str,
    factor_name: str = "momentum",
    ic: float = -0.03,
) -> ResearchSnapshot:
    return ResearchSnapshot(
        id=str(uuid.uuid4()),
        date=date.fromisoformat(snap_date),
        regime=MarketRegime.BEAR,
        factor_scores={
            factor_name: _make_factor_score(factor_name, ic=ic),
        },
        selected_factors=[],
    )


# ------------------------------------------------------------------
# Regime change
# ------------------------------------------------------------------


class TestRegimeChange:
    def test_regime_change_detected(self, tmp_path: object) -> None:
        store = AlphaStore(db_path=str(tmp_path / "s.json"))  # type: ignore[operator]
        mgr = AlertManager(store)

        alert = mgr.check_regime_change(MarketRegime.BULL, MarketRegime.BEAR)
        assert alert is not None
        assert alert.level == "warning"
        assert alert.category == "regime"
        assert "bull" in alert.message.lower()
        assert "bear" in alert.message.lower()

    def test_no_regime_change_same(self, tmp_path: object) -> None:
        store = AlphaStore(db_path=str(tmp_path / "s.json"))  # type: ignore[operator]
        mgr = AlertManager(store)

        alert = mgr.check_regime_change(MarketRegime.BULL, MarketRegime.BULL)
        assert alert is None

    def test_no_regime_change_prev_none(self, tmp_path: object) -> None:
        store = AlphaStore(db_path=str(tmp_path / "s.json"))  # type: ignore[operator]
        mgr = AlertManager(store)

        alert = mgr.check_regime_change(None, MarketRegime.BULL)
        assert alert is None


# ------------------------------------------------------------------
# Factor degradation
# ------------------------------------------------------------------


class TestFactorDegradation:
    def test_degradation_detected(self, tmp_path: object) -> None:
        store = AlphaStore(db_path=str(tmp_path / "s.json"))  # type: ignore[operator]
        mgr = AlertManager(store)

        prev = {"momentum": _make_factor_score("momentum", icir=0.8)}
        curr = {"momentum": _make_factor_score("momentum", icir=0.5)}

        alerts = mgr.check_factor_degradation(prev, curr, threshold=0.2)
        assert len(alerts) == 1
        assert "momentum" in alerts[0].message
        assert alerts[0].details["drop"] == pytest.approx(0.3)

    def test_no_degradation_small_drop(self, tmp_path: object) -> None:
        store = AlphaStore(db_path=str(tmp_path / "s.json"))  # type: ignore[operator]
        mgr = AlertManager(store)

        prev = {"momentum": _make_factor_score("momentum", icir=0.8)}
        curr = {"momentum": _make_factor_score("momentum", icir=0.7)}

        alerts = mgr.check_factor_degradation(prev, curr, threshold=0.2)
        assert len(alerts) == 0

    def test_degradation_multiple_factors(self, tmp_path: object) -> None:
        store = AlphaStore(db_path=str(tmp_path / "s.json"))  # type: ignore[operator]
        mgr = AlertManager(store)

        prev = {
            "momentum": _make_factor_score("momentum", icir=0.8),
            "value": _make_factor_score("value", icir=0.6),
        }
        curr = {
            "momentum": _make_factor_score("momentum", icir=0.5),
            "value": _make_factor_score("value", icir=0.3),
        }

        alerts = mgr.check_factor_degradation(prev, curr, threshold=0.2)
        assert len(alerts) == 2


# ------------------------------------------------------------------
# IC reversal
# ------------------------------------------------------------------


class TestICReversal:
    def test_ic_reversal_detected(self, tmp_path: object) -> None:
        store = AlphaStore(db_path=str(tmp_path / "s.json"))  # type: ignore[operator]
        mgr = AlertManager(store)

        # Save 10 days of negative IC for 'momentum'
        for i in range(10):
            store.save_snapshot(
                _make_snapshot_with_ic(f"2026-03-{10 + i:02d}", "momentum", ic=-0.03)
            )

        alert = mgr.check_ic_reversal(store, "momentum", days=10)
        assert alert is not None
        assert "momentum" in alert.message
        assert alert.details["consecutive_negative_days"] == 10

    def test_ic_reversal_not_enough_days(self, tmp_path: object) -> None:
        store = AlphaStore(db_path=str(tmp_path / "s.json"))  # type: ignore[operator]
        mgr = AlertManager(store)

        # Only 5 negative days
        for i in range(5):
            store.save_snapshot(
                _make_snapshot_with_ic(f"2026-03-{10 + i:02d}", "momentum", ic=-0.03)
            )

        alert = mgr.check_ic_reversal(store, "momentum", days=10)
        assert alert is None

    def test_ic_reversal_broken_by_positive(self, tmp_path: object) -> None:
        """Positive IC in the middle should break the streak."""
        store = AlphaStore(db_path=str(tmp_path / "s.json"))  # type: ignore[operator]
        mgr = AlertManager(store)

        for i in range(5):
            store.save_snapshot(
                _make_snapshot_with_ic(f"2026-03-{10 + i:02d}", "momentum", ic=-0.03)
            )
        # One positive day
        store.save_snapshot(
            _make_snapshot_with_ic("2026-03-15", "momentum", ic=0.02)
        )
        for i in range(4):
            store.save_snapshot(
                _make_snapshot_with_ic(f"2026-03-{16 + i:02d}", "momentum", ic=-0.03)
            )

        alert = mgr.check_ic_reversal(store, "momentum", days=10)
        assert alert is None


# ------------------------------------------------------------------
# No eligible factors
# ------------------------------------------------------------------


class TestNoEligibleFactors:
    def test_no_eligible_alert(self, tmp_path: object) -> None:
        store = AlphaStore(db_path=str(tmp_path / "s.json"))  # type: ignore[operator]
        mgr = AlertManager(store)

        alert = mgr.check_no_eligible_factors([])
        assert alert is not None
        assert alert.level == "critical"
        assert alert.category == "factor"

    def test_has_eligible_no_alert(self, tmp_path: object) -> None:
        store = AlphaStore(db_path=str(tmp_path / "s.json"))  # type: ignore[operator]
        mgr = AlertManager(store)

        alert = mgr.check_no_eligible_factors(["momentum", "value"])
        assert alert is None
