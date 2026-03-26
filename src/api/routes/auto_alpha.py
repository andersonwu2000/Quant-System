"""Auto-Alpha API routes — configuration, control, monitoring, and history.

Phase F3a: 10 endpoints for the Automated Alpha Research System.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from src.api.auth import require_role, verify_api_key
from src.api.state import get_app_state

router = APIRouter(prefix="/auto-alpha", tags=["auto-alpha"])


# ── Pydantic Schemas ─────────────────────────────────────────


class DecisionConfigUpdate(BaseModel):
    """Partial update model for DecisionConfig fields."""

    min_icir: float | None = None
    min_hit_rate: float | None = None
    max_cost_drag: float | None = None
    use_rolling_ic: bool | None = None
    regime_aware: bool | None = None


class AutoAlphaConfigUpdate(BaseModel):
    """Partial update model for AutoAlphaConfig."""

    schedule: str | None = None
    eod_schedule: str | None = None
    universe_count: int | None = None
    min_adv: int | None = None
    min_listing_days: int | None = None
    exclude_disposition: bool | None = None
    exclude_attention: bool | None = None
    lookback: int | None = None
    max_turnover: float | None = None
    min_trade_value: float | None = None
    max_consecutive_losses: int | None = None
    ic_reversal_days: int | None = None
    emergency_stop_drawdown: float | None = None
    decision: DecisionConfigUpdate | None = None


class AutoAlphaConfigResponse(BaseModel):
    """Full config response."""

    schedule: str
    eod_schedule: str
    universe_count: int
    min_adv: int
    min_listing_days: int
    exclude_disposition: bool
    exclude_attention: bool
    lookback: int
    max_turnover: float
    min_trade_value: float
    max_consecutive_losses: int
    ic_reversal_days: int
    emergency_stop_drawdown: float
    decision: dict[str, Any]


class StatusResponse(BaseModel):
    """Auto-alpha system status."""

    running: bool
    status: str  # "running", "stopped"
    last_run: str | None = None
    next_run: str | None = None
    regime: str | None = None
    selected_factors: list[str] = Field(default_factory=list)


class SnapshotSummary(BaseModel):
    """Brief snapshot entry for list view."""

    id: str
    date: str
    regime: str
    universe_size: int
    selected_factors: list[str]
    trades_count: int
    turnover: float
    daily_pnl: float | None = None
    cumulative_return: float | None = None


class SnapshotDetail(BaseModel):
    """Full snapshot detail."""

    id: str
    date: str
    regime: str
    universe: list[str]
    universe_size: int
    factor_scores: dict[str, Any]
    selected_factors: list[str]
    factor_weights: dict[str, float]
    target_weights: dict[str, float]
    trades_count: int
    turnover: float
    daily_pnl: float | None = None
    cumulative_return: float | None = None


class PerformanceResponse(BaseModel):
    """Cumulative performance summary."""

    total_days: int
    win_rate: float
    cumulative_return: float
    max_drawdown: float
    avg_daily_pnl: float
    best_day: float
    worst_day: float


class AlertResponse(BaseModel):
    """Single alert entry."""

    timestamp: str
    level: str
    category: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class RunNowResponse(BaseModel):
    """Response for the run-now endpoint."""

    task_id: str
    message: str


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


# ── Helper ───────────────────────────────────────────────────


def _config_to_dict(config: Any) -> dict[str, Any]:
    """Convert AutoAlphaConfig dataclass to a JSON-friendly dict."""
    d = asdict(config)
    # Remove alpha_config (complex nested object) from response for simplicity
    d.pop("alpha_config", None)
    return d


# ── Endpoints ────────────────────────────────────────────────


@router.get("/config", response_model=AutoAlphaConfigResponse)
async def get_config(
    _auth: str = Depends(verify_api_key),
) -> AutoAlphaConfigResponse:
    """Return current AutoAlphaConfig as JSON."""
    state = get_app_state()
    d = _config_to_dict(state.auto_alpha_config)
    return AutoAlphaConfigResponse(**d)


@router.put("/config", response_model=AutoAlphaConfigResponse)
async def update_config(
    body: AutoAlphaConfigUpdate,
    _auth: str = Depends(verify_api_key),
) -> AutoAlphaConfigResponse:
    """Update AutoAlphaConfig with partial updates."""
    state = get_app_state()
    cfg = state.auto_alpha_config

    updates = body.model_dump(exclude_none=True)

    # Handle nested decision config
    decision_updates = updates.pop("decision", None)
    if decision_updates:
        for key, val in decision_updates.items():
            if hasattr(cfg.decision, key):
                object.__setattr__(cfg.decision, key, val)

    # Apply top-level updates
    for key, val in updates.items():
        if hasattr(cfg, key):
            object.__setattr__(cfg, key, val)

    d = _config_to_dict(cfg)
    return AutoAlphaConfigResponse(**d)


@router.post("/start", response_model=MessageResponse)
async def start_auto_alpha(
    _auth: dict[str, Any] = Depends(require_role("trader")),
) -> MessageResponse:
    """Start the auto-alpha scheduler. Requires trader role."""
    state = get_app_state()
    if state.auto_alpha_running:
        raise HTTPException(status_code=409, detail="Auto-alpha is already running")
    state.auto_alpha_running = True
    return MessageResponse(message="Auto-alpha scheduler started")


@router.post("/stop", response_model=MessageResponse)
async def stop_auto_alpha(
    _auth: dict[str, Any] = Depends(require_role("trader")),
) -> MessageResponse:
    """Stop the auto-alpha scheduler. Requires trader role."""
    state = get_app_state()
    if not state.auto_alpha_running:
        raise HTTPException(status_code=409, detail="Auto-alpha is not running")
    state.auto_alpha_running = False
    return MessageResponse(message="Auto-alpha scheduler stopped")


@router.get("/status", response_model=StatusResponse)
async def get_status(
    _auth: str = Depends(verify_api_key),
) -> StatusResponse:
    """Current auto-alpha status (running/stopped, last_run, next_run, regime, selected_factors)."""
    state = get_app_state()
    running = state.auto_alpha_running
    status_str = "running" if running else "stopped"

    # Derive last_run info from most recent snapshot
    regime: str | None = None
    selected_factors: list[str] = []
    last_run: str | None = None

    snapshots = state.alpha_store.list_snapshots(limit=1)
    if snapshots:
        latest = snapshots[0]
        regime = latest.regime.value if hasattr(latest.regime, "value") else str(latest.regime)
        selected_factors = latest.selected_factors
        last_run = latest.date.isoformat() if hasattr(latest.date, "isoformat") else str(latest.date)

    return StatusResponse(
        running=running,
        status=status_str,
        last_run=last_run,
        next_run=None,  # Would require scheduler integration
        regime=regime,
        selected_factors=selected_factors,
    )


@router.get("/history", response_model=list[SnapshotSummary])
async def list_history(
    limit: int = Query(default=30, ge=1, le=365),
    _auth: str = Depends(verify_api_key),
) -> list[SnapshotSummary]:
    """List research snapshots (most recent first)."""
    state = get_app_state()
    snapshots = state.alpha_store.list_snapshots(limit=limit)
    result: list[SnapshotSummary] = []
    for snap in snapshots:
        regime_str = snap.regime.value if hasattr(snap.regime, "value") else str(snap.regime)
        date_str = snap.date.isoformat() if hasattr(snap.date, "isoformat") else str(snap.date)
        result.append(
            SnapshotSummary(
                id=snap.id,
                date=date_str,
                regime=regime_str,
                universe_size=snap.universe_size,
                selected_factors=snap.selected_factors,
                trades_count=snap.trades_count,
                turnover=snap.turnover,
                daily_pnl=snap.daily_pnl,
                cumulative_return=snap.cumulative_return,
            )
        )
    return result


@router.get("/history/{date}", response_model=SnapshotDetail)
async def get_history_by_date(
    date: str,
    _auth: str = Depends(verify_api_key),
) -> SnapshotDetail:
    """Get a specific date's research snapshot."""
    state = get_app_state()
    snapshot = state.alpha_store.get_snapshot(date)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"No snapshot found for date: {date}")

    regime_str = snapshot.regime.value if hasattr(snapshot.regime, "value") else str(snapshot.regime)
    date_str = snapshot.date.isoformat() if hasattr(snapshot.date, "isoformat") else str(snapshot.date)

    # Convert factor_scores to dict of dicts for JSON
    factor_scores_dict: dict[str, Any] = {}
    for name, score in snapshot.factor_scores.items():
        factor_scores_dict[name] = asdict(score) if hasattr(score, "__dataclass_fields__") else score

    return SnapshotDetail(
        id=snapshot.id,
        date=date_str,
        regime=regime_str,
        universe=snapshot.universe,
        universe_size=snapshot.universe_size,
        factor_scores=factor_scores_dict,
        selected_factors=snapshot.selected_factors,
        factor_weights=snapshot.factor_weights,
        target_weights=snapshot.target_weights,
        trades_count=snapshot.trades_count,
        turnover=snapshot.turnover,
        daily_pnl=snapshot.daily_pnl,
        cumulative_return=snapshot.cumulative_return,
    )


