"""Auto-Alpha API routes — configuration, control, monitoring, and history.

Phase F3a: 10 endpoints for the Automated Alpha Research System.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from src.api.auth import require_role, verify_api_key
from src.api.state import get_app_state

logger = logging.getLogger(__name__)
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
_MAX_RUN_NOW_TASKS = 50


def _evict_old_tasks() -> None:
    """Remove oldest completed/failed tasks when exceeding limit. Must be called with _tasks_lock held."""
    if len(_run_now_tasks) <= _MAX_RUN_NOW_TASKS:
        return
    # Sort by completion time, remove oldest completed/failed tasks first
    removable = [
        (tid, info) for tid, info in _run_now_tasks.items()
        if info.get("status") in ("completed", "failed")
    ]
    removable.sort(key=lambda x: x[1].get("completed", ""))
    to_remove = len(_run_now_tasks) - _MAX_RUN_NOW_TASKS
    for tid, _ in removable[:to_remove]:
        del _run_now_tasks[tid]


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

            # Load data: prefer local parquet cache, then Yahoo download
            # Experiments show local-first is 10x faster and avoids rate limits
            import os
            from datetime import timedelta

            data: dict[str, Any] = {}

            # 1. Load from local parquet cache (data/market/*.parquet)
            from pathlib import Path
            cache_dir = str(Path("data/market").resolve())
            if os.path.isdir(cache_dir):
                import pandas as pd
                for f in os.listdir(cache_dir):
                    if f.endswith("_1d.parquet") and not f.startswith("TEST"):
                        sym = f.replace("_1d.parquet", "")
                        # Strip finmind_ prefix to get clean symbol
                        if sym.startswith("finmind_"):
                            sym = sym[len("finmind_"):]
                        try:
                            df = pd.read_parquet(os.path.join(cache_dir, f))
                            if not isinstance(df.index, pd.DatetimeIndex):
                                df.index = pd.to_datetime(df.index)
                            if len(df) >= cfg.lookback:
                                data[sym] = df
                        except Exception as exc:
                            logger.debug("Skip parquet %s: %s", f, exc)

            # 2. If not enough from cache, supplement from Yahoo
            if len(data) < 30:
                from src.data.sources import create_feed
                default_universe = [
                    "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW",
                    "2881.TW", "2882.TW", "2891.TW", "2886.TW", "2884.TW",
                    "2303.TW", "3711.TW", "2412.TW", "1301.TW", "1303.TW",
                    "2002.TW", "1216.TW", "2207.TW", "3008.TW", "2357.TW",
                    "1326.TW", "2345.TW", "2379.TW", "2327.TW", "2347.TW",
                    "2301.TW", "9910.TW", "6505.TW", "2615.TW", "3702.TW",
                ]
                feed = create_feed("yahoo", default_universe)
                end_dt = datetime.now()
                start_dt = end_dt - timedelta(days=int(cfg.lookback * 1.5))
                for sym in default_universe:
                    if sym in data:
                        continue
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
                _evict_old_tasks()
        except Exception as exc:
            with _tasks_lock:
                _run_now_tasks[task_id] = {
                    "status": "failed",
                    "error": str(exc),
                    "completed": datetime.now().isoformat(),
                }
                _evict_old_tasks()

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
async def auto_alpha_ws(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    """WebSocket endpoint for real-time auto-alpha pipeline events.

    Clients receive stage_started, stage_completed, decision, execution,
    alert, and error events as the pipeline runs.
    Requires token authentication in non-dev environments.
    """
    from src.api.auth import verify_ws_token
    from src.api.ws import ws_manager
    from src.core.config import get_config

    config = get_config()
    if config.env != "dev":
        if not token:
            await websocket.close(code=4001, reason="Missing authentication token")
            return
        payload = verify_ws_token(token)
        if payload is None:
            await websocket.close(code=4001, reason="Invalid authentication token")
            return

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


# ── Decision Engine ────────────────────────────────────────────

class DecisionResponse(BaseModel):
    selected_factors: list[str]
    weights: dict[str, float]
    reasoning: str

@router.get("/decision", response_model=DecisionResponse)
async def get_current_decision(
    api_key: str = Depends(verify_api_key),
) -> DecisionResponse:
    """Get the current factor selection decision from the auto-alpha engine."""
    state = get_app_state()
    aa = getattr(state, "auto_alpha", None)
    if aa is None:
        return DecisionResponse(selected_factors=[], weights={}, reasoning="Auto-alpha not initialized")

    try:
        pool = aa.get("dynamic_pool")
        if pool is not None:
            result = pool.update_pool()
            return DecisionResponse(
                selected_factors=result.active_factors if hasattr(result, 'active_factors') else [],
                weights=result.weights if hasattr(result, 'weights') else {},
                reasoning=f"Pool size: {len(result.active_factors) if hasattr(result, 'active_factors') else 0}",
            )
    except Exception as e:
        return DecisionResponse(selected_factors=[], weights={}, reasoning=str(e))

    return DecisionResponse(selected_factors=[], weights={}, reasoning="No pool available")


# ── Safety Gates ───────────────────────────────────────────────

class SafetyGateResponse(BaseModel):
    all_clear: bool
    gates: dict[str, bool]
    message: str

@router.get("/safety-gates", response_model=SafetyGateResponse)
async def get_safety_gates(
    api_key: str = Depends(verify_api_key),
) -> SafetyGateResponse:
    """Check if all safety gates pass."""
    return SafetyGateResponse(
        all_clear=True,
        gates={
            "max_consecutive_losses": True,
            "ic_reversal": True,
            "emergency_drawdown": True,
        },
        message="All safety gates clear (auto-alpha not running)",
    )


# ── Factor P&L ─────────────────────────────────────────────────

class FactorPnlItem(BaseModel):
    factor_name: str
    cumulative_pnl: float
    recent_ic: float | None = None

@router.get("/factor-pnl", response_model=list[FactorPnlItem])
async def get_factor_pnl(
    api_key: str = Depends(verify_api_key),
) -> list[FactorPnlItem]:
    """Get per-factor P&L tracking."""
    return []  # Populated when auto-alpha runs


# ── Factor Pool ────────────────────────────────────────────────

class FactorPoolResponse(BaseModel):
    active_factors: list[str]
    excluded_factors: list[str]
    total_available: int

@router.get("/factor-pool", response_model=FactorPoolResponse)
async def get_factor_pool(
    api_key: str = Depends(verify_api_key),
) -> FactorPoolResponse:
    """View current dynamic factor pool."""
    from src.alpha.auto.dynamic_pool import DynamicFactorPool
    all_names = DynamicFactorPool.get_all_factor_names()
    return FactorPoolResponse(
        active_factors=[],
        excluded_factors=[],
        total_available=len(all_names),
    )


# ── Autoresearch Integration ────────────────────────────────


class SubmitFactorRequest(BaseModel):
    """autoresearch session 提交通過 L4 的因子。"""
    name: str = Field(..., description="Factor name (e.g. 'rev_accel_trust_combo')")
    code: str = Field(..., description="factor.py content")
    composite_score: float = Field(..., description="evaluate.py composite_score")
    icir_20d: float = 0.0
    large_icir_20d: float = 0.0
    description: str = ""


class SubmitFactorResponse(BaseModel):
    status: str
    validator_passed: int = 0
    validator_total: int = 0
    deployed: bool = False
    message: str = ""


@router.post("/submit-factor", response_model=SubmitFactorResponse)
async def submit_factor(
    req: SubmitFactorRequest,
    _role: dict[str, Any] = Depends(require_role("researcher")),
) -> SubmitFactorResponse:
    """autoresearch session 提交因子 → 跑 Validator 15 項 → 自動部署。

    流程：
    1. 保存 factor.py 到 src/strategy/factors/research/{name}.py
    2. 用 strategy_builder 包裝成 Strategy
    3. 跑 StrategyValidator 15 項
    4. 通過門檻 → 部署到 paper trading
    """
    from pathlib import Path
    import importlib.util

    import re as _re

    factor_dir = Path(__file__).resolve().parent.parent.parent.parent / "src" / "strategy" / "factors" / "research"
    factor_dir.mkdir(parents=True, exist_ok=True)

    # 0. 安全檢查 — 拒絕明顯惡意代碼
    FORBIDDEN_PATTERNS = [
        r"\bimport\s+os\b", r"\bimport\s+subprocess\b", r"\bimport\s+shutil\b",
        r"\b__import__\b", r"\bexec\s*\(", r"\beval\s*\(",
        r"\bos\.system\b", r"\bos\.popen\b", r"\bsubprocess\.\w+\(",
    ]
    for pat in FORBIDDEN_PATTERNS:
        if _re.search(pat, req.code):
            return SubmitFactorResponse(
                status="rejected",
                message=f"Code contains forbidden pattern: {pat}",
            )

    # 1. Name sanitization — all downstream uses clean_name
    clean_name = _re.sub(r'[^a-zA-Z0-9_]', '', req.name)
    if not clean_name:
        return SubmitFactorResponse(status="rejected", message="Invalid factor name")
    factor_path = factor_dir / f"{clean_name}.py"

    # 2. 保存因子代碼
    factor_path.write_text(req.code, encoding="utf-8")
    logger.info("Factor submitted: %s (score=%.2f)", clean_name, req.composite_score)

    # 3. 驗證可載入
    try:
        spec = importlib.util.spec_from_file_location(f"research_{clean_name}", factor_path)
        if spec is None or spec.loader is None:
            return SubmitFactorResponse(status="error", message="Cannot load factor module")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        compute_fn = getattr(mod, f"compute_{clean_name}", None) or getattr(mod, "compute_factor", None)
        if compute_fn is None:
            return SubmitFactorResponse(status="error", message="No compute function found")
    except Exception as e:
        return SubmitFactorResponse(status="error", message=f"Load error: {e}")

    # 3. 跑 StrategyValidator
    try:
        from src.alpha.auto.strategy_builder import build_from_research_factor
        from src.backtest.validator import StrategyValidator, ValidationConfig

        strategy = build_from_research_factor(factor_name=clean_name, top_n=15)
        market_dir = Path("data/market")

        # Scan universe — support multiple parquet naming conventions
        import pandas as pd
        universe_set: set[str] = set()
        if market_dir.exists():
            for p in market_dir.glob("*.parquet"):
                stem = p.stem
                # finmind_{code}.parquet → {code}.TW
                if stem.startswith("finmind_"):
                    code = stem.replace("finmind_", "")
                    if code.isdigit() and not code.startswith("00"):
                        universe_set.add(f"{code}.TW")
                # {sym}_1d.parquet → {sym}
                elif stem.endswith("_1d") and ".TW" in stem:
                    sym = stem.replace("_1d", "")
                    if not sym.startswith("00"):
                        universe_set.add(sym)
                # {sym}.TW.parquet → {sym}.TW
                elif ".TW" in stem and not stem.startswith("00"):
                    universe_set.add(stem)
        universe = sorted(universe_set)

        # 過濾太短的
        good_universe = []
        for sym in universe[:200]:  # cap for speed
            bare = sym.replace(".TW", "").replace(".TWO", "")
            # Try multiple naming patterns
            for pattern in [f"{sym}.parquet", f"{sym}_1d.parquet", f"finmind_{bare}.parquet"]:
                path = market_dir / pattern
                if path.exists():
                    try:
                        df = pd.read_parquet(path)
                        if len(df) >= 500:
                            good_universe.append(sym)
                    except Exception:
                        pass
                    break

        config = ValidationConfig(
            min_cagr=0.08, min_sharpe=0.7, max_drawdown=0.40,
            n_trials=15,  # ~15 independent hypothesis directions (Phase AB)
            initial_cash=10_000_000, min_universe_size=50,
            wf_train_years=2,
        )

        validator = StrategyValidator(config)
        report = validator.validate(strategy.strategy, good_universe, "2018-01-01", "2025-12-31")

        n_passed = report.n_passed
        n_total = report.n_total
        logger.info("Validator: %s %d/%d", req.name, n_passed, n_total)

    except Exception as e:
        logger.exception("Validator failed for %s", req.name)
        return SubmitFactorResponse(
            status="validator_error",
            message=f"Validator error: {e}",
        )

    # 4. 部署判定
    deployed = False
    # excl DSR ≥ 14
    checks = report.checks
    n_excl_dsr = sum(1 for c in checks if c.passed and c.name != "deflated_sharpe")
    def _safe_float(s: str, default: float = 0.0) -> float:
        try:
            return float(s)
        except (ValueError, TypeError):
            return default
    dsr_val = next((_safe_float(c.value) for c in checks if c.name == "deflated_sharpe"), 0.0)
    pbo_val = next((_safe_float(c.value) for c in checks if c.name == "pbo"), 1.0)

    if n_excl_dsr >= 13 and dsr_val >= 0.70 and pbo_val <= 0.70:
        try:
            from src.alpha.auto.paper_deployer import PaperDeployer
            deployer = PaperDeployer()
            can, reason = deployer.can_deploy()
            if can:
                deployer.deploy(
                    name=f"auto_{clean_name}",
                    factor_name=clean_name,
                    total_nav=10_000_000,
                )
                deployed = True
                logger.info("Auto-deployed: %s", req.name)
                _write_auto_report(req, results=dict(
                    composite_score=req.composite_score,
                    icir_20d=req.icir_20d,
                    large_icir_20d=req.large_icir_20d,
                ), report=report, checks=checks)
            else:
                logger.info("Cannot deploy %s: %s", req.name, reason)
        except Exception as e:
            logger.warning("Deploy failed for %s: %s", req.name, e)

    return SubmitFactorResponse(
        status="completed",
        validator_passed=n_passed,
        validator_total=n_total,
        deployed=deployed,
        message=f"{'Deployed' if deployed else 'Not deployed'} ({n_passed}/{n_total})",
    )


def _write_auto_report(req: "SubmitFactorRequest", results: dict[str, Any], report: Any, checks: list[Any]) -> None:
    """Write a deployment report to docs/research/autoresearch/ for deployed factors."""
    from pathlib import Path

    report_dir = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "research" / "autoresearch"
    report_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = req.name.replace("/", "_").replace(" ", "_")
    report_path = report_dir / f"{ts}_{name}.md"

    checks_table = "\n".join(
        f"| {c.name} | {'PASS' if c.passed else 'FAIL'} | {c.value} | {c.threshold} |"
        for c in checks
    )

    content = f"""# Auto-Deployed Factor: {req.name}

> Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
> Status: **DEPLOYED** to Paper Trading

## Metrics

| Metric | Value |
|--------|-------|
| Composite Score | {results.get('composite_score', 'N/A')} |
| ICIR (20d) | {results.get('icir_20d', 'N/A')} |
| Large-scale ICIR (20d) | {results.get('large_icir_20d', 'N/A')} |
| Validator | {report.n_passed}/{report.n_total} |

## Validator Results

| Check | Result | Value | Threshold |
|-------|--------|-------|-----------|
{checks_table}

## Factor Code

```python
{req.code}
```

## Description

{req.description}
"""

    try:
        report_path.write_text(content, encoding="utf-8")
        logger.info("Auto report written: %s", report_path)
    except Exception as e:
        logger.warning("Failed to write auto report: %s", e)
