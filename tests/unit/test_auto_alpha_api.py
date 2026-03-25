"""Unit tests for Auto-Alpha API routes.

Uses httpx.AsyncClient with in-memory state to avoid external dependencies.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from src.alpha.auto.config import AlphaAlert, FactorScore, ResearchSnapshot
from src.alpha.regime import MarketRegime
from src.api.app import create_app
from src.api.state import get_app_state, reset_app_state
from src.config import TradingConfig, override_config

API_KEY = "test-auto-alpha-key"
AUTH_HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture(autouse=True)
def _reset_state(tmp_path: Path):
    """Reset config and state before each test."""
    reset_app_state()
    override_config(
        TradingConfig(
            env="dev",
            api_key=API_KEY,
            jwt_secret="test-secret",
            database_url="sqlite:///:memory:",
        )
    )
    # Use tmp_path for AlphaStore to avoid file leaks between tests
    from src.alpha.auto.store import AlphaStore

    state = get_app_state()
    state.alpha_store = AlphaStore(db_path=str(tmp_path / "test_alpha.json"))

    from src.api.app import limiter

    limiter.enabled = False
    yield
    limiter.enabled = True
    reset_app_state()


@pytest.fixture()
def app():
    return create_app()


@pytest.fixture()
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── GET /config ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_config(client: AsyncClient):
    resp = await client.get("/api/v1/auto-alpha/config", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["schedule"] == "50 8 * * 1-5"
    assert data["universe_count"] == 150
    assert data["lookback"] == 252
    assert "decision" in data
    assert data["decision"]["min_icir"] == 0.3


# ── PUT /config ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_config(client: AsyncClient):
    resp = await client.put(
        "/api/v1/auto-alpha/config",
        json={"universe_count": 200, "lookback": 120},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["universe_count"] == 200
    assert data["lookback"] == 120
    # Other fields unchanged
    assert data["schedule"] == "50 8 * * 1-5"


@pytest.mark.asyncio
async def test_update_config_decision(client: AsyncClient):
    resp = await client.put(
        "/api/v1/auto-alpha/config",
        json={"decision": {"min_icir": 0.5, "regime_aware": False}},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"]["min_icir"] == 0.5
    assert data["decision"]["regime_aware"] is False


# ── POST /start and /stop ────────────────────────────────────


@pytest.mark.asyncio
async def test_start_and_stop(client: AsyncClient):
    # Start
    resp = await client.post("/api/v1/auto-alpha/start", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert "started" in resp.json()["message"]

    # Starting again should conflict
    resp = await client.post("/api/v1/auto-alpha/start", headers=AUTH_HEADERS)
    assert resp.status_code == 409

    # Stop
    resp = await client.post("/api/v1/auto-alpha/stop", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert "stopped" in resp.json()["message"]

    # Stopping again should conflict
    resp = await client.post("/api/v1/auto-alpha/stop", headers=AUTH_HEADERS)
    assert resp.status_code == 409


# ── GET /status ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_status_stopped(client: AsyncClient):
    resp = await client.get("/api/v1/auto-alpha/status", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["running"] is False
    assert data["status"] == "stopped"


@pytest.mark.asyncio
async def test_status_running(client: AsyncClient):
    # Start first
    await client.post("/api/v1/auto-alpha/start", headers=AUTH_HEADERS)
    resp = await client.get("/api/v1/auto-alpha/status", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["running"] is True
    assert data["status"] == "running"


# ── GET /history ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_history_empty(client: AsyncClient):
    resp = await client.get("/api/v1/auto-alpha/history", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_history_with_snapshots(client: AsyncClient):
    state = get_app_state()
    snap = ResearchSnapshot(
        date=date(2026, 3, 25),
        regime=MarketRegime.BULL,
        universe=["2330", "2317"],
        universe_size=2,
        selected_factors=["momentum", "value_pe"],
        factor_weights={"momentum": 0.6, "value_pe": 0.4},
        target_weights={"2330": 0.5, "2317": 0.5},
        trades_count=2,
        turnover=0.15,
    )
    state.alpha_store.save_snapshot(snap)

    resp = await client.get("/api/v1/auto-alpha/history?limit=10", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["date"] == "2026-03-25"
    assert data[0]["regime"] == "bull"
    assert data[0]["selected_factors"] == ["momentum", "value_pe"]


# ── GET /history/{date} ──────────────────────────────────────


@pytest.mark.asyncio
async def test_history_by_date_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/auto-alpha/history/2026-01-01", headers=AUTH_HEADERS)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_history_by_date_found(client: AsyncClient):
    state = get_app_state()
    snap = ResearchSnapshot(
        date=date(2026, 3, 26),
        regime=MarketRegime.SIDEWAYS,
        universe=["2330"],
        universe_size=1,
        selected_factors=["rsi"],
        factor_weights={"rsi": 1.0},
        factor_scores={
            "rsi": FactorScore(
                name="rsi", ic=0.03, icir=0.5, hit_rate=0.55,
                decay_half_life=5, turnover=0.1, cost_drag_bps=50.0,
                eligible=True,
            )
        },
        target_weights={"2330": 1.0},
    )
    state.alpha_store.save_snapshot(snap)

    resp = await client.get("/api/v1/auto-alpha/history/2026-03-26", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] == "2026-03-26"
    assert data["universe"] == ["2330"]
    assert "rsi" in data["factor_scores"]


# ── GET /performance ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_performance_empty(client: AsyncClient):
    resp = await client.get("/api/v1/auto-alpha/performance", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_days"] == 0
    assert data["cumulative_return"] == 0.0


# ── GET /alerts ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_alerts_empty(client: AsyncClient):
    resp = await client.get("/api/v1/auto-alpha/alerts", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_alerts_with_data(client: AsyncClient):
    state = get_app_state()
    alert = AlphaAlert(
        timestamp=datetime(2026, 3, 25, 8, 50),
        level="warning",
        category="regime",
        message="Market regime changed from sideways to bull",
        details={"old": "sideways", "new": "bull"},
    )
    state.alpha_store.save_alert(alert)

    resp = await client.get("/api/v1/auto-alpha/alerts?limit=10", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["level"] == "warning"
    assert data[0]["category"] == "regime"


# ── POST /run-now ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_now(client: AsyncClient):
    resp = await client.post("/api/v1/auto-alpha/run-now", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "task_id" in data
    assert data["message"] == "Auto-alpha cycle started in background"


# ── Auth required ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_endpoints_require_auth(client: AsyncClient):
    """All endpoints should reject requests without auth."""
    endpoints = [
        ("GET", "/api/v1/auto-alpha/config"),
        ("GET", "/api/v1/auto-alpha/status"),
        ("GET", "/api/v1/auto-alpha/history"),
        ("GET", "/api/v1/auto-alpha/performance"),
        ("GET", "/api/v1/auto-alpha/alerts"),
    ]
    for method, path in endpoints:
        resp = await client.request(method, path)
        assert resp.status_code == 401, f"{method} {path} should require auth"
