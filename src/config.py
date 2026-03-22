"""
配置體系 — Pydantic Settings，一目了然，型別安全。

優先級：環境變數 > .env 檔案 > 預設值
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QUANT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── 運行模式 ──
    mode: Literal["backtest", "paper", "live"] = "backtest"

    # ── 數據庫 ──
    database_url: str = "postgresql://postgres:postgres@localhost:5432/quant"

    # ── 數據源 ──
    data_source: Literal["yahoo", "fubon", "twse"] = "yahoo"

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
    api_key: str = "dev-key"
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 1440          # 24 小時

    # ── 日誌 ──
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "text"

    # ── 回測預設 ──
    backtest_initial_cash: float = 10_000_000.0
    backtest_start: str = "2020-01-01"
    backtest_end: str = "2025-12-31"


# 全局單例
_config: TradingConfig | None = None


def get_config() -> TradingConfig:
    global _config
    if _config is None:
        _config = TradingConfig()
    return _config


def override_config(config: TradingConfig) -> None:
    """測試用：注入自訂配置。"""
    global _config
    _config = config
