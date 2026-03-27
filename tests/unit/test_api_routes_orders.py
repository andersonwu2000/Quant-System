"""Unit tests for Order management API routes.

Tests order submission, cancellation, listing, and update endpoints
using httpx AsyncClient + ASGITransport.
"""

from __future__ import annotations

from decimal import Decimal
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import create_app
from src.api.state import get_app_state, reset_app_state
from src.core.config import TradingConfig, override_config
from src.core.models import Instrument, Order, OrderStatus, OrderType, Side

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

API_KEY = "test-orders-key"
AUTH_HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset app state, config, and rate limiter before each test."""
    reset_app_state()
    override_config(
        TradingConfig(
            env="dev",
            api_key=API_KEY,
            jwt_secret="test-secret-orders",
            database_url="sqlite:///test.db",
        )
    )

    from src.data import user_store as _us_mod
    _us_mod._user_store = None
    _us_mod._engine = None

    from src.api.app import limiter
    from src.api.routes.auth import _login_limiter
    limiter.enabled = False
    _login_limiter.enabled = False

    yield

    limiter.enabled = True
    _login_limiter.enabled = True
    _us_mod._user_store = None
    _us_mod._engine = None
    reset_app_state()


@pytest.fixture()
def app():
    return create_app()


@pytest.fixture()
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ===========================================================================
# 1. List orders
# ===========================================================================


class TestListOrders:
    """Tests for GET /orders endpoint."""

    @pytest.mark.asyncio
    async def test_list_orders_empty(self, client: AsyncClient):
        """Empty OMS returns empty list."""
        resp = await client.get("/api/v1/orders", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 0

    @pytest.mark.asyncio
    async def test_list_orders_with_orders(self, client: AsyncClient):
        """OMS with seeded orders returns them."""
        state = get_app_state()
        order = Order(
            instrument=Instrument(symbol="AAPL"),
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("100"),
            price=Decimal("150"),
            status=OrderStatus.SUBMITTED,
            strategy_id="manual",
        )
        state.oms.submit(order)

        resp = await client.get("/api/v1/orders", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["symbol"] == "AAPL"
        assert body[0]["side"] == "BUY"
        assert body[0]["quantity"] == 100.0
        assert body[0]["status"] == "SUBMITTED"

    @pytest.mark.asyncio
    async def test_list_orders_filter_open(self, client: AsyncClient):
        """Filter by status=open returns only non-terminal orders."""
        state = get_app_state()

        open_order = Order(
            instrument=Instrument(symbol="AAPL"),
            side=Side.BUY,
            quantity=Decimal("100"),
            status=OrderStatus.SUBMITTED,
            strategy_id="manual",
        )
        filled_order = Order(
            instrument=Instrument(symbol="MSFT"),
            side=Side.SELL,
            quantity=Decimal("50"),
            filled_qty=Decimal("50"),
            strategy_id="manual",
        )
        state.oms.submit(open_order)
        state.oms.submit(filled_order)
        # submit() resets status to SUBMITTED, so manually set after submit
        filled_order.status = OrderStatus.FILLED

        resp = await client.get(
            "/api/v1/orders", params={"status": "open"}, headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_list_orders_filter_filled(self, client: AsyncClient):
        """Filter by status=filled returns only filled orders."""
        state = get_app_state()

        open_order = Order(
            instrument=Instrument(symbol="AAPL"),
            side=Side.BUY,
            quantity=Decimal("100"),
            strategy_id="manual",
        )
        filled_order = Order(
            instrument=Instrument(symbol="MSFT"),
            side=Side.SELL,
            quantity=Decimal("50"),
            filled_qty=Decimal("50"),
            strategy_id="manual",
        )
        state.oms.submit(open_order)
        state.oms.submit(filled_order)
        # submit() resets status to SUBMITTED, so manually set after submit
        filled_order.status = OrderStatus.FILLED

        resp = await client.get(
            "/api/v1/orders", params={"status": "filled"}, headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["symbol"] == "MSFT"

    @pytest.mark.asyncio
    async def test_list_orders_pagination(self, client: AsyncClient):
        """Pagination with limit and offset works."""
        state = get_app_state()
        for i in range(5):
            order = Order(
                instrument=Instrument(symbol=f"SYM{i}"),
                side=Side.BUY,
                quantity=Decimal("10"),
                status=OrderStatus.SUBMITTED,
                strategy_id="manual",
            )
            state.oms.submit(order)

        resp = await client.get(
            "/api/v1/orders",
            params={"limit": 2, "offset": 1},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2

    @pytest.mark.asyncio
    async def test_list_orders_no_auth(self, client: AsyncClient):
        """Without auth returns 401."""
        resp = await client.get("/api/v1/orders")
        assert resp.status_code == 401


# ===========================================================================
# 2. Create order
# ===========================================================================


class TestCreateOrder:
    """Tests for POST /orders endpoint."""

    @pytest.mark.asyncio
    async def test_create_market_order(self, client: AsyncClient):
        """Create market order (no price) succeeds."""
        payload = {
            "symbol": "AAPL",
            "side": "BUY",
            "quantity": 100,
        }
        resp = await client.post("/api/v1/orders", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "AAPL"
        assert body["side"] == "BUY"
        assert body["quantity"] == 100.0
        assert body["price"] is None
        assert body["strategy_id"] == "manual"

    @pytest.mark.asyncio
    async def test_create_limit_order(self, client: AsyncClient):
        """Create limit order with price succeeds."""
        payload = {
            "symbol": "MSFT",
            "side": "SELL",
            "quantity": 50,
            "price": 400.0,
        }
        resp = await client.post("/api/v1/orders", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbol"] == "MSFT"
        assert body["side"] == "SELL"
        assert body["price"] == 400.0

    @pytest.mark.asyncio
    async def test_create_order_symbol_uppercased(self, client: AsyncClient):
        """Symbol is uppercased in the created order."""
        payload = {
            "symbol": "aapl",
            "side": "BUY",
            "quantity": 10,
        }
        resp = await client.post("/api/v1/orders", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_create_order_no_auth(self, client: AsyncClient):
        """Create without auth returns 401."""
        payload = {"symbol": "AAPL", "side": "BUY", "quantity": 100}
        resp = await client.post("/api/v1/orders", json=payload)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_order_missing_fields(self, client: AsyncClient):
        """Missing required fields returns 422."""
        resp = await client.post(
            "/api/v1/orders",
            json={"symbol": "AAPL"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_order_invalid_side(self, client: AsyncClient):
        """Invalid side value raises ValueError (unhandled enum conversion)."""
        payload = {"symbol": "AAPL", "side": "INVALID", "quantity": 100}
        with pytest.raises(ValueError, match="not a valid Side"):
            await client.post("/api/v1/orders", json=payload, headers=AUTH_HEADERS)


# ===========================================================================
# 3. Cancel order
# ===========================================================================


class TestCancelOrder:
    """Tests for DELETE /orders/{order_id} endpoint."""

    @pytest.mark.asyncio
    async def test_cancel_order_success(self, client: AsyncClient):
        """Cancel an open order succeeds."""
        state = get_app_state()
        order = Order(
            instrument=Instrument(symbol="AAPL"),
            side=Side.BUY,
            quantity=Decimal("100"),
            status=OrderStatus.SUBMITTED,
            strategy_id="manual",
        )
        state.oms.submit(order)
        order_id = order.id

        resp = await client.delete(f"/api/v1/orders/{order_id}", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "CANCELLED"
        assert body["id"] == order_id

    @pytest.mark.asyncio
    async def test_cancel_order_not_found(self, client: AsyncClient):
        """Cancel non-existent order returns 404."""
        resp = await client.delete("/api/v1/orders/nonexistent", headers=AUTH_HEADERS)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_already_filled(self, client: AsyncClient):
        """Cancel already filled order returns 400."""
        state = get_app_state()
        order = Order(
            instrument=Instrument(symbol="AAPL"),
            side=Side.BUY,
            quantity=Decimal("100"),
            filled_qty=Decimal("100"),
            strategy_id="manual",
        )
        state.oms.submit(order)
        # submit() resets to SUBMITTED; set terminal status after
        order.status = OrderStatus.FILLED
        order_id = order.id

        resp = await client.delete(f"/api/v1/orders/{order_id}", headers=AUTH_HEADERS)
        assert resp.status_code == 400
        assert "cannot cancel" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_cancel_already_cancelled(self, client: AsyncClient):
        """Cancel already cancelled order returns 400."""
        state = get_app_state()
        order = Order(
            instrument=Instrument(symbol="AAPL"),
            side=Side.BUY,
            quantity=Decimal("100"),
            strategy_id="manual",
        )
        state.oms.submit(order)
        # submit() resets to SUBMITTED; set terminal status after
        order.status = OrderStatus.CANCELLED
        order_id = order.id

        resp = await client.delete(f"/api/v1/orders/{order_id}", headers=AUTH_HEADERS)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_cancel_no_auth(self, client: AsyncClient):
        """Cancel without auth returns 401."""
        resp = await client.delete("/api/v1/orders/someorder")
        assert resp.status_code == 401


# ===========================================================================
# 4. Update order
# ===========================================================================


class TestUpdateOrder:
    """Tests for PUT /orders/{order_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_order_price(self, client: AsyncClient):
        """Update order price succeeds."""
        state = get_app_state()
        order = Order(
            instrument=Instrument(symbol="AAPL"),
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("100"),
            price=Decimal("150"),
            status=OrderStatus.SUBMITTED,
            strategy_id="manual",
        )
        state.oms.submit(order)
        order_id = order.id

        resp = await client.put(
            f"/api/v1/orders/{order_id}",
            json={"price": 155.0},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["price"] == 155.0

    @pytest.mark.asyncio
    async def test_update_order_quantity(self, client: AsyncClient):
        """Update order quantity succeeds."""
        state = get_app_state()
        order = Order(
            instrument=Instrument(symbol="AAPL"),
            side=Side.BUY,
            quantity=Decimal("100"),
            price=Decimal("150"),
            status=OrderStatus.SUBMITTED,
            strategy_id="manual",
        )
        state.oms.submit(order)
        order_id = order.id

        resp = await client.put(
            f"/api/v1/orders/{order_id}",
            json={"quantity": 200.0},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["quantity"] == 200.0

    @pytest.mark.asyncio
    async def test_update_order_not_found(self, client: AsyncClient):
        """Update non-existent order returns 404."""
        resp = await client.put(
            "/api/v1/orders/nonexistent",
            json={"price": 100.0},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_filled_order(self, client: AsyncClient):
        """Update filled order returns 400."""
        state = get_app_state()
        order = Order(
            instrument=Instrument(symbol="AAPL"),
            side=Side.BUY,
            quantity=Decimal("100"),
            filled_qty=Decimal("100"),
            strategy_id="manual",
        )
        state.oms.submit(order)
        # submit() resets to SUBMITTED; set terminal status after
        order.status = OrderStatus.FILLED
        order_id = order.id

        resp = await client.put(
            f"/api/v1/orders/{order_id}",
            json={"price": 160.0},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_update_no_auth(self, client: AsyncClient):
        """Update without auth returns 401."""
        resp = await client.put(
            "/api/v1/orders/someorder",
            json={"price": 100.0},
        )
        assert resp.status_code == 401
