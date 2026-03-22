"""System API routes."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from src.api.auth import verify_api_key
from src.api.schemas import HealthResponse, SystemStatusResponse
from src.api.state import get_app_state
from src.config import get_config

router = APIRouter(prefix="/system", tags=["system"])

_start_time = time.time()


@router.get("/health", response_model=HealthResponse)
async def health():
    """健康檢查（不需要認證）。"""
    return HealthResponse(status="ok", version="0.1.0")


@router.get("/status", response_model=SystemStatusResponse)
async def system_status(api_key: str = Depends(verify_api_key)):
    """系統狀態。"""
    config = get_config()
    state = get_app_state()

    running = sum(
        1 for s in state.strategies.values() if s.get("status") == "running"
    )

    return SystemStatusResponse(
        mode=config.mode,
        uptime_seconds=time.time() - _start_time,
        strategies_running=running,
        data_source=config.data_source,
        database="sqlite" if "sqlite" in config.database_url else "postgresql",
    )
