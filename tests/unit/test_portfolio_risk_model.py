"""Unit tests for portfolio risk model.

Tests VaR, CVaR, covariance estimation, portfolio risk, and risk contribution.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.portfolio.risk_model import (
    RiskModel,
    RiskModelConfig,
    estimate_factor_covariance,
    estimate_garch_volatility,
    shrink_mean,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_returns(n: int = 252, n_assets: int = 3, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic daily returns DataFrame."""
    rng = np.random.RandomState(seed)
    data = rng.randn(n, n_assets) * 0.01 + 0.0003
    symbols = [f"A{i}" for i in range(n_assets)]
    dates = pd.bdate_range("2023-01-01", periods=n)
    return pd.DataFrame(data, index=dates, columns=symbols)


def _make_return_series(n: int = 252, seed: int = 42) -> pd.Series:
    """Generate synthetic daily return Series."""
    rng = np.random.RandomState(seed)
    data = rng.randn(n) * 0.015 - 0.0001
    dates = pd.bdate_range("2023-01-01", periods=n)
    return pd.Series(data, index=dates, name="returns")


# ===========================================================================
# 1. VaR computation
# ===========================================================================


class TestVaR:
    """Tests for RiskModel.compute_var."""

    def test_historical_var_basic(self):
        """Historical VaR returns positive value for typical returns."""
        returns = _make_return_series(252)
        var = RiskModel.compute_var(returns, confidence=0.95, method="historical")
        assert var >= 0.0
        assert isinstance(var, float)

    def test_parametric_var_basic(self):
        """Parametric VaR returns positive value for typical returns."""
        returns = _make_return_series(252)
        var = RiskModel.compute_var(returns, confidence=0.95, method="parametric")
        assert var >= 0.0
        assert isinstance(var, float)

    def test_var_higher_confidence_is_larger(self):
        """99% VaR should be >= 95% VaR."""
        returns = _make_return_series(500, seed=123)
        var_95 = RiskModel.compute_var(returns, confidence=0.95)
        var_99 = RiskModel.compute_var(returns, confidence=0.99)
        assert var_99 >= var_95

    def test_var_empty_series(self):
        """Empty series returns 0."""
        returns = pd.Series(dtype=float)
        var = RiskModel.compute_var(returns, confidence=0.95)
        assert var == 0.0

    def test_var_single_value(self):
        """Single value returns 0."""
        returns = pd.Series([0.01])
        var = RiskModel.compute_var(returns, confidence=0.95)
        assert var == 0.0

    def test_var_all_positive(self):
        """All-positive returns should produce VaR close to 0."""
        returns = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05] * 20)
        var = RiskModel.compute_var(returns, confidence=0.95)
        assert var == 0.0  # No losses

    def test_var_all_nan(self):
        """All-NaN returns 0."""
        returns = pd.Series([np.nan, np.nan, np.nan])
        var = RiskModel.compute_var(returns, confidence=0.95)
        assert var == 0.0

    def test_parametric_var_zero_sigma(self):
        """Constant returns gives zero parametric VaR."""
        returns = pd.Series([0.01] * 100)
        var = RiskModel.compute_var(returns, confidence=0.95, method="parametric")
        assert var == 0.0


# ===========================================================================
# 2. CVaR computation
# ===========================================================================


