"""Execution & Paper Trading API routes."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.auth import verify_api_key, require_role

router = APIRouter(prefix="/execution", tags=["execution"])


# ── Schemas ───────────────────────────────────────────────


class ExecutionStatusResponse(BaseModel):
    mode: str
    connected: bool
    broker_type: str
    simulation: bool
    queued_orders: int


class ReconcileResponse(BaseModel):
    is_clean: bool
    matched: int
    mismatched: int
    system_only: int
    broker_only: int
    details: list[dict[str, Any]]
    summary: str


class MarketHoursResponse(BaseModel):
    session: str
    is_tradable: bool
    is_odd_lot: bool
    next_open: str


class PaperTradingStatusResponse(BaseModel):
    active: bool
    mode: str
    broker_connected: bool
    portfolio_nav: float
    open_orders: int
    queued_orders: int


# ── Endpoints ─────────────────────────────────────────────


@router.get("/status", response_model=ExecutionStatusResponse)
async def get_execution_status(
    api_key: str = Depends(verify_api_key),
) -> ExecutionStatusResponse:
    """查詢執行服務狀態。"""
    from src.api.state import get_app_state

    state = get_app_state()
    exec_svc = state.execution_service

    broker = exec_svc.broker
    connected = broker.is_connected() if broker else False
    broker_type = type(broker).__name__ if broker else "none"

    simulation = True
    if broker is not None:
        simulation = getattr(broker, "simulation", True)

    return ExecutionStatusResponse(
        mode=exec_svc.mode,
        connected=connected,
        broker_type=broker_type,
        simulation=simulation,
        queued_orders=exec_svc.order_queue.size,
    )


@router.get("/market-hours", response_model=MarketHoursResponse)
async def get_market_hours(
    api_key: str = Depends(verify_api_key),
) -> MarketHoursResponse:
    """查詢當前交易時段。"""
    from src.execution.market_hours import (
        get_current_session,
        is_odd_lot_session,
        is_tradable,
        next_open,
    )

    session = get_current_session()
    return MarketHoursResponse(
        session=session.value,
        is_tradable=is_tradable(),
        is_odd_lot=is_odd_lot_session(),
        next_open=next_open().isoformat(),
    )


@router.post("/reconcile", response_model=ReconcileResponse)
async def run_reconciliation(
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("trader")),
) -> ReconcileResponse:
    """執行 EOD 持倉對帳。"""
    from src.api.state import get_app_state
    from src.execution.reconcile import reconcile

    state = get_app_state()
    exec_svc = state.execution_service

    if exec_svc.broker is None:
        raise HTTPException(
            status_code=400,
            detail="Execution service not initialized or no broker connected",
        )

    broker_positions = exec_svc.broker.query_positions()
    result = reconcile(state.portfolio, broker_positions)

    details: list[dict[str, Any]] = []
    for diff_list in [result.mismatched, result.system_only, result.broker_only]:
        for d in diff_list:
            details.append({
                "symbol": d.symbol,
                "system_qty": float(d.system_qty),
                "broker_qty": float(d.broker_qty),
                "diff_qty": float(d.diff_qty),
                "diff_pct": d.diff_pct,
            })

    return ReconcileResponse(
        is_clean=result.is_clean,
        matched=len(result.matched),
        mismatched=len(result.mismatched),
        system_only=len(result.system_only),
        broker_only=len(result.broker_only),
        details=details,
        summary=result.summary(),
    )


@router.post("/reconcile/auto-correct")
async def auto_correct_positions(
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("risk_manager")),
) -> dict[str, Any]:
    """根據券商端持倉自動修正系統持倉（需 risk_manager 權限）。"""
    from src.api.state import get_app_state
    from src.execution.reconcile import auto_correct, reconcile

    state = get_app_state()
    exec_svc = state.execution_service

    if exec_svc.broker is None:
        raise HTTPException(
            status_code=400,
            detail="Execution service not initialized or no broker connected",
        )

    broker_positions = exec_svc.broker.query_positions()
    result = reconcile(state.portfolio, broker_positions)

    async with state.mutation_lock:
        corrections = auto_correct(state.portfolio, result, trust_broker=True)

    return {
        "corrections": corrections,
        "count": len(corrections),
    }


@router.get("/paper-trading/status", response_model=PaperTradingStatusResponse)
async def paper_trading_status(
    api_key: str = Depends(verify_api_key),
) -> PaperTradingStatusResponse:
    """查詢 Paper Trading 狀態。"""
    from src.api.state import get_app_state

    state = get_app_state()
    exec_svc = state.execution_service

    active = exec_svc.is_initialized and exec_svc.mode in ("paper", "live")

    broker_connected = False
    if exec_svc.broker:
        broker_connected = exec_svc.broker.is_connected()

    return PaperTradingStatusResponse(
        active=active,
        mode=exec_svc.mode,
        broker_connected=broker_connected,
        portfolio_nav=float(state.portfolio.nav),
        open_orders=len(state.oms.get_open_orders()),
        queued_orders=exec_svc.order_queue.size,
    )


@router.get("/queued-orders")
async def list_queued_orders(
    api_key: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """查詢盤外佇列中的待處理訂單。"""
    from src.api.state import get_app_state

    state = get_app_state()
    exec_svc = state.execution_service

    pending = exec_svc.order_queue.pending_orders
    items: list[dict[str, str]] = []
    for o in pending:
        order_obj = o.get("order")
        symbol = (
            order_obj.instrument.symbol
            if order_obj is not None and hasattr(order_obj, "instrument")
            else "unknown"
        )
        items.append({"symbol": symbol, "timestamp": o.get("timestamp", "")})
    return {"orders": items, "count": len(pending)}


# ── Trading Limits & Settlements ──────────────────────────


@router.get("/trading-limits")
async def get_trading_limits(
    api_key: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """查詢交易額度（可用額度/融資/融券）。"""
    from src.api.state import get_app_state

    state = get_app_state()
    exec_svc = state.execution_service
    if exec_svc.broker is None or not exec_svc.broker.is_connected():
        raise HTTPException(status_code=503, detail="Broker not connected")

    from src.execution.broker.sinopac import SinopacBroker

    if not isinstance(exec_svc.broker, SinopacBroker):
        raise HTTPException(status_code=400, detail="Trading limits only available for SinopacBroker")

    return exec_svc.broker.query_trading_limits()


@router.get("/settlements")
async def get_settlements(
    api_key: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """查詢交割資訊（T+N 金額/日期）。"""
    from src.api.state import get_app_state

    state = get_app_state()
    exec_svc = state.execution_service
    if exec_svc.broker is None or not exec_svc.broker.is_connected():
        raise HTTPException(status_code=503, detail="Broker not connected")

    from src.execution.broker.sinopac import SinopacBroker

    if not isinstance(exec_svc.broker, SinopacBroker):
        raise HTTPException(status_code=400, detail="Settlements only available for SinopacBroker")

    settlements = exec_svc.broker.query_settlements()
    return {"settlements": settlements, "count": len(settlements)}


@router.get("/dispositions")
async def get_dispositions(
    api_key: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """查詢處置股清單（受交易限制的標的）。"""
    from src.api.state import get_app_state

    state = get_app_state()
    exec_svc = state.execution_service
    if exec_svc.broker is None or not exec_svc.broker.is_connected():
        raise HTTPException(status_code=503, detail="Broker not connected")

    from src.execution.broker.sinopac import SinopacBroker

    if not isinstance(exec_svc.broker, SinopacBroker):
        return {"codes": [], "count": 0}

    codes = exec_svc.broker.check_dispositions()
    return {"codes": sorted(codes), "count": len(codes)}


# ── Stop Orders ───────────────────────────────────────────


class StopOrderRequest(BaseModel):
    symbol: str
    stop_price: float
    direction: str = "below"  # "below" (stop-loss) or "above" (buy-stop)
    side: str = "SELL"
    quantity: float
    order_price: float | None = None


class StopOrderResponse(BaseModel):
    symbol: str
    stop_price: float
    direction: str
    executed: bool
    created_at: str


@router.get("/stop-orders")
async def list_stop_orders(
    api_key: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """列出所有觸價委託（pending + executed）。"""
    from src.api.state import get_app_state

    state = get_app_state()
    mgr = state.stop_order_manager

    pending = [
        StopOrderResponse(
            symbol=s.symbol, stop_price=float(s.stop_price),
            direction=s.direction, executed=s.executed,
            created_at=s.created_at.isoformat(),
        ).model_dump()
        for s in mgr.get_pending()
    ]
    executed = [
        StopOrderResponse(
            symbol=s.symbol, stop_price=float(s.stop_price),
            direction=s.direction, executed=s.executed,
            created_at=s.created_at.isoformat(),
        ).model_dump()
        for s in mgr.get_executed()
    ]
    return {
        "pending": pending,
        "executed": executed,
        "pending_count": len(pending),
        "executed_count": len(executed),
    }


@router.post("/stop-orders")
async def create_stop_order(
    req: StopOrderRequest,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("trader")),
) -> dict[str, Any]:
    """新增觸價委託。"""
    from src.api.state import get_app_state
    from src.core.models import Instrument, Order, OrderType, Side

    state = get_app_state()
    mgr = state.stop_order_manager

    order = Order(
        instrument=Instrument(symbol=req.symbol.upper()),
        side=Side(req.side.upper()),
        order_type=OrderType.LIMIT if req.order_price else OrderType.MARKET,
        quantity=Decimal(str(req.quantity)),
        price=Decimal(str(req.order_price)) if req.order_price else None,
        strategy_id="stop_order",
    )

    stop = mgr.add(
        symbol=req.symbol.upper(),
        stop_price=Decimal(str(req.stop_price)),
        order=order,
        direction=req.direction,
    )

    return {
        "symbol": stop.symbol,
        "stop_price": float(stop.stop_price),
        "direction": stop.direction,
        "created_at": stop.created_at.isoformat(),
    }


@router.delete("/stop-orders/{symbol}")
async def cancel_stop_orders(
    symbol: str,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("trader")),
) -> dict[str, Any]:
    """取消指定標的的所有觸價委託。"""
    from src.api.state import get_app_state

    state = get_app_state()
    count = state.stop_order_manager.cancel(symbol.upper())
    return {"cancelled": count, "symbol": symbol.upper()}


@router.delete("/stop-orders")
async def cancel_all_stop_orders(
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("trader")),
) -> dict[str, Any]:
    """取消所有觸價委託。"""
    from src.api.state import get_app_state

    state = get_app_state()
    count = state.stop_order_manager.cancel_all()
    return {"cancelled": count}
