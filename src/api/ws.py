"""
WebSocket 管理 — 即時推送持倉、PnL、告警。
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """管理所有 WebSocket 連線。"""

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}  # channel → connections

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        await websocket.accept()
        self._connections.setdefault(channel, []).append(websocket)
        logger.info("WS connected: channel=%s, total=%d", channel, len(self._connections[channel]))

    def disconnect(self, websocket: WebSocket, channel: str) -> None:
        if channel in self._connections:
            self._connections[channel] = [
                ws for ws in self._connections[channel] if ws != websocket
            ]
            logger.info("WS disconnected: channel=%s", channel)

    async def broadcast(self, channel: str, data: dict) -> None:
        """向指定頻道的所有連線推送數據。"""
        if channel not in self._connections:
            return

        message = json.dumps({
            "type": "update",
            "channel": channel,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        })

        dead: list[WebSocket] = []
        for ws in self._connections[channel]:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        # 清理斷開的連線
        for ws in dead:
            self._connections[channel].remove(ws)

    async def send_alert(self, data: dict) -> None:
        """推送告警到 alerts 頻道。"""
        await self.broadcast("alerts", data)

    @property
    def connection_count(self) -> int:
        return sum(len(conns) for conns in self._connections.values())


# 全局實例
ws_manager = ConnectionManager()
