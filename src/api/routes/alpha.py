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

    with state.alpha_lock:
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
                with state.alpha_lock:
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
                with state.alpha_lock:
                    state.alpha_tasks[task_id]["status"] = "failed"
                    state.alpha_tasks[task_id]["error"] = "No data available for the given universe and date range"
                return

            update_progress(len(req.universe))

            # 執行研究
            report = pipeline.research(data)

            update_progress(total_steps)

            # 轉換為前端需要的格式
            result = _format_report(report, task_id, req)

            with state.alpha_lock:
                state.alpha_tasks[task_id]["status"] = "completed"
                state.alpha_tasks[task_id]["result"] = result

        except Exception as e:
            logger.error("Alpha research failed: %s", e, exc_info=True)
            with state.alpha_lock:
                state.alpha_tasks[task_id]["status"] = "failed"
                state.alpha_tasks[task_id]["error"] = str(e)

    # 在背景線程執行
    loop = asyncio.get_running_loop()
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


# ── Regime Classification ──────────────────────────────────────

class RegimeResponse(BaseModel):
    regime: str
    regime_series: dict[str, str] | None = None  # date -> regime


@router.get("/regime", response_model=RegimeResponse)
async def get_market_regime(
    symbol: str = "0050.TW",
    lookback: int = 60,
    api_key: str = Depends(verify_api_key),
) -> RegimeResponse:
    """Get current market regime classification."""
    try:
        from src.alpha.regime import classify_regimes
        from src.data.sources.yahoo import YahooFeed

        feed = YahooFeed()
        bars = feed.get_bars(symbol)
        if bars.empty:
            raise HTTPException(status_code=404, detail=f"No data for {symbol}")

        returns = bars["close"].pct_change().dropna()
        regimes = classify_regimes(returns)
        current = str(regimes.iloc[-1]) if not regimes.empty else "unknown"

        # Last 20 regime values
        recent = {str(d.date()) if hasattr(d, 'date') else str(d): str(v) for d, v in regimes.tail(20).items()}

        return RegimeResponse(regime=current, regime_series=recent)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Turnover Analysis ──────────────────────────────────────────

class TurnoverRequest(BaseModel):
    symbols: list[str]
    factor_name: str
    start: str
    end: str
    n_quantiles: int = 5
    holding_period: int = 5
    cost_bps: float = 30.0


class TurnoverResponse(BaseModel):
    factor_name: str
    avg_turnover: float
    cost_drag_annual_bps: float
    net_alpha_bps: float


