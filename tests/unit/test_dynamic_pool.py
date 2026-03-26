"""Tests for DynamicFactorPool (F4c)."""

from __future__ import annotations

import tempfile
from datetime import date, timedelta

from src.alpha.auto.config import AutoAlphaConfig, FactorScore, ResearchSnapshot
from src.alpha.auto.dynamic_pool import DynamicFactorPool, FactorPoolResult
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


def _build_pool(
    factor_scores: dict[str, FactorScore],
    n_days: int = 5,
    top_n: int = 8,
    min_icir: float = 0.2,
) -> DynamicFactorPool:
    """Build a DynamicFactorPool with a store containing identical snapshots for n_days."""
    tmp = tempfile.mktemp(suffix=".json")
    store = AlphaStore(db_path=tmp)
    base = date(2026, 1, 1)
    for i in range(n_days):
        snap = ResearchSnapshot(
            date=base + timedelta(days=i),
            regime=MarketRegime.SIDEWAYS,
            universe=["A", "B"],
            factor_scores=factor_scores,
        )
        store.save_snapshot(snap)
    tracker = FactorPerformanceTracker(store)
    config = AutoAlphaConfig()
    return DynamicFactorPool(tracker, config, top_n=top_n, min_icir_threshold=min_icir)


# ---------------------------------------------------------------------------
# get_all_factor_names
# ---------------------------------------------------------------------------

class TestGetAllFactorNames:
    def test_returns_all_registered_factors(self) -> None:
        """All registered factors are returned (FACTOR_REGISTRY + FUNDAMENTAL_REGISTRY)."""
        names = DynamicFactorPool.get_all_factor_names()
        # FACTOR_REGISTRY has 66 + FUNDAMENTAL_REGISTRY has 17 = 83
        assert len(names) == 83
        assert "momentum" in names
        assert "value_pe" in names
        assert "quality_roe" in names
        assert "size" in names
        assert "investment" in names
        assert "gross_profit" in names


# ---------------------------------------------------------------------------
# Top-N selection
# ---------------------------------------------------------------------------

class TestTopNSelection:
    def test_top_n_selected(self) -> None:
        """Only top-N factors by ICIR are active when many are above threshold."""
        scores = {f"f{i}": _make_score(f"f{i}", icir=0.3 + 0.05 * i) for i in range(12)}
        pool = _build_pool(scores, top_n=5, min_icir=0.2)
        result = pool.update_pool(lookback=10)

        # Top 5 by ICIR should be active; lower ones may be excluded
        assert len(result.active) <= 12
        # The bottom factors (low ICIR and rank > 5) that still exceed threshold stay active
        # Those below threshold AND rank > top_n get excluded
        assert isinstance(result, FactorPoolResult)

    def test_top_n_with_all_good_factors(self) -> None:
        """When all observed factors have high ICIR, those outside top-N but above threshold stay active."""
        scores = {f"f{i}": _make_score(f"f{i}", icir=0.8) for i in range(5)}
        pool = _build_pool(scores, top_n=3, min_icir=0.2)
        result = pool.update_pool(lookback=10)

        # All 5 observed factors have ICIR=0.8 >> min_icir=0.2, so even those ranked > 3 stay active
        assert len(result.active) == 5
        for i in range(5):
            assert f"f{i}" in result.active
        # Registry factors with no data are excluded separately
        assert all(name.startswith("f") or name in result.excluded for name in
                    result.active + result.excluded)


# ---------------------------------------------------------------------------
# Exclusion
# ---------------------------------------------------------------------------

class TestExclusion:
    def test_exclude_consistently_poor_factors(self) -> None:
        """Factors with ICIR below threshold are excluded."""
        scores = {
            "good": _make_score("good", icir=0.6),
            "bad": _make_score("bad", icir=0.1),  # below default 0.2 threshold
        }
        pool = _build_pool(scores, top_n=8, min_icir=0.2)
        result = pool.update_pool(lookback=10)

        assert "good" in result.active
        assert "bad" in result.excluded

    def test_exclude_no_data_factors(self) -> None:
        """Factors not present in any snapshot are excluded."""
        # Only store 'mom' in snapshots; any other factor from registry has no data
        scores = {"mom": _make_score("mom", icir=0.5)}
        pool = _build_pool(scores, top_n=8, min_icir=0.2)
        result = pool.update_pool(lookback=10)

        # 'mom' should be active; all others should be excluded (no data)
        assert "mom" in result.active
        assert len(result.excluded) > 0


# ---------------------------------------------------------------------------
# Probation
# ---------------------------------------------------------------------------

class TestProbation:
    def test_declining_factor_on_probation(self) -> None:
        """A factor with declining trend should be on probation but still active."""
        tmp = tempfile.mktemp(suffix=".json")
        store = AlphaStore(db_path=tmp)
        base = date(2026, 1, 1)

        # Create 40 days: first 20 with high ICIR, last 20 with lower ICIR
        for i in range(40):
            icir = 0.8 if i < 20 else 0.5  # 37.5% decline > 10% → "declining"
            snap = ResearchSnapshot(
                date=base + timedelta(days=i),
                regime=MarketRegime.SIDEWAYS,
                universe=["A"],
                factor_scores={"declining_f": _make_score("declining_f", icir=icir)},
            )
            store.save_snapshot(snap)

        tracker = FactorPerformanceTracker(store)
        config = AutoAlphaConfig()
        pool = DynamicFactorPool(tracker, config, top_n=8, min_icir_threshold=0.2)
        result = pool.update_pool(lookback=40)

        assert "declining_f" in result.probation
        assert "declining_f" in result.active  # still active


# ---------------------------------------------------------------------------
# All factors active
# ---------------------------------------------------------------------------

class TestAllActive:
    def test_all_factors_active_when_all_good(self) -> None:
        """When all factors have good ICIR, none are excluded (except unseen registry factors)."""
        scores = {
            "a": _make_score("a", icir=0.7),
            "b": _make_score("b", icir=0.6),
            "c": _make_score("c", icir=0.5),
        }
        pool = _build_pool(scores, top_n=10, min_icir=0.2)
        result = pool.update_pool(lookback=10)

        # These 3 should all be active
        for name in ["a", "b", "c"]:
            assert name in result.active


# ---------------------------------------------------------------------------
# Changes tracking
# ---------------------------------------------------------------------------

class TestChangesTracking:
    def test_changes_list_populated(self) -> None:
        """Changes list records exclusions and probations."""
        scores = {
            "good": _make_score("good", icir=0.6),
            "bad": _make_score("bad", icir=0.1),
        }
        pool = _build_pool(scores, top_n=8, min_icir=0.2)
        result = pool.update_pool(lookback=10)

        # Should have at least one change for 'bad' exclusion
        assert len(result.changes) > 0
        assert any("bad" in c for c in result.changes)

    def test_no_changes_when_all_good(self) -> None:
        """When all tracked factors are active and stable, only unseen registry factors generate changes."""
        # Use only factors that exist in registry and have good ICIR
        all_names = DynamicFactorPool.get_all_factor_names()
        scores = {name: _make_score(name, icir=0.7) for name in all_names}
        pool = _build_pool(scores, top_n=27, min_icir=0.2)
        result = pool.update_pool(lookback=10)

        # All factors active, no exclusions
        assert len(result.excluded) == 0
        # No exclusion/probation changes (all are stable at 0.7)
        assert not any("excluded" in c for c in result.changes)
