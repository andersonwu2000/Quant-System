"""WebSocket broadcast optimisation tests."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.ws import ConnectionManager


def _make_ws(*, fail: bool = False, slow: float = 0.0) -> MagicMock:
    """Create a fake WebSocket.

    Args:
        fail: If True, send_text raises an exception.
        slow: If > 0, send_text sleeps this many seconds before returning.
    """
    ws = MagicMock()

    async def _send_text(msg: str) -> None:
        if slow > 0:
            await asyncio.sleep(slow)
        if fail:
            raise ConnectionError("connection closed")

    ws.send_text = AsyncMock(side_effect=_send_text)
    return ws


class TestBroadcastAllClients:
    """broadcast() sends the message to every connected client."""

    @pytest.mark.asyncio
    async def test_sends_to_all(self) -> None:
        manager = ConnectionManager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        ws3 = _make_ws()

        # Manually inject connections (skip accept handshake)
        manager._connections["test"] = [ws1, ws2, ws3]

        await manager.broadcast("test", {"value": 42})

        for ws in [ws1, ws2, ws3]:
            ws.send_text.assert_called_once()
            payload = json.loads(ws.send_text.call_args[0][0])
            assert payload["channel"] == "test"
            assert payload["data"] == {"value": 42}
            assert payload["type"] == "update"


class TestBroadcastDeadConnection:
    """Dead connections are removed after a failed send."""

    @pytest.mark.asyncio
    async def test_dead_connection_removed(self) -> None:
        manager = ConnectionManager()
        ws_good = _make_ws()
        ws_dead = _make_ws(fail=True)

        manager._connections["alerts"] = [ws_good, ws_dead]

        await manager.broadcast("alerts", {"alert": "test"})

        # Good client received the message
        ws_good.send_text.assert_called_once()

        # Dead client was removed
        assert ws_dead not in manager._connections["alerts"]
        assert ws_good in manager._connections["alerts"]
        assert len(manager._connections["alerts"]) == 1


class TestBroadcastSlowClientTimeout:
    """A slow client that exceeds the 5-second timeout is treated as dead."""

    @pytest.mark.asyncio
    async def test_slow_client_times_out(self) -> None:
        manager = ConnectionManager()
        ws_fast = _make_ws()
        # Simulate a client that takes 10 seconds — should exceed the 5s timeout
        ws_slow = _make_ws(slow=10.0)

        manager._connections["portfolio"] = [ws_fast, ws_slow]

        await manager.broadcast("portfolio", {"nav": 1000000})

        # Fast client received the message
        ws_fast.send_text.assert_called_once()

        # Slow client was removed due to timeout
        assert ws_slow not in manager._connections["portfolio"]
        assert ws_fast in manager._connections["portfolio"]
