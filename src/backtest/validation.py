"""
回測驗證 — 確保回測結果的嚴謹性。

包含兩類驗證：
1. 靜態驗證（validate_backtest）: 檢查回測結果的合理性
2. 品質驗證（check_causality / check_determinism / check_sensitivity）:
   動態重跑回測，檢查因果性、確定性、穩健性
"""

from __future__ import annotations

import copy
import logging
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any


from src.backtest.analytics import BacktestResult

if TYPE_CHECKING:
    from src.backtest.engine import BacktestConfig
    from src.strategy.base import Strategy

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """驗證結果。"""
    passed: bool
    checks: list[dict[str, Any]]

    def summary(self) -> str:
        lines = ["═══ Backtest Validation ═══"]
        for c in self.checks:
            status = "PASS" if c["passed"] else "FAIL"
            lines.append(f"  [{status}] {c['name']}: {c['detail']}")
        overall = "ALL PASSED" if self.passed else "SOME CHECKS FAILED"
        lines.append(f"\nResult: {overall}")
        return "\n".join(lines)


def validate_backtest(result: BacktestResult) -> ValidationResult:
    """執行所有驗證檢查。"""
    checks: list[dict[str, Any]] = []

    # 1. 非零交易檢查
    checks.append(_check_nonzero_trades(result))

    # 2. NAV 連續性 (不能有突變)
    checks.append(_check_nav_continuity(result))

    # 3. 收益合理性 (年化報酬不應超過 200%)
    checks.append(_check_return_sanity(result))

    # 4. Sharpe 合理性
    checks.append(_check_sharpe_sanity(result))

    # 5. 交易成本影響
    checks.append(_check_cost_impact(result))

    all_passed = all(c["passed"] for c in checks)
    return ValidationResult(passed=all_passed, checks=checks)


def _check_nonzero_trades(result: BacktestResult) -> dict[str, Any]:
    passed = result.total_trades > 0
    return {
        "name": "非零交易",
        "passed": passed,
        "detail": f"{result.total_trades} 筆交易" if passed else "無任何交易，策略可能有問題",
    }


def _check_nav_continuity(result: BacktestResult) -> dict[str, Any]:
    """NAV 序列不應有日報酬 > 50% 的突變。"""
    if result.daily_returns.empty:
        return {"name": "NAV 連續性", "passed": True, "detail": "無數據"}

    max_daily = float(result.daily_returns.abs().max())
    passed = max_daily < 0.50
    return {
        "name": "NAV 連續性",
        "passed": passed,
        "detail": f"最大日報酬 {max_daily:.2%}" + (" (異常!)" if not passed else ""),
    }


def _check_return_sanity(result: BacktestResult) -> dict[str, Any]:
    """年化報酬不應超過 200%（除非是極短期回測）。"""
    passed = abs(result.annual_return) < 2.0
    return {
        "name": "收益合理性",
        "passed": passed,
        "detail": f"年化 {result.annual_return:.2%}" + (" (可能過擬合)" if not passed else ""),
    }


def _check_sharpe_sanity(result: BacktestResult) -> dict[str, Any]:
    """Sharpe > 3.0 通常暗示過擬合。"""
    suspicious = result.sharpe > 3.0
    return {
        "name": "Sharpe 合理性",
        "passed": not suspicious,
        "detail": f"Sharpe {result.sharpe:.2f}" + (" (疑似過擬合)" if suspicious else ""),
    }


def _check_cost_impact(result: BacktestResult) -> dict[str, Any]:
    """交易成本佔總收益的比例。"""
    if result.total_return == 0:
        return {"name": "成本影響", "passed": True, "detail": "總收益為零"}

    total_pnl = result.initial_cash * result.total_return
    if total_pnl == 0:
        return {"name": "成本影響", "passed": True, "detail": "無損益"}

    cost_ratio = result.total_commission / abs(total_pnl)
    passed = cost_ratio < 0.50  # 成本不應超過收益的 50%
    return {
        "name": "成本影響",
        "passed": passed,
        "detail": f"成本佔收益 {cost_ratio:.1%}" + (" (成本過高)" if not passed else ""),
    }


# ─── 品質驗證（動態重跑）──────────────────────────────


@dataclass
class QualityValidationResult:
    """單一品質驗證項目的結果。"""
    test_name: str
    passed: bool
    details: str


def _run_backtest_fresh(
    strategy: "Strategy",
    config: "BacktestConfig",
) -> BacktestResult:
    """建立全新引擎並執行回測，避免狀態洩漏。"""
    from src.backtest.engine import BacktestEngine

    engine = BacktestEngine()
    return engine.run(strategy, config)


