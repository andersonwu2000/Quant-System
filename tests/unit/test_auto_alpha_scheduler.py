"""Tests for AlphaScheduler (F1f)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from src.alpha.auto.config import AutoAlphaConfig, FactorScore, ResearchSnapshot
from src.alpha.auto.decision import AlphaDecisionEngine, DecisionResult
from src.alpha.auto.executor import AlphaExecutor, ExecutionResult
from src.alpha.auto.scheduler import AlphaScheduler, SCHEDULES
from src.alpha.auto.universe import UniverseResult, UniverseSelector
from src.alpha.regime import MarketRegime
from src.core.models import Portfolio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_data() -> dict[str, pd.DataFrame]:
    dates = pd.date_range("2024-01-01", periods=60, freq="B")
    result: dict[str, pd.DataFrame] = {}
    for sym in ["AAPL", "MSFT"]:
        df = pd.DataFrame(
            {
                "open": 100.0,
                "high": 105.0,
                "low": 95.0,
                "close": 102.0,
                "volume": 1_000_000,
            },
            index=dates,
        )
        result[sym] = df
    return result


def _good_score(name: str) -> FactorScore:
    return FactorScore(
        name=name, ic=0.04, icir=0.6, hit_rate=0.58,
        decay_half_life=5, turnover=0.1, cost_drag_bps=80.0,
        long_short_sharpe=1.2, eligible=True,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCreateJobs:
    """AlphaScheduler.create_jobs() returns correct job specs."""

    def test_returns_list_of_dicts(self) -> None:
        cfg = AutoAlphaConfig()
        scheduler = AlphaScheduler(cfg)
        jobs = scheduler.create_jobs()

        assert isinstance(jobs, list)
        assert len(jobs) == len(SCHEDULES)

    def test_job_keys(self) -> None:
        cfg = AutoAlphaConfig()
        scheduler = AlphaScheduler(cfg)
        jobs = scheduler.create_jobs()

        for job in jobs:
            assert "id" in job
            assert "func_path" in job
            assert "cron" in job
            assert job["id"].startswith("auto_alpha_")

    def test_cron_matches_schedules(self) -> None:
        cfg = AutoAlphaConfig()
        scheduler = AlphaScheduler(cfg)
        jobs = scheduler.create_jobs()

        job_by_id = {j["id"]: j for j in jobs}
        for stage, cron in SCHEDULES.items():
            job_id = f"auto_alpha_{stage}"
            assert job_id in job_by_id
            assert job_by_id[job_id]["cron"] == cron


class TestRunFullCycle:
    """AlphaScheduler.run_full_cycle() orchestration."""

    def test_full_cycle_with_mocks(self) -> None:
        """Full cycle executes all 4 stages."""
        cfg = AutoAlphaConfig()

        # Mock universe selector
        universe_selector = MagicMock(spec=UniverseSelector)
        universe_selector.select.return_value = UniverseResult(
            symbols=["AAPL", "MSFT"],
            total_candidates=5,
        )

        # Mock researcher
        snapshot = ResearchSnapshot(
            regime=MarketRegime.BULL,
            universe=["AAPL", "MSFT"],
            factor_scores={"momentum": _good_score("momentum")},
        )
        researcher = MagicMock()
        researcher.run.return_value = snapshot

        # Mock decision engine
        decision_engine = MagicMock(spec=AlphaDecisionEngine)
        decision_engine.decide.return_value = DecisionResult(
            selected_factors=["momentum"],
            factor_weights={"momentum": 1.0},
            regime=MarketRegime.BULL,
            reason="test",
        )

        # Mock executor
        executor = MagicMock(spec=AlphaExecutor)
        executor.execute.return_value = ExecutionResult(
            trades_count=2, turnover=0.05,
            orders_submitted=2, orders_rejected=0,
        )

        scheduler = AlphaScheduler(
            cfg,
            universe_selector=universe_selector,
            researcher=researcher,
            decision_engine=decision_engine,
            executor=executor,
        )

        data = _make_data()
        portfolio = Portfolio()
        risk_engine = MagicMock()
        exec_service = MagicMock()

        summary = scheduler.run_full_cycle(
            data=data,
            portfolio=portfolio,
            execution_service=exec_service,
            risk_engine=risk_engine,
        )

        assert summary["universe"]["count"] == 2
        assert summary["snapshot"] is snapshot
        assert summary["decision"]["regime"] == "bull"
        assert summary["execution"]["trades_count"] == 2

        universe_selector.select.assert_called_once()
        researcher.run.assert_called_once()
        decision_engine.decide.assert_called_once()
        executor.execute.assert_called_once()

    def test_empty_universe_short_circuits(self) -> None:
        """When universe is empty, later stages are skipped."""
        cfg = AutoAlphaConfig()

        universe_selector = MagicMock(spec=UniverseSelector)
        universe_selector.select.return_value = UniverseResult(symbols=[])

        researcher = MagicMock()

        scheduler = AlphaScheduler(
            cfg,
            universe_selector=universe_selector,
            researcher=researcher,
        )

        data = _make_data()
        portfolio = Portfolio()
        risk_engine = MagicMock()
        exec_service = MagicMock()

        summary = scheduler.run_full_cycle(
            data=data,
            portfolio=portfolio,
            execution_service=exec_service,
            risk_engine=risk_engine,
        )

        assert summary["universe"]["count"] == 0
        assert summary["snapshot"] is None
        assert summary["decision"] is None
        assert summary["execution"] is None
        researcher.run.assert_not_called()
