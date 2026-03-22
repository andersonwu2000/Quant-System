"""Risk management API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import verify_api_key
from src.api.schemas import RiskAlertResponse, RiskRuleResponse
from src.api.state import get_app_state

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/rules", response_model=list[RiskRuleResponse])
async def get_risk_rules(api_key: str = Depends(verify_api_key)):
    """取得所有風控規則。"""
    state = get_app_state()
    return [
        RiskRuleResponse(name=rule.name, enabled=rule.enabled)
        for rule in state.risk_engine.rules
    ]


@router.put("/rules/{rule_name}")
async def toggle_rule(rule_name: str, enabled: bool = True, api_key: str = Depends(verify_api_key)):
    """啟用/停用風控規則。"""
    state = get_app_state()
    for rule in state.risk_engine.rules:
        if rule.name == rule_name:
            rule.enabled = enabled
            return {"message": f"Rule {rule_name} {'enabled' if enabled else 'disabled'}"}
    raise HTTPException(status_code=404, detail=f"Rule {rule_name} not found")


@router.get("/alerts", response_model=list[RiskAlertResponse])
async def get_risk_alerts(api_key: str = Depends(verify_api_key)):
    """取得風控告警歷史。"""
    state = get_app_state()
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
        for a in state.risk_engine.get_alerts()
    ]


@router.post("/kill-switch")
async def kill_switch(api_key: str = Depends(verify_api_key)):
    """緊急熔斷：停止所有策略，撤銷所有訂單。"""
    state = get_app_state()

    # 停止所有策略
    for name in state.strategies:
        state.strategies[name]["status"] = "stopped"

    # 撤銷所有訂單
    cancelled = state.oms.cancel_all()

    return {
        "message": "Kill switch activated",
        "strategies_stopped": len(state.strategies),
        "orders_cancelled": cancelled,
    }