@router.get("/performance", response_model=PerformanceResponse)
async def get_performance(
    _auth: str = Depends(verify_api_key),
) -> PerformanceResponse:
    """Cumulative performance summary from AlphaStore."""
    state = get_app_state()
    summary = state.alpha_store.get_performance_summary()
    return PerformanceResponse(**summary)


@router.get("/alerts", response_model=list[AlertResponse])
async def list_alerts(
    limit: int = Query(default=50, ge=1, le=500),
    _auth: str = Depends(verify_api_key),
) -> list[AlertResponse]:
    """List recent alerts (most recent first)."""
    state = get_app_state()
    alerts = state.alpha_store.list_alerts(limit=limit)
    result: list[AlertResponse] = []
    for alert in alerts:
        ts = alert.timestamp
        ts_str = ts.isoformat() if isinstance(ts, datetime) else str(ts)
        result.append(
            AlertResponse(
                timestamp=ts_str,
                level=alert.level,
                category=alert.category,
                message=alert.message,
                details=alert.details,
            )
        )
    return result


# ── Background tasks tracking ────────────────────────────────

_run_now_tasks: dict[str, dict[str, Any]] = {}
_tasks_lock = threading.Lock()


@router.post("/run-now", response_model=RunNowResponse)
async def run_now(
    _auth: dict[str, Any] = Depends(require_role("trader")),
) -> RunNowResponse:
    """Execute one full auto-alpha cycle immediately in a background thread.

    Returns a task_id for tracking. Requires trader role.
    """
    state = get_app_state()
    task_id = str(uuid.uuid4())

    def _run_cycle() -> None:
        from src.alpha.auto.researcher import AlphaResearcher
        from src.alpha.auto.scheduler import AlphaScheduler

        try:
            with _tasks_lock:
                _run_now_tasks[task_id] = {"status": "running", "stage": "downloading", "started": datetime.now().isoformat()}

            cfg = state.auto_alpha_config

            # Pre-fetch data for default universe when scanner is unavailable
            default_universe = [
                "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW",
                "2881.TW", "2882.TW", "2891.TW", "2886.TW", "2884.TW",
                "2303.TW", "3711.TW", "2412.TW", "1301.TW", "1303.TW",
                "2002.TW", "1216.TW", "2207.TW", "3008.TW", "2357.TW",
            ]
            from src.data.sources import create_feed
            from datetime import timedelta

            feed = create_feed("yahoo", default_universe)
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=int(cfg.lookback * 1.5))
            data: dict[str, Any] = {}
            for sym in default_universe:
                try:
                    bars = feed.get_bars(sym, start=start_dt, end=end_dt)
                    if not bars.empty and len(bars) >= 60:
                        data[sym] = bars
                except Exception:
                    pass

            with _tasks_lock:
                _run_now_tasks[task_id]["stage"] = "researching"
                _run_now_tasks[task_id]["symbols_loaded"] = len(data)

            researcher = AlphaResearcher(cfg)

            scheduler = AlphaScheduler(
                config=cfg,
                researcher=researcher,
                store=state.alpha_store,  # Use global store so status endpoint can read it
            )
            result = scheduler.run_full_cycle(
                data=data,
                portfolio=state.portfolio,
                execution_service=state.execution_service,
                risk_engine=state.risk_engine,
            )

            # Save snapshot to global store for status/history endpoints
            snap = result.get("snapshot")
            if snap is not None:
                state.alpha_store.save_snapshot(snap)

            with _tasks_lock:
                _run_now_tasks[task_id] = {
                    "status": "completed",
                    "result": result,
                    "completed": datetime.now().isoformat(),
                }
        except Exception as exc:
            with _tasks_lock:
                _run_now_tasks[task_id] = {
                    "status": "failed",
                    "error": str(exc),
                    "completed": datetime.now().isoformat(),
                }

    thread = threading.Thread(target=_run_cycle, daemon=True)
    thread.start()

    return RunNowResponse(task_id=task_id, message="Auto-alpha cycle started in background")


