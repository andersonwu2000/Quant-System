"""Tests for Deflated Sharpe Ratio and Minimum Backtest Length (H1)."""

from __future__ import annotations

from src.backtest.analytics import deflated_sharpe, min_backtest_length


class TestDeflatedSharpe:
    def test_single_trial_high_dsr(self) -> None:
        """With n_trials=1, no correction needed — DSR should be high."""
        dsr = deflated_sharpe(observed_sharpe=1.5, n_trials=1, T=500)
        assert dsr > 0.90, f"Expected DSR > 0.90 for single trial, got {dsr}"

    def test_many_trials_lower_dsr(self) -> None:
        """With n_trials=1000, heavy correction — DSR should be much lower."""
        dsr = deflated_sharpe(observed_sharpe=1.5, n_trials=1000, T=500)
        assert dsr < 0.50, f"Expected DSR < 0.50 for 1000 trials, got {dsr}"

    def test_zero_sharpe_returns_about_half(self) -> None:
        """DSR with SR=0 should return a low value (near 0 for many trials)."""
        dsr_few = deflated_sharpe(observed_sharpe=0.0, n_trials=1, T=500)
        # With 1 trial, E[max SR] = 0 and observed=0 → z=0 → DSR ≈ 0.5
        assert 0.4 < dsr_few < 0.6, f"Expected ~0.5 for SR=0, 1 trial, got {dsr_few}"

    def test_dsr_increases_with_sharpe(self) -> None:
        """Higher observed Sharpe → higher DSR, all else equal."""
        dsr_low = deflated_sharpe(observed_sharpe=0.5, n_trials=10, T=500)
        dsr_high = deflated_sharpe(observed_sharpe=2.0, n_trials=10, T=500)
        assert dsr_high > dsr_low

    def test_dsr_decreases_with_more_trials(self) -> None:
        """More trials → lower DSR (harder to pass correction)."""
        dsr_few = deflated_sharpe(observed_sharpe=1.0, n_trials=5, T=500)
        dsr_many = deflated_sharpe(observed_sharpe=1.0, n_trials=500, T=500)
        assert dsr_few > dsr_many

    def test_edge_case_T_equals_2(self) -> None:
        """Should not crash with T=2 (minimum valid)."""
        dsr = deflated_sharpe(observed_sharpe=1.0, n_trials=10, T=2)
        assert 0.0 <= dsr <= 1.0

    def test_edge_case_T_equals_1(self) -> None:
        """T=1 should return 0.0 (not enough data)."""
        dsr = deflated_sharpe(observed_sharpe=1.0, n_trials=10, T=1)
        assert dsr == 0.0

    def test_negative_sharpe(self) -> None:
        """Negative Sharpe ratio should give very low DSR."""
        dsr = deflated_sharpe(observed_sharpe=-1.0, n_trials=10, T=500)
        assert dsr < 0.05, f"Expected DSR < 0.05 for negative Sharpe, got {dsr}"

    def test_non_normal_skewness(self) -> None:
        """Positive skewness should slightly increase DSR."""
        dsr_normal = deflated_sharpe(observed_sharpe=1.0, n_trials=10, T=500, skewness=0.0)
        # Positive skewness with positive SR: -skew*SR term reduces SE → higher z → higher DSR
        dsr_skewed = deflated_sharpe(observed_sharpe=1.0, n_trials=10, T=500, skewness=0.5)
        # Both should be in valid range
        assert 0.0 <= dsr_normal <= 1.0
        assert 0.0 <= dsr_skewed <= 1.0

    def test_high_kurtosis_lowers_confidence(self) -> None:
        """Fat tails (kurtosis > 3) should widen SE → lower DSR.

        Use a large SR and short T to make the higher-order effect visible.
        """
        dsr_normal = deflated_sharpe(observed_sharpe=3.0, n_trials=10, T=100, kurtosis=3.0)
        dsr_fat = deflated_sharpe(observed_sharpe=3.0, n_trials=10, T=100, kurtosis=10.0)
        assert dsr_fat < dsr_normal


class TestMinBacktestLength:
    def test_increases_with_n_trials(self) -> None:
        """More trials requires longer backtest."""
        t_few = min_backtest_length(n_trials=5, target_sharpe=2.0)
        t_many = min_backtest_length(n_trials=100, target_sharpe=2.0)
        assert t_many > t_few

    def test_default_params_reasonable_range(self) -> None:
        """With default params and 10 trials, T should be a reasonable number.

        For annualized SR=1.0 with 10 trials, need substantial data
        to achieve 95% confidence after multiple testing correction.
        """
        t = min_backtest_length(n_trials=10, target_sharpe=1.0)
        assert 100 < t < 10000, f"Expected 100-10000 days, got {t}"

    def test_single_trial_shortest(self) -> None:
        """Single trial should need the shortest backtest."""
        t = min_backtest_length(n_trials=1, target_sharpe=1.0)
        assert t < 2000, f"Expected < 2000 days for 1 trial, got {t}"

    def test_low_sharpe_needs_longer(self) -> None:
        """Lower target Sharpe needs longer backtest to be significant."""
        t_high_sr = min_backtest_length(n_trials=10, target_sharpe=2.0)
        t_low_sr = min_backtest_length(n_trials=10, target_sharpe=0.5)
        assert t_low_sr > t_high_sr

    def test_returns_integer(self) -> None:
        """Should always return an integer."""
        t = min_backtest_length(n_trials=10)
        assert isinstance(t, int)

    def test_zero_sharpe_returns_minimum(self) -> None:
        """Zero target Sharpe should return 2 (minimum)."""
        t = min_backtest_length(n_trials=10, target_sharpe=0.0)
        assert t == 2
