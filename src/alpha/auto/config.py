"""AutoAlphaConfig, DecisionConfig, and supporting data models for the Automated Alpha Research System."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

from src.alpha.pipeline import AlphaConfig, FactorSpec
from src.alpha.regime import MarketRegime


def _default_alpha_config() -> AlphaConfig:
    """Build AlphaConfig with all registered price-based factors."""
    from src.strategy.research import FACTOR_REGISTRY

    factors = [
        FactorSpec(name=name, direction=1)
        for name in FACTOR_REGISTRY
    ]
    return AlphaConfig(factors=factors)


@dataclass
class DecisionConfig:
    """Factor selection and weight decision parameters."""

    min_icir: float = 0.5
    min_hit_rate: float = 0.52
    max_cost_drag: float = 200.0
    use_rolling_ic: bool = True
    regime_aware: bool = True
    oos_decay_factor: float = 0.42  # McLean-Pontiff (2016): OOS alpha ~ 0.42x IS
    momentum_crash_market_threshold: float = -0.20
    momentum_crash_vol_multiplier: float = 2.0
    volatility_scaling_enabled: bool = False
    volatility_scaling_target: float = 0.15


@dataclass
class AutoAlphaConfig:
    """Automated Alpha system configuration (architecture doc section 3.1)."""

    # Schedule
    schedule: str = "50 8 * * 1-5"
    eod_schedule: str = "00 14 * * 1-5"

    # Universe
    universe_count: int = 150
    min_adv: int = 500_000
    min_listing_days: int = 120
    exclude_disposition: bool = True
    exclude_attention: bool = False

    # Research
    lookback: int = 252
    alpha_config: AlphaConfig = field(default_factory=lambda: _default_alpha_config())

    # Decision
    decision: DecisionConfig = field(default_factory=DecisionConfig)

    # Execution
    max_turnover: float = 0.30
    min_trade_value: float = 50_000

    # Safety
    max_consecutive_losses: int = 5
    ic_reversal_days: int = 10
    emergency_stop_drawdown: float = 0.05

    # Momentum crash protection (Daniel & Moskowitz 2016)
    momentum_crash_market_threshold: float = -0.20
    momentum_crash_vol_multiplier: float = 2.0

    # Volatility scaling (optional)
    volatility_scaling_enabled: bool = False
    volatility_scaling_target: float = 0.15

    # Convenience accessors that mirror flat attributes from DecisionConfig
    @property
    def min_icir(self) -> float:
        return self.decision.min_icir

    @property
    def min_hit_rate(self) -> float:
        return self.decision.min_hit_rate

    @property
    def max_cost_drag(self) -> float:
        return self.decision.max_cost_drag

    @property
    def use_rolling_ic(self) -> bool:
        return self.decision.use_rolling_ic

    @property
    def regime_aware(self) -> bool:
        return self.decision.regime_aware


@dataclass
class FactorScore:
    """Per-factor daily score."""

    name: str
    ic: float
    icir: float
    hit_rate: float
    decay_half_life: int
    turnover: float
    cost_drag_bps: float
    regime_ic: dict[str, float] = field(default_factory=dict)
    long_short_sharpe: float = 0.0
    eligible: bool = False


@dataclass
class ResearchSnapshot:
    """Daily research snapshot (persisted to DB)."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    date: date = field(default_factory=date.today)
    regime: MarketRegime = MarketRegime.SIDEWAYS
    universe: list[str] = field(default_factory=list)
    universe_size: int = 0
    # Factor analysis
    factor_scores: dict[str, FactorScore] = field(default_factory=dict)
    selected_factors: list[str] = field(default_factory=list)
    factor_weights: dict[str, float] = field(default_factory=dict)
    # Portfolio
    target_weights: dict[str, float] = field(default_factory=dict)
    # Execution results
    trades_count: int = 0
    turnover: float = 0.0
    # Performance (filled in after EOD)
    daily_pnl: float | None = None
    cumulative_return: float | None = None

    def __post_init__(self) -> None:
        if self.universe_size == 0 and self.universe:
            self.universe_size = len(self.universe)


@dataclass
class AlphaAlert:
    """Alpha system alert."""

    timestamp: datetime = field(default_factory=datetime.now)
    level: Literal["info", "warning", "critical"] = "info"
    category: str = ""  # "factor", "regime", "execution", "drawdown"
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


# Alert rule templates
ALERT_RULES: dict[str, str] = {
    "regime_change": "Market regime changed from {old} to {new}",
    "factor_degraded": "Factor {name} ICIR dropped from {old:.2f} to {new:.2f}",
    "ic_reversal": "Factor {name} has negative IC for {days} consecutive days",
    "high_turnover": "Today's turnover {turnover:.1%} exceeds threshold {threshold:.1%}",
    "drawdown_warning": "Cumulative drawdown {dd:.1%} approaching stop threshold {threshold:.1%}",
    "emergency_stop": "Drawdown reached {dd:.1%}, triggering emergency stop",
    "no_eligible_factors": "No factors passed selection threshold today",
    "disposition_added": "{count} holdings added to disposition list",
}