@router.get("/run-now/{task_id}")
async def get_run_now_status(
    task_id: str,
    _auth: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """Poll the status of a run-now background task."""
    with _tasks_lock:
        task = _run_now_tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    # Don't return the full result object (may be huge); just status + summary
    resp: dict[str, Any] = {"task_id": task_id, "status": task.get("status", "unknown")}
    if task.get("stage"):
        resp["stage"] = task["stage"]
    if task.get("symbols_loaded"):
        resp["symbols_loaded"] = task["symbols_loaded"]
    if task.get("error"):
        resp["error"] = task["error"]
    if task.get("completed"):
        resp["completed"] = task["completed"]
    if task.get("started"):
        resp["started"] = task["started"]
    result = task.get("result")
    if result and isinstance(result, dict):
        snap = result.get("snapshot")
        if snap and hasattr(snap, "factor_scores"):
            resp["factors_computed"] = len(snap.factor_scores)
            resp["selected_factors"] = snap.selected_factors
            resp["regime"] = snap.regime.value if hasattr(snap.regime, "value") else str(snap.regime)
    return resp


# ── WebSocket endpoint ────────────────────────────────────────


@router.websocket("/ws")
async def auto_alpha_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time auto-alpha pipeline events.

    Clients receive stage_started, stage_completed, decision, execution,
    alert, and error events as the pipeline runs.
    """
    from src.api.ws import ws_manager

    await ws_manager.connect(websocket, "auto-alpha")
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(websocket, "auto-alpha")
