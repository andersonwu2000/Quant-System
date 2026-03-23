"""Orders API routes."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query

from src.api.auth import verify_api_key, require_role
from src.api.schemas import ManualOrderRequest, OrderResponse
from src.api.state import get_app_state
from src.api.ws import ws_manager
from src.domain.models import Instrument, Order, OrderStatus, OrderType, Side

router = APIRouter(prefix="/orders", tags=["orders"])


def _to_response(o: Order) -> OrderResponse:
    return OrderResponse(
        id=o.id,
        symbol=o.instrument.symbol,
        side=o.side.value,
        quantity=float(o.quantity),
        price=float(o.price) if o.price else None,
        status=o.status.value,
        filled_qty=float(o.filled_qty),
        filled_avg_price=float(o.filled_avg_price),
        commission=float(o.commission),
        created_at=str(o.created_at),
        strategy_id=o.strategy_id,
    )


@router.get("", response_model=list[OrderResponse])
async def list_orders(
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    api_key: str = Depends(verify_api_key),
) -> list[OrderResponse]:
    """列出訂單（支援分頁）。"""
    state = get_app_state()
    orders = state.oms.get_all_orders()

    if status == "open":
        orders = [o for o in orders if not o.is_terminal]
    elif status == "filled":
        orders = [o for o in orders if o.status.value == "FILLED"]

    paginated = orders[offset:offset + limit]
    return [_to_response(o) for o in paginated]


@router.post("", response_model=OrderResponse)
async def create_order(
    req: ManualOrderRequest,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("trader")),
) -> OrderResponse:
    """手動下單。"""
    state = get_app_state()

    order = Order(
        instrument=Instrument(symbol=req.symbol.upper()),
        side=Side(req.side),
        order_type=OrderType.LIMIT if req.price is not None else OrderType.MARKET,
        quantity=Decimal(str(req.quantity)),
        price=Decimal(str(req.price)) if req.price is not None else None,
        strategy_id="manual",
    )

    # Run through risk engine before submitting
    decision = state.risk_engine.check_order(order, state.portfolio)
    if not decision.approved:
        order.status = OrderStatus.REJECTED
        order.reject_reason = decision.reason
    else:
        if decision.modified_qty is not None:
            order.quantity = decision.modified_qty
        state.oms.submit(order)

    response = _to_response(order)

    # Broadcast new order to "orders" WS channel (fire-and-forget)
    asyncio.create_task(ws_manager.broadcast("orders", response.model_dump()))

    return response