def check_causality(
    strategy: "Strategy",
    config: "BacktestConfig",
    seed: int = 42,
) -> QualityValidationResult:
    """
    因果性檢查：打亂時間軸，結果應不同。

    Run backtest normally, then run with shuffled trading dates.
    If results are identical, the strategy may be using future data.
    """
    from src.backtest.engine import BacktestEngine

    # Run 1: normal
    result_a = _run_backtest_fresh(strategy, config)

    # Run 2: shuffled trading dates
    engine_b = BacktestEngine()
    original_method = engine_b._get_trading_dates

    def _shuffled_trading_dates(feed, cfg):  # type: ignore[no-untyped-def]
        dates = original_method(feed, cfg)
        rng = random.Random(seed)
        rng.shuffle(dates)
        return dates

    engine_b._get_trading_dates = _shuffled_trading_dates  # type: ignore[method-assign]
    result_b = engine_b.run(strategy, config)

    if result_a.total_return == result_b.total_return and result_a.total_trades > 0:
        return QualityValidationResult(
            test_name="causality",
            passed=False,
            details=(
                f"Shuffled dates produced identical total_return "
                f"({result_a.total_return:.6f}). "
                f"Strategy may be using future data (look-ahead bias)."
            ),
        )

    return QualityValidationResult(
        test_name="causality",
        passed=True,
        details=(
            f"Normal return={result_a.total_return:.6f}, "
            f"shuffled return={result_b.total_return:.6f} — "
            f"results differ, no obvious look-ahead bias."
        ),
    )


def check_determinism(
    strategy: "Strategy",
    config: "BacktestConfig",
) -> QualityValidationResult:
    """
    確定性檢查：相同輸入跑兩次，結果應完全相同。
    """
    result_a = _run_backtest_fresh(strategy, config)
    result_b = _run_backtest_fresh(strategy, config)

    mismatches: list[str] = []
    for attr in ("total_return", "sharpe", "max_drawdown", "total_trades"):
        val_a = getattr(result_a, attr)
        val_b = getattr(result_b, attr)
        if val_a != val_b:
            mismatches.append(f"{attr}: {val_a} != {val_b}")

    if mismatches:
        return QualityValidationResult(
            test_name="determinism",
            passed=False,
            details=f"Mismatches on identical runs: {'; '.join(mismatches)}",
        )

    return QualityValidationResult(
        test_name="determinism",
        passed=True,
        details=(
            f"Two identical runs produced matching results: "
            f"return={result_a.total_return:.6f}, "
            f"sharpe={result_a.sharpe:.4f}, "
            f"max_dd={result_a.max_drawdown:.6f}, "
            f"trades={result_a.total_trades}"
        ),
    )


def check_sensitivity(
    strategy: "Strategy",
    config: "BacktestConfig",
    slippage_multipliers: tuple[float, ...] = (0.5, 1.5, 2.0),
) -> QualityValidationResult:
    """
    穩健性檢查：微調滑價，結果不應崩潰。

    - All runs must complete without error.
    - Total return shouldn't flip sign between runs
      (strategy is directionally robust).
    """
    base_result = _run_backtest_fresh(strategy, config)
    base_sign = 1 if base_result.total_return >= 0 else -1

    results: list[tuple[float, float]] = [
        (config.slippage_bps, base_result.total_return),
    ]
    sign_flips: list[str] = []
    errors: list[str] = []

    for mult in slippage_multipliers:
        variant_config = copy.copy(config)
        variant_config.slippage_bps = config.slippage_bps * mult

        try:
            result = _run_backtest_fresh(strategy, variant_config)
        except Exception as exc:
            errors.append(f"slippage x{mult}: {exc}")
            continue

        results.append((variant_config.slippage_bps, result.total_return))

        variant_sign = 1 if result.total_return >= 0 else -1
        # Only flag sign flips when the base return is meaningfully non-zero
        if abs(base_result.total_return) > 1e-6 and variant_sign != base_sign:
            sign_flips.append(
                f"slippage x{mult}: return={result.total_return:.6f} "
                f"(base={base_result.total_return:.6f})"
            )

    if errors:
        return QualityValidationResult(
            test_name="sensitivity",
            passed=False,
            details=f"Runs failed: {'; '.join(errors)}",
        )

    if sign_flips:
        return QualityValidationResult(
            test_name="sensitivity",
            passed=False,
            details=(
                f"Return sign flipped under slippage variation: "
                f"{'; '.join(sign_flips)}"
            ),
        )

    summary = ", ".join(
        f"slip={s:.1f}bps->ret={r:.6f}" for s, r in results
    )
    return QualityValidationResult(
        test_name="sensitivity",
        passed=True,
        details=f"All slippage variants completed, directionally consistent: {summary}",
    )


def run_all_quality_validations(
    strategy: "Strategy",
    config: "BacktestConfig",
) -> list[QualityValidationResult]:
    """Run all quality validation checks and return results."""
    return [
        check_causality(strategy, config),
        check_determinism(strategy, config),
        check_sensitivity(strategy, config),
    ]
