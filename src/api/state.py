"""
應用狀態 — 交易引擎的全局狀態（單體架構的核心）。

所有 API route 透過 get_app_state() 存取共享狀態。
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.alpha.auto.config import AutoAlphaConfig
from src.alpha.auto.store import AlphaStore
from src.data.store import DataStore
from src.core.models import (
    AssetClass, Instrument, Market, Portfolio, Position, SubClass,
)
from src.execution.service import ExecutionService
from src.execution.oms import OrderManager
from src.execution.stop_order import StopOrderManager
from src.risk.engine import RiskEngine

logger = logging.getLogger(__name__)

# Lock ordering (to prevent deadlocks):
# 1. state.mutation_lock (asyncio.Lock) — acquired first for async routes
# 2. portfolio.lock (threading.Lock) — acquired second for portfolio mutations
# Never acquire portfolio.lock then mutation_lock (reverse order = deadlock risk)
# Shioaji tick callback thread: only acquires portfolio.lock (no mutation_lock)
#
# WARNING: mutation_lock is asyncio.Lock, portfolio.lock is threading.Lock.
# These are different runtime types — do NOT await mutation_lock from sync code
# or acquire portfolio.lock from async code without run_in_executor.
# Future: AN-37 plans to unify via responsibility split (option C).

# ── Portfolio persistence ────────────────────────────────────────
_PERSIST_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "paper_trading"
_PERSIST_PATH = _PERSIST_DIR / "portfolio_state.json"


def _make_risk_engine() -> RiskEngine:
    store = DataStore()
    return RiskEngine(persist_fn=store.save_risk_event)


def save_portfolio(portfolio: Portfolio) -> None:
    """Serialize portfolio state to JSON for crash recovery."""
    try:
        _PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        positions: dict[str, dict[str, str]] = {}
        for symbol, pos in portfolio.positions.items():
            positions[symbol] = {
                "quantity": str(pos.quantity),
                "avg_cost": str(pos.avg_cost),
                "market_price": str(pos.market_price),
                "asset_class": pos.instrument.asset_class.value if hasattr(pos.instrument.asset_class, 'value') else str(pos.instrument.asset_class),
                "sub_class": pos.instrument.sub_class.value if hasattr(pos.instrument.sub_class, 'value') else str(pos.instrument.sub_class),
                "market": pos.instrument.market.value if hasattr(pos.instrument.market, 'value') else str(pos.instrument.market),
                "currency": pos.instrument.currency,
                "lot_size": str(pos.instrument.lot_size),
                "multiplier": str(pos.instrument.multiplier),
                "name": pos.instrument.name,
            }
        state = {
            "cash": str(portfolio.cash),
            "initial_cash": str(portfolio.initial_cash),
            "nav_sod": str(portfolio.nav_sod),
            "as_of": portfolio.as_of.isoformat() if portfolio.as_of else "",
            "pending_settlements": [
                [sd, str(amt)] for sd, amt in portfolio.pending_settlements
            ],
            "positions": positions,
        }
        tmp_path = _PERSIST_PATH.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        tmp_path.replace(_PERSIST_PATH)
        logger.debug("Portfolio state persisted to %s", _PERSIST_PATH)
    except Exception:
        logger.warning("Failed to persist portfolio state", exc_info=True)


def load_portfolio() -> Portfolio | None:
    """Load portfolio state from JSON. Returns None if no file or error."""
    if not _PERSIST_PATH.exists():
        return None
    try:
        raw = json.loads(_PERSIST_PATH.read_text(encoding="utf-8"))
        positions: dict[str, Position] = {}
        for symbol, pos_data in raw.get("positions", {}).items():
            instrument = Instrument(
                symbol=symbol,
                name=pos_data.get("name", ""),
                asset_class=AssetClass(pos_data.get("asset_class", "EQUITY")),
                sub_class=SubClass(pos_data.get("sub_class", "stock")),
                market=Market(pos_data.get("market", "us")),
                currency=pos_data.get("currency", "TWD"),
                lot_size=int(pos_data.get("lot_size", 1)),
                multiplier=Decimal(pos_data.get("multiplier", "1")),
            )
            positions[symbol] = Position(
                instrument=instrument,
                quantity=Decimal(pos_data["quantity"]),
                avg_cost=Decimal(pos_data["avg_cost"]),
                market_price=Decimal(pos_data["market_price"]),
            )
        cash = Decimal(raw["cash"])
        initial_cash = Decimal(raw.get("initial_cash", raw["cash"]))
        # Restore pending settlements
        settlements: list[tuple[str, Decimal]] = []
        for item in raw.get("pending_settlements", []):
            if isinstance(item, list) and len(item) == 2:
                settlements.append((item[0], Decimal(item[1])))

        portfolio = Portfolio(
            cash=cash,
            initial_cash=initial_cash,
            positions=positions,
            pending_settlements=settlements,
        )
        # E5: nav_sod 預設為當前 NAV（不是 0），避免 kill switch 失效
        saved_nav_sod = raw.get("nav_sod", "0")
        nav_sod = Decimal(saved_nav_sod) if saved_nav_sod != "0" else portfolio.nav
        portfolio.nav_sod = nav_sod
        # P12: 恢復 as_of
        saved_as_of = raw.get("as_of", "")
        if saved_as_of:
            try:
                portfolio.as_of = datetime.fromisoformat(saved_as_of)
            except (ValueError, TypeError):
                pass
        logger.info(
            "Loaded persisted portfolio: cash=%s, %d positions",
            portfolio.cash, len(portfolio.positions),
        )

        # Replay ledger fills that occurred after portfolio was saved.
        # This handles crash between trade execution and portfolio save.
        try:
            portfolio = _replay_ledger(portfolio)
        except Exception:
            logger.warning("Ledger replay failed (non-fatal)", exc_info=True)

        return portfolio
    except Exception:
        logger.warning("Failed to load persisted portfolio state", exc_info=True)
        return None


def _replay_ledger(portfolio: Portfolio) -> Portfolio:
    """Replay trade ledger fills newer than portfolio.as_of.

    If the system crashed between apply_trades (which writes ledger)
    and save_portfolio (which writes JSON), the ledger has fills that
    the portfolio JSON doesn't reflect. Replay them.
    """
    from src.execution.trade_ledger import get_fills_since

    as_of_str = portfolio.as_of.isoformat() if portfolio.as_of else ""
    if not as_of_str:
        return portfolio

    fills = get_fills_since(as_of_str)
    if not fills:
        return portfolio

    logger.warning("Replaying %d ledger fills after portfolio as_of=%s", len(fills), as_of_str)

    for fill in fills:
        sym = fill["symbol"]
        side = fill["side"]
        qty = Decimal(str(fill["quantity"]))
        price = Decimal(str(fill["fill_price"]))
        commission = Decimal(str(fill.get("commission", 0)))

        if "BUY" in side:
            portfolio.cash -= qty * price + commission
            if sym in portfolio.positions:
                pos = portfolio.positions[sym]
                total_cost = pos.avg_cost * pos.quantity + price * qty
                new_qty = pos.quantity + qty
                pos.avg_cost = total_cost / new_qty if new_qty > 0 else Decimal("0")
                pos.quantity = new_qty
                pos.market_price = price
            else:
                from src.core.models import Instrument, Position as Pos
                _is_tw = sym.endswith(".TW") or sym.endswith(".TWO")
                portfolio.positions[sym] = Pos(
                    instrument=Instrument(symbol=sym, lot_size=1000 if _is_tw else 1, market="tw" if _is_tw else "us"),
                    quantity=qty, avg_cost=price, market_price=price,
                )
        elif "SELL" in side:
            portfolio.cash += qty * price - commission
            if sym in portfolio.positions:
                portfolio.positions[sym].quantity -= qty
                if portfolio.positions[sym].quantity <= 0:
                    del portfolio.positions[sym]

    logger.info("Ledger replay complete: %d fills applied", len(fills))
    # Re-save to reflect replayed fills
    save_portfolio(portfolio)
    return portfolio


@dataclass
class AppState:
    """應用全局狀態。"""
    portfolio: Portfolio = field(default_factory=lambda: Portfolio(cash=Decimal("10000000")))
    oms: OrderManager = field(default_factory=OrderManager)
    risk_engine: RiskEngine = field(default_factory=_make_risk_engine)
    execution_service: ExecutionService = field(default_factory=ExecutionService)
    stop_order_manager: StopOrderManager = field(default_factory=StopOrderManager)
    strategies: dict[str, dict[str, Any]] = field(default_factory=dict)
    backtest_tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    alpha_tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Auto-alpha state
    auto_alpha_config: AutoAlphaConfig = field(default_factory=AutoAlphaConfig)
    alpha_store: AlphaStore = field(default_factory=AlphaStore)
    auto_alpha_running: bool = False
    # Realtime components (set during paper/live mode startup)
    realtime_risk_monitor: Any = None
    quote_manager: Any = None
    # 保護 portfolio mutation 的非同步鎖
    mutation_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    # 保護 backtest_tasks 跨執行緒存取
    backtest_lock: threading.Lock = field(default_factory=threading.Lock)
    # 保護 alpha_tasks 跨執行緒存取
    alpha_lock: threading.Lock = field(default_factory=threading.Lock)
    # D2: kill switch re-trigger guard
    kill_switch_fired: bool = False


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
