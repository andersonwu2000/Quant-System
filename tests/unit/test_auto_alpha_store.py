"""Tests for AlphaStore — JSON file persistence for snapshots and alerts."""

from __future__ import annotations

import uuid
from datetime import date, datetime

import pytest

from src.alpha.auto.config import AlphaAlert, FactorScore, ResearchSnapshot
from src.alpha.auto.store import AlphaStore
from src.alpha.regime import MarketRegime


def _make_snapshot(
    snap_date: str = "2026-03-26",
    regime: MarketRegime = MarketRegime.BULL,
    daily_pnl: float | None = None,
) -> ResearchSnapshot:
    """Helper to build a snapshot with minimal boilerplate."""
    return ResearchSnapshot(
        id=str(uuid.uuid4()),
        date=date.fromisoformat(snap_date),
        regime=regime,
        universe=["2330", "2317"],
        universe_size=2,
        factor_scores={
            "momentum": FactorScore(
                name="momentum",
                ic=0.05,
                icir=0.8,
                hit_rate=0.55,
                decay_half_life=5,
                turnover=0.1,
                cost_drag_bps=50.0,
                eligible=True,
            ),
        },
        selected_factors=["momentum"],
        factor_weights={"momentum": 1.0},
        target_weights={"2330": 0.5, "2317": 0.5},
        trades_count=2,
        turnover=0.15,
        daily_pnl=daily_pnl,
    )


def _make_alert(level: str = "warning", category: str = "factor") -> AlphaAlert:
    return AlphaAlert(
        timestamp=datetime.now(),
        level=level,  # type: ignore[arg-type]
        category=category,
        message="test alert",
        details={"foo": "bar"},
    )


# ------------------------------------------------------------------
# Snapshot round-trip
# ------------------------------------------------------------------


class TestSnapshotPersistence:
    def test_save_and_get_snapshot(self, tmp_path: object) -> None:
        store = AlphaStore(db_path=str(tmp_path / "store.json"))  # type: ignore[operator]
        snap = _make_snapshot("2026-03-20", daily_pnl=100.0)
        store.save_snapshot(snap)

        loaded = store.get_snapshot("2026-03-20")
        assert loaded is not None
        assert loaded.date == date(2026, 3, 20)
        assert loaded.regime == MarketRegime.BULL
        assert loaded.daily_pnl == 100.0
        assert "momentum" in loaded.factor_scores
        assert loaded.factor_scores["momentum"].icir == 0.8

    def test_get_snapshot_not_found(self, tmp_path: object) -> None:
        store = AlphaStore(db_path=str(tmp_path / "store.json"))  # type: ignore[operator]
        assert store.get_snapshot("2099-01-01") is None

    def test_list_snapshots_ordering(self, tmp_path: object) -> None:
        """Most recent snapshot should come first."""
        store = AlphaStore(db_path=str(tmp_path / "store.json"))  # type: ignore[operator]
        for i in range(5):
            store.save_snapshot(_make_snapshot(f"2026-03-{20 + i:02d}"))

        result = store.list_snapshots(limit=3)
        assert len(result) == 3
        # Most recent first
        assert result[0].date == date(2026, 3, 24)
        assert result[1].date == date(2026, 3, 23)
        assert result[2].date == date(2026, 3, 22)

    def test_list_snapshots_limit(self, tmp_path: object) -> None:
        store = AlphaStore(db_path=str(tmp_path / "store.json"))  # type: ignore[operator]
        for i in range(10):
            store.save_snapshot(_make_snapshot(f"2026-01-{i + 1:02d}"))

        result = store.list_snapshots(limit=5)
        assert len(result) == 5

    def test_max_entries_limit(self, tmp_path: object) -> None:
        """Store should keep at most 365 snapshots."""
        store = AlphaStore(db_path=str(tmp_path / "store.json"))  # type: ignore[operator]
        # Save 370 snapshots
        for i in range(370):
            day = date(2025, 1, 1).toordinal() + i
            d = date.fromordinal(day)
            store.save_snapshot(_make_snapshot(d.isoformat()))

        all_snaps = store.list_snapshots(limit=400)
        assert len(all_snaps) == 365

    def test_empty_store(self, tmp_path: object) -> None:
        store = AlphaStore(db_path=str(tmp_path / "store.json"))  # type: ignore[operator]
        assert store.list_snapshots() == []
        assert store.get_snapshot("2026-01-01") is None


# ------------------------------------------------------------------
# Alerts
# ------------------------------------------------------------------


class TestAlertPersistence:
    def test_save_and_list_alerts(self, tmp_path: object) -> None:
        store = AlphaStore(db_path=str(tmp_path / "store.json"))  # type: ignore[operator]
        store.save_alert(_make_alert("warning", "factor"))
        store.save_alert(_make_alert("critical", "drawdown"))

        alerts = store.list_alerts(limit=10)
        assert len(alerts) == 2
        # Most recent first
        assert alerts[0].category == "drawdown"
        assert alerts[1].category == "factor"

    def test_list_alerts_empty(self, tmp_path: object) -> None:
        store = AlphaStore(db_path=str(tmp_path / "store.json"))  # type: ignore[operator]
        assert store.list_alerts() == []


# ------------------------------------------------------------------
# Performance summary
# ------------------------------------------------------------------


class TestPerformanceSummary:
    def test_performance_summary_basic(self, tmp_path: object) -> None:
        store = AlphaStore(db_path=str(tmp_path / "store.json"))  # type: ignore[operator]
        # 3 winning days, 1 losing day
        for i, pnl in enumerate([100.0, 200.0, -50.0, 150.0]):
            store.save_snapshot(
                _make_snapshot(f"2026-03-{20 + i:02d}", daily_pnl=pnl)
            )

        summary = store.get_performance_summary()
        assert summary["total_days"] == 4
        assert summary["win_rate"] == 0.75
        assert summary["cumulative_return"] == pytest.approx(400.0)
        assert summary["best_day"] == 200.0
        assert summary["worst_day"] == -50.0
        assert summary["avg_daily_pnl"] == pytest.approx(100.0)
        # Max drawdown: peak=300 after day 2, then drop to 250 after day 3 → dd=50
        assert summary["max_drawdown"] == pytest.approx(50.0)

    def test_performance_summary_empty(self, tmp_path: object) -> None:
        store = AlphaStore(db_path=str(tmp_path / "store.json"))  # type: ignore[operator]
        summary = store.get_performance_summary()
        assert summary["total_days"] == 0
        assert summary["win_rate"] == 0.0
        assert summary["cumulative_return"] == 0.0
