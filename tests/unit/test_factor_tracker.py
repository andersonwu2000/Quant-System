"""Tests for FactorPerformanceTracker (F4b)."""

from __future__ import annotations

import tempfile
from datetime import date, timedelta

from src.alpha.auto.config import FactorScore, ResearchSnapshot
from src.alpha.auto.factor_tracker import FactorPerformanceTracker
from src.alpha.auto.store import AlphaStore
from src.alpha.regime import MarketRegime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_score(name: str, ic: float = 0.03, icir: float = 0.5, hit_rate: float = 0.55) -> FactorScore:
    return FactorScore(
        name=name,
        ic=ic,
        icir=icir,
        hit_rate=hit_rate,
        decay_half_life=5,
        turnover=0.1,
        cost_drag_bps=100.0,
        long_short_sharpe=1.0,
        eligible=True,
    )


def _make_snapshot(
    day: date,
    factor_scores: dict[str, FactorScore],
    regime: MarketRegime = MarketRegime.SIDEWAYS,
) -> ResearchSnapshot:
    return ResearchSnapshot(
        date=day,
        regime=regime,
        universe=["A", "B"],
        factor_scores=factor_scores,
    )


def _build_store_with_snapshots(snapshots: list[ResearchSnapshot]) -> AlphaStore:
    """Create a temp AlphaStore and save snapshots."""
    tmp = tempfile.mktemp(suffix=".json")
    store = AlphaStore(db_path=tmp)
    for snap in snapshots:
        store.save_snapshot(snap)
    return store


# ---------------------------------------------------------------------------
# Cumulative IC
# ---------------------------------------------------------------------------

class TestCumulativeIC:
    def test_cumulative_ic_basic(self) -> None:
        """Cumulative IC sums individual ICs over time."""
        base = date(2026, 1, 1)
        snaps = [
            _make_snapshot(base + timedelta(days=i), {"mom": _make_score("mom", ic=0.01 * (i + 1))})
            for i in range(5)
        ]
        store = _build_store_with_snapshots(snaps)
        tracker = FactorPerformanceTracker(store)
        result = tracker.compute_cumulative_ic("mom", lookback=10)

        assert len(result) == 5
        # Cumulative should be increasing: 0.01, 0.01+0.02, ...
        assert result[0]["cumulative_ic"] == round(0.01, 6)
        assert result[4]["cumulative_ic"] == round(0.01 + 0.02 + 0.03 + 0.04 + 0.05, 6)

    def test_cumulative_ic_missing_factor(self) -> None:
        """If factor is not present in snapshots, cumulative IC stays 0."""
        base = date(2026, 1, 1)
        snaps = [_make_snapshot(base + timedelta(days=i), {"mom": _make_score("mom")}) for i in range(3)]
        store = _build_store_with_snapshots(snaps)
        tracker = FactorPerformanceTracker(store)
        result = tracker.compute_cumulative_ic("nonexistent", lookback=10)

        assert len(result) == 3
        assert all(r["cumulative_ic"] == 0.0 for r in result)

    def test_cumulative_ic_respects_lookback(self) -> None:
        """Lookback limits the number of snapshots considered."""
        base = date(2026, 1, 1)
        snaps = [
            _make_snapshot(base + timedelta(days=i), {"mom": _make_score("mom", ic=0.01)})
            for i in range(10)
        ]
        store = _build_store_with_snapshots(snaps)
        tracker = FactorPerformanceTracker(store)
        result = tracker.compute_cumulative_ic("mom", lookback=5)

        assert len(result) == 5


# ---------------------------------------------------------------------------
# Factor ranking
# ---------------------------------------------------------------------------

class TestRankFactors:
    def test_rank_by_icir(self) -> None:
        """Factors are ranked by ICIR descending."""
        base = date(2026, 1, 1)
        scores = {
            "mom": _make_score("mom", icir=0.8),
            "vol": _make_score("vol", icir=0.3),
            "rsi": _make_score("rsi", icir=0.6),
        }
        snaps = [_make_snapshot(base, scores)]
        store = _build_store_with_snapshots(snaps)
        tracker = FactorPerformanceTracker(store)
        ranking = tracker.rank_factors(metric="icir", lookback=10)

        assert ranking[0]["name"] == "mom"
        assert ranking[0]["rank"] == 1
        assert ranking[1]["name"] == "rsi"
        assert ranking[2]["name"] == "vol"

    def test_rank_by_hit_rate(self) -> None:
        """Ranking by hit_rate works correctly."""
        base = date(2026, 1, 1)
        scores = {
            "a": _make_score("a", hit_rate=0.7),
            "b": _make_score("b", hit_rate=0.5),
        }
        snaps = [_make_snapshot(base, scores)]
        store = _build_store_with_snapshots(snaps)
        tracker = FactorPerformanceTracker(store)
        ranking = tracker.rank_factors(metric="hit_rate", lookback=10)

        assert ranking[0]["name"] == "a"
        assert ranking[1]["name"] == "b"


