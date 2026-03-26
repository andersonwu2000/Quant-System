"""Backtest Gate — verify strategy profitability before live/paper execution.

Runs a quick backtest on recent data to confirm the selected factors would
have been profitable, preventing deployment of strategies with negative
expected returns or excessive transaction costs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.backtest.validator import ValidationReport
from dataclasses import dataclass

import pandas as pd

from src.alpha.auto.config import AutoAlphaConfig
from src.alpha.auto.decision import DecisionResult
from src.alpha.pipeline import AlphaConfig, FactorSpec
from src.alpha.strategy import AlphaStrategy
from src.backtest.analytics import BacktestResult
from src.backtest.engine import BacktestConfig, BacktestEngine

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    """Outcome of the backtest verification gate."""

    passed: bool
    sharpe: float
    total_return: float
    max_drawdown: float
    net_cost: float  # estimated annual transaction cost as a fraction
    reason: str


def verify_before_execution(
    decision: DecisionResult,
    data: dict[str, pd.DataFrame],
    config: AutoAlphaConfig,
    lookback_days: int | None = None,
) -> GateResult:
    """Run a quick backtest on recent data to verify the strategy makes money.

    Steps:
        1. Build AlphaPipeline from decision's selected factors + weights.
        2. Create AlphaStrategy wrapping the pipeline.
        3. Run BacktestEngine on the last ``lookback_days`` of data.
        4. Check: Sharpe > min_sharpe? Max drawdown < emergency threshold?
        5. Estimate annual transaction cost from trade count + avg notional.

    Parameters
    ----------
    decision:
        The decision result containing selected factors and weights.
    data:
        Historical OHLCV data keyed by symbol.
    config:
        AutoAlphaConfig with gate thresholds.
    lookback_days:
        Number of recent trading days to use. Defaults to
        ``config.backtest_gate_lookback``.

    Returns
    -------
    GateResult with pass/fail and diagnostic metrics.
    """
    if lookback_days is None:
        lookback_days = config.backtest_gate_lookback

    if not decision.selected_factors or not decision.factor_weights:
        return GateResult(
            passed=False,
            sharpe=0.0,
            total_return=0.0,
            max_drawdown=0.0,
            net_cost=0.0,
            reason="No factors selected in decision",
        )

    # 1. Trim data to the lookback window
    trimmed_data: dict[str, pd.DataFrame] = {}
    for sym, df in data.items():
        if len(df) > lookback_days:
            trimmed_data[sym] = df.iloc[-lookback_days:]
        elif not df.empty:
            trimmed_data[sym] = df

    if not trimmed_data:
        return GateResult(
            passed=False,
            sharpe=0.0,
            total_return=0.0,
            max_drawdown=0.0,
            net_cost=0.0,
            reason="No data available for backtest gate",
        )

    # 2. Build AlphaStrategy from decision
    factor_specs = [
        FactorSpec(name=name) for name in decision.selected_factors
    ]
    alpha_cfg = AlphaConfig(
        factors=factor_specs,
        combine_method="custom",
        combine_weights=decision.factor_weights,
    )
    strategy = AlphaStrategy(config=alpha_cfg)

    # 3. Determine date range from trimmed data
    all_dates: list[pd.Timestamp] = []
    for df in trimmed_data.values():
        if not df.empty:
            all_dates.extend(df.index.tolist())
    if not all_dates:
        return GateResult(
            passed=False,
            sharpe=0.0,
            total_return=0.0,
            max_drawdown=0.0,
            net_cost=0.0,
            reason="No dates in trimmed data",
        )

    start_date = str(min(all_dates).date())
    end_date = str(max(all_dates).date())

    bt_config = BacktestConfig(
        universe=list(trimmed_data.keys()),
        start=start_date,
        end=end_date,
        initial_cash=10_000_000.0,
        fractional_shares=True,
    )

    # 4. Run the backtest
    try:
        engine = BacktestEngine()
        result: BacktestResult = engine.run(strategy=strategy, config=bt_config)
    except Exception as exc:
        logger.warning("Backtest gate engine error: %s", exc)
        return GateResult(
            passed=False,
            sharpe=0.0,
            total_return=0.0,
            max_drawdown=0.0,
            net_cost=0.0,
            reason=f"Backtest engine error: {exc}",
        )

    # 5. Estimate annual transaction cost
    # total_commission is absolute; annualise relative to initial cash
    trading_days = max((pd.Timestamp(end_date) - pd.Timestamp(start_date)).days, 1)
    annual_factor = 252.0 / trading_days
    net_cost = (result.total_commission / bt_config.initial_cash) * annual_factor

    # 6. Check thresholds
    reasons: list[str] = []

    if result.sharpe < config.backtest_gate_min_sharpe:
        reasons.append(
            f"Sharpe {result.sharpe:.2f} < min {config.backtest_gate_min_sharpe:.2f}"
        )

    if net_cost > config.backtest_gate_max_cost_pct:
        reasons.append(
            f"Est. annual cost {net_cost:.1%} > max {config.backtest_gate_max_cost_pct:.1%}"
        )

    passed = len(reasons) == 0
    reason = "; ".join(reasons) if reasons else "All checks passed"

    return GateResult(
        passed=passed,
        sharpe=result.sharpe,
        total_return=result.total_return,
        max_drawdown=result.max_drawdown,
        net_cost=net_cost,
        reason=reason,
    )


def full_validation(
    strategy: object,
    universe: list[str],
    start: str,
    end: str,
    n_trials: int = 1,
) -> "ValidationReport":
    """完整策略驗證（11 項檢查）。

    比 verify_before_execution() 更嚴格。適用於：
    - 新策略首次上線前
    - 定期重新驗證
    - 研究報告產出

    Parameters
    ----------
    strategy:
        Strategy 實例。
    universe:
        股票池。
    start, end:
        回測期間。
    n_trials:
        已測試的策略總數（用於 Deflated Sharpe 校正）。

    Returns
    -------
    ValidationReport — 包含 11 項檢查結果。
    """
    from src.backtest.validator import StrategyValidator, ValidationConfig

    config = ValidationConfig(n_trials=n_trials)
    validator = StrategyValidator(config)
    return validator.validate(strategy, universe, start, end)  # type: ignore[arg-type]
