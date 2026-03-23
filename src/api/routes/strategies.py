"""Strategy management API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import verify_api_key
from src.api.schemas import StrategyInfo, StrategyListResponse
from src.api.state import get_app_state

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("", response_model=StrategyListResponse)
async def list_strategies(api_key: str = Depends(verify_api_key)) -> StrategyListResponse:
    """列出所有已註冊策略。"""
    state = get_app_state()
    strategies = []
    for name, info in state.strategies.items():
        strategies.append(StrategyInfo(
            name=name,
            status=info.get("status", "stopped"),
            pnl=info.get("pnl", 0.0),
        ))
    return StrategyListResponse(strategies=strategies)


@router.get("/{strategy_id}", response_model=StrategyInfo)
async def get_strategy(strategy_id: str, api_key: str = Depends(verify_api_key)) -> StrategyInfo:
    """取得單一策略詳情。"""
    state = get_app_state()
    info = state.strategies.get(strategy_id)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
    return StrategyInfo(
        name=strategy_id,
        status=info.get("status", "stopped"),
        pnl=info.get("pnl", 0.0),
    )


@router.post("/{strategy_id}/start")
async def start_strategy(strategy_id: str, api_key: str = Depends(verify_api_key)) -> dict[str, str]:
    """啟動策略。"""
    state = get_app_state()
    if strategy_id not in state.strategies:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
    state.strategies[strategy_id]["status"] = "running"
    return {"message": f"Strategy {strategy_id} started"}


@router.post("/{strategy_id}/stop")
async def stop_strategy(strategy_id: str, api_key: str = Depends(verify_api_key)) -> dict[str, str]:
    """停止策略。"""
    state = get_app_state()
    if strategy_id not in state.strategies:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
    state.strategies[strategy_id]["status"] = "stopped"
    return {"message": f"Strategy {strategy_id} stopped"}
