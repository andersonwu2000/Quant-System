"""
回測驗證 — 確保回測結果的嚴謹性。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.backtest.analytics import BacktestResult

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """驗證結果。"""
    passed: bool
    checks: list[dict]

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
    checks: list[dict] = []

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


def _check_nonzero_trades(result: BacktestResult) -> dict:
    passed = result.total_trades > 0
    return {
        "name": "非零交易",
        "passed": passed,
        "detail": f"{result.total_trades} 筆交易" if passed else "無任何交易，策略可能有問題",
    }


def _check_nav_continuity(result: BacktestResult) -> dict:
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


def _check_return_sanity(result: BacktestResult) -> dict:
    """年化報酬不應超過 200%（除非是極短期回測）。"""
    passed = abs(result.annual_return) < 2.0
    return {
        "name": "收益合理性",
        "passed": passed,
        "detail": f"年化 {result.annual_return:.2%}" + (" (可能過擬合)" if not passed else ""),
    }


def _check_sharpe_sanity(result: BacktestResult) -> dict:
    """Sharpe > 3.0 通常暗示過擬合。"""
    suspicious = result.sharpe > 3.0
    return {
        "name": "Sharpe 合理性",
        "passed": not suspicious,
        "detail": f"Sharpe {result.sharpe:.2f}" + (" (疑似過擬合)" if suspicious else ""),
    }


def _check_cost_impact(result: BacktestResult) -> dict:
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
