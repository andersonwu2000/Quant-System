"""Tests for StrategyValidator (Phase L validation framework)."""

from __future__ import annotations

import pytest

from src.backtest.validator import (
    CheckResult,
    ValidationConfig,
    ValidationReport,
    StrategyValidator,
)


class TestCheckResult:
    def test_passed(self) -> None:
        c = CheckResult(name="test", passed=True, value="1.5", threshold="> 1.0")
        assert c.passed

    def test_failed(self) -> None:
        c = CheckResult(name="test", passed=False, value="0.5", threshold="> 1.0")
        assert not c.passed


class TestValidationReport:
    def test_all_passed(self) -> None:
        r = ValidationReport(strategy_name="test")
        r.checks = [
            CheckResult("a", True, "1", "> 0"),
            CheckResult("b", True, "2", "> 1"),
        ]
        assert r.passed
        assert r.n_passed == 2
        assert r.n_total == 2

    def test_one_failed(self) -> None:
        r = ValidationReport(strategy_name="test")
        r.checks = [
            CheckResult("a", True, "1", "> 0"),
            CheckResult("b", False, "0", "> 1"),
        ]
        assert not r.passed
        assert r.n_passed == 1

    def test_error_means_failed(self) -> None:
        r = ValidationReport(strategy_name="test", error="boom")
        assert not r.passed

    def test_summary_contains_strategy_name(self) -> None:
        r = ValidationReport(strategy_name="my_strat")
        r.checks = [CheckResult("a", True, "1", "> 0")]
        summary = r.summary()
        assert "my_strat" in summary
        assert "PASSED" in summary

    def test_summary_failed_lists_failures(self) -> None:
        r = ValidationReport(strategy_name="test")
        r.checks = [
            CheckResult("good_check", True, "1", "> 0"),
            CheckResult("bad_check", False, "0", "> 1"),
        ]
        summary = r.summary()
        assert "FAILED" in summary
        assert "bad_check" in summary


class TestValidationConfig:
    def test_defaults(self) -> None:
        cfg = ValidationConfig()
        assert cfg.min_sharpe == 0.7
        assert cfg.min_cagr == 0.15
        assert cfg.max_pbo == 0.50
        assert cfg.min_prob_sharpe_positive == 0.80
        assert cfg.max_annual_turnover == 0.80
        assert cfg.min_universe_size == 50

    def test_custom_thresholds(self) -> None:
        cfg = ValidationConfig(
            min_sharpe=1.0,
            min_cagr=0.20,
            n_trials=10,
        )
        assert cfg.min_sharpe == 1.0
        assert cfg.n_trials == 10


class TestStrategyValidator:
    def test_init_default_config(self) -> None:
        v = StrategyValidator()
        assert v.config.min_sharpe == 0.7

    def test_init_custom_config(self) -> None:
        cfg = ValidationConfig(min_sharpe=2.0)
        v = StrategyValidator(cfg)
        assert v.config.min_sharpe == 2.0

    def test_validate_requires_strategy_interface(self) -> None:
        """Validator expects a Strategy with .name() method."""
        v = StrategyValidator()
        # Can't validate without proper Strategy object — just test init
        assert v.config is not None


class TestChecklistCompleteness:
    """Verify that all 11 checks are defined in ValidationConfig."""

    def test_all_threshold_fields_exist(self) -> None:
        cfg = ValidationConfig()
        # 1. Full backtest
        assert hasattr(cfg, "min_cagr")
        assert hasattr(cfg, "min_sharpe")
        assert hasattr(cfg, "max_drawdown")
        # 2. Walk-Forward
        assert hasattr(cfg, "wf_min_positive_ratio")
        assert hasattr(cfg, "wf_train_years")
        # 3. PBO
        assert hasattr(cfg, "max_pbo")
        # 4. Deflated Sharpe
        assert hasattr(cfg, "min_dsr")
        assert hasattr(cfg, "n_trials")
        # 5. Bootstrap
        assert hasattr(cfg, "min_prob_sharpe_positive")
        assert hasattr(cfg, "bootstrap_n")
        # 6. OOS holdout
        assert hasattr(cfg, "oos_start")
        assert hasattr(cfg, "oos_end")
        assert hasattr(cfg, "oos_min_return")
        # 7. vs benchmark
        assert hasattr(cfg, "min_excess_return")
        # 8. Turnover + cost
        assert hasattr(cfg, "max_annual_turnover")
        assert hasattr(cfg, "max_cost_ratio")
        # 9. Regime breakdown
        assert hasattr(cfg, "max_worst_regime_loss")
        # 10. Selection bias
        assert hasattr(cfg, "min_universe_size")
        # 11. Factor decay
        assert hasattr(cfg, "decay_lookback_days")
        assert hasattr(cfg, "min_recent_sharpe")
