"""
配置體系 — Pydantic Settings，一目了然，型別安全。

優先級：環境變數 > .env 檔案 > 預設值
"""

from __future__ import annotations

import hmac
import json
import threading
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

VALID_ROLES: frozenset[str] = frozenset({"viewer", "researcher", "trader", "risk_manager", "admin"})


class TradingConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QUANT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── 環境 ──
    env: Literal["dev", "staging", "prod"] = "dev"

    # ── 運行模式 ──
    mode: Literal["backtest", "paper", "live"] = "backtest"

    # ── 數據庫 ──
    database_url: str = "postgresql://postgres:postgres@localhost:5432/quant"

    # ── 數據源 ──
    data_source: Literal["yahoo", "fubon", "twse"] = "yahoo"
    data_cache_dir: str = ".cache/market_data"

    # ── 風控 ──
    max_position_pct: float = 0.05
    max_sector_pct: float = 0.20
    max_daily_drawdown_pct: float = 0.03
    kill_switch_weekly_drawdown_pct: float = 0.10
    max_daily_trades: int = 100
    fat_finger_pct: float = 0.05
    max_order_vs_adv_pct: float = 0.10

    # ── 執行 ──
    default_slippage_bps: float = 5.0
    commission_rate: float = 0.001425       # 台灣券商手續費
    tax_rate: float = 0.003                 # 台灣證交稅 (賣出)

    # ── API ──
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1
    api_key: str = "dev-key"
    api_key_roles: dict[str, str] = {}      # 額外 key→role 映射，env var: QUANT_API_KEY_ROLES (JSON)
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 1440          # 24 小時
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    allowed_origins: list[str] = ["http://localhost:3000"]

    # ── 日誌 ──
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "text"

    # ── 回測 ──
    backtest_initial_cash: float = 10_000_000.0
    backtest_start: str = "2020-01-01"
    backtest_end: str = "2025-12-31"
    backtest_timeout: int = 1800            # 秒

    @field_validator("api_key_roles", mode="before")
    @classmethod
    def _parse_api_key_roles(cls, v: object) -> dict[str, str]:
        """接受 dict 或 JSON 字串（env var 傳入時為字串）。"""
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "QUANT_API_KEY_ROLES must be valid JSON, "
                    'e.g.: \'{"viewer-key": "viewer"}\''
                ) from exc
        if not isinstance(v, dict):
            raise ValueError("api_key_roles must be a dict")
        return v

    @model_validator(mode="after")
    def _check_prod_secrets(self) -> "TradingConfig":
        """Non-dev environments must not use default secrets."""
        if self.env != "dev":
            if self.api_key == "dev-key":
                raise ValueError("QUANT_API_KEY must be set in non-dev environments (cannot use 'dev-key')")
            if self.jwt_secret == "change-me-in-production":
                raise ValueError("QUANT_JWT_SECRET must be set in non-dev environments")
        for role in self.api_key_roles.values():
            if role not in VALID_ROLES:
                raise ValueError(
                    f"Invalid role '{role}' in QUANT_API_KEY_ROLES. "
                    f"Must be one of: {sorted(VALID_ROLES)}"
                )
        if self.api_key in self.api_key_roles:
            raise ValueError(
                "QUANT_API_KEY must not also appear in QUANT_API_KEY_ROLES"
            )
        return self

    def resolve_api_key_role(self, provided_key: str) -> str | None:
        """查詢 API Key 對應的角色。回傳 None 表示 key 無效。

        對所有 key 都執行 constant-time 比較（防 timing side-channel）。
        查詢順序：api_key_roles → api_key (fallback admin)。
        """
        matched: str | None = None
        for stored_key, role in self.api_key_roles.items():
            if hmac.compare_digest(provided_key, stored_key):
                matched = role  # 不 break，繼續跑完所有比較
        if matched is not None:
            return matched
        if hmac.compare_digest(provided_key, self.api_key):
            return "admin"
        return None


# 全局單例（thread-safe）
_config: TradingConfig | None = None
_config_lock = threading.Lock()


def get_config() -> TradingConfig:
    global _config
    if _config is None:
        with _config_lock:
            if _config is None:
                _config = TradingConfig()
    return _config


def override_config(config: TradingConfig) -> None:
    """測試用：注入自訂配置。"""
    global _config
    _config = config
