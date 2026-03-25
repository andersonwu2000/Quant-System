"""AlphaScheduler — orchestrator for the automated alpha pipeline stages.

This module defines job specifications that SchedulerService can consume and
provides a ``run_full_cycle`` method for synchronous (test / manual) execution.

It does NOT import APScheduler directly — it only returns job dicts.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.alpha.auto.config import AutoAlphaConfig
from src.alpha.auto.decision import AlphaDecisionEngine, DecisionResult
from src.alpha.auto.executor import AlphaExecutor, ExecutionResult
from src.alpha.auto.universe import UniverseResult, UniverseSelector
from src.domain.models import Portfolio
from src.execution.execution_service import ExecutionService
from src.risk.engine import RiskEngine

logger = logging.getLogger(__name__)

# Schedule definitions — cron expressions for each pipeline stage.
SCHEDULES: dict[str, str] = {
    "health_check": "30 8 * * 1-5",
    "universe": "50 8 * * 1-5",
    "research": "52 8 * * 1-5",
    "decision": "55 8 * * 1-5",
    "execution": "00 9 * * 1-5",
    "eod_processing": "30 13 * * 1-5",
    "safety_check": "35 13 * * 1-5",
    "weekly_report": "00 9 * * 1",
}


class AlphaScheduler:
    """Pure orchestrator that wires universe → research → decision → execution.

    Parameters
    ----------
    config:
        Automated Alpha configuration.
    universe_selector:
        Optional pre-built UniverseSelector (injected for testing).
    researcher:
        Optional AlphaResearcher instance (injected for testing).
    decision_engine:
        Optional AlphaDecisionEngine (injected for testing).
    executor:
        Optional AlphaExecutor (injected for testing).
    """

    def __init__(
        self,
        config: AutoAlphaConfig,
        *,
        universe_selector: UniverseSelector | None = None,
        researcher: Any | None = None,
        decision_engine: AlphaDecisionEngine | None = None,
        executor: AlphaExecutor | None = None,
    ) -> None:
        self._config = config
        self._universe_selector = universe_selector or UniverseSelector(config)
        self._researcher = researcher
        self._decision_engine = decision_engine or AlphaDecisionEngine(config)
        self._executor = executor or AlphaExecutor(config)

    def create_jobs(self) -> list[dict[str, str]]:
        """Return job definitions consumable by SchedulerService.

        Each dict has keys: ``id``, ``func_path``, ``cron``.
        """
        base_path = "src.alpha.auto.scheduler"
        jobs: list[dict[str, str]] = []

        for stage, cron in SCHEDULES.items():
            jobs.append(
                {
                    "id": f"auto_alpha_{stage}",
                    "func_path": f"{base_path}.{stage}",
                    "cron": cron,
                }
            )

        return jobs

    def run_full_cycle(
        self,
        data: dict[str, pd.DataFrame],
        portfolio: Portfolio,
        execution_service: ExecutionService,
        risk_engine: RiskEngine,
        current_weights: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Execute the full pipeline synchronously (for testing / manual trigger).

        Returns a summary dict with keys:
        ``universe``, ``snapshot``, ``decision``, ``execution``.
        """
        summary: dict[str, Any] = {}

        # Stage 1: Universe selection
        universe_result: UniverseResult = self._universe_selector.select(data=data)
        summary["universe"] = {
            "count": len(universe_result.symbols),
            "excluded_disposition": len(universe_result.excluded_disposition),
            "excluded_attention": len(universe_result.excluded_attention),
        }
        logger.info(
            "Stage 1 Universe: %d symbols selected", len(universe_result.symbols)
        )

        if not universe_result.symbols:
            summary["snapshot"] = None
            summary["decision"] = None
            summary["execution"] = None
            return summary

        # Stage 2: Research
        snapshot = None
        if self._researcher is not None:
            snapshot = self._researcher.run(
                universe=universe_result.symbols,
                data=data,
            )
        summary["snapshot"] = snapshot

        if snapshot is None:
            logger.warning("No researcher available — skipping research stage")
            summary["decision"] = None
            summary["execution"] = None
            return summary

        # Stage 3: Decision
        decision: DecisionResult = self._decision_engine.decide(
            snapshot=snapshot,
            current_weights=current_weights,
        )
        summary["decision"] = {
            "selected_factors": decision.selected_factors,
            "factor_weights": decision.factor_weights,
            "regime": decision.regime.value,
            "reason": decision.reason,
        }
        logger.info(
            "Stage 3 Decision: %d factors selected, regime=%s",
            len(decision.selected_factors),
            decision.regime.value,
        )

        # Stage 4: Execution
        exec_result: ExecutionResult = self._executor.execute(
            decision=decision,
            data=data,
            portfolio=portfolio,
            execution_service=execution_service,
            risk_engine=risk_engine,
        )
        summary["execution"] = {
            "trades_count": exec_result.trades_count,
            "turnover": exec_result.turnover,
            "orders_submitted": exec_result.orders_submitted,
            "orders_rejected": exec_result.orders_rejected,
        }
        logger.info(
            "Stage 4 Execution: %d trades, turnover=%.2f%%",
            exec_result.trades_count,
            exec_result.turnover * 100,
        )

        return summary
