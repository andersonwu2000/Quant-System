"""
WebSocket 管理 — 即時推送持倉、PnL、告警。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """管理所有 WebSocket 連線。"""

    def __init__(self) -> None:
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

    async def broadcast(self, channel: str, data: dict[str, Any]) -> None:
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
        for ws in list(self._connections[channel]):  # iterate a copy
            try:
                await ws.send_text(message)
            except Exception:
                logger.debug("WS send failed for channel=%s", channel, exc_info=True)
                dead.append(ws)

        # 清理斷開的連線
        if dead:
            self._connections[channel] = [
                ws for ws in self._connections[channel] if ws not in dead
            ]

    async def send_alert(self, data: dict[str, Any]) -> None:
        """推送告警到 alerts 頻道。"""
        await self.broadcast("alerts", data)

    async def close_all(self) -> None:
        """關閉所有連線（優雅關機用）。"""
        for channel, connections in self._connections.items():
            for ws in connections:
                try:
                    await ws.send_text('{"type":"shutdown"}')
                    await ws.close()
                except Exception:
                    pass
            logger.info("Closed %d connections on channel=%s", len(connections), channel)
        self._connections.clear()

    @property
    def connection_count(self) -> int:
        return sum(len(conns) for conns in self._connections.values())


# 全局實例
ws_manager = ConnectionManager()
