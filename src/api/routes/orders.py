"""Orders API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.api.auth import verify_api_key
from src.api.schemas import OrderResponse
from src.api.state import get_app_state

router = APIRouter(prefix="/orders", tags=["orders"])


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

    return [
        OrderResponse(
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
        for o in paginated
    ]
