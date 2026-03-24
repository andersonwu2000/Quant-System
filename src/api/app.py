"""
FastAPI Application — 量化交易系統的 API 入口。
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from prometheus_fastapi_instrumentator import Instrumentator

from src.api.auth import verify_ws_token
from src.api.middleware import AuditMiddleware
from src.api.routes import admin, allocation, alpha, auth, backtest, orders, portfolio, risk, strategies, system
from src.api.ws import ws_manager
from src.config import get_config
from src.logging_config import setup_logging

logger = logging.getLogger(__name__)

# Rate limiter（全域）
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


def _seed_admin(config: object) -> None:
    """首次啟動時建立預設 admin 帳號（若不存在）。"""
    from src.config import TradingConfig
    from src.data.store import metadata
    from src.data.user_store import get_user_store, _get_engine
    from src.api.password import hash_password

    engine = _get_engine()
    metadata.create_all(engine)

    store = get_user_store()
    if store.get_by_username("admin"):
        return  # 已存在，跳過

    cfg = config if isinstance(config, TradingConfig) else get_config()
    pw_hash, pw_salt = hash_password(cfg.admin_password)
    store.create("admin", "Administrator", pw_hash, pw_salt, "admin")
    logger.warning(
        "Default admin account created. Username: admin  Password: %s  "
        "Please change it immediately after first login.",
        cfg.admin_password,
    )


def create_app() -> FastAPI:
    """建立 FastAPI 應用。"""
    config = get_config()

    # 初始化 structured logging
    setup_logging(config.log_level, config.log_format)

    app = FastAPI(
        title="Quant Trading System",
        description="量化交易平台 API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # Audit logging middleware
    app.add_middleware(AuditMiddleware)

    # CORS — 從配置讀取允許的來源
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Prometheus metrics
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    # 註冊路由
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(alpha.router, prefix="/api/v1")
    app.include_router(allocation.router, prefix="/api/v1")
    app.include_router(portfolio.router, prefix="/api/v1")
    app.include_router(strategies.router, prefix="/api/v1")
    app.include_router(orders.router, prefix="/api/v1")
    app.include_router(backtest.router, prefix="/api/v1")
    app.include_router(risk.router, prefix="/api/v1")
    app.include_router(system.router, prefix="/api/v1")

    # WebSocket 端點（需要 token 認證）
    @app.websocket("/ws/{channel}")
    async def websocket_endpoint(
        websocket: WebSocket,
        channel: str,
        token: str | None = Query(default=None),
    ) -> None:
        """WebSocket 連線端點。支持頻道：portfolio, alerts, orders, market"""
        valid_channels = {"portfolio", "alerts", "orders", "market"}
        if channel not in valid_channels:
            await websocket.close(code=4000, reason=f"Invalid channel: {channel}")
            return

        # 認證：dev 模式下 token 可選，其他模式必須提供
        if config.env != "dev":
            if not token:
                await websocket.close(code=4001, reason="Missing authentication token")
                return
            payload = verify_ws_token(token)
            if payload is None:
                await websocket.close(code=4001, reason="Invalid authentication token")
                return

        await ws_manager.connect(websocket, channel)
        try:
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.debug("WS error on channel=%s", channel, exc_info=True)
        finally:
            ws_manager.disconnect(websocket, channel)

    @app.on_event("startup")
    async def startup() -> None:
        logger.info(
            "Quant Trading System starting (env=%s, mode=%s)",
            config.env, config.mode,
        )
        from src.api.state import get_app_state
        from src.strategy.registry import list_strategies
        state = get_app_state()
        state.strategies = {
            name: {"status": "stopped", "pnl": 0.0}
            for name in list_strategies()
        }
        _seed_admin(config)

        # 背景 Kill Switch 監控（每 5 秒檢查一次）
        async def _kill_switch_monitor() -> None:
            while True:
                await asyncio.sleep(5)
                try:
                    if state.risk_engine.kill_switch(state.portfolio):
                        for name in state.strategies:
                            state.strategies[name]["status"] = "stopped"
                        state.oms.cancel_all()
                        await ws_manager.broadcast("alerts", {
                            "type": "kill_switch",
                            "message": "Kill switch triggered — all strategies stopped",
                        })
                except Exception:
                    logger.debug("Kill switch monitor error", exc_info=True)

        app.state.kill_switch_task = asyncio.create_task(_kill_switch_monitor())

        # 啟動排程器（若啟用）
        from src.scheduler import SchedulerService

        scheduler = SchedulerService()
        scheduler.start(config)
        app.state.scheduler = scheduler

    @app.on_event("shutdown")
    async def shutdown() -> None:
        logger.info("Quant Trading System shutting down...")
        if hasattr(app.state, "scheduler"):
            app.state.scheduler.stop()
        if hasattr(app.state, "kill_switch_task"):
            app.state.kill_switch_task.cancel()
        await ws_manager.close_all()

    return app


# uvicorn 入口
app = create_app()
