"""Auto-Alpha API routes — production alpha engine: config, control, deployed strategies.

Research endpoints (submit-factor, run-now, status, history, alerts, decision)
live in factor_research.py (AP-5 split). This module re-includes that router
so all /api/v1/auto-alpha/* URLs still work (backward compat).
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.auth import require_role, verify_api_key
from src.api.state import get_app_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auto-alpha", tags=["auto-alpha"])


# ── Backward compat: delegate research endpoints to factor_research ──

from src.api.routes import factor_research as _fr

@router.get("/status", response_model=_fr.StatusResponse)
async def get_status(_auth: str = Depends(verify_api_key)) -> _fr.StatusResponse:
    return await _fr.get_status(_auth=_auth)

@router.get("/history", response_model=list[_fr.SnapshotSummary])
async def list_history(limit: int = Query(default=30, ge=1, le=365), _auth: str = Depends(verify_api_key)) -> list[_fr.SnapshotSummary]:
    return await _fr.list_history(limit=limit, _auth=_auth)

@router.get("/history/{date}", response_model=_fr.SnapshotDetail)
async def get_history_by_date(date: str, _auth: str = Depends(verify_api_key)) -> _fr.SnapshotDetail:
    return await _fr.get_history_by_date(date=date, _auth=_auth)

@router.get("/alerts", response_model=list[_fr.AlertResponse])
async def list_alerts(limit: int = Query(default=50, ge=1, le=500), _auth: str = Depends(verify_api_key)) -> list[_fr.AlertResponse]:
    return await _fr.list_alerts(limit=limit, _auth=_auth)

@router.post("/run-now", response_model=_fr.RunNowResponse)
async def run_now(_auth: dict[str, Any] = Depends(require_role("trader"))) -> _fr.RunNowResponse:
    return await _fr.run_now(_auth=_auth)

@router.get("/run-now/{task_id}")
async def get_run_now_status(task_id: str, _auth: str = Depends(verify_api_key)) -> dict[str, Any]:
    return await _fr.get_run_now_status(task_id=task_id, _auth=_auth)

@router.get("/decision", response_model=_fr.DecisionResponse)
async def get_current_decision(api_key: str = Depends(verify_api_key)) -> _fr.DecisionResponse:
    return await _fr.get_current_decision(api_key=api_key)

@router.post("/submit-factor", response_model=_fr.SubmitFactorResponse)
async def submit_factor(req: _fr.SubmitFactorRequest, _role: dict[str, Any] = Depends(require_role("researcher"))) -> _fr.SubmitFactorResponse:
    return await _fr.submit_factor(req=req, _role=_role)

@router.websocket("/ws")
async def auto_alpha_ws(websocket, token: str | None = Query(default=None)):
    return await _fr.factor_research_ws(websocket=websocket, token=token)


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


class PerformanceResponse(BaseModel):
    """Cumulative performance summary."""

    total_days: int
    win_rate: float
    cumulative_return: float
    max_drawdown: float
    avg_daily_pnl: float
    best_day: float
    worst_day: float


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class SafetyGateResponse(BaseModel):
    all_clear: bool
    gates: dict[str, bool]
    message: str


class FactorPnlItem(BaseModel):
    factor_name: str
    cumulative_pnl: float
    recent_ic: float | None = None


class FactorPoolResponse(BaseModel):
    active_factors: list[str]
    excluded_factors: list[str]
    total_available: int


# ── Helper ───────────────────────────────────────────────────


def _config_to_dict(config: Any) -> dict[str, Any]:
    """Convert AutoAlphaConfig dataclass to a JSON-friendly dict."""
    d = asdict(config)
    d.pop("alpha_config", None)
    return d


# ── Production Endpoints ─────────────────────────────────────


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

    decision_updates = updates.pop("decision", None)
    if decision_updates:
        for key, val in decision_updates.items():
            if hasattr(cfg.decision, key):
                object.__setattr__(cfg.decision, key, val)

    for key, val in updates.items():
        if hasattr(cfg, key):
            object.__setattr__(cfg, key, val)

    d = _config_to_dict(cfg)
    return AutoAlphaConfigResponse(**d)


@router.post("/start", response_model=MessageResponse)
async def start_auto_alpha(
    _auth: dict[str, Any] = Depends(require_role("trader")),
) -> MessageResponse:
    """Start autoresearch Docker containers + research loop."""
    state = get_app_state()
    if state.auto_alpha_running:
        raise HTTPException(status_code=409, detail="Auto-alpha is already running")

    result = await _docker_compose_action("up", "-d")
    if result["returncode"] != 0:
        raise HTTPException(status_code=500, detail=f"Docker start failed: {result['stderr'][:200]}")

    state.auto_alpha_running = True
    return MessageResponse(message=f"Auto-alpha started. {result['stdout'][:100]}")


@router.post("/stop", response_model=MessageResponse)
async def stop_auto_alpha(
    _auth: dict[str, Any] = Depends(require_role("trader")),
) -> MessageResponse:
    """Stop autoresearch Docker containers."""
    state = get_app_state()

    result = await _docker_compose_action("down")
    state.auto_alpha_running = False
    return MessageResponse(message=f"Auto-alpha stopped. {result['stdout'][:100]}")


async def _docker_compose_action(*args: str) -> dict:
    """Run docker compose command for autoresearch stack."""
    import asyncio
    import subprocess
    from pathlib import Path

    compose_dir = Path("docker/autoresearch")
    if not (compose_dir / "docker-compose.yml").exists():
        return {"returncode": 1, "stdout": "", "stderr": "docker-compose.yml not found"}

    compose_file = (compose_dir / "docker-compose.yml").resolve()
    cmd = ["docker", "compose", "-f", str(compose_file), *args]

    def _run() -> dict:
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120,
            )
            return {
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"returncode": 1, "stdout": "", "stderr": "Docker command timed out"}
        except Exception as e:
            return {"returncode": 1, "stdout": "", "stderr": str(e)}

    return await asyncio.to_thread(_run)


@router.get("/performance", response_model=PerformanceResponse)
async def get_performance(
    _auth: str = Depends(verify_api_key),
) -> PerformanceResponse:
    """Cumulative performance summary from AlphaStore."""
    state = get_app_state()
    summary = state.alpha_store.get_performance_summary()
    return PerformanceResponse(**summary)


# AP-3: stub endpoint
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
        message="[PLACEHOLDER] All safety gates clear (auto-alpha not running)",
    )


# AP-3: stub endpoint
@router.get("/factor-pnl", response_model=list[FactorPnlItem])
async def get_factor_pnl(
    api_key: str = Depends(verify_api_key),
) -> list[FactorPnlItem]:
    """Get per-factor P&L tracking."""
    return []


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


# ── Deployed Strategy Management ──────────────────────────────


@router.get("/deployed")
async def list_deployed(
    api_key: str = Depends(verify_api_key),
) -> list[dict[str, Any]]:
    """List all deployed strategies (active, stopped, expired, killed)."""
    from src.alpha.auto.paper_deployer import PaperDeployer
    deployer = PaperDeployer.get_instance()
    results = []
    for d in deployer._deployed:
        pnl = (d.current_nav / d.initial_nav - 1) * 100 if d.initial_nav > 0 else 0
        mdd = (d.peak_nav - d.current_nav) / d.peak_nav * 100 if d.peak_nav > 0 else 0
        results.append({
            "name": d.name,
            "factor_name": d.factor_name,
            "status": d.status,
            "deploy_date": d.deploy_date[:10],
            "stop_date": d.stop_date[:10],
            "initial_nav": d.initial_nav,
            "current_nav": d.current_nav,
            "peak_nav": d.peak_nav,
            "pnl_pct": round(pnl, 2),
            "mdd_pct": round(mdd, 2),
            "n_days": len(d.daily_navs),
        })
    return results


@router.get("/deployed/{name}/history")
async def deployed_history(
    name: str,
    api_key: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """Get NAV history and latest holdings for a deployed strategy."""
    from src.alpha.auto.paper_deployer import PaperDeployer
    from src.alpha.auto.deployed_executor import _load_last_trade
    deployer = PaperDeployer.get_instance()

    target = None
    for d in deployer._deployed:
        if d.name == name:
            target = d
            break
    if target is None:
        raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")

    last_trade = _load_last_trade(name)
    return {
        "name": target.name,
        "status": target.status,
        "daily_navs": target.daily_navs[-90:],
        "latest_weights": last_trade.get("weights", {}) if last_trade else {},
        "latest_date": last_trade.get("date", "") if last_trade else "",
        "n_positions": last_trade.get("n_positions", 0) if last_trade else 0,
    }


@router.post("/deployed/{name}/stop")
async def stop_deployed(
    name: str,
    _role: dict[str, Any] = Depends(require_role("admin")),
) -> dict[str, str]:
    """Manually stop a deployed strategy."""
    from src.alpha.auto.paper_deployer import PaperDeployer
    deployer = PaperDeployer.get_instance()

    found = any(d.name == name and d.status == "active" for d in deployer._deployed)
    if not found:
        raise HTTPException(status_code=404, detail=f"No active strategy '{name}'")

    deployer.stop(name, reason="manual_api")
    return {"status": "stopped", "name": name}
