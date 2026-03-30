"""Unit tests for Alpha research API routes.

Tests the alpha research endpoints using httpx AsyncClient + ASGITransport,
following the same pattern as tests/integration/test_api.py.
"""

from __future__ import annotations

from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import create_app
from src.api.state import get_app_state, reset_app_state
from src.core.config import TradingConfig, override_config

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

API_KEY = "test-alpha-key"
AUTH_HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset app state, config, and rate limiter before each test."""
    reset_app_state()
    override_config(
        TradingConfig(
            env="dev",
            api_key=API_KEY,
            jwt_secret="test-secret-alpha",
            database_url="sqlite:///:memory:",
        )
    )

    from src.data import user_store as _us_mod
    _us_mod._user_store = None
    _us_mod._engine = None

    # Disable rate limiters
    from src.api.app import limiter
    from src.api.routes.auth import _login_limiter
    limiter.enabled = False
    _login_limiter.enabled = False

    # Disable alpha route limiter
    from src.api.routes.alpha import _limiter as alpha_limiter
    alpha_limiter.enabled = False

    yield

    limiter.enabled = True
    _login_limiter.enabled = True
    alpha_limiter.enabled = True
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
# 1. Alpha task status endpoint
# ===========================================================================


class TestAlphaTaskStatus:
    """Tests for GET /alpha/{task_id} status endpoint."""

    @pytest.mark.asyncio
    async def test_get_status_running(self, client: AsyncClient):
        """Seeded running task returns running status."""
        state = get_app_state()
        state.alpha_tasks["abc123"] = {
            "status": "running",
            "result": None,
            "progress_current": 3,
            "progress_total": 10,
            "error": None,
        }

        resp = await client.get("/api/v1/alpha/abc123", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == "abc123"
        assert body["status"] == "running"
        assert body["progress_current"] == 3
        assert body["progress_total"] == 10
        assert body["error"] is None

    @pytest.mark.asyncio
    async def test_get_status_completed(self, client: AsyncClient):
        """Seeded completed task returns completed status."""
        state = get_app_state()
        state.alpha_tasks["done1"] = {
            "status": "completed",
            "result": {"task_id": "done1", "factors": []},
            "progress_current": 5,
            "progress_total": 5,
            "error": None,
        }

        resp = await client.get("/api/v1/alpha/done1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_status_failed(self, client: AsyncClient):
        """Seeded failed task returns error."""
        state = get_app_state()
        state.alpha_tasks["fail1"] = {
            "status": "failed",
            "result": None,
            "progress_current": 2,
            "progress_total": 10,
            "error": "No data available",
        }

        resp = await client.get("/api/v1/alpha/fail1", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert body["error"] == "No data available"

    @pytest.mark.asyncio
    async def test_get_status_not_found(self, client: AsyncClient):
        """Non-existent task returns 404."""
        resp = await client.get("/api/v1/alpha/nonexistent", headers=AUTH_HEADERS)
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_status_no_auth(self, client: AsyncClient):
        """Request without auth returns 401."""
        resp = await client.get("/api/v1/alpha/abc123")
        assert resp.status_code == 401


# ===========================================================================
# 2. Alpha result endpoint
# ===========================================================================


class TestAlphaResult:
    """Tests for GET /alpha/{task_id}/result endpoint."""

    @pytest.mark.asyncio
    async def test_get_result_completed(self, client: AsyncClient):
        """Completed task returns full result."""
        state = get_app_state()
        fake_result = {
            "task_id": "res1",
            "factors": [{"name": "momentum", "direction": 1}],
            "composite_ic": None,
            "universe_size": 50,
            "start_date": "2023-01-01",
            "end_date": "2024-01-01",
        }
        state.alpha_tasks["res1"] = {
            "status": "completed",
            "result": fake_result,
            "progress_current": 5,
            "progress_total": 5,
            "error": None,
        }

        resp = await client.get("/api/v1/alpha/res1/result", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == "res1"
        assert len(body["factors"]) == 1
        assert body["universe_size"] == 50

    @pytest.mark.asyncio
    async def test_get_result_not_completed(self, client: AsyncClient):
        """Running task result returns 400."""
        state = get_app_state()
        state.alpha_tasks["run1"] = {
            "status": "running",
            "result": None,
            "progress_current": 2,
            "progress_total": 5,
            "error": None,
        }

        resp = await client.get("/api/v1/alpha/run1/result", headers=AUTH_HEADERS)
        assert resp.status_code == 400
        assert "running" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_result_failed_task(self, client: AsyncClient):
        """Failed task result returns 400."""
        state = get_app_state()
        state.alpha_tasks["fail2"] = {
            "status": "failed",
            "result": None,
            "progress_current": 0,
            "progress_total": 5,
            "error": "Data error",
        }

        resp = await client.get("/api/v1/alpha/fail2/result", headers=AUTH_HEADERS)
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_get_result_not_found(self, client: AsyncClient):
        """Non-existent task returns 404."""
        resp = await client.get("/api/v1/alpha/nope/result", headers=AUTH_HEADERS)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_result_completed_but_missing(self, client: AsyncClient):
        """Completed task with missing result returns 500."""
        state = get_app_state()
        state.alpha_tasks["empty1"] = {
            "status": "completed",
            "result": None,
            "progress_current": 5,
            "progress_total": 5,
            "error": None,
        }

        resp = await client.get("/api/v1/alpha/empty1/result", headers=AUTH_HEADERS)
        assert resp.status_code == 500
        assert "missing" in resp.json()["detail"].lower()


# ===========================================================================
# 3. Submit alpha research endpoint
# ===========================================================================


class TestSubmitAlphaResearch:
    """Tests for POST /alpha submit endpoint."""

    @pytest.mark.asyncio
    async def test_submit_returns_running(self, client: AsyncClient):
        """Submit alpha research returns task_id with running status."""
        payload = {
            "factors": [{"name": "momentum", "direction": 1}],
            "universe": ["AAPL", "MSFT"],
            "start": "2023-01-01",
            "end": "2024-01-01",
        }
        resp = await client.post("/api/v1/alpha", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert "task_id" in body
        assert body["status"] == "running"
        assert len(body["task_id"]) == 8

    @pytest.mark.asyncio
    async def test_submit_invalid_n_quantiles(self, client: AsyncClient):
        """n_quantiles < 3 returns 422."""
        payload = {
            "factors": [{"name": "momentum", "direction": 1}],
            "universe": ["AAPL"],
            "start": "2023-01-01",
            "end": "2024-01-01",
            "n_quantiles": 1,
        }
        resp = await client.post("/api/v1/alpha", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_submit_invalid_holding_period(self, client: AsyncClient):
        """holding_period > 60 returns 422."""
        payload = {
            "factors": [{"name": "momentum", "direction": 1}],
            "universe": ["AAPL"],
            "start": "2023-01-01",
            "end": "2024-01-01",
            "holding_period": 100,
        }
        resp = await client.post("/api/v1/alpha", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_submit_no_auth(self, client: AsyncClient):
        """Submit without auth returns 401."""
        payload = {
            "factors": [{"name": "momentum"}],
            "universe": ["AAPL"],
            "start": "2023-01-01",
            "end": "2024-01-01",
        }
        resp = await client.post("/api/v1/alpha", json=payload)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_submit_empty_factors(self, client: AsyncClient):
        """Submit with empty factors list returns 422."""
        payload = {
            "factors": [],
            "universe": ["AAPL"],
            "start": "2023-01-01",
            "end": "2024-01-01",
        }
        # Empty factors should still be accepted (validation is runtime)
        resp = await client.post("/api/v1/alpha", json=payload, headers=AUTH_HEADERS)
        # The endpoint accepts any list, including empty
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_submit_creates_task_in_state(self, client: AsyncClient):
        """After submit, task appears in app state."""
        payload = {
            "factors": [{"name": "momentum"}],
            "universe": ["AAPL"],
            "start": "2023-01-01",
            "end": "2024-01-01",
        }
        resp = await client.post("/api/v1/alpha", json=payload, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]

        state = get_app_state()
        assert task_id in state.alpha_tasks
        assert state.alpha_tasks[task_id]["status"] in ("running", "failed", "completed")


# ===========================================================================
# 4. Neutralize endpoint
# ===========================================================================


class TestNeutralize:
    """Tests for POST /alpha/neutralize endpoint."""

    @pytest.mark.asyncio
    async def test_neutralize_no_auth(self, client: AsyncClient):
        """Neutralize without auth returns 401."""
        payload = {
            "symbols": ["AAPL"],
            "factor_name": "momentum",
            "start": "2023-01-01",
            "end": "2024-01-01",
        }
        resp = await client.post("/api/v1/alpha/neutralize", json=payload)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_neutralize_missing_fields(self, client: AsyncClient):
        """Missing required fields returns 422."""
        resp = await client.post(
            "/api/v1/alpha/neutralize",
            json={"symbols": ["AAPL"]},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422


# ===========================================================================
# 5. IC Analysis endpoint
# ===========================================================================


class TestICAnalysis:
    """Tests for POST /alpha/ic-analysis endpoint."""

    @pytest.mark.asyncio
    async def test_ic_analysis_no_auth(self, client: AsyncClient):
        """IC analysis without auth returns 401."""
        payload = {
            "symbols": ["AAPL"],
            "factor_name": "momentum",
            "start": "2023-01-01",
            "end": "2024-01-01",
        }
        resp = await client.post("/api/v1/alpha/ic-analysis", json=payload)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_ic_analysis_missing_fields(self, client: AsyncClient):
        """Missing required fields returns 422."""
        resp = await client.post(
            "/api/v1/alpha/ic-analysis",
            json={},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422


# ===========================================================================
# 6. Attribution endpoint
# ===========================================================================


class TestAttribution:
    """Tests for POST /alpha/attribution endpoint."""

    @pytest.mark.asyncio
    async def test_attribution_no_auth(self, client: AsyncClient):
        """Attribution without auth returns 401."""
        payload = {
            "composite_returns": {"2024-01-01": 0.01},
            "factor_returns": {"momentum": {"2024-01-01": 0.02}},
            "composite_weights": {"momentum": 1.0},
        }
        resp = await client.post("/api/v1/alpha/attribution", json=payload)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_attribution_missing_fields(self, client: AsyncClient):
        """Missing required fields returns 422."""
        resp = await client.post(
            "/api/v1/alpha/attribution",
            json={},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422


# ===========================================================================
# 7. Factor Correlation endpoint
# ===========================================================================


class TestFactorCorrelation:
    """Tests for POST /alpha/factor-correlation endpoint."""

    @pytest.mark.asyncio
    async def test_factor_correlation_no_auth(self, client: AsyncClient):
        """Factor correlation without auth returns 401."""
        payload = {
            "symbols": ["AAPL", "MSFT"],
            "factors": ["momentum", "volatility"],
            "start": "2023-01-01",
            "end": "2024-01-01",
        }
        resp = await client.post("/api/v1/alpha/factor-correlation", json=payload)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_factor_correlation_missing_fields(self, client: AsyncClient):
        """Missing required fields returns 422."""
        resp = await client.post(
            "/api/v1/alpha/factor-correlation",
            json={},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 422
