"""Risk management API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.auth import verify_api_key, require_role
from src.api.schemas import KillSwitchResponse, RiskAlertResponse, RiskRuleResponse, MessageResponse
from src.api.state import get_app_state

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/rules", response_model=list[RiskRuleResponse])
async def get_risk_rules(api_key: str = Depends(verify_api_key)) -> list[RiskRuleResponse]:
    """取得所有風控規則。"""
    state = get_app_state()
    return [
        RiskRuleResponse(name=rule.name, enabled=rule.enabled)
        for rule in state.risk_engine.rules
    ]


@router.put("/rules/{rule_name}", response_model=MessageResponse)
async def toggle_rule(rule_name: str, enabled: bool = True, api_key: str = Depends(verify_api_key), _role: dict[str, Any] = Depends(require_role("risk_manager"))) -> MessageResponse:
    """啟用/停用風控規則。"""
    state = get_app_state()
    for rule in state.risk_engine.rules:
        if rule.name == rule_name:
            rule.enabled = enabled
            return MessageResponse(message=f"Rule {rule_name} {'enabled' if enabled else 'disabled'}")
    raise HTTPException(status_code=404, detail=f"Rule {rule_name} not found")


@router.get("/alerts", response_model=list[RiskAlertResponse])
async def get_risk_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    api_key: str = Depends(verify_api_key),
) -> list[RiskAlertResponse]:
    """取得風控告警歷史（支援分頁）。"""
    state = get_app_state()
    alerts = state.risk_engine.get_alerts()
    paginated = alerts[offset:offset + limit]
    return [
        RiskAlertResponse(
            timestamp=str(a.timestamp),
            rule_name=a.rule_name,
            severity=a.severity.value,
            metric_value=a.metric_value,
            threshold=a.threshold,
            action_taken=a.action_taken,
            message=a.message,
        )
        for a in paginated
    ]


@router.get("/realtime")
async def get_realtime_risk(api_key: str = Depends(verify_api_key)) -> dict[str, Any]:
    """取得即時風控狀態（日內回撤、NAV 高點、告警數）。"""
    state = get_app_state()
    monitor = getattr(state, "realtime_risk_monitor", None)
    if monitor is None:
        raise HTTPException(
            status_code=503,
            detail="Realtime risk monitor not available (only in paper/live mode)",
        )
    result: dict[str, Any] = monitor.get_status()
    return result


@router.post("/kill-switch", response_model=KillSwitchResponse)
async def kill_switch(api_key: str = Depends(verify_api_key), _role: dict[str, Any] = Depends(require_role("risk_manager"))) -> KillSwitchResponse:
    """緊急熔斷：停止所有策略，撤銷所有訂單。"""
    state = get_app_state()

    # 停止所有策略
    for name in state.strategies:
        state.strategies[name]["status"] = "stopped"

    # 撤銷所有訂單
    cancelled = state.oms.cancel_all()

    return KillSwitchResponse(
        message="Kill switch activated",
        strategies_stopped=len(state.strategies),
        orders_cancelled=cancelled,
    )


# ── Risk Config ────────────────────────────────────────────────

class RiskConfigUpdate(BaseModel):
    max_position_pct: float | None = None
    max_daily_drawdown_pct: float | None = None
    kill_switch_pct: float | None = None

@router.put("/config", response_model=MessageResponse)
async def update_risk_config(
    req: RiskConfigUpdate,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("risk_manager")),
) -> MessageResponse:
    """Update risk monitor thresholds."""
    from src.core.config import get_config
    config = get_config()
    updated = []
    if req.max_position_pct is not None:
        config.max_position_pct = req.max_position_pct
        updated.append(f"max_position_pct={req.max_position_pct}")
    if req.max_daily_drawdown_pct is not None:
        config.max_daily_drawdown_pct = req.max_daily_drawdown_pct
        updated.append(f"max_daily_drawdown_pct={req.max_daily_drawdown_pct}")
    if req.kill_switch_pct is not None:
        # Update kill switch rule threshold
        state = get_app_state()
        for rule in state.risk_engine.rules:
            if rule.name == "kill_switch":
                if hasattr(rule, 'params'):
                    rule.params["threshold"] = req.kill_switch_pct
                updated.append(f"kill_switch_pct={req.kill_switch_pct}")
    return MessageResponse(message=f"Updated: {', '.join(updated)}" if updated else "No changes")


class RuleConfigUpdate(BaseModel):
    params: dict[str, float]

@router.put("/rules/{rule_name}/config", response_model=MessageResponse)
async def update_rule_config(
    rule_name: str,
    req: RuleConfigUpdate,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("risk_manager")),
) -> MessageResponse:
    """Update rule parameters."""
    state = get_app_state()
    for rule in state.risk_engine.rules:
        if rule.name == rule_name:
            if hasattr(rule, 'params'):
                rule.params.update(req.params)
            return MessageResponse(message=f"Rule {rule_name} config updated: {req.params}")
    raise HTTPException(status_code=404, detail=f"Rule {rule_name} not found")
