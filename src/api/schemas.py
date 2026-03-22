"""
API 請求/回應模型 — Pydantic models → 自動生成 OpenAPI spec。
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


# ─── 通用 ─────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
    code: str = "error"


# ─── Portfolio ────────────────────────────────────

class PositionResponse(BaseModel):
    symbol: str
    quantity: float
    avg_cost: float
    market_price: float
    market_value: float
    unrealized_pnl: float
    weight: float


class PortfolioResponse(BaseModel):
    nav: float
    cash: float
    gross_exposure: float
    net_exposure: float
    positions_count: int
    daily_pnl: float = 0.0
    daily_pnl_pct: float = 0.0
    positions: list[PositionResponse]
    as_of: str


# ─── Strategy ────────────────────────────────────

class StrategyInfo(BaseModel):
    name: str
    status: str = "stopped"         # "running", "stopped", "error"
    pnl: float = 0.0


class StrategyStartRequest(BaseModel):
    params: dict = Field(default_factory=dict)


class StrategyListResponse(BaseModel):
    strategies: list[StrategyInfo]


# ─── Orders ──────────────────────────────────────

class OrderResponse(BaseModel):
    id: str
    symbol: str
    side: str
    quantity: float
    price: float | None
    status: str
    filled_qty: float
    filled_avg_price: float
    commission: float
    created_at: str
    strategy_id: str


class ManualOrderRequest(BaseModel):
    symbol: str
    side: str                       # "BUY" or "SELL"
    quantity: float
    price: float | None = None      # None = 市價


# ─── Backtest ────────────────────────────────────

class BacktestRequest(BaseModel):
    strategy: str
    universe: list[str]
    start: str = "2020-01-01"
    end: str = "2025-12-31"
    initial_cash: float = 10_000_000.0
    params: dict = Field(default_factory=dict)
    slippage_bps: float = 5.0
    commission_rate: float = 0.001425
    rebalance_freq: str = "weekly"


class BacktestSummaryResponse(BaseModel):
    task_id: str
    status: str                     # "running", "completed", "failed"
    strategy_name: str = ""
    total_return: float | None = None
    annual_return: float | None = None
    sharpe: float | None = None
    max_drawdown: float | None = None
    total_trades: int | None = None
    # 完整結果通過 /backtest/{id}/result 取得


class BacktestResultResponse(BaseModel):
    strategy_name: str
    start_date: str
    end_date: str
    initial_cash: float
    total_return: float
    annual_return: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    max_drawdown_duration: int
    volatility: float
    total_trades: int
    win_rate: float
    total_commission: float
    nav_series: list[dict] | None = None


# ─── Risk ────────────────────────────────────────

class RiskRuleResponse(BaseModel):
    name: str
    enabled: bool


class RiskAlertResponse(BaseModel):
    timestamp: str
    rule_name: str
    severity: str
    metric_value: float
    threshold: float
    action_taken: str
    message: str


# ─── System ──────────────────────────────────────

class SystemStatusResponse(BaseModel):
    mode: str
    uptime_seconds: float
    strategies_running: int
    data_source: str
    database: str


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