class TestCVaR:
    """Tests for RiskModel.compute_cvar."""

    def test_historical_cvar_basic(self):
        """Historical CVaR returns positive value."""
        returns = _make_return_series(252)
        cvar = RiskModel.compute_cvar(returns, confidence=0.95, method="historical")
        assert cvar >= 0.0

    def test_parametric_cvar_basic(self):
        """Parametric CVaR returns positive value."""
        returns = _make_return_series(252)
        cvar = RiskModel.compute_cvar(returns, confidence=0.95, method="parametric")
        assert cvar >= 0.0

    def test_cvar_ge_var(self):
        """CVaR should be >= VaR (Expected Shortfall is worse than VaR)."""
        returns = _make_return_series(500, seed=99)
        var = RiskModel.compute_var(returns, confidence=0.95)
        cvar = RiskModel.compute_cvar(returns, confidence=0.95)
        assert cvar >= var - 1e-10  # small tolerance

    def test_cvar_empty_series(self):
        """Empty series returns 0."""
        returns = pd.Series(dtype=float)
        cvar = RiskModel.compute_cvar(returns, confidence=0.95)
        assert cvar == 0.0

    def test_cvar_single_value(self):
        """Single value returns 0."""
        returns = pd.Series([0.01])
        cvar = RiskModel.compute_cvar(returns, confidence=0.95)
        assert cvar == 0.0

    def test_parametric_cvar_zero_sigma(self):
        """Constant returns gives zero parametric CVaR."""
        returns = pd.Series([0.01] * 100)
        cvar = RiskModel.compute_cvar(returns, confidence=0.95, method="parametric")
        assert cvar == 0.0


# ===========================================================================
# 3. Covariance estimation
# ===========================================================================


class TestCovarianceEstimation:
    """Tests for RiskModel.estimate_covariance."""

    def test_basic_covariance(self):
        """Covariance matrix has correct shape."""
        returns = _make_returns(252, 3)
        model = RiskModel()
        cov = model.estimate_covariance(returns)
        assert cov.shape == (3, 3)
        assert list(cov.columns) == ["A0", "A1", "A2"]

    def test_covariance_is_symmetric(self):
        """Covariance matrix is symmetric."""
        returns = _make_returns(252, 4)
        model = RiskModel()
        cov = model.estimate_covariance(returns)
        np.testing.assert_array_almost_equal(cov.values, cov.values.T)

    def test_covariance_positive_diagonal(self):
        """Diagonal elements (variances) are positive."""
        returns = _make_returns(252, 3)
        model = RiskModel()
        cov = model.estimate_covariance(returns)
        for i in range(3):
            assert cov.values[i, i] > 0

    def test_covariance_annualized(self):
        """Default config annualizes covariance."""
        returns = _make_returns(252, 2)
        model_ann = RiskModel(RiskModelConfig(annualize=True, shrinkage=False))
        model_raw = RiskModel(RiskModelConfig(annualize=False, shrinkage=False))
        cov_ann = model_ann.estimate_covariance(returns)
        cov_raw = model_raw.estimate_covariance(returns)
        # Annualized should be ~252x raw
        ratio = cov_ann.values[0, 0] / cov_raw.values[0, 0]
        assert abs(ratio - 252) < 1.0

    def test_covariance_insufficient_data(self):
        """Insufficient data returns empty DataFrame."""
        returns = _make_returns(10, 3)  # Less than min_history=60
        model = RiskModel()
        cov = model.estimate_covariance(returns)
        assert cov.empty

    def test_covariance_empty_returns(self):
        """Empty DataFrame returns empty covariance."""
        returns = pd.DataFrame()
        model = RiskModel()
        cov = model.estimate_covariance(returns)
        assert cov.empty

    def test_covariance_single_asset(self):
        """Single asset returns empty (need >= 2)."""
        returns = _make_returns(252, 1)
        model = RiskModel()
        cov = model.estimate_covariance(returns)
        assert cov.empty

    def test_covariance_with_ewm(self):
        """EWM covariance runs without error."""
        returns = _make_returns(252, 3)
        model = RiskModel(RiskModelConfig(ewm_halflife=30, shrinkage=False))
        cov = model.estimate_covariance(returns)
        assert cov.shape == (3, 3)

    def test_covariance_with_shrinkage(self):
        """Ledoit-Wolf shrinkage produces valid covariance."""
        returns = _make_returns(252, 3)
        model = RiskModel(RiskModelConfig(shrinkage=True))
        cov = model.estimate_covariance(returns)
        assert cov.shape == (3, 3)
        # Diagonal should still be positive
        for i in range(3):
            assert cov.values[i, i] > 0


# ===========================================================================
# 4. Portfolio risk
# ===========================================================================