# ---------------------------------------------------------------------------
# Trend detection
# ---------------------------------------------------------------------------

class TestTrendDetection:
    def test_improving_trend(self) -> None:
        """Series with significantly increasing ICIR is 'improving'."""
        # Prior 20 days: ICIR=0.3, recent 20 days: ICIR=0.5 (67% increase > 10%)
        base = date(2026, 1, 1)
        snaps = []
        for i in range(40):
            icir = 0.3 if i < 20 else 0.5
            snaps.append(_make_snapshot(
                base + timedelta(days=i),
                {"f": _make_score("f", icir=icir)},
            ))
        store = _build_store_with_snapshots(snaps)
        tracker = FactorPerformanceTracker(store)
        summary = tracker.get_factor_summary(lookback=40)

        assert summary["f"]["trend"] == "improving"

    def test_declining_trend(self) -> None:
        """Series with significantly decreasing ICIR is 'declining'."""
        base = date(2026, 1, 1)
        snaps = []
        for i in range(40):
            icir = 0.5 if i < 20 else 0.3
            snaps.append(_make_snapshot(
                base + timedelta(days=i),
                {"f": _make_score("f", icir=icir)},
            ))
        store = _build_store_with_snapshots(snaps)
        tracker = FactorPerformanceTracker(store)
        summary = tracker.get_factor_summary(lookback=40)

        assert summary["f"]["trend"] == "declining"

    def test_stable_trend(self) -> None:
        """Series with flat ICIR is 'stable'."""
        base = date(2026, 1, 1)
        snaps = []
        for i in range(40):
            snaps.append(_make_snapshot(
                base + timedelta(days=i),
                {"f": _make_score("f", icir=0.5)},
            ))
        store = _build_store_with_snapshots(snaps)
        tracker = FactorPerformanceTracker(store)
        summary = tracker.get_factor_summary(lookback=40)

        assert summary["f"]["trend"] == "stable"


# ---------------------------------------------------------------------------
# Drawdown
# ---------------------------------------------------------------------------

class TestDrawdown:
    def test_drawdown_computation(self) -> None:
        """Drawdown measures peak-to-trough in cumulative IC."""
        base = date(2026, 1, 1)
        # IC goes up then down: +0.05, +0.05, -0.1 → peak=0.10, trough=0.0, dd=0.10
        ics = [0.05, 0.05, -0.10]
        snaps = [
            _make_snapshot(base + timedelta(days=i), {"f": _make_score("f", ic=ics[i])})
            for i in range(3)
        ]
        store = _build_store_with_snapshots(snaps)
        tracker = FactorPerformanceTracker(store)
        dd = tracker.compute_factor_drawdown("f")

        assert dd["peak_ic"] == round(0.10, 6)
        assert dd["current_ic"] == 0.0
        assert dd["drawdown"] == round(0.10, 6)


# ---------------------------------------------------------------------------
# Empty store
# ---------------------------------------------------------------------------

class TestEmptyStore:
    def test_empty_store_cumulative_ic(self) -> None:
        """Empty store returns empty list."""
        tmp = tempfile.mktemp(suffix=".json")
        store = AlphaStore(db_path=tmp)
        tracker = FactorPerformanceTracker(store)
        result = tracker.compute_cumulative_ic("any_factor")

        assert result == []

    def test_empty_store_summary(self) -> None:
        """Empty store returns empty summary."""
        tmp = tempfile.mktemp(suffix=".json")
        store = AlphaStore(db_path=tmp)
        tracker = FactorPerformanceTracker(store)
        summary = tracker.get_factor_summary()

        assert summary == {}

    def test_empty_store_drawdown(self) -> None:
        """Empty store returns zero drawdown."""
        tmp = tempfile.mktemp(suffix=".json")
        store = AlphaStore(db_path=tmp)
        tracker = FactorPerformanceTracker(store)
        dd = tracker.compute_factor_drawdown("any_factor")

        assert dd["drawdown"] == 0.0
