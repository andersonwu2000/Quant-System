"""Portfolio API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.auth import verify_api_key
from src.api.schemas import PortfolioResponse, PositionResponse
from src.api.state import get_app_state

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioResponse)
async def get_portfolio(api_key: str = Depends(verify_api_key)) -> PortfolioResponse:
    """取得當前投資組合。"""
    state = get_app_state()
    portfolio = state.portfolio

    positions = []
    for symbol, pos in portfolio.positions.items():
        nav = portfolio.nav
        weight = float(pos.market_value / nav) if nav > 0 else 0
        positions.append(PositionResponse(
            symbol=symbol,
            quantity=float(pos.quantity),
            avg_cost=float(pos.avg_cost),
            market_price=float(pos.market_price),
            market_value=float(pos.market_value),
            unrealized_pnl=float(pos.unrealized_pnl),
            weight=weight,
        ))

    nav_float = float(portfolio.nav)
    daily_pnl = float(portfolio.daily_pnl)

    return PortfolioResponse(
        nav=nav_float,
        cash=float(portfolio.cash),
        gross_exposure=float(portfolio.gross_exposure),
        net_exposure=float(portfolio.net_exposure),
        positions_count=len(portfolio.positions),
        daily_pnl=daily_pnl,
        daily_pnl_pct=daily_pnl / nav_float if nav_float > 0 else 0.0,
        positions=positions,
        as_of=str(portfolio.as_of),
    )


@router.get("/positions", response_model=list[PositionResponse])
async def get_positions(api_key: str = Depends(verify_api_key)) -> list[PositionResponse]:
    """取得所有持倉明細。"""
    state = get_app_state()
    portfolio = state.portfolio
    nav = portfolio.nav

    return [
        PositionResponse(
            symbol=symbol,
            quantity=float(pos.quantity),
            avg_cost=float(pos.avg_cost),
            market_price=float(pos.market_price),
            market_value=float(pos.market_value),
            unrealized_pnl=float(pos.unrealized_pnl),
            weight=float(pos.market_value / nav) if nav > 0 else 0,
        )
        for symbol, pos in portfolio.positions.items()
    ]
