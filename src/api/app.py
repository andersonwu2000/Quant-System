"""
FastAPI Application — 量化交易系統的 API 入口。
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from prometheus_fastapi_instrumentator import Instrumentator

from src.api.auth import verify_ws_token
from src.api.middleware import AuditMiddleware
from src.api.routes import admin, allocation, alpha, auth, auto_alpha, backtest, data, execution, orders, portfolio, risk, scanner, scheduler_routes, strategies, strategy_center, system
from src.api.ws import ws_manager
from src.core.config import get_config
from src.core.logging import setup_logging

logger = logging.getLogger(__name__)

# Rate limiter（全域）
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


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

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Application lifespan: startup & shutdown logic."""
        logger.info("Quant Trading System starting (env=%s, mode=%s)", config.env, config.mode)
        from src.api.state import get_app_state, load_portfolio
        from src.strategy.registry import list_strategies
        state = get_app_state()
        state.strategies = {name: {"status": "stopped", "pnl": 0.0} for name in list_strategies()}

        # Restore paper-trading portfolio from disk (if available)
        if config.mode in ("paper", "live"):
            persisted = load_portfolio()
            if persisted is not None:
                state.portfolio = persisted
                logger.info("Restored persisted portfolio on startup")

        _seed_admin(config)

        from src.execution.service import ExecutionConfig, ExecutionService as ExecSvc
        exec_config = ExecutionConfig(
            mode=config.mode,
            sinopac_api_key=config.sinopac_api_key,
            sinopac_secret_key=config.sinopac_secret_key,
            sinopac_ca_path=config.sinopac_ca_path,
            sinopac_ca_password=config.sinopac_ca_password,
        )
        state.execution_service = ExecSvc(exec_config)
        state.execution_service.initialize()
        logger.info("ExecutionService initialized: mode=%s", config.mode)

        # ── Market channel + Realtime risk (paper/live only) ──
        if config.mode in ("paper", "live"):
            loop = asyncio.get_running_loop()

            from src.execution.broker.sinopac import SinopacBroker
            from src.execution.quote.sinopac import SinopacQuoteManager, TickData
            from src.risk.realtime import RealtimeRiskMonitor

            broker = state.execution_service.broker
            quote_manager: SinopacQuoteManager | None = None

            if isinstance(broker, SinopacBroker) and broker.api is not None:
                quote_manager = SinopacQuoteManager(broker.api)
                quote_manager.set_event_loop(loop)

                # Broadcast ticks to WebSocket market channel
                _qm = quote_manager  # bind for closure (always non-None here)

                async def _ws_broadcast_tick(tick_data: TickData) -> None:
                    payload = _qm.to_ws_payload(tick_data)
                    await ws_manager.broadcast("market", payload)

                quote_manager.set_broadcast_callback(_ws_broadcast_tick, loop)

                # Subscribe to current portfolio positions
                for symbol in list(state.portfolio.positions.keys()):
                    quote_manager.subscribe(symbol)

                logger.info(
                    "Market channel: SinopacQuoteManager connected, %d symbols subscribed",
                    len(state.portfolio.positions),
                )

            # Realtime risk monitor
            realtime_risk = RealtimeRiskMonitor(
                portfolio=state.portfolio,
                risk_engine=state.risk_engine,
                ws_manager=ws_manager,
                loop=loop,
                execution_service=state.execution_service,
            )
            state.realtime_risk_monitor = realtime_risk

            if quote_manager is not None:
                # Register price update callback for risk monitoring
                def _risk_on_tick(tick_data: TickData) -> None:
                    realtime_risk.on_price_update(tick_data.symbol, tick_data.price)

                quote_manager.on_tick(_risk_on_tick)

            state.quote_manager = quote_manager

            # Fallback: if no tick subscription, poll prices periodically
            if quote_manager is None or not state.portfolio.positions:
                from src.data.sources import create_feed as _create_feed

                async def _price_poll_loop() -> None:
                    """Poll latest prices every 60s when ticks unavailable."""
                    _cached_feed = None
                    _cached_syms: list[str] = []
                    while True:
                        await asyncio.sleep(60)
                        try:
                            syms = sorted(state.portfolio.positions.keys())
                            if not syms:
                                continue
                            # Cache feed, only recreate when symbols change
                            if syms != _cached_syms:
                                _cached_feed = _create_feed(config.data_source, syms)
                                _cached_syms = syms
                            if _cached_feed is not None:
                                realtime_risk.poll_prices_from_feed(_cached_feed)
                        except Exception:
                            logger.debug("Price poll failed", exc_info=True)

                asyncio.create_task(_price_poll_loop())
                logger.info("Price polling fallback started (60s interval)")

            # #12: 每日 NAV snapshot（13:35 台股收盤後）
            async def _daily_nav_snapshot() -> None:
                """每日記錄 NAV snapshot 到 data/paper_trading/snapshots/。"""
                import json as _json
                from pathlib import Path as _Path
                from datetime import datetime as _dt

                snap_dir = _Path("data/paper_trading/snapshots")
                snap_dir.mkdir(parents=True, exist_ok=True)

                while True:
                    await asyncio.sleep(300)  # check every 5 min
                    now = _dt.now()
                    # 只在 13:25-13:55 之間存一次（台股收盤，寬鬆窗口避免 sleep drift）
                    if now.hour == 13 and 25 <= now.minute <= 55:
                        today = now.strftime("%Y-%m-%d")
                        path = snap_dir / f"{today}.json"
                        if not path.exists():
                            snap = {
                                "date": today,
                                "nav": float(state.portfolio.nav),
                                "cash": float(state.portfolio.cash),
                                "positions": {
                                    s: {"qty": float(p.quantity), "price": float(p.market_price)}
                                    for s, p in state.portfolio.positions.items()
                                },
                                "n_positions": len(state.portfolio.positions),
                            }
                            try:
                                path.write_text(_json.dumps(snap, indent=2, ensure_ascii=False))
                                logger.info("Daily NAV snapshot: %s (NAV=%s)", today, snap["nav"])
                            except Exception:
                                logger.debug("NAV snapshot write failed", exc_info=True)

            if config.mode in ("paper", "live"):
                asyncio.create_task(_daily_nav_snapshot())

            logger.info("RealtimeRiskMonitor initialized")

        state.kill_switch_fired = False  # D2: re-trigger guard, accessible via API

        async def _kill_switch_monitor() -> None:
            while True:
                await asyncio.sleep(5)
                try:
                    # D2: skip if already fired (wait for manual reset via API)
                    if state.kill_switch_fired:
                        continue

                    if state.risk_engine.kill_switch(state.portfolio):
                        state.kill_switch_fired = True  # D2: prevent re-trigger

                        # Acquire mutation lock for portfolio changes
                        async with state.mutation_lock:
                            for name in list(state.strategies):
                                state.strategies[name]["status"] = "stopped"
                            state.oms.cancel_all()

                            # Paper/live: generate, submit, and APPLY liquidation orders
                            if config.mode in ("paper", "live") and state.execution_service.is_initialized:
                                liq_orders = state.risk_engine.generate_liquidation_orders(
                                    state.portfolio
                                )
                                if liq_orders:
                                    logger.critical(
                                        "Kill switch: submitting %d liquidation orders",
                                        len(liq_orders),
                                    )
                                    trades = state.execution_service.submit_orders(
                                        liq_orders, state.portfolio
                                    )
                                    if trades:
                                        from src.execution.oms import apply_trades
                                        apply_trades(state.portfolio, trades)
                                        logger.critical(
                                            "Kill switch: %d liquidation trades executed, NAV=%s",
                                            len(trades), state.portfolio.nav,
                                        )

                        await ws_manager.broadcast("alerts", {
                            "type": "kill_switch",
                            "message": "Kill switch triggered — all strategies stopped, positions liquidated",
                        })
                except Exception:
                    logger.warning("Kill switch monitor error", exc_info=True)

        kill_switch_task = asyncio.create_task(_kill_switch_monitor())
        ws_manager.start_ping_task()

        from src.scheduler import SchedulerService
        scheduler = SchedulerService()
        scheduler.start(config)

        yield

        logger.info("Quant Trading System shutting down...")
        scheduler.stop()
        kill_switch_task.cancel()
        ws_manager.stop_ping_task()
        from src.api.state import get_app_state as _get_state
        _get_state().execution_service.shutdown()
        await ws_manager.close_all()

    app = FastAPI(
        title="Quant Trading System",
        description="量化交易平台 API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
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
    app.include_router(auto_alpha.router, prefix="/api/v1")
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

    # ── 全域例外處理器 ──────────────────────────────────
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """捕獲所有未處理的例外，避免洩漏堆疊資訊到客戶端。"""
        logger.error("Unhandled exception: %s %s → %s", request.method, request.url.path, exc, exc_info=True)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    # ── Serve Web 前端靜態檔 ──────────────────────────
    # 若 apps/web/dist 存在，則在 API 之後 mount SPA fallback
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    web_dist = Path(__file__).resolve().parent.parent.parent / "apps" / "web" / "dist"
    if web_dist.is_dir():
        # 靜態資源（JS/CSS/images）
        app.mount("/assets", StaticFiles(directory=str(web_dist / "assets")), name="static-assets")

        # SPA fallback: 所有非 /api 路由回傳 index.html
        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str) -> FileResponse:
            file_path = (web_dist / full_path).resolve()
            if file_path.is_file() and file_path.is_relative_to(web_dist):
                return FileResponse(str(file_path))
            return FileResponse(str(web_dist / "index.html"))

        logger.info("Serving Web frontend from %s", web_dist)

    return app


# uvicorn 入口
app = create_app()
