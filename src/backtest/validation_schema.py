"""Unified validation report JSON schema.

Every strategy validation produces a JSON report with this structure.
Used by paper/live promotion decisions.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass
class ValidationReportJSON:
    """Standard JSON output for all strategy validations."""

    strategy_name: str
    timestamp: str = ""
    validator_version: str = "v3.0-AM"
    decision: str = ""  # "pass" / "pass-with-warning" / "fail"

    # Gate results: name -> {passed, value, threshold}
    hard_gates: dict = field(default_factory=dict)
    soft_gates: dict = field(default_factory=dict)
    n_hard_pass: int = 0
    n_hard_total: int = 0
    n_soft_fail: int = 0

    # Descriptive sections
    cost_breakdown: str = ""
    regime_split: str = ""
    capacity_analysis: str = ""
    stress_test: str = ""
    benchmark_relative: str = ""
    factor_attribution: str = ""
    exit_warning: str = ""
    oos_regime: str = ""
    announcement_warning: str = ""

    # Config fingerprint
    universe_size: int = 0
    initial_cash: float = 0
    n_trials: int = 0
    oos_start: str = ""
    oos_end: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False, default=str)

    @classmethod
    def from_validation_report(cls, report, config=None) -> ValidationReportJSON:
        """Convert ValidationReport to standard JSON schema."""
        from src.backtest.validator import VALIDATOR_VERSION

        hard_checks = [c for c in report.checks if c.hard]
        soft_checks = [c for c in report.checks if not c.hard]

        n_soft_fail = sum(1 for c in soft_checks if not c.passed)
        all_hard_pass = all(c.passed for c in hard_checks)

        if not all_hard_pass or report.error:
            decision = "fail"
        elif n_soft_fail > 0:
            decision = "pass-with-warning"
        else:
            decision = "pass"

        obj = cls(
            strategy_name=report.strategy_name,
            timestamp=datetime.now().isoformat(),
            validator_version=VALIDATOR_VERSION,
            decision=decision,
            hard_gates={
                c.name: {"passed": c.passed, "value": c.value, "threshold": c.threshold}
                for c in hard_checks
            },
            soft_gates={
                c.name: {"passed": c.passed, "value": c.value, "threshold": c.threshold}
                for c in soft_checks
            },
            n_hard_pass=sum(1 for c in hard_checks if c.passed),
            n_hard_total=len(hard_checks),
            n_soft_fail=n_soft_fail,
            cost_breakdown=report.cost_breakdown,
            regime_split=report.regime_split,
            capacity_analysis=report.capacity_analysis,
            stress_test=report.stress_test,
            benchmark_relative=report.benchmark_relative,
            factor_attribution=report.factor_attribution,
            exit_warning=report.exit_warning,
            oos_regime=report.oos_regime,
            announcement_warning=report.announcement_warning,
        )

        if config:
            obj.universe_size = getattr(config, "universe_size", 0)
            obj.initial_cash = getattr(config, "initial_cash", 0)
            obj.n_trials = getattr(config, "n_bootstrap_trials", 0)

        return obj
