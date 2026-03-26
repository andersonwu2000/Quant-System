"""AlphaScheduler — orchestrator for the automated alpha pipeline stages.

This module defines job specifications that SchedulerService can consume and
provides a ``run_full_cycle`` method for synchronous (test / manual) execution.

It does NOT import APScheduler directly — it only returns job dicts.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pandas as pd

from src.alpha.auto.config import AutoAlphaConfig
from src.alpha.auto.decision import AlphaDecisionEngine, DecisionResult
from src.alpha.auto.dynamic_pool import DynamicFactorPool
from src.alpha.auto.executor import AlphaExecutor, ExecutionResult
from src.alpha.auto.factor_tracker import FactorPerformanceTracker
from src.alpha.auto.safety import SafetyChecker
from src.alpha.auto.store import AlphaStore
from src.alpha.auto.universe import UniverseResult, UniverseSelector
from src.core.models import Portfolio
from src.execution.service import ExecutionService
from src.risk.engine import RiskEngine

logger = logging.getLogger(__name__)


def _broadcast_event(event_type: str, data: dict[str, Any]) -> None:
    """Fire-and-forget broadcast to auto-alpha WS channel."""
    try:
        from src.api.ws import ws_manager

        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(
                ws_manager.broadcast("auto-alpha", {"type": event_type, **data})
            )
        else:
            loop.run_until_complete(
                ws_manager.broadcast("auto-alpha", {"type": event_type, **data})
            )
    except Exception:
        pass  # WS broadcast is best-effort

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
        store: AlphaStore | None = None,
    ) -> None:
        self._config = config
        self._universe_selector = universe_selector or UniverseSelector(config)
        self._researcher = researcher
        self._decision_engine = decision_engine or AlphaDecisionEngine(config)
        self._executor = executor or AlphaExecutor(config)
        self._store = store

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
        auto_alpha_paused: bool = False,
        days_since_pause: int = 0,
    ) -> dict[str, Any]:
        """Execute the full pipeline synchronously (for testing / manual trigger).

        Returns a summary dict with keys:
        ``universe``, ``snapshot``, ``decision``, ``execution``.
        """
        summary: dict[str, Any] = {}

        try:
            # Pre-check: skip on non-trading days
            from src.core.calendar import get_tw_calendar
            from datetime import date as _date

            cal = get_tw_calendar()
            today = _date.today()
            if not cal.is_trading_day(today):
                logger.info(
                    "Skipping full cycle — %s is not a trading day", today.isoformat()
                )
                summary["skipped"] = True
                summary["reason"] = f"{today.isoformat()} is not a trading day"
                return summary

            # Stage 1: Universe selection
            _broadcast_event("stage_started", {"stage": "universe"})
            universe_result: UniverseResult = self._universe_selector.select(data=data)
            summary["universe"] = {
                "count": len(universe_result.symbols),
                "excluded_disposition": len(universe_result.excluded_disposition),
                "excluded_attention": len(universe_result.excluded_attention),
            }
            _broadcast_event(
                "stage_completed",
                {"stage": "universe", "count": len(universe_result.symbols)},
            )
            logger.info(
                "Stage 1 Universe: %d symbols selected", len(universe_result.symbols)
            )

            if not universe_result.symbols:
                summary["snapshot"] = None
                summary["decision"] = None
                summary["execution"] = None
                return summary

            # Stage 2: Research
            _broadcast_event("stage_started", {"stage": "research"})
            snapshot = None
            if self._researcher is not None:
                snapshot = self._researcher.run(
                    universe=universe_result.symbols,
                    data=data,
                )
            summary["snapshot"] = snapshot

            if snapshot is None:
                logger.warning("No researcher available — skipping research stage")
                _broadcast_event(
                    "stage_completed", {"stage": "research", "factors": 0}
                )
                summary["decision"] = None
                summary["execution"] = None
                return summary

            _broadcast_event(
                "stage_completed",
                {"stage": "research", "factors": len(snapshot.factor_scores)},
            )

            # Stage 2.5: Dynamic factor pool (between research and decision)
            if self._store is not None:
                try:
                    tracker = FactorPerformanceTracker(self._store)
                    pool = DynamicFactorPool(tracker, self._config)
                    pool_result = pool.update_pool()
                    logger.info(
                        "DynamicFactorPool: active=%d, probation=%d, excluded=%d",
                        len(pool_result.active),
                        len(pool_result.probation),
                        len(pool_result.excluded),
                    )
                    if pool_result.excluded:
                        logger.info(
                            "Excluded factors: %s", pool_result.excluded,
                        )
                    if pool_result.probation:
                        logger.warning(
                            "Probation factors (declining trend): %s",
                            pool_result.probation,
                        )
                except Exception:
                    logger.warning(
                        "DynamicFactorPool evaluation failed, proceeding without pool filter",
                        exc_info=True,
                    )

            # Stage 3: Decision
            _broadcast_event("stage_started", {"stage": "decision"})
            decision: DecisionResult = self._decision_engine.decide(
                snapshot=snapshot,
                current_weights=current_weights,
                store=self._store,
            )
            summary["decision"] = {
                "selected_factors": decision.selected_factors,
                "factor_weights": decision.factor_weights,
                "regime": decision.regime.value,
                "reason": decision.reason,
            }
            _broadcast_event(
                "decision",
                {
                    "factors": decision.selected_factors,
                    "regime": decision.regime.value,
                    "weights": decision.factor_weights,
                },
            )
            logger.info(
                "Stage 3 Decision: %d factors selected, regime=%s",
                len(decision.selected_factors),
                decision.regime.value,
            )

            # Stage 3.5: Backtest Gate — verify strategy would have been profitable recently
            if self._config.backtest_gate_enabled and decision.selected_factors:
                from src.alpha.auto.backtest_gate import verify_before_execution

                _broadcast_event("stage_started", {"stage": "backtest_gate"})
                gate_result = verify_before_execution(
                    decision=decision,
                    data=data,
                    config=self._config,
                )
                summary["gate"] = {
                    "passed": gate_result.passed,
                    "sharpe": gate_result.sharpe,
                    "total_return": gate_result.total_return,
                    "max_drawdown": gate_result.max_drawdown,
                    "net_cost": gate_result.net_cost,
                    "reason": gate_result.reason,
                }
                if not gate_result.passed:
                    logger.warning(
                        "Backtest gate BLOCKED execution: %s", gate_result.reason
                    )
                    _broadcast_event(
                        "gate_blocked",
                        {"reason": gate_result.reason, "sharpe": gate_result.sharpe},
                    )
                    summary["execution"] = None
                    return summary
                logger.info("Backtest gate PASSED: Sharpe=%.2f", gate_result.sharpe)
                _broadcast_event(
                    "stage_completed",
                    {"stage": "backtest_gate", "sharpe": gate_result.sharpe},
                )

            # Kill switch recovery check
            if auto_alpha_paused:
                safety_checker = SafetyChecker(self._config, self._store or AlphaStore())
                recovery = safety_checker.check_recovery(days_since_pause)
                summary["recovery"] = {
                    "can_resume": recovery.can_resume,
                    "position_scale": recovery.position_scale,
                    "reason": recovery.reason,
                }
                if not recovery.can_resume:
                    logger.info("Kill switch recovery: %s", recovery.reason)
                    summary["execution"] = None
                    return summary
                # Scale down factor weights during recovery ramp
                for factor in list(decision.factor_weights):
                    decision.factor_weights[factor] *= recovery.position_scale
                logger.info(
                    "Resuming with %.0f%% position", recovery.position_scale * 100
                )

            # Stage 4: Execution
            _broadcast_event("stage_started", {"stage": "execution"})
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
            _broadcast_event(
                "execution",
                {
                    "trades": exec_result.trades_count,
                    "turnover": exec_result.turnover,
                },
            )
            logger.info(
                "Stage 4 Execution: %d trades, turnover=%.2f%%",
                exec_result.trades_count,
                exec_result.turnover * 100,
            )

            # Broadcast alert if there were rejected orders
            if exec_result.orders_rejected > 0:
                _broadcast_event(
                    "alert",
                    {
                        "level": "warning",
                        "message": f"{exec_result.orders_rejected} orders rejected",
                    },
                )

            return summary

        except Exception as exc:
            _broadcast_event("error", {"message": str(exc)})
            raise
