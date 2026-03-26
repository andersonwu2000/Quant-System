"""Automated Alpha Research System — daily scheduled factor research, decision, and execution."""

from src.alpha.auto.alerts import AlertManager
from src.alpha.auto.backtest_gate import GateResult
from src.alpha.auto.config import (
    AlphaAlert,
    AutoAlphaConfig,
    DecisionConfig,
    FactorScore,
    ResearchSnapshot,
)
from src.alpha.auto.decision import AlphaDecisionEngine, DecisionResult
from src.alpha.auto.dynamic_pool import DynamicFactorPool, FactorPoolResult
from src.alpha.auto.executor import AlphaExecutor, ExecutionResult
from src.alpha.auto.factor_tracker import FactorPerformanceTracker
from src.alpha.auto.researcher import AlphaResearcher
from src.alpha.auto.safety import RecoveryResult, SafetyChecker, SafetyResult
from src.alpha.auto.scheduler import AlphaScheduler
from src.alpha.auto.store import AlphaStore
from src.alpha.auto.universe import UniverseResult, UniverseSelector

__all__ = [
    "AlertManager",
    "AlphaAlert",
    "AlphaDecisionEngine",
    "AlphaExecutor",
    "AlphaResearcher",
    "AlphaScheduler",
    "AlphaStore",
    "AutoAlphaConfig",
    "DecisionConfig",
    "DecisionResult",
    "DynamicFactorPool",
    "ExecutionResult",
    "GateResult",
    "FactorPerformanceTracker",
    "FactorPoolResult",
    "FactorScore",
    "RecoveryResult",
    "ResearchSnapshot",
    "SafetyChecker",
    "SafetyResult",
    "UniverseResult",
    "UniverseSelector",
]
