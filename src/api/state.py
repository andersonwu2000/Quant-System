"""
應用狀態 — 交易引擎的全局狀態（單體架構的核心）。

所有 API route 透過 get_app_state() 存取共享狀態。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from src.domain.models import Portfolio
from src.execution.oms import OrderManager
from src.risk.engine import RiskEngine


@dataclass
class AppState:
    """應用全局狀態。"""
    portfolio: Portfolio = field(default_factory=lambda: Portfolio(cash=Decimal("10000000")))
    oms: OrderManager = field(default_factory=OrderManager)
    risk_engine: RiskEngine = field(default_factory=RiskEngine)
    strategies: dict[str, dict] = field(default_factory=dict)
    backtest_tasks: dict[str, dict] = field(default_factory=dict)


_state: AppState | None = None


def get_app_state() -> AppState:
    global _state
    if _state is None:
        _state = AppState()
    return _state


def reset_app_state() -> None:
    """測試用：重置狀態。"""
    global _state
    _state = None
