"""Backtest API routes."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from typing import Any, cast, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from prometheus_client import Histogram
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
    WalkForwardFoldResponse,
    WalkForwardRequest,
    WalkForwardResultResponse,
)
from src.api.state import get_app_state
from src.backtest.engine import BacktestCancelled, BacktestConfig, BacktestEngine
from src.backtest.walk_forward import WalkForwardAnalyzer, WFAConfig
from src.data.store import DataStore
from src.strategy.registry import resolve_strategy
from src.config import get_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/backtest", tags=["backtest"])

BACKTEST_DURATION = Histogram(
    "backtest_duration_seconds",
    "Time spent running a backtest",
    labelnames=["strategy"],
)
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

    cancel_event = threading.Event()

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
            start_time = time.monotonic()
            result = engine.run(strategy, bt_config, progress_callback=progress_cb, cancel_event=cancel_event)
            duration = time.monotonic() - start_time
            BACKTEST_DURATION.labels(strategy=req.strategy).observe(duration)
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
        except BacktestCancelled:
            logger.info("Backtest %s cancelled by timeout", task_id)
            with state.backtest_lock:
                state.backtest_tasks[task_id]["status"] = "failed"
                state.backtest_tasks[task_id]["error"] = (
                    f"Backtest timed out after {config.backtest_timeout}s"
                )
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
            # 通知執行緒停止：設定 cancel_event，執行緒在下一個 bar 會檢查並退出
            cancel_event.set()
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
            quantity=int(t.quantity),
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


@router.post("/walk-forward", response_model=WalkForwardResultResponse)
@_limiter.limit("5/minute")
async def submit_walk_forward(
    request: Request,
    req: WalkForwardRequest,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("researcher")),
) -> WalkForwardResultResponse:
    """提交 Walk-Forward Analysis（同步執行於背景線程）。"""
    config = get_config()
    wf_cancel_event = threading.Event()

    def _run() -> WalkForwardResultResponse:
        wfa_config = WFAConfig(
            train_days=req.train_days,
            test_days=req.test_days,
            step_days=req.step_days,
            universe=req.universe,
            initial_cash=req.initial_cash,
        )

        analyzer = WalkForwardAnalyzer()
        result = analyzer.run(
            strategy_name=req.strategy,
            universe=req.universe,
            start=req.start,
            end=req.end,
            config=wfa_config,
            param_grid=req.param_grid,
            cancel_event=wf_cancel_event,
        )

        fold_responses = [
            WalkForwardFoldResponse(
                fold_index=f.fold_index,
                train_start=f.train_start,
                train_end=f.train_end,
                test_start=f.test_start,
                test_end=f.test_end,
                train_sharpe=f.train_sharpe,
                test_sharpe=f.test_sharpe,
                test_total_return=f.test_total_return,
                best_params=f.best_params,
            )
            for f in result.folds
        ]

        return WalkForwardResultResponse(
            folds=fold_responses,
            oos_total_return=result.oos_total_return,
            oos_sharpe=result.oos_sharpe,
            oos_max_drawdown=result.oos_max_drawdown,
            param_stability=result.param_stability,
        )

    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(_run),
            timeout=config.backtest_timeout,
        )
    except asyncio.TimeoutError:
        # 通知執行緒停止
        wf_cancel_event.set()
        raise HTTPException(
            status_code=504,
            detail=f"Walk-forward analysis timed out after {config.backtest_timeout}s",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return response


