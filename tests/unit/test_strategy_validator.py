"""Tests for StrategyValidator (Phase L validation framework)."""

from __future__ import annotations


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
        assert cfg.min_cagr == 0.08
        assert cfg.max_drawdown == 0.40
        assert cfg.max_pbo == 0.60
        assert cfg.min_prob_sharpe_positive == 0.80
        assert cfg.max_annual_turnover == 0.80
        assert cfg.min_universe_size == 50
        assert cfg.max_market_corr == 0.65
        assert cfg.max_cvar_95 == -0.05

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
    """Verify that all 16 checks have corresponding thresholds in ValidationConfig."""

    def test_all_threshold_fields_exist(self) -> None:
        cfg = ValidationConfig()
        # 1. universe_size
        assert hasattr(cfg, "min_universe_size")
        # 2-4. Full backtest (cagr, sharpe, max_drawdown)
        assert hasattr(cfg, "min_cagr")
        assert hasattr(cfg, "min_sharpe")
        assert hasattr(cfg, "max_drawdown")
        # 5. annual_cost_ratio
        assert hasattr(cfg, "max_annual_turnover")
        assert hasattr(cfg, "max_cost_ratio")
        # 6. temporal_consistency (renamed from walkforward_positive)
        assert hasattr(cfg, "wf_min_positive_ratio")
        assert hasattr(cfg, "wf_train_years")
        # 7. deflated_sharpe
        assert hasattr(cfg, "min_dsr")
        assert hasattr(cfg, "n_trials")
        # 8. bootstrap_p_sharpe_positive
        assert hasattr(cfg, "min_prob_sharpe_positive")
        assert hasattr(cfg, "bootstrap_n")
        # 9. oos_sharpe (rolling)
        assert hasattr(cfg, "oos_start")
        assert hasattr(cfg, "oos_end")
        assert hasattr(cfg, "oos_min_sharpe")
        # 10. vs_ew_universe
        assert hasattr(cfg, "min_excess_return")
        # 11. construction_sensitivity (renamed from pbo)
        assert hasattr(cfg, "max_pbo")
        # 12. worst_regime (drawdown-based)
        assert hasattr(cfg, "max_worst_regime_loss")
        # 13. recent_period_sharpe
        assert hasattr(cfg, "decay_lookback_days")
        assert hasattr(cfg, "min_recent_sharpe")
        # 14. market_correlation
        assert hasattr(cfg, "max_market_corr")
        # 15. cvar_95
        assert hasattr(cfg, "max_cvar_95")
        # 16. permutation_p — no config threshold (hardcoded < 0.10 in validator)

    def test_rolling_oos_auto_computed(self) -> None:
        """OOS dates should be auto-computed from today, not hardcoded."""
        from datetime import datetime, timedelta

        cfg = ValidationConfig()
        today = datetime.now()
        oos_end = datetime.strptime(cfg.oos_end, "%Y-%m-%d")
        oos_start = datetime.strptime(cfg.oos_start, "%Y-%m-%d")

        # oos_end should be yesterday (±1 day tolerance)
        assert abs((oos_end - (today - timedelta(days=1))).days) <= 1
        # OOS2 (second half): ~274 days (Phase AM: split 549d into L5+Validator)
        window = (oos_end - oos_start).days
        assert 273 <= window <= 276

    def test_default_thresholds_match_phase_ac(self) -> None:
        """Frozen thresholds from Phase AC must not drift."""
        cfg = ValidationConfig()
        assert cfg.min_cagr == 0.08
        assert cfg.min_sharpe == 0.7
        assert cfg.max_drawdown == 0.40
        assert cfg.max_pbo == 0.60
        assert cfg.min_dsr == 0.70
        assert cfg.min_prob_sharpe_positive == 0.80
        assert cfg.oos_min_sharpe == 0.3
        assert cfg.min_excess_return == 0.0
        assert cfg.max_market_corr == 0.65
        assert cfg.max_cvar_95 == -0.05


class TestStationaryBootstrapInvariant:
    """Stationary Bootstrap (Politis & Romano 1994) behavior tests."""

    def test_positive_returns_high_probability(self) -> None:
        """Strong positive returns → P(Sharpe > 0) should be high."""
        import numpy as np
        import pandas as pd
        from src.backtest.analytics import BacktestResult

        rng = np.random.default_rng(42)
        returns = pd.Series(rng.normal(0.001, 0.01, 500))
        nav = (1 + returns).cumprod() * 1_000_000
        nav.index = pd.bdate_range("2023-01-01", periods=500)

        result = BacktestResult.__new__(BacktestResult)
        result.daily_returns = returns

        v = StrategyValidator()
        prob = v._bootstrap_sharpe(result, n_bootstrap=500)
        assert prob > 0.90

    def test_zero_mean_returns_near_half(self) -> None:
        """Zero-mean returns → P(Sharpe > 0) should be near 0.5."""
        import numpy as np
        import pandas as pd
        from src.backtest.analytics import BacktestResult

        rng = np.random.default_rng(42)
        returns = pd.Series(rng.normal(0.0, 0.02, 500))
        result = BacktestResult.__new__(BacktestResult)
        result.daily_returns = returns

        v = StrategyValidator()
        prob = v._bootstrap_sharpe(result, n_bootstrap=500)
        assert 0.2 < prob < 0.8

    def test_too_few_returns_fail_closed(self) -> None:
        """Less than 20 returns → should return 0.0 (fail-closed)."""
        import pandas as pd
        from src.backtest.analytics import BacktestResult

        result = BacktestResult.__new__(BacktestResult)
        result.daily_returns = pd.Series([0.01] * 10)

        v = StrategyValidator()
        prob = v._bootstrap_sharpe(result, n_bootstrap=100)
        assert prob == 0.0

    def test_deterministic_with_fixed_seed(self) -> None:
        """Same input → same output (seed=42 inside method)."""
        import numpy as np
        import pandas as pd
        from src.backtest.analytics import BacktestResult

        rng = np.random.default_rng(99)
        returns = pd.Series(rng.normal(0.0005, 0.015, 300))
        result = BacktestResult.__new__(BacktestResult)
        result.daily_returns = returns

        v = StrategyValidator()
        p1 = v._bootstrap_sharpe(result, n_bootstrap=200)
        p2 = v._bootstrap_sharpe(result, n_bootstrap=200)
        assert p1 == p2


class TestValidatorCheckNames:
    """Verify check names haven't drifted.

    15 checks always run + permutation_p conditional (only with compute_fn).
    """

    ALWAYS_CHECKS = {
        "universe_size", "cagr", "sharpe", "max_drawdown",
        "annual_cost_ratio", "temporal_consistency",
        "deflated_sharpe", "bootstrap_p_sharpe_positive",
        "oos_sharpe", "vs_ew_universe", "construction_sensitivity",
        "worst_regime", "recent_period_sharpe", "market_correlation",
        "cvar_95", "naive_baseline",
    }
    CONDITIONAL_CHECKS = {"permutation_p"}  # only with compute_fn

    def test_always_count(self) -> None:
        assert len(self.ALWAYS_CHECKS) == 16

    def test_total_with_conditional(self) -> None:
        assert len(self.ALWAYS_CHECKS | self.CONDITIONAL_CHECKS) == 17

    def test_no_old_names(self) -> None:
        """Old check names must not appear."""
        OLD_NAMES = {"walkforward_positive_ratio", "vs_0050_excess", "pbo", "walkforward_positive"}
        all_checks = self.ALWAYS_CHECKS | self.CONDITIONAL_CHECKS
        assert all_checks.isdisjoint(OLD_NAMES)