@router.post("/turnover-analysis", response_model=TurnoverResponse)
async def analyze_turnover(
    req: TurnoverRequest,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("researcher")),
) -> TurnoverResponse:
    """Analyze factor turnover and cost drag."""
    try:
        from src.alpha.turnover import analyze_factor_turnover
        from src.strategy.research import compute_factor_values, compute_forward_returns, compute_ic
        from src.data.sources.yahoo import YahooFeed

        feed = YahooFeed(universe=req.symbols)
        data = {}
        for sym in req.symbols:
            bars = feed.get_bars(sym, start=req.start, end=req.end)
            if not bars.empty:
                data[sym] = bars

        fv = compute_factor_values(data, req.factor_name)
        fwd = compute_forward_returns(data, horizon=req.holding_period)
        ic = compute_ic(fv, fwd)

        result = analyze_factor_turnover(
            fv, n_quantiles=req.n_quantiles, holding_period=req.holding_period,
            cost_bps=req.cost_bps, gross_ic=ic.ic_mean, factor_name=req.factor_name,
        )

        return TurnoverResponse(
            factor_name=req.factor_name,
            avg_turnover=result.avg_turnover,
            cost_drag_annual_bps=result.cost_drag_annual_bps,
            net_alpha_bps=abs(ic.ic_mean) * 10000 - result.cost_drag_annual_bps,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── IC Analysis ────────────────────────────────────────────────

class ICAnalysisRequest(BaseModel):
    symbols: list[str]
    factor_name: str
    start: str
    end: str
    horizon: int = 5


class ICAnalysisResponse(BaseModel):
    factor_name: str
    ic_mean: float
    icir: float
    hit_rate: float
    ic_std: float


@router.post("/ic-analysis", response_model=ICAnalysisResponse)
async def compute_ic_analysis(
    req: ICAnalysisRequest,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("researcher")),
) -> ICAnalysisResponse:
    """Compute IC/ICIR for a factor."""
    try:
        from src.strategy.research import compute_factor_values, compute_forward_returns, compute_ic
        from src.data.sources.yahoo import YahooFeed

        feed = YahooFeed(universe=req.symbols)
        data = {}
        for sym in req.symbols:
            bars = feed.get_bars(sym, start=req.start, end=req.end)
            if not bars.empty:
                data[sym] = bars

        fv = compute_factor_values(data, req.factor_name)
        fwd = compute_forward_returns(data, horizon=req.horizon)
        ic = compute_ic(fv, fwd)

        return ICAnalysisResponse(
            factor_name=req.factor_name,
            ic_mean=ic.ic_mean,
            icir=ic.icir,
            hit_rate=ic.hit_rate,
            ic_std=ic.ic_std,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Attribution ────────────────────────────────────────────────

class AttributionRequest(BaseModel):
    composite_returns: dict[str, float]  # date -> return
    factor_returns: dict[str, dict[str, float]]  # factor_name -> {date -> return}
    composite_weights: dict[str, float]  # factor_name -> weight
    method: str = "weight_based"


class AttributionResponse(BaseModel):
    total_return: float
    factor_contributions: dict[str, float]
    residual_return: float


@router.post("/attribution", response_model=AttributionResponse)
async def compute_attribution(
    req: AttributionRequest,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("researcher")),
) -> AttributionResponse:
    """Decompose returns into factor contributions."""
    try:
        import pandas as pd
        from src.alpha.attribution import attribute_returns

        comp = pd.Series(req.composite_returns, dtype=float)
        comp.index = pd.to_datetime(comp.index)

        factor_ret = {}
        for name, data in req.factor_returns.items():
            s = pd.Series(data, dtype=float)
            s.index = pd.to_datetime(s.index)
            factor_ret[name] = s

        result = attribute_returns(comp, factor_ret, req.composite_weights, method=req.method)

        return AttributionResponse(
            total_return=result.total_return,
            factor_contributions=result.factor_contributions,
            residual_return=result.residual_return,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Factor Correlation Matrix ──────────────────────────────────


class CorrelationMatrixRequest(BaseModel):
    symbols: list[str]
    factors: list[str]
    start: str
    end: str

class CorrelationMatrixResponse(BaseModel):
    matrix: dict[str, dict[str, float]]
    n_factors: int

@router.post("/factor-correlation", response_model=CorrelationMatrixResponse)
async def compute_factor_correlation(
    req: CorrelationMatrixRequest,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("researcher")),
) -> CorrelationMatrixResponse:
    """Compute pairwise correlation matrix between factors."""
    try:
        from src.strategy.research import FACTOR_REGISTRY, compute_factor_values
        from src.data.sources.yahoo import YahooFeed

        feed = YahooFeed(universe=req.symbols)
        data = {}
        for sym in req.symbols:
            bars = feed.get_bars(sym, start=req.start, end=req.end)
            if not bars.empty:
                data[sym] = bars

        if len(data) < 5:
            raise HTTPException(status_code=400, detail="Need at least 5 symbols with data")

        factor_dfs = {}
        for name in req.factors:
            if name not in FACTOR_REGISTRY:
                continue
            try:
                fv = compute_factor_values(data, name)
                if not fv.empty:
                    factor_dfs[name] = fv
            except Exception:
                continue

        if len(factor_dfs) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 computable factors")

        from src.alpha.orthogonalize import factor_correlation_matrix
        corr = factor_correlation_matrix(factor_dfs)

        matrix = {
            r: {c: float(corr.loc[r, c]) for c in corr.columns}
            for r in corr.index
        }
        return CorrelationMatrixResponse(matrix=matrix, n_factors=len(factor_dfs))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Neutralize ─────────────────────────────────────────────────


class NeutralizeRequest(BaseModel):
    symbols: list[str]
    factor_name: str
    start: str
    end: str
    method: str = "market"  # "market" | "industry"

class NeutralizeResponse(BaseModel):
    factor_name: str
    method: str
    n_dates: int
    n_symbols: int
    sample: dict[str, float]  # last date's neutralized values

