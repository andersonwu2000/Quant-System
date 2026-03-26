"""Alpha Research API routes."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.api.auth import verify_api_key, require_role
from src.api.state import get_app_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/alpha", tags=["alpha"])
_limiter = Limiter(key_func=get_remote_address)
_background_tasks: set[asyncio.Future[None]] = set()


# ── Request / Response schemas ───────────────────────────────────


class AlphaFactorSpec(BaseModel):
    name: str
    direction: int = 1


class AlphaRunRequest(BaseModel):
    factors: list[AlphaFactorSpec]
    universe: list[str]
    start: str
    end: str
    neutralize_method: str = "market"
    n_quantiles: int = Field(default=5, ge=3, le=10)
    holding_period: int = Field(default=5, ge=1, le=60)
    # 多資產支援 — 可選參數
    min_listing_days: int = Field(default=60, ge=0)
    min_avg_volume: float | None = None
    asset_classes: list[str] = Field(default_factory=list)


class AlphaSummaryResponse(BaseModel):
    task_id: str
    status: str
    progress_current: int | None = None
    progress_total: int | None = None
    error: str | None = None


# ── Endpoints ────────────────────────────────────────────────────


@router.post("", response_model=AlphaSummaryResponse)
@_limiter.limit("5/minute")
async def submit_alpha_research(
    request: Request,
    req: AlphaRunRequest,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("researcher")),
) -> AlphaSummaryResponse:
    """提交 Alpha 研究任務（異步執行）。"""
    state = get_app_state()
    task_id = uuid.uuid4().hex[:8]

    state.alpha_tasks[task_id] = {
        "status": "running",
        "result": None,
        "progress_current": None,
        "progress_total": None,
        "error": None,
    }

    def _run() -> None:
        try:
            from src.alpha.pipeline import AlphaConfig, AlphaPipeline, FactorSpec
            from src.alpha.universe import UniverseConfig
            from src.alpha.construction import ConstructionConfig
            from src.alpha.neutralize import NeutralizeMethod
            from src.data.sources import create_feed
            from src.core.config import get_config

            config = get_config()

            # 建立因子規格
            factor_specs = [
                FactorSpec(name=f.name, direction=f.direction)
                for f in req.factors
            ]

            # 中性化方法
            method_map = {
                "market": NeutralizeMethod.MARKET,
                "industry": NeutralizeMethod.INDUSTRY,
                "size": NeutralizeMethod.SIZE,
                "industry_size": NeutralizeMethod.INDUSTRY_SIZE,
                "ind_size": NeutralizeMethod.INDUSTRY_SIZE,
            }
            neutralize = method_map.get(req.neutralize_method, NeutralizeMethod.MARKET)

            alpha_config = AlphaConfig(
                universe=UniverseConfig(
                    min_listing_days=req.min_listing_days,
                    min_avg_volume=req.min_avg_volume,
                    asset_classes=req.asset_classes,
                ),
                factors=factor_specs,
                neutralize_method=neutralize,
                n_quantiles=req.n_quantiles,
                holding_period=req.holding_period,
                construction=ConstructionConfig(
                    cost_bps=config.commission_rate * 10000 + config.tax_rate * 10000,
                ),
            )

            pipeline = AlphaPipeline(alpha_config)

            # 設定進度：下載 N 標的 + 研究分析 1 步
            total_steps = len(req.universe) + 1
            current_step = 0

            def update_progress(step: int) -> None:
                nonlocal current_step
                current_step = step
                state.alpha_tasks[task_id]["progress_current"] = current_step
                state.alpha_tasks[task_id]["progress_total"] = total_steps

            update_progress(0)

            # 平行下載數據（用 ThreadPoolExecutor 加速）
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import pandas as pd

            feed = create_feed(
                source=config.data_source,
                universe=req.universe,
                token=config.finmind_token if config.data_source == "finmind" else "",
            )

            data: dict[str, Any] = {}
            done_count = 0

            def _fetch(symbol: str) -> tuple[str, pd.DataFrame | None]:
                try:
                    bars = feed.get_bars(symbol, start=req.start, end=req.end)
                    return (symbol, bars if not bars.empty else None)
                except Exception:
                    logger.debug("Failed to fetch %s", symbol, exc_info=True)
                    return (symbol, None)

            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = {pool.submit(_fetch, sym): sym for sym in req.universe}
                for future in as_completed(futures, timeout=120):
                    try:
                        sym, bars = future.result(timeout=60)
                    except Exception:
                        done_count += 1
                        update_progress(done_count)
                        continue
                    if bars is not None:
                        data[sym] = bars
                    done_count += 1
                    update_progress(done_count)

            if not data:
                state.alpha_tasks[task_id]["status"] = "failed"
                state.alpha_tasks[task_id]["error"] = "No data available for the given universe and date range"
                return

            update_progress(len(req.universe))

            # 執行研究
            report = pipeline.research(data)

            update_progress(total_steps)

            # 轉換為前端需要的格式
            result = _format_report(report, task_id, req)

            state.alpha_tasks[task_id]["status"] = "completed"
            state.alpha_tasks[task_id]["result"] = result

        except Exception as e:
            logger.error("Alpha research failed: %s", e, exc_info=True)
            state.alpha_tasks[task_id]["status"] = "failed"
            state.alpha_tasks[task_id]["error"] = str(e)

    # 在背景線程執行
    loop = asyncio.get_event_loop()
    task = asyncio.ensure_future(loop.run_in_executor(None, _run))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return AlphaSummaryResponse(task_id=task_id, status="running")


@router.get("/{task_id}", response_model=AlphaSummaryResponse)
async def get_alpha_status(
    task_id: str,
    api_key: str = Depends(verify_api_key),
) -> AlphaSummaryResponse:
    """查詢 Alpha 研究任務狀態。"""
    state = get_app_state()
    task = state.alpha_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return AlphaSummaryResponse(
        task_id=task_id,
        status=task["status"],
        progress_current=task.get("progress_current"),
        progress_total=task.get("progress_total"),
        error=task.get("error"),
    )


@router.get("/{task_id}/result")
async def get_alpha_result(
    task_id: str,
    api_key: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """取得 Alpha 研究完整結果。"""
    state = get_app_state()
    task = state.alpha_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Task is {task['status']}, not completed")
    if not task.get("result"):
        raise HTTPException(status_code=500, detail="Result missing")
    result: dict[str, Any] = task["result"]
    return result


# ── 格式轉換 ─────────────────────────────────────────────────


def _format_report(report: Any, task_id: str, req: AlphaRunRequest) -> dict[str, Any]:
    """將 AlphaReport 轉為前端 AlphaReport 介面格式。"""
    from src.alpha.pipeline import AlphaReport as PipelineReport

    rpt: PipelineReport = report
    factors_out: list[dict[str, Any]] = []

    for spec in req.factors:
        name = spec.name
        ic = rpt.factor_ics.get(name)
        to = rpt.factor_turnovers.get(name)
        qr = rpt.quantile_results.get(name)

        ic_out: dict[str, Any] = {"ic_mean": 0, "ic_std": 0, "icir": 0, "hit_rate": 0}
        ic_series: list[dict[str, Any]] = []
        if ic:
            ic_out = {
                "ic_mean": ic.ic_mean,
                "ic_std": ic.ic_std,
                "icir": ic.icir,
                "hit_rate": ic.hit_rate,
            }
            if hasattr(ic, "ic_series") and not ic.ic_series.empty:
                ic_series = [
                    {"date": str(d.date()) if hasattr(d, "date") else str(d), "ic": float(v)}
                    for d, v in ic.ic_series.items()
                ]
            ic_out["ic_series"] = ic_series

        to_out = {"avg_turnover": 0.0, "cost_drag_annual_bps": 0.0, "breakeven_cost_bps": 0.0}
        if to:
            to_out = {
                "avg_turnover": to.avg_turnover,
                "cost_drag_annual_bps": to.cost_drag_annual_bps,
                "breakeven_cost_bps": to.breakeven_cost_bps,
            }

        q_out: list[dict[str, Any]] = []
        ls_sharpe = 0.0
        mono = 0.0
        if qr:
            ls_sharpe = qr.long_short_sharpe
            mono = qr.monotonicity_score
            for qi in range(qr.n_quantiles):
                label = f"Q{qi + 1}"
                mean_ret = float(qr.mean_returns.get(label, 0.0)) if hasattr(qr.mean_returns, "get") else 0.0
                q_out.append({
                    "quantile": qi + 1,
                    "mean_return": mean_ret,
                    "annual_return": mean_ret,
                })

        factors_out.append({
            "name": name,
            "direction": spec.direction,
            "ic": ic_out,
            "turnover": to_out,
            "quantile_returns": q_out,
            "long_short_sharpe": ls_sharpe,
            "monotonicity_score": mono,
        })

    # Composite
    composite_ic_out = None
    if rpt.composite_ic:
        composite_ic_out = {
            "ic_mean": rpt.composite_ic.ic_mean,
            "ic_std": rpt.composite_ic.ic_std,
            "icir": rpt.composite_ic.icir,
            "hit_rate": rpt.composite_ic.hit_rate,
        }

    composite_q_out = None
    composite_ls_sharpe = None
    if rpt.composite_quantile:
        composite_ls_sharpe = rpt.composite_quantile.long_short_sharpe
        composite_q_out = []
        for qi in range(rpt.composite_quantile.n_quantiles):
            label = f"Q{qi + 1}"
            mean_ret = float(rpt.composite_quantile.mean_returns.get(label, 0.0)) if hasattr(rpt.composite_quantile.mean_returns, "get") else 0.0
            composite_q_out.append({
                "quantile": qi + 1,
                "mean_return": mean_ret,
                "annual_return": mean_ret,
            })

    return {
        "task_id": task_id,
        "factors": factors_out,
        "composite_ic": composite_ic_out,
        "composite_long_short_sharpe": composite_ls_sharpe,
        "composite_quantile_returns": composite_q_out,
        "universe_size": rpt.universe_counts.get("avg", 0),
        "start_date": req.start,
        "end_date": req.end,
    }
