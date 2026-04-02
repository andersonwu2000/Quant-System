"""
FastAPI Application — 量化交易系統的 API 入口。

Startup logic split into bootstrap/ modules (AN-1):
  - bootstrap/market.py: quote manager, realtime risk, price polling
  - bootstrap/monitoring.py: monitoring loop, kill switch, scheduler, shutdown
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from decimal import Decimal

from prometheus_fastapi_instrumentator import Instrumentator

from src.api.auth import verify_ws_token
from src.core.models import Portfolio
from src.api.middleware import AuditMiddleware
from src.api.routes import admin, allocation, alpha, auth, auto_alpha, backtest, data, execution, factor_research, orders, portfolio, risk, scanner, scheduler_routes, strategies, strategy_center, system
from src.api.ws import ws_manager
from src.core.config import get_config
from src.core.logging import setup_logging

logger = logging.getLogger(__name__)

# Rate limiter — per-user when authenticated, per-IP otherwise (AN-32)
def _rate_limit_key(request) -> str:
    """Use authenticated username if available, else remote IP."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from jose import jwt
            config = get_config()
            payload = jwt.decode(auth_header[7:], config.jwt_secret, algorithms=["HS256"])
            username = payload.get("sub", "")
            if username:
                return f"user:{username}"
        except Exception:
            pass
    return get_remote_address(request)

limiter = Limiter(key_func=_rate_limit_key, default_limits=["60/minute"])


def _seed_admin(config: object) -> None:
    """首次啟動時建立預設 admin 帳號（若不存在）。"""
    from src.core.config import TradingConfig
    from src.data.store import metadata
    from src.data.user_store import get_user_store, _get_engine
    from src.api.password import hash_password

    engine = _get_engine()
    metadata.create_all(engine)

    store = get_user_store()
    if store.get_by_username("admin"):
        return

    cfg = config if isinstance(config, TradingConfig) else get_config()
    pw_hash, pw_salt = hash_password(cfg.admin_password)
    store.create("admin", "Administrator", pw_hash, pw_salt, "admin")
    logger.warning(
        "Default admin account created. Username: admin  "
        "Please change the password immediately after first login.",
    )


def create_app() -> FastAPI:
    """建立 FastAPI 應用。"""
    config = get_config()

    # AN-30 TODO: Add file handler for persistent logging
    setup_logging(config.log_level, config.log_format)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Application lifespan: startup & shutdown logic."""
        logger.info("Quant Trading System starting (env=%s, mode=%s)", config.env, config.mode)
        from src.api.state import get_app_state, load_portfolio
        from src.strategy.registry import list_strategies
        state = get_app_state()
        state.strategies = {name: {"status": "stopped", "pnl": 0.0} for name in list_strategies()}

        # Restore paper-trading portfolio from disk
        if config.mode in ("paper", "live"):
            persisted = load_portfolio()
            if persisted is not None:
                state.portfolio = persisted
                logger.info("Restored persisted portfolio on startup")
            else:
                from src.api.state import save_portfolio
                initial_cash = Decimal(str(config.backtest_initial_cash))
                state.portfolio = Portfolio(cash=initial_cash, initial_cash=initial_cash)
                save_portfolio(state.portfolio)
                logger.info("No persisted portfolio, created with initial_cash=%s", initial_cash)

        _seed_admin(config)

        # Execution service init
        from src.execution.service import ExecutionConfig, ExecutionService as ExecSvc
        exec_config = ExecutionConfig(
            mode=config.mode,
            sinopac_api_key=config.sinopac_api_key,
            sinopac_secret_key=config.sinopac_secret_key,
            sinopac_ca_path=config.sinopac_ca_path,
            sinopac_ca_password=config.sinopac_ca_password,
            commission_rate=config.commission_rate,
            tax_rate=config.tax_rate,
            default_slippage_bps=config.default_slippage_bps,
        )
        state.execution_service = ExecSvc(exec_config)

        # Market feed + realtime risk (paper/live only)
        if config.mode in ("paper", "live"):
            from src.api.bootstrap.market import setup_market_feed
            setup_market_feed(state, config, ws_manager)
        else:
            state.execution_service.initialize()
            logger.info("ExecutionService initialized: mode=%s", config.mode)

        state.kill_switch_fired = False

        # Background tasks: monitoring + kill switch + scheduler
        from src.api.bootstrap.monitoring import start_background_tasks, shutdown_app
        bg_tasks, scheduler = await start_background_tasks(state, config, ws_manager)

        yield

        # Graceful shutdown
        await shutdown_app(state, config, scheduler, bg_tasks, ws_manager)

    # Disable Swagger/Redoc in non-dev environments
    is_dev = config.env == "dev"
    app = FastAPI(
        title="Quant Trading System",
        description="量化交易平台 API",
        version="0.1.0",
        docs_url="/docs" if is_dev else None,
        redoc_url="/redoc" if is_dev else None,
        lifespan=lifespan,
    )

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # Audit logging middleware
    app.add_middleware(AuditMiddleware)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Prometheus metrics — only expose /metrics in dev mode
    instrumentator = Instrumentator()
    instrumentator.instrument(app)
    if config.env == "dev":
        instrumentator.expose(app, endpoint="/metrics")

    # Routes
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(alpha.router, prefix="/api/v1")
    app.include_router(auto_alpha.router, prefix="/api/v1")
    app.include_router(factor_research.router, prefix="/api/v1")
    app.include_router(strategy_center.router, prefix="/api/v1")
    app.include_router(allocation.router, prefix="/api/v1")
    app.include_router(portfolio.router, prefix="/api/v1")
    app.include_router(strategies.router, prefix="/api/v1")
    app.include_router(orders.router, prefix="/api/v1")
    app.include_router(backtest.router, prefix="/api/v1")
    app.include_router(risk.router, prefix="/api/v1")
    app.include_router(system.router, prefix="/api/v1")
    app.include_router(execution.router, prefix="/api/v1")
    app.include_router(scanner.router, prefix="/api/v1")
    app.include_router(data.router, prefix="/api/v1")
    app.include_router(scheduler_routes.router, prefix="/api/v1")

    from src.api.routes import ops
    app.include_router(ops.router, prefix="/api/v1")

    # WebSocket endpoint
    @app.websocket("/ws/{channel}")
    async def websocket_endpoint(
        websocket: WebSocket,
        channel: str,
        token: str | None = Query(default=None),
    ) -> None:
        valid_channels = {"portfolio", "alerts", "orders", "market"}
        if channel not in valid_channels:
            await websocket.close(code=4000, reason=f"Invalid channel: {channel}")
            return

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
            logger.debug("Suppressed exception", exc_info=True)
        except Exception:
            logger.debug("WS error on channel=%s", channel, exc_info=True)
        finally:
            ws_manager.disconnect(websocket, channel)

    # Global exception handler
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception: %s %s", request.method, request.url.path, exc_info=True)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    # Serve Web frontend static files
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    web_dist = Path(__file__).resolve().parent.parent.parent / "apps" / "web" / "dist"
    if web_dist.is_dir():
        app.mount("/assets", StaticFiles(directory=str(web_dist / "assets")), name="static-assets")

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str) -> FileResponse:
            file_path = (web_dist / full_path).resolve()
            if file_path.is_file() and file_path.is_relative_to(web_dist):
                return FileResponse(str(file_path))
            return FileResponse(str(web_dist / "index.html"))

        logger.info("Serving Web frontend from %s", web_dist)

    return app


# uvicorn entry
app = create_app()
