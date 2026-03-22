"""Backtest API routes."""

from __future__ import annotations

import uuid
import threading

from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import verify_api_key
from src.api.schemas import (
    BacktestRequest,
    BacktestResultResponse,
    BacktestSummaryResponse,
)
from src.api.state import get_app_state
from src.backtest.engine import BacktestConfig, BacktestEngine

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post("", response_model=BacktestSummaryResponse)
async def submit_backtest(req: BacktestRequest, api_key: str = Depends(verify_api_key)):
    """提交回測任務（異步執行）。"""
    state = get_app_state()
    task_id = uuid.uuid4().hex[:8]

    # 記錄任務
    state.backtest_tasks[task_id] = {
        "status": "running",
        "strategy_name": req.strategy,
        "result": None,
    }

    # 在背景執行緒執行回測
    def _run():
        try:
            strategy = _resolve_strategy(req.strategy, req.params)
            config = BacktestConfig(
                universe=req.universe,
                start=req.start,
                end=req.end,
                initial_cash=req.initial_cash,
                slippage_bps=req.slippage_bps,
                commission_rate=req.commission_rate,
                rebalance_freq=req.rebalance_freq,
            )
            engine = BacktestEngine()
            result = engine.run(strategy, config)
            state.backtest_tasks[task_id]["status"] = "completed"
            state.backtest_tasks[task_id]["result"] = result
        except Exception as e:
            state.backtest_tasks[task_id]["status"] = "failed"
            state.backtest_tasks[task_id]["error"] = str(e)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return BacktestSummaryResponse(
        task_id=task_id,
        status="running",
        strategy_name=req.strategy,
    )


@router.get("/{task_id}", response_model=BacktestSummaryResponse)
async def get_backtest_status(task_id: str, api_key: str = Depends(verify_api_key)):
    """查詢回測狀態。"""
    state = get_app_state()
    task = state.backtest_tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Backtest task not found")

    result = task.get("result")
    return BacktestSummaryResponse(
        task_id=task_id,
        status=task["status"],
        strategy_name=task["strategy_name"],
        total_return=result.total_return if result else None,
        annual_return=result.annual_return if result else None,
        sharpe=result.sharpe if result else None,
        max_drawdown=result.max_drawdown if result else None,
        total_trades=result.total_trades if result else None,
    )


@router.get("/{task_id}/result", response_model=BacktestResultResponse)
async def get_backtest_result(task_id: str, api_key: str = Depends(verify_api_key)):
    """取得完整回測結果。"""
    state = get_app_state()
    task = state.backtest_tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Backtest task not found")

    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Backtest status: {task['status']}")

    result = task["result"]
    nav_data = [
        {"date": str(date), "nav": float(nav)}
        for date, nav in result.nav_series.items()
    ]

    return BacktestResultResponse(
        strategy_name=result.strategy_name,
        start_date=result.start_date,
        end_date=result.end_date,
        initial_cash=result.initial_cash,
        total_return=result.total_return,
        annual_return=result.annual_return,
        sharpe=result.sharpe,
        sortino=result.sortino,
        calmar=result.calmar,
        max_drawdown=result.max_drawdown,
        max_drawdown_duration=result.max_drawdown_duration,
        volatility=result.volatility,
        total_trades=result.total_trades,
        win_rate=result.win_rate,
        total_commission=result.total_commission,
        nav_series=nav_data,
    )


def _resolve_strategy(name: str, params: dict):
    """根據名稱解析策略類別。"""
    from strategies.momentum import MomentumStrategy
    from strategies.mean_reversion import MeanReversionStrategy

    strategy_map = {
        "momentum": MomentumStrategy,
        "momentum_12_1": MomentumStrategy,
        "mean_reversion": MeanReversionStrategy,
    }

    cls = strategy_map.get(name)
    if cls is None:
        raise ValueError(f"Unknown strategy: {name}. Available: {list(strategy_map.keys())}")

    return cls(**params) if params else cls()
