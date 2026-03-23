"""Backtest API routes."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, cast, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.api.auth import verify_api_key, require_role
from src.api.schemas import (
    BacktestHistoryItem,
    BacktestHistoryResponse,
    BacktestRequest,
    BacktestResultResponse,
    BacktestSummaryResponse,
    TradeRecordResponse,
)
from src.api.state import get_app_state
from src.backtest.engine import BacktestConfig, BacktestEngine
from src.data.store import DataStore
from src.strategy.registry import resolve_strategy
from src.config import get_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/backtest", tags=["backtest"])
_limiter = Limiter(key_func=get_remote_address)
_MAX_BACKTEST_TASKS = 50  # evict oldest tasks beyond this limit
_background_tasks: set[asyncio.Task[None]] = set()  # prevent GC of fire-and-forget tasks


@router.post("", response_model=BacktestSummaryResponse)
@_limiter.limit("10/minute")
async def submit_backtest(request: Request, req: BacktestRequest, api_key: str = Depends(verify_api_key), _role: dict[str, Any] = Depends(require_role("researcher"))) -> BacktestSummaryResponse:
    """提交回測任務（異步執行）。"""
    state = get_app_state()
    config = get_config()
    task_id = uuid.uuid4().hex[:8]

    # 記錄任務
    state.backtest_tasks[task_id] = {
        "status": "running",
        "strategy_name": req.strategy,
        "result": None,
        "progress": None,
    }

    def _run() -> None:
        try:
            strategy = resolve_strategy(req.strategy, req.params)
            bt_config = BacktestConfig(
                universe=req.universe,
                start=req.start,
                end=req.end,
                initial_cash=req.initial_cash,
                slippage_bps=req.slippage_bps,
                commission_rate=req.commission_rate,
                rebalance_freq=cast(Literal["daily", "weekly", "monthly"], req.rebalance_freq),
            )

            def progress_cb(current: int, total: int) -> None:
                with state.backtest_lock:
                    state.backtest_tasks[task_id]["progress"] = {
                        "current": current,
                        "total": total,
                    }

            engine = BacktestEngine()
            result = engine.run(strategy, bt_config, progress_callback=progress_cb)
            with state.backtest_lock:
                state.backtest_tasks[task_id]["status"] = "completed"
                state.backtest_tasks[task_id]["result"] = result

            # 持久化至 SQLite
            try:
                store = DataStore()
                store.save_backtest_result(
                    result_id=task_id,
                    strategy_name=req.strategy,
                    config={
                        "universe": req.universe,
                        "start": req.start,
                        "end": req.end,
                        "initial_cash": req.initial_cash,
                        "rebalance_freq": req.rebalance_freq,
                    },
                    sharpe=result.sharpe,
                    max_drawdown=result.max_drawdown,
                    total_return=result.total_return,
                    annual_return=result.annual_return,
                    detail={
                        "sortino": result.sortino,
                        "calmar": result.calmar,
                        "volatility": result.volatility,
                        "total_trades": result.total_trades,
                        "win_rate": result.win_rate,
                        "total_commission": result.total_commission,
                    },
                )
            except Exception:
                logger.debug("Failed to persist backtest result %s", task_id, exc_info=True)
        except Exception as e:
            logger.exception("Backtest %s failed", task_id)
            with state.backtest_lock:
                state.backtest_tasks[task_id]["status"] = "failed"
                state.backtest_tasks[task_id]["error"] = str(e)

    # 在背景執行，設定超時
    async def _run_with_timeout() -> None:
        try:
            await asyncio.wait_for(
                asyncio.to_thread(_run),
                timeout=config.backtest_timeout,
            )
        except asyncio.TimeoutError:
            with state.backtest_lock:
                state.backtest_tasks[task_id]["status"] = "failed"
                state.backtest_tasks[task_id]["error"] = (
                    f"Backtest timed out after {config.backtest_timeout}s"
                )

    # Evict oldest completed/failed tasks if over limit
    if len(state.backtest_tasks) >= _MAX_BACKTEST_TASKS:
        to_remove = [
            tid for tid, t in state.backtest_tasks.items()
            if t["status"] in ("completed", "failed")
        ]
        # Remove half of completed tasks, or all if needed
        remove_count = max(1, len(state.backtest_tasks) - _MAX_BACKTEST_TASKS + 1)
        for tid in to_remove[:remove_count]:
            del state.backtest_tasks[tid]
        # If still at capacity (all running), reject
        if len(state.backtest_tasks) >= _MAX_BACKTEST_TASKS:
            raise HTTPException(
                status_code=429,
                detail=f"Too many concurrent backtests (max {_MAX_BACKTEST_TASKS})",
            )

    task = asyncio.create_task(_run_with_timeout())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return BacktestSummaryResponse(
        task_id=task_id,
        status="running",
        strategy_name=req.strategy,
    )


@router.get("/history", response_model=BacktestHistoryResponse)
async def get_backtest_history(
    strategy: str | None = None,
    limit: int = 50,
    api_key: str = Depends(verify_api_key),
) -> BacktestHistoryResponse:
    """查詢歷史回測記錄（從 SQLite 讀取）。"""
    store = DataStore()
    rows = store.load_backtest_history(strategy_name=strategy, limit=min(limit, 200))
    items = [BacktestHistoryItem(**r) for r in rows]
    return BacktestHistoryResponse(items=items)


@router.get("/{task_id}", response_model=BacktestSummaryResponse)
async def get_backtest_status(task_id: str, api_key: str = Depends(verify_api_key)) -> BacktestSummaryResponse:
    """查詢回測狀態。"""
    state = get_app_state()
    task = state.backtest_tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Backtest task not found")

    result = task.get("result")
    progress = task.get("progress")
    return BacktestSummaryResponse(
        task_id=task_id,
        status=task["status"],
        strategy_name=task["strategy_name"],
        total_return=result.total_return if result else None,
        annual_return=result.annual_return if result else None,
        sharpe=result.sharpe if result else None,
        max_drawdown=result.max_drawdown if result else None,
        total_trades=result.total_trades if result else None,
        progress_current=progress["current"] if progress else None,
        progress_total=progress["total"] if progress else None,
        error=task.get("error"),
    )


@router.get("/{task_id}/result", response_model=BacktestResultResponse)
async def get_backtest_result(task_id: str, api_key: str = Depends(verify_api_key)) -> BacktestResultResponse:
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

    _MAX_TRADES = 10_000
    trade_data = [
        TradeRecordResponse(
            date=str(t.timestamp),
            symbol=t.symbol,
            side=t.side.value,
            quantity=float(t.quantity),
            price=float(t.price),
            commission=float(t.commission),
        )
        for t in result.trades[:_MAX_TRADES]
    ] if result.trades else None

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
        trades=trade_data,
    )