@router.post("/neutralize", response_model=NeutralizeResponse)
async def neutralize_factor(
    req: NeutralizeRequest,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("researcher")),
) -> NeutralizeResponse:
    """Neutralize a factor (remove market or industry exposure)."""
    try:
        from src.strategy.research import compute_factor_values
        from src.alpha.neutralize import neutralize, NeutralizeMethod
        from src.data.sources.yahoo import YahooFeed

        feed = YahooFeed(universe=req.symbols)
        data: dict[str, Any] = {}
        for sym in req.symbols:
            bars = feed.get_bars(sym, start=req.start, end=req.end)
            if not bars.empty:
                data[sym] = bars

        fv = compute_factor_values(data, req.factor_name)
        if fv.empty:
            raise HTTPException(status_code=400, detail=f"No factor values for {req.factor_name}")

        neutralized = neutralize(fv, method=NeutralizeMethod(req.method))
        last_row = neutralized.iloc[-1].dropna()

        return NeutralizeResponse(
            factor_name=req.factor_name,
            method=req.method,
            n_dates=len(neutralized),
            n_symbols=len(last_row),
            sample={str(k): float(v) for k, v in last_row.head(10).items()},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Filter Strategy ────────────────────────────────────────────


class FilterStrategyRequest(BaseModel):
    universe: list[str]
    filters: list[dict[str, Any]]  # [{"factor": "revenue_yoy", "operator": "gt", "threshold": 15}]
    rank_by: str = "revenue_yoy"
    top_n: int = 15
    start: str = "2020-01-01"
    end: str = "2025-12-31"

class FilterStrategyResponse(BaseModel):
    task_id: str
    status: str
    message: str

@router.post("/filter-strategy", response_model=FilterStrategyResponse)
async def run_filter_strategy(
    req: FilterStrategyRequest,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("researcher")),
) -> FilterStrategyResponse:
    """Run a custom filter-based strategy backtest."""
    try:
        from src.alpha.filter_strategy import FilterCondition, FilterStrategyConfig, FilterStrategy
        from src.backtest.engine import BacktestConfig, BacktestEngine

        conditions = [
            FilterCondition(
                factor_name=f["factor"],
                operator=f["operator"],
                threshold=f["threshold"],
            )
            for f in req.filters
        ]

        config = FilterStrategyConfig(
            filters=conditions,
            rank_by=req.rank_by,
            top_n=req.top_n,
        )
        strategy = FilterStrategy(config)

        bt_config = BacktestConfig(
            universe=req.universe,
            start=req.start,
            end=req.end,
            rebalance_freq="monthly",
            fractional_shares=True,
        )

        engine = BacktestEngine()
        result = engine.run(strategy, bt_config)

        task_id = uuid.uuid4().hex[:8]
        state = get_app_state()
        state.backtest_tasks[task_id] = {
            "status": "completed",
            "type": "filter_strategy",
            "result": {
                "total_return": result.total_return,
                "sharpe": result.sharpe,
                "max_drawdown": result.max_drawdown,
                "total_trades": result.total_trades,
            },
        }

        return FilterStrategyResponse(
            task_id=task_id,
            status="completed",
            message=f"Return: {result.total_return:+.2%}, Sharpe: {result.sharpe:.3f}, Trades: {result.total_trades}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Event Rebalancer Config ────────────────────────────────────


class EventRebalancerConfig(BaseModel):
    revenue_trigger_day_lo: int = 11
    revenue_trigger_day_hi: int = 13
    institutional_sigma: float = 3.0
    fallback_monthly: bool = True

class EventRebalancerResponse(BaseModel):
    config: dict[str, Any]
    test_date: str
    would_trigger: bool
    trigger_type: str

@router.post("/event-rebalancer/test", response_model=EventRebalancerResponse)
async def test_event_rebalancer(
    req: EventRebalancerConfig,
    test_date: str = "2025-03-11",
    api_key: str = Depends(verify_api_key),
) -> EventRebalancerResponse:
    """Test event-driven rebalancer configuration against a date."""
    from src.alpha.event_rebalancer import EventDrivenRebalancer

    rebalancer = EventDrivenRebalancer(
        revenue_trigger_day_range=(req.revenue_trigger_day_lo, req.revenue_trigger_day_hi),
        institutional_sigma=req.institutional_sigma,
        fallback_monthly=req.fallback_monthly,
    )
    signal = rebalancer.check(test_date)

    return EventRebalancerResponse(
        config={
            "revenue_trigger_days": f"{req.revenue_trigger_day_lo}-{req.revenue_trigger_day_hi}",
            "institutional_sigma": req.institutional_sigma,
            "fallback_monthly": req.fallback_monthly,
        },
        test_date=test_date,
        would_trigger=signal.should_rebalance,
        trigger_type=signal.trigger,
    )
