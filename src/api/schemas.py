"""
API 請求/回應模型 — Pydantic models → 自動生成 OpenAPI spec。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic import ValidationInfo


# ─── 通用 ─────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
    code: str = "error"


# ─── Shared validators ──────────────────────────────

def _validate_strategy_not_empty(v: str) -> str:
    if not v.strip():
        raise ValueError("strategy must not be empty")
    return v.strip()


def _validate_end_after_start(v: str, info: ValidationInfo) -> str:
    start = info.data.get("start", "")
    if start and v <= start:
        raise ValueError("end date must be after start date")
    return v


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
    params: dict[str, Any] = Field(default_factory=dict)


class MessageResponse(BaseModel):
    message: str


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
    universe: list[str] = Field(min_length=1)
    start: str = Field(default="2020-01-01", pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str = Field(default="2025-12-31", pattern=r"^\d{4}-\d{2}-\d{2}$")
    initial_cash: float = Field(default=10_000_000.0, gt=0)
    params: dict[str, Any] = Field(default_factory=dict)
    slippage_bps: float = Field(default=5.0, ge=0)
    commission_rate: float = Field(default=0.001425, ge=0, le=1)
    rebalance_freq: str = "weekly"

    @field_validator("strategy")
    @classmethod
    def strategy_not_empty(cls, v: str) -> str:
        return _validate_strategy_not_empty(v)

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: str, info: ValidationInfo) -> str:
        return _validate_end_after_start(v, info)


class BacktestSummaryResponse(BaseModel):
    task_id: str
    status: str                     # "running", "completed", "failed"
    strategy_name: str = ""
    total_return: float | None = None
    annual_return: float | None = None
    sharpe: float | None = None
    max_drawdown: float | None = None
    total_trades: int | None = None
    progress_current: int | None = None
    progress_total: int | None = None
    error: str | None = None


class TradeRecordResponse(BaseModel):
    date: str
    symbol: str
    side: str
    quantity: int
    price: float
    commission: float


class BacktestHistoryItem(BaseModel):
    id: str
    strategy_name: str
    config: dict[str, Any] = Field(default_factory=dict)
    started_at: str
    finished_at: str | None = None
    total_return: float | None = None
    annual_return: float | None = None
    sharpe: float | None = None
    max_drawdown: float | None = None


class BacktestHistoryResponse(BaseModel):
    items: list[BacktestHistoryItem]


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
    nav_series: list[dict[str, Any]] | None = None
    trades: list[TradeRecordResponse] | None = None


# ─── Risk ────────────────────────────────────────

class RiskRuleResponse(BaseModel):
    name: str
    enabled: bool


class KillSwitchResponse(BaseModel):
    message: str
    strategies_stopped: int
    orders_cancelled: int


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


# ─── Users ──────────────────────────────────────

class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    failed_login_count: int
    locked_until: str | None
    created_at: str
    updated_at: str


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    display_name: str = Field(default="", max_length=128)
    password: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9]+$")
    role: str = Field(default="viewer")

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v: str) -> str:
        from src.config import VALID_ROLES
        if v not in VALID_ROLES:
            raise ValueError(f"Invalid role: {v}. Must be one of: {sorted(VALID_ROLES)}")
        return v


class UpdateUserRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=128)
    role: str | None = None
    is_active: bool | None = None

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v: str | None) -> str | None:
        if v is not None:
            from src.config import VALID_ROLES
            if v not in VALID_ROLES:
                raise ValueError(f"Invalid role: {v}. Must be one of: {sorted(VALID_ROLES)}")
        return v


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9]+$")


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9]+$")


# ─── Walk-Forward Analysis ──────────────────────

class WalkForwardRequest(BaseModel):
    strategy: str
    universe: list[str] = Field(min_length=1)
    start: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    train_days: int = Field(gt=0)
    test_days: int = Field(gt=0)
    step_days: int = Field(gt=0)
    initial_cash: float = Field(default=10_000_000.0, gt=0)
    params: dict[str, Any] = Field(default_factory=dict)
    param_grid: dict[str, list[Any]] | None = None

    @field_validator("strategy")
    @classmethod
    def strategy_not_empty(cls, v: str) -> str:
        return _validate_strategy_not_empty(v)

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: str, info: ValidationInfo) -> str:
        return _validate_end_after_start(v, info)


class WalkForwardFoldResponse(BaseModel):
    fold_index: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_sharpe: float
    test_sharpe: float
    test_total_return: float
    best_params: dict[str, Any] | None = None


class WalkForwardResultResponse(BaseModel):
    folds: list[WalkForwardFoldResponse]
    oos_total_return: float
    oos_sharpe: float
    oos_max_drawdown: float
    param_stability: dict[str, Any]


# ─── Portfolio CRUD ─────────────────────────────────

class PortfolioCreateRequest(BaseModel):
    name: str
    initial_cash: float = 10_000_000.0
    strategy_name: str = ""


class PortfolioDetailResponse(BaseModel):
    id: str
    name: str
    cash: float
    initial_cash: float
    strategy_name: str
    positions: list[dict[str, Any]]
    nav: float
    created_at: str


class PortfolioListItem(BaseModel):
    id: str
    name: str
    cash: float
    initial_cash: float
    strategy_name: str
    position_count: int
    created_at: str


class PortfolioListResponse(BaseModel):
    portfolios: list[PortfolioListItem]


# ─── Rebalance Preview ─────────────────────────────

class RebalancePreviewRequest(BaseModel):
    strategy: str
    universes: list[str] = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    slippage_bps: float | None = None
    commission_rate: float | None = None
    tax_rate: float | None = None


class SuggestedTrade(BaseModel):
    symbol: str
    side: str  # "BUY" or "SELL"
    quantity: int
    estimated_price: float
    estimated_cost: float


class RebalancePreviewResponse(BaseModel):
    strategy: str
    target_weights: dict[str, float]
    current_weights: dict[str, float]
    suggested_trades: list[SuggestedTrade]
    estimated_total_commission: float
    estimated_total_tax: float


# ─── Randomized Backtest ──────────────────────────

class RandomizedBacktestRequest(BaseModel):
    strategy: str
    universe: list[str] = Field(min_length=1)
    start: str = Field(default="2020-01-01", pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str = Field(default="2025-12-31", pattern=r"^\d{4}-\d{2}-\d{2}$")
    params: dict[str, Any] = Field(default_factory=dict)
    n_iterations: int = Field(default=100, ge=1, le=1000)
    asset_sample_pct: float = Field(default=0.7, gt=0.0, le=1.0)
    time_sample_pct: float = Field(default=0.8, gt=0.0, le=1.0)
    initial_cash: float = Field(default=10_000_000.0, gt=0)
    slippage_bps: float = Field(default=5.0, ge=0)
    commission_rate: float = Field(default=0.001425, ge=0, le=1)
    rebalance_freq: str = "weekly"

    @field_validator("strategy")
    @classmethod
    def strategy_not_empty(cls, v: str) -> str:
        return _validate_strategy_not_empty(v)

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: str, info: ValidationInfo) -> str:
        return _validate_end_after_start(v, info)


class RandomizedBacktestResponse(BaseModel):
    iterations: int
    median_sharpe: float
    sharpe_5th_pct: float
    sharpe_95th_pct: float
    probability_positive_sharpe: float


# ─── PBO ─────────────────────────────────────────

class PBORequest(BaseModel):
    returns_matrix: list[list[float]] = Field(
        ..., min_length=1,
        description="List of columns; each column is a list of daily returns for one strategy variant.",
    )
    strategy_labels: list[str] | None = None
    n_partitions: int = Field(default=10, ge=2)


class PBOResponse(BaseModel):
    pbo: float
    is_overfit: bool
    n_combinations: int


# ─── Stress Test ─────────────────────────────────

class StressTestRequest(BaseModel):
    strategy: str
    universe: list[str] = Field(min_length=1)
    start: str = Field(default="2020-01-01", pattern=r"^\d{4}-\d{2}-\d{2}$")
    end: str = Field(default="2025-12-31", pattern=r"^\d{4}-\d{2}-\d{2}$")
    params: dict[str, Any] = Field(default_factory=dict)
    scenarios: list[str] | None = None
    initial_cash: float = Field(default=10_000_000.0, gt=0)
    slippage_bps: float = Field(default=5.0, ge=0)
    commission_rate: float = Field(default=0.001425, ge=0, le=1)
    rebalance_freq: str = "weekly"
    seed: int = 42

    @field_validator("strategy")
    @classmethod
    def strategy_not_empty(cls, v: str) -> str:
        return _validate_strategy_not_empty(v)

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: str, info: ValidationInfo) -> str:
        return _validate_end_after_start(v, info)


class StressTestScenarioResult(BaseModel):
    scenario: str
    total_return: float
    annual_return: float
    sharpe: float
    max_drawdown: float


class StressTestResponse(BaseModel):
    results: list[StressTestScenarioResult]
