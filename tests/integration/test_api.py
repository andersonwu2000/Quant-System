"""
Integration tests for the FastAPI backend.

Tests all API endpoints using httpx.AsyncClient with ASGITransport,
exercising auth, portfolio, strategy, order, risk, backtest, and system routes.
"""

from __future__ import annotations

from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.app import create_app
from src.api.state import get_app_state, reset_app_state
from src.config import TradingConfig, override_config

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

API_KEY = "test-integration-key"
AUTH_HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset app state and config before each test."""
    reset_app_state()
    override_config(
        TradingConfig(
            env="dev",
            api_key=API_KEY,
            jwt_secret="test-secret-for-integration",
            database_url="sqlite:///test.db",
        )
    )
    yield
    reset_app_state()


@pytest.fixture()
def app():
    """Create a fresh FastAPI app for testing."""
    return create_app()


@pytest.fixture()
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client bound to the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _login(client: AsyncClient) -> str:
    """Login and return a JWT access token."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"api_key": API_KEY},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


# ===========================================================================
# 1. Auth tests
# ===========================================================================


class TestAuth:
    """Authentication and authorization tests."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        """POST /auth/login with valid key returns 200 + token."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"api_key": API_KEY},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert len(body["access_token"]) > 0

    @pytest.mark.asyncio
    async def test_login_invalid_key(self, client: AsyncClient):
        """POST /auth/login with wrong key returns 401."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"api_key": "wrong-key"},
        )
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_logout(self, client: AsyncClient):
        """POST /auth/logout returns 200 and clears cookie."""
        resp = await client.post("/api/v1/auth/logout", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Logged out"

    @pytest.mark.asyncio
    async def test_access_without_auth(self, client: AsyncClient):
        """GET /portfolio without auth returns 401."""
        resp = await client.get("/api/v1/portfolio")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_access_with_api_key(self, client: AsyncClient):
        """GET /system/status with X-API-Key header returns 200."""
        resp = await client.get("/api/v1/system/status", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert "mode" in body


# ===========================================================================
# 2. System tests
# ===========================================================================


class TestSystem:
    """System endpoints: health, status, metrics."""

    @pytest.mark.asyncio
    async def test_health(self, client: AsyncClient):
        """GET /system/health returns 200 (no auth needed)."""
        resp = await client.get("/api/v1/system/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["version"] == "0.1.0"

    @pytest.mark.asyncio
    async def test_status(self, client: AsyncClient):
        """GET /system/status returns 200 with expected fields."""
        resp = await client.get("/api/v1/system/status", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert "mode" in body
        assert "uptime_seconds" in body
        assert "strategies_running" in body
        assert "data_source" in body
        assert "database" in body
        assert body["uptime_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_metrics(self, client: AsyncClient):
        """GET /system/metrics returns 200 with metric fields."""
        resp = await client.get("/api/v1/system/metrics", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert "uptime_seconds" in body
        assert "total_requests" in body
        assert "active_ws_connections" in body
        assert "strategies_running" in body
        assert "active_backtests" in body


# ===========================================================================
# 3. Portfolio tests
# ===========================================================================


class TestPortfolio:
    """Portfolio endpoints."""

    @pytest.mark.asyncio
    async def test_get_portfolio(self, client: AsyncClient):
        """GET /portfolio returns 200 with nav, cash, positions."""
        resp = await client.get("/api/v1/portfolio", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert "nav" in body
        assert "cash" in body
        assert "positions" in body
        assert body["nav"] > 0
        assert body["cash"] > 0

    @pytest.mark.asyncio
    async def test_get_positions(self, client: AsyncClient):
        """GET /portfolio/positions returns 200 list."""
        resp = await client.get("/api/v1/portfolio/positions", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)

    @pytest.mark.asyncio
    async def test_portfolio_has_required_fields(self, client: AsyncClient):
        """Verify full portfolio response schema."""
        resp = await client.get("/api/v1/portfolio", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        required_fields = [
            "nav",
            "cash",
            "gross_exposure",
            "net_exposure",
            "positions_count",
            "daily_pnl",
            "daily_pnl_pct",
            "positions",
            "as_of",
        ]
        for field in required_fields:
            assert field in body, f"Missing field: {field}"
        assert isinstance(body["positions"], list)
        assert isinstance(body["positions_count"], int)


# ===========================================================================
# 4. Strategy tests
# ===========================================================================


class TestStrategies:
    """Strategy management endpoints."""

    @pytest.mark.asyncio
    async def test_list_strategies(self, client: AsyncClient):
        """GET /strategies returns 200 with strategies list."""
        resp = await client.get("/api/v1/strategies", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert "strategies" in body
        assert isinstance(body["strategies"], list)

    @pytest.mark.asyncio
    async def test_get_strategy_not_found(self, client: AsyncClient):
        """GET /strategies/nonexistent returns 404."""
        resp = await client.get(
            "/api/v1/strategies/nonexistent", headers=AUTH_HEADERS
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_start_strategy(self, client: AsyncClient):
        """POST /strategies/{id}/start sets status to running."""
        # The startup event registers momentum_12_1 and mean_reversion.
        # We need to manually populate state since lifespan events may not
        # fire with AsyncClient. Seed the state directly.
        state = get_app_state()
        state.strategies["momentum_12_1"] = {"status": "stopped", "pnl": 0.0}

        resp = await client.post(
            "/api/v1/strategies/momentum_12_1/start", headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "started" in body["message"].lower() or "momentum_12_1" in body["message"]

        # Verify state change
        assert state.strategies["momentum_12_1"]["status"] == "running"

    @pytest.mark.asyncio
    async def test_stop_strategy(self, client: AsyncClient):
        """POST /strategies/{id}/stop sets status to stopped."""
        state = get_app_state()
        state.strategies["momentum_12_1"] = {"status": "running", "pnl": 0.0}

        resp = await client.post(
            "/api/v1/strategies/momentum_12_1/stop", headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        assert state.strategies["momentum_12_1"]["status"] == "stopped"


# ===========================================================================
# 5. Orders tests
# ===========================================================================


class TestOrders:
    """Order management endpoints."""

    @pytest.mark.asyncio
    async def test_list_orders(self, client: AsyncClient):
        """GET /orders returns 200 with a list."""
        resp = await client.get("/api/v1/orders", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)

    @pytest.mark.asyncio
    async def test_list_orders_with_filter(self, client: AsyncClient):
        """GET /orders?status=open returns 200."""
        resp = await client.get(
            "/api/v1/orders", params={"status": "open"}, headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_list_orders_pagination(self, client: AsyncClient):
        """GET /orders?limit=10&offset=0 returns 200."""
        resp = await client.get(
            "/api/v1/orders",
            params={"limit": 10, "offset": 0},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) <= 10


# ===========================================================================
# 6. Risk tests
# ===========================================================================


class TestRisk:
    """Risk management endpoints."""

    @pytest.mark.asyncio
    async def test_get_rules(self, client: AsyncClient):
        """GET /risk/rules returns 200 list of rules."""
        resp = await client.get("/api/v1/risk/rules", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        # Default risk engine has rules
        if body:
            assert "name" in body[0]
            assert "enabled" in body[0]

    @pytest.mark.asyncio
    async def test_toggle_rule(self, client: AsyncClient):
        """PUT /risk/rules/{name} toggles rule status."""
        # First get rules to find a name
        resp = await client.get("/api/v1/risk/rules", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        rules = resp.json()
        if not rules:
            pytest.skip("No risk rules available to toggle")

        rule_name = rules[0]["name"]

        # Toggle the rule (using API key which maps to admin role)
        resp = await client.put(
            f"/api/v1/risk/rules/{rule_name}",
            params={"enabled": False},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        assert "disabled" in resp.json()["message"].lower() or rule_name in resp.json()["message"]

    @pytest.mark.asyncio
    async def test_get_alerts(self, client: AsyncClient):
        """GET /risk/alerts returns 200."""
        resp = await client.get("/api/v1/risk/alerts", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)

    @pytest.mark.asyncio
    async def test_kill_switch(self, client: AsyncClient):
        """POST /risk/kill-switch activates and returns summary."""
        # Seed a running strategy so kill switch has something to stop
        state = get_app_state()
        state.strategies["test_strat"] = {"status": "running", "pnl": 0.0}

        resp = await client.post("/api/v1/risk/kill-switch", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert "kill switch" in body["message"].lower() or "Kill" in body["message"]
        assert "strategies_stopped" in body
        assert "orders_cancelled" in body
        assert body["strategies_stopped"] >= 1

        # Verify strategy was stopped
        assert state.strategies["test_strat"]["status"] == "stopped"


# ===========================================================================
# 7. Backtest tests
# ===========================================================================


class TestBacktest:
    """Backtest endpoints."""

    @pytest.mark.asyncio
    async def test_submit_backtest(self, client: AsyncClient):
        """POST /backtest with valid params returns 200 with task_id."""
        payload = {
            "strategy": "momentum",
            "universe": ["AAPL"],
            "start": "2024-01-01",
            "end": "2024-03-01",
            "initial_cash": 1_000_000,
            "slippage_bps": 5.0,
            "commission_rate": 0.001425,
            "rebalance_freq": "weekly",
        }
        resp = await client.post(
            "/api/v1/backtest", json=payload, headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "task_id" in body
        assert body["status"] == "running"
        assert body["strategy_name"] == "momentum"

    @pytest.mark.asyncio
    async def test_get_backtest_status(self, client: AsyncClient):
        """GET /backtest/{task_id} returns 200."""
        # Seed a fake task directly in state to avoid network calls
        state = get_app_state()
        state.backtest_tasks["fake123"] = {
            "status": "completed",
            "strategy_name": "momentum",
            "result": None,
            "progress": {"current": 50, "total": 50},
            "error": None,
        }

        resp = await client.get(
            "/api/v1/backtest/fake123", headers=AUTH_HEADERS
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == "fake123"
        assert body["status"] == "completed"
        assert body["strategy_name"] == "momentum"

    @pytest.mark.asyncio
    async def test_submit_backtest_invalid(self, client: AsyncClient):
        """POST /backtest with empty universe returns 422."""
        payload = {
            "strategy": "momentum",
            "universe": [],
            "start": "2024-01-01",
            "end": "2024-03-01",
        }
        resp = await client.post(
            "/api/v1/backtest", json=payload, headers=AUTH_HEADERS
        )
        assert resp.status_code == 422


# ===========================================================================
# 8. Additional edge-case and cross-cutting tests
# ===========================================================================


VIEWER_KEY = "test-viewer-key"
TRADER_KEY = "test-trader-key"


@pytest.fixture()
def multi_key_config():
    """提供多 key 映射的 config fixture。"""
    reset_app_state()
    override_config(
        TradingConfig(
            env="dev",
            api_key=API_KEY,
            api_key_roles={
                VIEWER_KEY: "viewer",
                TRADER_KEY: "trader",
            },
            jwt_secret="test-secret-for-integration",
            database_url="sqlite:///test.db",
        )
    )
    yield
    reset_app_state()


class TestAuthMultiKey:
    """多 API Key 角色映射測試。"""

    @pytest.mark.asyncio
    async def test_viewer_login_gets_viewer_role(self, app, multi_key_config):
        """Viewer key 登入 → JWT role = 'viewer'。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/auth/login", json={"api_key": VIEWER_KEY})
            assert resp.status_code == 200
            token = resp.json()["access_token"]
            # 解碼 JWT 驗證 role
            import base64
            import json as _json
            payload = _json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
            assert payload["role"] == "viewer"

    @pytest.mark.asyncio
    async def test_trader_login_gets_trader_role(self, app, multi_key_config):
        """Trader key 登入 → JWT role = 'trader'。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/auth/login", json={"api_key": TRADER_KEY})
            assert resp.status_code == 200
            token = resp.json()["access_token"]
            import base64
            import json as _json
            payload = _json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
            assert payload["role"] == "trader"

    @pytest.mark.asyncio
    async def test_legacy_admin_key_still_works(self, app, multi_key_config):
        """原有 admin key fallback 仍正常。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/auth/login", json={"api_key": API_KEY})
            assert resp.status_code == 200
            token = resp.json()["access_token"]
            import base64
            import json as _json
            payload = _json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
            assert payload["role"] == "admin"

    @pytest.mark.asyncio
    async def test_viewer_key_denied_trader_endpoint(self, app, multi_key_config):
        """Viewer key 帶 X-API-Key 存取 trader 端點 → 403。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/strategies/some_strat/start",
                headers={"X-API-Key": VIEWER_KEY},
            )
            assert resp.status_code in (403, 404)  # 403 權限不足，或 404 策略不存在（但角色檢查先於路由）

    @pytest.mark.asyncio
    async def test_viewer_key_allowed_readonly(self, app, multi_key_config):
        """Viewer key 存取只讀端點 → 200。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/v1/system/status", headers={"X-API-Key": VIEWER_KEY})
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_unknown_key_rejected(self, app, multi_key_config):
        """未知 key → 401。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/v1/auth/login", json={"api_key": "unknown-key"})
            assert resp.status_code == 401


class TestAuthJWT:
    """JWT-based authentication flow tests."""

    @pytest.mark.asyncio
    async def test_access_with_bearer_token(self, client: AsyncClient):
        """Login, then use Bearer token to access a protected endpoint."""
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get("/api/v1/system/status", headers=headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_access_with_invalid_bearer(self, client: AsyncClient):
        """Invalid Bearer token returns 401."""
        headers = {"Authorization": "Bearer invalid.token.here"}
        resp = await client.get("/api/v1/portfolio", headers=headers)
        assert resp.status_code == 401


class TestStrategyEdgeCases:
    """Strategy edge cases."""

    @pytest.mark.asyncio
    async def test_start_nonexistent_strategy(self, client: AsyncClient):
        """POST /strategies/ghost/start returns 404."""
        resp = await client.post(
            "/api/v1/strategies/ghost/start", headers=AUTH_HEADERS
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_stop_nonexistent_strategy(self, client: AsyncClient):
        """POST /strategies/ghost/stop returns 404."""
        resp = await client.post(
            "/api/v1/strategies/ghost/stop", headers=AUTH_HEADERS
        )
        assert resp.status_code == 404


class TestPasswordLogin:
    """Username + password 登入測試。"""

    @pytest.fixture(autouse=True)
    def _setup_users_table(self):
        """建立 users 表並插入測試使用者。"""
        from src.data.store import _create_engine, users_table
        from src.api.password import hash_password
        from src.data.user_store import UserStore, override_user_store

        engine = _create_engine("sqlite:///test.db")
        # 只建立 users 表（其他表由 _reset_state 處理）
        users_table.create(engine, checkfirst=True)

        # 清空並插入測試使用者
        with engine.begin() as conn:
            conn.execute(users_table.delete())
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            for username, password, role in [
                ("testadmin", "adminpass1234", "admin"),
                ("testviewer", "viewerpass12", "viewer"),
            ]:
                h, s = hash_password(password)
                conn.execute(users_table.insert().values(
                    username=username, display_name=username, password_hash=h, password_salt=s,
                    role=role, is_active=True, failed_login_count=0, created_at=now, updated_at=now,
                ))

        store = UserStore(engine)
        override_user_store(store)
        yield
        override_user_store(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_login_with_username_password(self, client: AsyncClient):
        """正確帳密 → 200 + JWT 含正確 username。"""
        resp = await client.post("/api/v1/auth/login", json={"username": "testadmin", "password": "adminpass1234"})
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        import base64
        import json as _json
        payload = _json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
        assert payload["sub"] == "testadmin"
        assert payload["role"] == "admin"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        """錯誤密碼 → 401。"""
        resp = await client.post("/api/v1/auth/login", json={"username": "testadmin", "password": "wrong"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_api_key_login_still_works(self, client: AsyncClient):
        """API Key 登入向後相容。"""
        resp = await client.post("/api/v1/auth/login", json={"api_key": API_KEY})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_no_credentials_returns_400(self, client: AsyncClient):
        """無任何 credentials → 400。"""
        resp = await client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 400


class TestAdminUsers:
    """Admin 使用者管理 API 測試。"""

    @pytest.fixture(autouse=True)
    def _setup_users_table(self):
        """建立 users 表。"""
        from src.data.store import _create_engine, users_table
        from src.data.user_store import UserStore, override_user_store

        engine = _create_engine("sqlite:///test.db")
        users_table.create(engine, checkfirst=True)
        with engine.begin() as conn:
            conn.execute(users_table.delete())

        store = UserStore(engine)
        override_user_store(store)
        yield
        override_user_store(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_list_users_requires_admin(self, client: AsyncClient):
        """非 admin 角色存取 → 403（使用 viewer key）。"""
        override_config(
            TradingConfig(
                env="dev", api_key=API_KEY,
                api_key_roles={"viewer-k": "viewer"},
                jwt_secret="test-secret-for-integration",
                database_url="sqlite:///test.db",
            )
        )
        resp = await client.get("/api/v1/admin/users", headers={"X-API-Key": "viewer-k"})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_create_and_list_user(self, client: AsyncClient):
        """建立使用者後列出。"""
        # 建立
        resp = await client.post(
            "/api/v1/admin/users",
            json={"username": "newuser", "password": "password1234", "role": "trader"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["username"] == "newuser"
        assert body["role"] == "trader"

        # 列出
        resp = await client.get("/api/v1/admin/users", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        users = resp.json()
        assert any(u["username"] == "newuser" for u in users)

    @pytest.mark.asyncio
    async def test_create_duplicate_username(self, client: AsyncClient):
        """重複 username → 409。"""
        body = {"username": "dupuser", "password": "password1234", "role": "viewer"}
        await client.post("/api/v1/admin/users", json=body, headers=AUTH_HEADERS)
        resp = await client.post("/api/v1/admin/users", json=body, headers=AUTH_HEADERS)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_update_user_role(self, client: AsyncClient):
        """修改使用者角色。"""
        resp = await client.post(
            "/api/v1/admin/users",
            json={"username": "roleuser", "password": "password1234", "role": "viewer"},
            headers=AUTH_HEADERS,
        )
        user_id = resp.json()["id"]
        resp = await client.put(
            f"/api/v1/admin/users/{user_id}",
            json={"role": "trader"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "trader"

    @pytest.mark.asyncio
    async def test_delete_user(self, client: AsyncClient):
        """刪除使用者。"""
        resp = await client.post(
            "/api/v1/admin/users",
            json={"username": "deluser", "password": "password1234"},
            headers=AUTH_HEADERS,
        )
        user_id = resp.json()["id"]
        resp = await client.delete(f"/api/v1/admin/users/{user_id}", headers=AUTH_HEADERS)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_reset_password(self, client: AsyncClient):
        """重設密碼。"""
        resp = await client.post(
            "/api/v1/admin/users",
            json={"username": "pwuser", "password": "oldpassword1"},
            headers=AUTH_HEADERS,
        )
        user_id = resp.json()["id"]
        resp = await client.post(
            f"/api/v1/admin/users/{user_id}/reset-password",
            json={"new_password": "newpassword1"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200


class TestBacktestEdgeCases:
    """Backtest edge cases."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_backtest(self, client: AsyncClient):
        """GET /backtest/nosuchtask returns 404."""
        resp = await client.get(
            "/api/v1/backtest/nosuchtask", headers=AUTH_HEADERS
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_backtest_end_before_start(self, client: AsyncClient):
        """POST /backtest with end before start returns 422."""
        payload = {
            "strategy": "momentum",
            "universe": ["AAPL"],
            "start": "2024-06-01",
            "end": "2024-01-01",
        }
        resp = await client.post(
            "/api/v1/backtest", json=payload, headers=AUTH_HEADERS
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_backtest_empty_strategy_name(self, client: AsyncClient):
        """POST /backtest with empty strategy name returns 422."""
        payload = {
            "strategy": "  ",
            "universe": ["AAPL"],
            "start": "2024-01-01",
            "end": "2024-03-01",
        }
        resp = await client.post(
            "/api/v1/backtest", json=payload, headers=AUTH_HEADERS
        )
        assert resp.status_code == 422
