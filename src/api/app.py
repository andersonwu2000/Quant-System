"""
FastAPI Application — 量化交易系統的 API 入口。
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import backtest, orders, portfolio, risk, strategies, system
from src.api.ws import ws_manager
from src.config import get_config

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """建立 FastAPI 應用。"""
    config = get_config()

    app = FastAPI(
        title="Quant Trading System",
        description="量化交易平台 API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — 允許前端跨域存取
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生產環境應限縮
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 註冊路由
    app.include_router(portfolio.router, prefix="/api/v1")
    app.include_router(strategies.router, prefix="/api/v1")
    app.include_router(orders.router, prefix="/api/v1")
    app.include_router(backtest.router, prefix="/api/v1")
    app.include_router(risk.router, prefix="/api/v1")
    app.include_router(system.router, prefix="/api/v1")

    # WebSocket 端點
    @app.websocket("/ws/{channel}")
    async def websocket_endpoint(websocket: WebSocket, channel: str):
        """WebSocket 連線端點。支持頻道：portfolio, alerts, orders"""
        valid_channels = {"portfolio", "alerts", "orders", "market"}
        if channel not in valid_channels:
            await websocket.close(code=4000, reason=f"Invalid channel: {channel}")
            return

        await ws_manager.connect(websocket, channel)
        try:
            while True:
                data = await websocket.receive_text()
                # 處理客戶端訊息（目前只用於 keepalive）
                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket, channel)

    @app.on_event("startup")
    async def startup():
        logger.info("Quant Trading System starting (mode=%s)", config.mode)
        # 初始化策略列表
        from src.api.state import get_app_state
        state = get_app_state()
        state.strategies = {
            "momentum_12_1": {"status": "stopped", "pnl": 0.0},
            "mean_reversion": {"status": "stopped", "pnl": 0.0},
        }

    return app


# uvicorn 入口
app = create_app()
