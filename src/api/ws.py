"""
WebSocket 管理 — 即時推送持倉、PnL、告警。
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


MAX_CONNECTIONS_PER_CHANNEL = 200
SERVER_PING_INTERVAL = 30  # 秒：伺服器端 ping 間隔
SERVER_PING_TIMEOUT = 10   # 秒：等待 pong 的超時


class ConnectionManager:
    """管理所有 WebSocket 連線。"""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}  # channel → connections
        self._ping_task: asyncio.Task[None] | None = None

    def start_ping_task(self) -> None:
        """啟動伺服器端 ping 背景任務，主動偵測死連線。"""
        if self._ping_task is None or self._ping_task.done():
            self._ping_task = asyncio.create_task(self._server_ping_loop())

    def stop_ping_task(self) -> None:
        """停止伺服器端 ping 背景任務。"""
        if self._ping_task and not self._ping_task.done():
            self._ping_task.cancel()

    async def _server_ping_loop(self) -> None:
        """每隔 SERVER_PING_INTERVAL 秒向所有連線發送 ping，清理未回應的死連線。"""
        while True:
            await asyncio.sleep(SERVER_PING_INTERVAL)
            for channel in list(self._connections.keys()):
                clients = list(self._connections.get(channel, []))
                if not clients:
                    continue
                dead: set[WebSocket] = set()
                for ws in clients:
                    try:
                        await asyncio.wait_for(
                            ws.send_text("ping"),
                            timeout=SERVER_PING_TIMEOUT,
                        )
                    except Exception:
                        dead.add(ws)
                if dead:
                    self._connections[channel] = [
                        ws for ws in self._connections.get(channel, [])
                        if ws not in dead
                    ]
                    logger.info(
                        "Server ping cleaned %d dead connections on channel=%s",
                        len(dead), channel,
                    )

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        await websocket.accept()
        conns = self._connections.setdefault(channel, [])
        # 防止同一 WebSocket 重複加入
        if websocket not in conns:
            # 限制每個 channel 的最大連線數
            if len(conns) >= MAX_CONNECTIONS_PER_CHANNEL:
                logger.warning("WS channel=%s reached max connections (%d), rejecting", channel, MAX_CONNECTIONS_PER_CHANNEL)
                await websocket.close(code=4002, reason="Too many connections")
                return
            conns.append(websocket)
        logger.info("WS connected: channel=%s, total=%d", channel, len(conns))

    def disconnect(self, websocket: WebSocket, channel: str) -> None:
        if channel in self._connections:
            self._connections[channel] = [
                ws for ws in self._connections[channel] if ws != websocket
            ]
            logger.info("WS disconnected: channel=%s", channel)

    _broadcast_in_progress: dict[str, bool] = {}

    async def broadcast(self, channel: str, data: dict[str, Any]) -> None:
        """向指定頻道的所有連線推送數據。

        Pre-serializes JSON once, sends to all clients in parallel via
        asyncio.gather, and cleans up dead/slow connections.

        Backpressure: if a broadcast for this channel is already in progress,
        the new message is dropped (latest-wins for high-frequency updates).
        """
        if channel not in self._connections:
            return

        # Backpressure: skip if previous broadcast still in progress
        if self._broadcast_in_progress.get(channel, False):
            logger.debug("WS broadcast backpressure: dropping message for channel=%s", channel)
            return

        self._broadcast_in_progress[channel] = True
        try:
            # Pre-serialize once for all clients
            message = json.dumps({
                "type": "update",
                "channel": channel,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": data,
            })

            clients = list(self._connections[channel])
            if not clients:
                return

            # Batch sends: limit concurrency to avoid memory spike
            BATCH_SIZE = 50
            dead: set[WebSocket] = set()

            async def _send(ws: WebSocket) -> WebSocket | None:
                """Send to a single client; return ws on failure for cleanup."""
                try:
                    await asyncio.wait_for(ws.send_text(message), timeout=5.0)
                    return None
                except Exception:
                    logger.debug("WS send failed for channel=%s", channel, exc_info=True)
                    return ws

            for i in range(0, len(clients), BATCH_SIZE):
                batch = clients[i:i + BATCH_SIZE]
                results = await asyncio.gather(*[_send(ws) for ws in batch])
                dead.update(ws for ws in results if ws is not None)

            # 清理斷開或超時的連線
            if dead:
                self._connections[channel] = [
                    ws for ws in self._connections[channel] if ws not in dead
                ]
        finally:
            self._broadcast_in_progress[channel] = False

    async def send_alert(self, data: dict[str, Any]) -> None:
        """推送告警到 alerts 頻道。"""
        await self.broadcast("alerts", data)

    # Market channel: SinopacQuoteManager feeds tick data via broadcast("market", {...}).
    # Integration point: sinopac_quote.py → to_ws_payload() → broadcast.
    # Requires Shioaji API key for live connection.

    async def close_all(self) -> None:
        """關閉所有連線（優雅關機用），每個連線最多等 3 秒。"""
        for channel, connections in self._connections.items():
            for ws in connections:
                try:
                    await asyncio.wait_for(ws.send_text('{"type":"shutdown"}'), timeout=3.0)
                    await asyncio.wait_for(ws.close(), timeout=3.0)
                except Exception:
                    pass
            logger.info("Closed %d connections on channel=%s", len(connections), channel)
        self._connections.clear()

    @property
    def connection_count(self) -> int:
        return sum(len(conns) for conns in self._connections.values())


# 全局實例
ws_manager = ConnectionManager()