class TestPortfolioRisk:
    """Tests for RiskModel.portfolio_risk."""

    def test_basic_portfolio_risk(self):
        """Portfolio risk returns positive value."""
        returns = _make_returns(252, 3)
        model = RiskModel()
        cov = model.estimate_covariance(returns)
        weights = {"A0": 0.4, "A1": 0.3, "A2": 0.3}
        risk = model.portfolio_risk(weights, cov)
        assert risk > 0.0

    def test_empty_portfolio(self):
        """Empty weights returns 0."""
        cov = pd.DataFrame(np.eye(2), columns=["A", "B"], index=["A", "B"])
        model = RiskModel()
        risk = model.portfolio_risk({}, cov)
        assert risk == 0.0

    def test_empty_covariance(self):
        """Empty covariance returns 0."""
        model = RiskModel()
        risk = model.portfolio_risk({"A": 0.5}, pd.DataFrame())
        assert risk == 0.0

    def test_single_asset_risk(self):
        """Single asset portfolio risk equals asset volatility * weight."""
        vol = 0.20
        cov = pd.DataFrame(
            [[vol**2]],
            columns=["A"],
            index=["A"],
        )
        model = RiskModel()
        risk = model.portfolio_risk({"A": 1.0}, cov)
        assert abs(risk - vol) < 1e-10

    def test_weights_not_in_covariance(self):
        """Weights with symbols not in covariance returns 0."""
        cov = pd.DataFrame(np.eye(2), columns=["A", "B"], index=["A", "B"])
        model = RiskModel()
        risk = model.portfolio_risk({"X": 0.5, "Y": 0.5}, cov)
        assert risk == 0.0


# ===========================================================================
# 5. Risk contribution
# ===========================================================================


class TestRiskContribution:
    """Tests for RiskModel.risk_contribution."""

    def test_risk_contribution_sums_to_one(self):
        """Risk contributions sum to 1.0."""
        returns = _make_returns(252, 3)
        model = RiskModel()
        cov = model.estimate_covariance(returns)
        weights = {"A0": 0.4, "A1": 0.3, "A2": 0.3}
        rc = model.risk_contribution(weights, cov)
        assert abs(sum(rc.values()) - 1.0) < 1e-6

    def test_risk_contribution_all_positive(self):
        """Positive weights with positive cov gives positive contributions."""
        returns = _make_returns(252, 3)
        model = RiskModel()
        cov = model.estimate_covariance(returns)
        weights = {"A0": 0.4, "A1": 0.3, "A2": 0.3}
        rc = model.risk_contribution(weights, cov)
        for v in rc.values():
            assert v > 0.0

    def test_risk_contribution_empty(self):
        """Empty weights returns empty dict."""
        model = RiskModel()
        rc = model.risk_contribution({}, pd.DataFrame())
        assert rc == {}

    def test_risk_contribution_single_asset(self):
        """Single asset gets risk contribution of 1.0."""
        cov = pd.DataFrame([[0.04]], columns=["A"], index=["A"])
        model = RiskModel()
        rc = model.risk_contribution({"A": 1.0}, cov)
        assert rc == {"A": 1.0}


# ===========================================================================
# 6. Correlation and volatility
# ===========================================================================


class TestCorrelationAndVolatility:
    """Tests for correlation and volatility methods."""

    def test_correlation_diagonal_is_one(self):
        """Correlation matrix diagonal should be 1."""
        returns = _make_returns(252, 3)
        model = RiskModel()
        corr = model.estimate_correlation(returns)
        for i in range(3):
            assert abs(corr.values[i, i] - 1.0) < 1e-10

    def test_correlation_range(self):
        """All correlations are in [-1, 1]."""
        returns = _make_returns(252, 3)
        model = RiskModel()
        corr = model.estimate_correlation(returns)
        assert (corr.values >= -1.0 - 1e-10).all()
        assert (corr.values <= 1.0 + 1e-10).all()

    def test_volatilities_positive(self):
        """Computed volatilities are positive."""
        returns = _make_returns(252, 3)
        model = RiskModel()
        vols = model.compute_volatilities(returns)
        assert len(vols) == 3
        for v in vols:
            assert v > 0.0

    def test_volatilities_annualized(self):
        """Annualized vols are ~sqrt(252)x daily."""
        returns = _make_returns(252, 2)
        model_ann = RiskModel(RiskModelConfig(annualize=True))
        model_raw = RiskModel(RiskModelConfig(annualize=False))
        vols_ann = model_ann.compute_volatilities(returns)
        vols_raw = model_raw.compute_volatilities(returns)
        ratio = vols_ann.iloc[0] / vols_raw.iloc[0]
        assert abs(ratio - np.sqrt(252)) < 0.1

    def test_volatilities_empty(self):
        """Empty returns gives empty series."""
        model = RiskModel()
        vols = model.compute_volatilities(pd.DataFrame())
        assert len(vols) == 0


