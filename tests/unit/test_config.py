"""Config 層單元測試 — api_key_roles 欄位與 resolve_api_key_role 方法。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.core.config import TradingConfig


class TestResolveApiKeyRole:
    """resolve_api_key_role 查詢邏輯。"""

    def test_returns_mapped_role(self):
        cfg = TradingConfig(env="dev", api_key="admin-k", api_key_roles={"viewer-k": "viewer"})
        assert cfg.resolve_api_key_role("viewer-k") == "viewer"

    def test_fallback_admin(self):
        cfg = TradingConfig(env="dev", api_key="admin-k", api_key_roles={"viewer-k": "viewer"})
        assert cfg.resolve_api_key_role("admin-k") == "admin"

    def test_unknown_key_returns_none(self):
        cfg = TradingConfig(env="dev", api_key="admin-k", api_key_roles={"viewer-k": "viewer"})
        assert cfg.resolve_api_key_role("garbage") is None

    def test_multiple_roles(self):
        cfg = TradingConfig(
            env="dev",
            api_key="admin-k",
            api_key_roles={"v": "viewer", "t": "trader", "r": "risk_manager"},
        )
        assert cfg.resolve_api_key_role("v") == "viewer"
        assert cfg.resolve_api_key_role("t") == "trader"
        assert cfg.resolve_api_key_role("r") == "risk_manager"

    def test_empty_roles_only_fallback(self):
        cfg = TradingConfig(env="dev", api_key="admin-k")
        assert cfg.resolve_api_key_role("admin-k") == "admin"
        assert cfg.resolve_api_key_role("other") is None


class TestApiKeyRolesValidation:
    """api_key_roles 欄位驗證。"""

    def test_json_string_parsing(self):
        cfg = TradingConfig(env="dev", api_key="admin-k", api_key_roles='{"k1": "viewer"}')
        assert cfg.api_key_roles == {"k1": "viewer"}

    def test_invalid_json_raises(self):
        with pytest.raises(ValidationError, match="valid JSON"):
            TradingConfig(env="dev", api_key="admin-k", api_key_roles="not-json")

    def test_invalid_role_raises(self):
        with pytest.raises(ValidationError, match="Invalid role"):
            TradingConfig(env="dev", api_key="admin-k", api_key_roles={"k": "superuser"})

    def test_duplicate_key_in_roles_raises(self):
        with pytest.raises(ValidationError, match="must not also appear"):
            TradingConfig(env="dev", api_key="same-key", api_key_roles={"same-key": "viewer"})
