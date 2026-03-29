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
    database_url: str = "sqlite:///data/quant.db"

    # ── 數據源 ──
    data_source: Literal["yahoo", "finmind"] = "yahoo"
    finmind_token: str = ""
    data_cache_dir: str = ".cache/market_data"

    # ── 風控 ──
    max_position_pct: float = 0.10    # 10%（配合 15 支等權策略的 ~6.7%，含容差）
    max_sector_pct: float = 0.20
    max_daily_drawdown_pct: float = 0.03
    max_daily_trades: int = 100
    fat_finger_pct: float = 0.05
    max_order_vs_adv_pct: float = 0.10

    # ── 市場交易單位 ──
    market_lot_sizes: dict[str, int] = {
        ".TW": 1000,    # TWSE 整股 (整張)
        ".TWO": 1000,   # OTC 整股 (整張)
        # US stocks default to 1 (no suffix match)
        # Add ".T": 100 for Japan, etc.
    }
    fractional_shares: bool = False   # True = allow fractional (零股模式)

    # ── 執行 ──
    default_slippage_bps: float = 5.0
    commission_rate: float = 0.001425       # 台灣券商手續費
    tax_rate: float = 0.003                 # 台灣證交稅 (賣出)

    # ── Smart Order (TWAP) ──
    smart_order_enabled: bool = False
    smart_order_slices: int = 5

    # ── 永豐 Shioaji 券商 ──
    sinopac_api_key: str = ""
    sinopac_secret_key: str = ""
    sinopac_ca_path: str = ""
    sinopac_ca_password: str = ""

    # ── API ──
    api_host: str = "127.0.0.1"  # 預設只綁定 localhost（生產用 QUANT_API_HOST 覆蓋）
    api_port: int = 8000
    api_workers: int = 1
    api_key: str = "dev-key"
    api_key_roles: dict[str, str] = {}      # 額外 key→role 映射，env var: QUANT_API_KEY_ROLES (JSON)
    admin_password: str = "Admin1234"          # 首次啟動預設密碼，可用 QUANT_ADMIN_PASSWORD 覆蓋
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 1440          # 24 小時
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    allowed_origins: list[str] = ["http://localhost:3000"]

    # ── 通知 ──
    notify_provider: Literal["discord", "line", "telegram", ""] = ""
    discord_webhook_url: str = ""
    line_notify_token: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # ── 排程 ──
    scheduler_enabled: bool = False
    # 統一交易管線（Phase S）
    active_strategy: str = "revenue_momentum_hedged"
    trading_pipeline_cron: str = "30 8 11 * *"
    pipeline_data_update: bool = True
    # 收盤後自動對帳（paper/live mode）
    reconcile_cron: str = "30 14 * * 1-5"   # 台股收盤後 14:30，平日
    # 舊 config（向後相容，deprecated）
    rebalance_cron: str = "0 9 1 * *"
    revenue_scheduler_enabled: bool = True
    revenue_update_cron: str = "30 8 11 * *"
    revenue_rebalance_cron: str = "5 9 11 * *"

    # ── 日誌 ──
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "text"

    # ── 數據快取 ──
    data_cache_size: int = 128                  # LRU memory cache 最大條目數

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