# ===========================================================================
# 7. GARCH volatility
# ===========================================================================


class TestGARCH:
    """Tests for estimate_garch_volatility."""

    def test_garch_returns_series(self):
        """GARCH returns a Series of the same length."""
        returns = _make_return_series(252)
        vol = estimate_garch_volatility(returns)
        assert len(vol) == len(returns.dropna())

    def test_garch_positive_values(self):
        """GARCH volatility values are all positive."""
        returns = _make_return_series(252)
        vol = estimate_garch_volatility(returns)
        assert (vol > 0).all()

    def test_garch_short_series(self):
        """Series with < 10 points returns empty."""
        returns = pd.Series([0.01, 0.02, 0.03])
        vol = estimate_garch_volatility(returns)
        assert len(vol) == 0

    def test_garch_annualized(self):
        """Annualized GARCH vols are larger than non-annualized."""
        returns = _make_return_series(100)
        vol_ann = estimate_garch_volatility(returns, annualize=True)
        vol_raw = estimate_garch_volatility(returns, annualize=False)
        assert vol_ann.mean() > vol_raw.mean()


# ===========================================================================
# 8. Factor model covariance
# ===========================================================================


class TestFactorCovariance:
    """Tests for estimate_factor_covariance."""

    def test_factor_cov_shape(self):
        """Factor covariance has correct shape."""
        returns = _make_returns(100, 5)
        cov = estimate_factor_covariance(returns, n_factors=3)
        assert cov.shape == (5, 5)

    def test_factor_cov_symmetric(self):
        """Factor covariance is symmetric."""
        returns = _make_returns(100, 5)
        cov = estimate_factor_covariance(returns, n_factors=3)
        np.testing.assert_array_almost_equal(cov, cov.T)

    def test_factor_cov_short_data(self):
        """Short data fallbacks to np.cov."""
        returns = _make_returns(5, 3)
        cov = estimate_factor_covariance(returns, n_factors=2)
        assert cov.shape == (3, 3)


# ===========================================================================
# 9. Shrink mean (James-Stein)
# ===========================================================================


class TestShrinkMean:
    """Tests for shrink_mean."""

    def test_shrink_basic(self):
        """Shrunk mean has same length as input."""
        mu = np.array([0.1, 0.2, 0.3, 0.4, 0.05])
        result = shrink_mean(mu, n_obs=252)
        assert len(result) == 5

    def test_shrink_two_elements_no_shrinkage(self):
        """With p < 3, no shrinkage applied."""
        mu = np.array([0.1, 0.2])
        result = shrink_mean(mu, n_obs=252)
        np.testing.assert_array_equal(result, mu)

    def test_shrink_toward_grand_mean(self):
        """Shrinkage moves values toward the grand mean."""
        mu = np.array([0.5, -0.5, 0.0, 0.3, -0.3])
        result = shrink_mean(mu, n_obs=10)
        grand_mean = float(np.mean(mu))
        # Each element should be (weakly) closer to grand_mean
        for i in range(len(mu)):
            assert abs(result[i] - grand_mean) <= abs(mu[i] - grand_mean) + 1e-10

    def test_shrink_all_same(self):
        """All-same values returns copy of input."""
        mu = np.array([0.1, 0.1, 0.1, 0.1])
        result = shrink_mean(mu, n_obs=252)
        np.testing.assert_array_almost_equal(result, mu)
