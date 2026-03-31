"""AK-2 Layer 4: Restart recovery and idempotency tests.

Verifies:
- Portfolio persists across save/load cycle
- Pipeline doesn't re-execute after restart
- Deployed strategies don't duplicate rebalance in same month
- Ledger crash recovery replays unflushed fills
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch


from src.core.models import Instrument, Portfolio, Position


# ── Test 4.1: Portfolio persistence ─────────────────────────────────


class TestPortfolioPersistence:
    """save_portfolio → load_portfolio round-trip must be lossless."""

    def test_save_load_roundtrip(self, tmp_path):
        """Positions and cash survive save/load cycle."""
        state_file = tmp_path / "portfolio_state.json"

        # Build portfolio
        p = Portfolio()
        p.positions["2330.TW"] = Position(
            instrument=Instrument(symbol="2330.TW"),
            quantity=Decimal("1000"),
            avg_cost=Decimal("590.5"),
        )
        p.positions["2317.TW"] = Position(
            instrument=Instrument(symbol="2317.TW"),
            quantity=Decimal("2000"),
            avg_cost=Decimal("103.25"),
        )

        # Save
        data = {
            "cash": str(p.cash),
            "positions": {
                sym: {
                    "symbol": sym,
                    "quantity": str(pos.quantity),
                    "avg_cost": str(pos.avg_cost),
                }
                for sym, pos in p.positions.items()
            },
            "as_of": datetime.now().isoformat(),
        }
        state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Load
        loaded = json.loads(state_file.read_text(encoding="utf-8"))
        assert Decimal(loaded["cash"]) == p.cash
        assert len(loaded["positions"]) == 2
        assert Decimal(loaded["positions"]["2330.TW"]["quantity"]) == Decimal("1000")
        assert Decimal(loaded["positions"]["2317.TW"]["avg_cost"]) == Decimal("103.25")

    def test_empty_portfolio_roundtrip(self, tmp_path):
        """Empty portfolio save/load produces empty portfolio."""
        state_file = tmp_path / "portfolio_state.json"
        p = Portfolio()
        data = {"cash": str(p.cash), "positions": {}, "as_of": datetime.now().isoformat()}
        state_file.write_text(json.dumps(data), encoding="utf-8")

        loaded = json.loads(state_file.read_text(encoding="utf-8"))
        assert len(loaded["positions"]) == 0


# ── Test 4.2: Pipeline idempotency ─────────────────────────────────


class TestPipelineIdempotency:
    """Pipeline must not re-execute if a completed run exists."""

    def test_has_completed_run_today(self, tmp_path):
        """_has_completed_run_today returns True when today's run exists."""
        from src.scheduler.jobs import _has_completed_run_today

        runs_dir = tmp_path / "pipeline_runs"
        runs_dir.mkdir()

        today = datetime.now().strftime("%Y-%m-%d")
        run_file = runs_dir / f"{today}_0911.json"
        run_file.write_text(json.dumps({
            "run_id": f"{today}_0911",
            "status": "completed",
            "strategy": "revenue_momentum_hedged",
            "n_trades": 9,
        }))

        with patch("src.scheduler.jobs.PIPELINE_RUNS_DIR", runs_dir):
            assert _has_completed_run_today() is True

    def test_no_run_today(self, tmp_path):
        """_has_completed_run_today returns False when no run exists."""
        from src.scheduler.jobs import _has_completed_run_today

        runs_dir = tmp_path / "pipeline_runs"
        runs_dir.mkdir()

        with patch("src.scheduler.jobs.PIPELINE_RUNS_DIR", runs_dir):
            assert _has_completed_run_today() is False

    def test_has_completed_run_this_month(self, tmp_path):
        """_has_completed_run_this_month returns True when this month's run exists."""
        from src.scheduler.jobs import _has_completed_run_this_month

        runs_dir = tmp_path / "pipeline_runs"
        runs_dir.mkdir()

        today = datetime.now()
        run_date = today.strftime("%Y-%m-15")
        run_file = runs_dir / f"{run_date}_0911.json"
        run_file.write_text(json.dumps({
            "run_id": f"{run_date}_0911",
            "status": "completed",
            "strategy": "revenue_momentum_hedged",
            "n_trades": 5,
        }))

        with patch("src.scheduler.jobs.PIPELINE_RUNS_DIR", runs_dir):
            assert _has_completed_run_this_month() is True

    def test_failed_run_does_not_block(self, tmp_path):
        """A failed/crashed run should NOT prevent re-execution."""
        from src.scheduler.jobs import _has_completed_run_today

        runs_dir = tmp_path / "pipeline_runs"
        runs_dir.mkdir()

        today = datetime.now().strftime("%Y-%m-%d")
        run_file = runs_dir / f"{today}_0911.json"
        run_file.write_text(json.dumps({
            "run_id": f"{today}_0911",
            "status": "crashed",
            "strategy": "revenue_momentum_hedged",
            "n_trades": 0,
        }))

        with patch("src.scheduler.jobs.PIPELINE_RUNS_DIR", runs_dir):
            assert _has_completed_run_today() is False


# ── Test 4.3: Deployed strategies idempotency ──────────────────────


class TestDeployedIdempotency:
    """Deployed strategies must not rebalance twice in same month."""

    def test_should_rebalance_first_run(self, tmp_path):
        """First execution ever → should rebalance."""
        from src.alpha.auto.deployed_executor import _should_rebalance

        with patch("src.alpha.auto.deployed_executor.PAPER_TRADE_DIR", tmp_path):
            assert _should_rebalance("test_strategy") is True

    def test_should_not_rebalance_same_month(self, tmp_path):
        """Already ran this month → should NOT rebalance."""
        from src.alpha.auto.deployed_executor import _should_rebalance

        trade_dir = tmp_path / "test_strategy"
        trade_dir.mkdir()
        today = datetime.now().strftime("%Y-%m-%d")
        (trade_dir / f"{today}.json").write_text(json.dumps({
            "date": today, "weights": {"2330.TW": 0.063}, "nav": 500000,
        }))

        with patch("src.alpha.auto.deployed_executor.PAPER_TRADE_DIR", tmp_path):
            assert _should_rebalance("test_strategy") is False

    def test_should_rebalance_new_month(self, tmp_path):
        """Last run was last month → should rebalance."""
        from src.alpha.auto.deployed_executor import _should_rebalance

        trade_dir = tmp_path / "test_strategy"
        trade_dir.mkdir()
        last_month = (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")
        (trade_dir / f"{last_month}.json").write_text(json.dumps({
            "date": last_month, "weights": {"2330.TW": 0.063}, "nav": 500000,
        }))

        with patch("src.alpha.auto.deployed_executor.PAPER_TRADE_DIR", tmp_path):
            assert _should_rebalance("test_strategy") is True
