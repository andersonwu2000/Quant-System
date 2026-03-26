"""Tests for EOD reconciliation — 持倉對帳。"""

from __future__ import annotations

from decimal import Decimal

from src.core.models import Instrument, Portfolio, Position
from src.execution.reconcile import (
    PositionDiff,
    auto_correct,
    reconcile,
)


def _make_portfolio(**positions: tuple[int, float]) -> Portfolio:
    """建立投資組合。positions: symbol → (qty, avg_cost)"""
    p = Portfolio()
    for symbol, (qty, cost) in positions.items():
        p.positions[symbol] = Position(
            instrument=Instrument(symbol=symbol),
            quantity=Decimal(str(qty)),
            avg_cost=Decimal(str(cost)),
        )
    return p


class TestReconcile:
    def test_perfect_match(self) -> None:
        portfolio = _make_portfolio(**{"2330": (1000, 590), "2317": (2000, 100)})
        broker_positions = {
            "2330": {"quantity": 1000, "avg_cost": 590},
            "2317": {"quantity": 2000, "avg_cost": 100},
        }
        result = reconcile(portfolio, broker_positions)
        assert result.is_clean
        assert len(result.matched) == 2
        assert len(result.mismatched) == 0

    def test_quantity_mismatch(self) -> None:
        portfolio = _make_portfolio(**{"2330": (1000, 590)})
        broker_positions = {"2330": {"quantity": 2000, "avg_cost": 590}}

        result = reconcile(portfolio, broker_positions)
        assert not result.is_clean
        assert len(result.mismatched) == 1
        assert result.mismatched[0].diff_qty == Decimal("1000")

    def test_system_only(self) -> None:
        portfolio = _make_portfolio(**{"2330": (1000, 590), "2317": (500, 100)})
        broker_positions = {"2330": {"quantity": 1000, "avg_cost": 590}}

        result = reconcile(portfolio, broker_positions)
        assert not result.is_clean
        assert len(result.system_only) == 1
        assert result.system_only[0].symbol == "2317"

    def test_broker_only(self) -> None:
        portfolio = _make_portfolio(**{"2330": (1000, 590)})
        broker_positions = {
            "2330": {"quantity": 1000, "avg_cost": 590},
            "2454": {"quantity": 3000, "avg_cost": 80},
        }

        result = reconcile(portfolio, broker_positions)
        assert not result.is_clean
        assert len(result.broker_only) == 1
        assert result.broker_only[0].symbol == "2454"

    def test_empty_both(self) -> None:
        portfolio = Portfolio()
        result = reconcile(portfolio, {})
        assert result.is_clean
        assert result.total_positions == 0

    def test_tolerance(self) -> None:
        portfolio = _make_portfolio(**{"2330": (1000, 590)})
        broker_positions = {"2330": {"quantity": 1001, "avg_cost": 590}}

        # Without tolerance → mismatch
        result = reconcile(portfolio, broker_positions, tolerance=Decimal("0"))
        assert not result.is_clean

        # With tolerance → match
        result = reconcile(portfolio, broker_positions, tolerance=Decimal("5"))
        assert result.is_clean

    def test_summary_output(self) -> None:
        portfolio = _make_portfolio(**{"2330": (1000, 590)})
        broker_positions = {"2330": {"quantity": 2000, "avg_cost": 590}}
        result = reconcile(portfolio, broker_positions)
        summary = result.summary()
        assert "DISCREPANCY" in summary
        assert "2330" in summary


class TestPositionDiff:
    def test_is_matched(self) -> None:
        d = PositionDiff("2330", Decimal("1000"), Decimal("1000"), Decimal("0"), Decimal("590"), Decimal("590"))
        assert d.is_matched

    def test_diff_pct(self) -> None:
        d = PositionDiff("2330", Decimal("1000"), Decimal("1100"), Decimal("100"), Decimal("590"), Decimal("590"))
        assert abs(d.diff_pct - 0.1) < 0.001

    def test_diff_pct_zero_system(self) -> None:
        d = PositionDiff("2330", Decimal("0"), Decimal("100"), Decimal("100"), Decimal("0"), Decimal("590"))
        assert d.diff_pct == float("inf")

    def test_diff_pct_both_zero(self) -> None:
        d = PositionDiff("2330", Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"))
        assert d.diff_pct == 0.0


class TestAutoCorrect:
    def test_correct_mismatch(self) -> None:
        portfolio = _make_portfolio(**{"2330": (1000, 590)})
        broker_positions = {"2330": {"quantity": 2000, "avg_cost": 595}}
        result = reconcile(portfolio, broker_positions)

        corrections = auto_correct(portfolio, result)
        assert len(corrections) == 1
        assert portfolio.positions["2330"].quantity == Decimal("2000")
        assert portfolio.positions["2330"].avg_cost == Decimal("595")

    def test_add_broker_only(self) -> None:
        portfolio = Portfolio()
        broker_positions = {"2454": {"quantity": 3000, "avg_cost": 80}}
        result = reconcile(portfolio, broker_positions)

        auto_correct(portfolio, result)
        assert "2454" in portfolio.positions
        assert portfolio.positions["2454"].quantity == Decimal("3000")

    def test_remove_system_only(self) -> None:
        portfolio = _make_portfolio(**{"2330": (1000, 590)})
        result = reconcile(portfolio, {})

        auto_correct(portfolio, result)
        assert "2330" not in portfolio.positions

    def test_no_correct_when_trust_broker_false(self) -> None:
        portfolio = _make_portfolio(**{"2330": (1000, 590)})
        broker_positions = {"2330": {"quantity": 2000, "avg_cost": 595}}
        result = reconcile(portfolio, broker_positions)

        corrections = auto_correct(portfolio, result, trust_broker=False)
        assert len(corrections) == 0
        assert portfolio.positions["2330"].quantity == Decimal("1000")  # Unchanged
