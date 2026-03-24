"""
應用狀態 — 交易引擎的全局狀態（單體架構的核心）。

所有 API route 透過 get_app_state() 存取共享狀態。
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from src.data.store import DataStore
from src.domain.models import Portfolio
from src.execution.oms import OrderManager
from src.risk.engine import RiskEngine


def _make_risk_engine() -> RiskEngine:
    store = DataStore()
    return RiskEngine(persist_fn=store.save_risk_event)


@dataclass
class AppState:
    """應用全局狀態。"""
    portfolio: Portfolio = field(default_factory=lambda: Portfolio(cash=Decimal("10000000")))
    oms: OrderManager = field(default_factory=OrderManager)
    risk_engine: RiskEngine = field(default_factory=_make_risk_engine)
    strategies: dict[str, dict[str, Any]] = field(default_factory=dict)
    backtest_tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    alpha_tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    # 保護 portfolio mutation 的非同步鎖
    mutation_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # 保護 backtest_tasks 跨執行緒存取
    backtest_lock: threading.Lock = field(default_factory=threading.Lock)


_state: AppState | None = None
_state_lock = threading.Lock()


def get_app_state() -> AppState:
    global _state
    if _state is None:
        with _state_lock:
            if _state is None:
                _state = AppState()
    return _state


def reset_app_state() -> None:
    """測試用：重置狀態。"""
    global _state
    _state = None
