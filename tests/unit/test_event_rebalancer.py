"""Tests for EventDrivenRebalancer (Phase L+.3)."""

import pandas as pd

from src.alpha.event_rebalancer import EventDrivenRebalancer, RebalanceSignal


class TestRebalanceSignal:
    def test_default_no_rebalance(self) -> None:
        s = RebalanceSignal(should_rebalance=False)
        assert not s.should_rebalance
        assert s.trigger == ""

    def test_with_trigger(self) -> None:
        s = RebalanceSignal(should_rebalance=True, trigger="revenue_announcement")
        assert s.should_rebalance
        assert s.trigger == "revenue_announcement"


class TestEventDrivenRebalancer:
    def test_revenue_announcement_day(self) -> None:
        """Day 11-13 should trigger revenue announcement."""
        r = EventDrivenRebalancer()
        signal = r.check("2024-03-11")
        assert signal.should_rebalance
        assert signal.trigger == "revenue_announcement"

    def test_non_trigger_day(self) -> None:
        """Day 5 should not trigger."""
        r = EventDrivenRebalancer()
        signal = r.check("2024-03-05")
        assert not signal.should_rebalance

    def test_no_duplicate_trigger_same_month(self) -> None:
        """Same month should not trigger twice."""
        r = EventDrivenRebalancer()
        s1 = r.check("2024-03-11")
        s2 = r.check("2024-03-12")
        assert s1.should_rebalance
        assert not s2.should_rebalance  # already triggered this month

    def test_different_month_triggers(self) -> None:
        """Different months should trigger independently."""
        r = EventDrivenRebalancer()
        s1 = r.check("2024-03-11")
        s2 = r.check("2024-04-11")
        assert s1.should_rebalance
        assert s2.should_rebalance

    def test_fallback_monthly(self) -> None:
        """Day >= 25 should trigger monthly fallback."""
        r = EventDrivenRebalancer(fallback_monthly=True)
        signal = r.check("2024-03-25")
        assert signal.should_rebalance
        assert signal.trigger == "monthly_fallback"

    def test_no_fallback_when_disabled(self) -> None:
        r = EventDrivenRebalancer(fallback_monthly=False)
        signal = r.check("2024-03-25")
        assert not signal.should_rebalance

    def test_custom_day_range(self) -> None:
        r = EventDrivenRebalancer(revenue_trigger_day_range=(8, 10))
        assert r.check("2024-03-09").should_rebalance
        assert not r.check("2024-04-11").should_rebalance  # outside 8-10


class TestInstitutionalSurge:
    def test_no_surge_normal(self) -> None:
        r = EventDrivenRebalancer()
        # Normal series, no surge
        series = pd.Series([100.0] * 70)
        assert not r.check_institutional_surge(series)

    def test_surge_detected(self) -> None:
        r = EventDrivenRebalancer(institutional_sigma=2.0)
        # Normal then huge spike
        values = [100.0] * 60 + [10000.0] * 10  # massive spike in last 10
        series = pd.Series(values)
        assert r.check_institutional_surge(series)

    def test_insufficient_data(self) -> None:
        r = EventDrivenRebalancer()
        series = pd.Series([100.0] * 10)  # too short
        assert not r.check_institutional_surge(series)
