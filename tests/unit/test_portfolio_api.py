"""Unit tests for portfolio CRUD API routes.

Uses httpx.AsyncClient with in-memory SQLite to avoid external dependencies.
"""

from __future__ import annotations

from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import create_app
from src.api.state import reset_app_state
from src.config import TradingConfig, override_config

API_KEY = "test-portfolio-key"
AUTH_HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset config and state before each test."""
    reset_app_state()
    from src.api.routes.portfolio import reset_portfolio_engine
    reset_portfolio_engine()
    override_config(
        TradingConfig(
            env="dev",
            api_key=API_KEY,
            jwt_secret="test-secret",
            database_url="sqlite:///:memory:",
        )
    )

    from src.api.app import limiter
    limiter.enabled = False
    yield
    limiter.enabled = True
    reset_portfolio_engine()
    reset_app_state()


@pytest.fixture()
def app():
    return create_app()


@pytest.fixture()
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ─── Portfolio CRUD ──────────────────────────────────────


@pytest.mark.asyncio
async def test_create_portfolio(client: AsyncClient):
    resp = await client.post(
        "/api/v1/portfolio/saved",
        json={"name": "Test Portfolio", "initial_cash": 5000000, "strategy_name": "momentum"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Portfolio"
    assert data["cash"] == 5000000.0
    assert data["initial_cash"] == 5000000.0
    assert data["strategy_name"] == "momentum"
    assert data["nav"] == 5000000.0
    assert data["positions"] == []
    assert "id" in data


@pytest.mark.asyncio
async def test_list_portfolios(client: AsyncClient):
    # Create two portfolios
    await client.post(
        "/api/v1/portfolio/saved",
        json={"name": "Port A"},
        headers=AUTH_HEADERS,
    )
    await client.post(
        "/api/v1/portfolio/saved",
        json={"name": "Port B"},
        headers=AUTH_HEADERS,
    )

    resp = await client.get("/api/v1/portfolio/saved", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["portfolios"]) == 2


@pytest.mark.asyncio
async def test_get_portfolio_by_id(client: AsyncClient):
    create_resp = await client.post(
        "/api/v1/portfolio/saved",
        json={"name": "Get Test", "initial_cash": 3000000},
        headers=AUTH_HEADERS,
    )
    pid = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/portfolio/saved/{pid}", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == pid
    assert data["name"] == "Get Test"
    assert data["cash"] == 3000000.0


@pytest.mark.asyncio
async def test_get_portfolio_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/portfolio/saved/nonexistent", headers=AUTH_HEADERS)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_portfolio(client: AsyncClient):
    create_resp = await client.post(
        "/api/v1/portfolio/saved",
        json={"name": "To Delete"},
        headers=AUTH_HEADERS,
    )
    pid = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/portfolio/saved/{pid}", headers=AUTH_HEADERS)
    assert del_resp.status_code == 200

    get_resp = await client.get(f"/api/v1/portfolio/saved/{pid}", headers=AUTH_HEADERS)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_portfolio_not_found(client: AsyncClient):
    resp = await client.delete("/api/v1/portfolio/saved/nonexistent", headers=AUTH_HEADERS)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_trades_empty(client: AsyncClient):
    create_resp = await client.post(
        "/api/v1/portfolio/saved",
        json={"name": "Trades Test"},
        headers=AUTH_HEADERS,
    )
    pid = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/portfolio/saved/{pid}/trades", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_legacy_portfolio_endpoint(client: AsyncClient):
    """Ensure the existing in-memory portfolio endpoint still works."""
    resp = await client.get("/api/v1/portfolio", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "nav" in data
    assert "cash" in data
    assert "positions" in data
