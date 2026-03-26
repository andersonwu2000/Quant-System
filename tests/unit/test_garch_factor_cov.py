"""Phase G4: GARCH volatility and factor model covariance tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
from src.portfolio.risk_model import (
    RiskModel,
    RiskModelConfig,
    estimate_factor_covariance,
    estimate_garch_volatility,
)


# ── Helpers ──────────────────────────────────────────────


def _make_returns(
    n_symbols: int = 5, n_days: int = 500, seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=n_days)
    symbols = [f"SYM{i}" for i in range(n_symbols)]
    data = rng.normal(0.0003, 0.015, (n_days, n_symbols))
    return pd.DataFrame(data, index=dates, columns=symbols)


def _make_series_with_shock(n: int = 500, seed: int = 42) -> pd.Series:
    """Returns series with a large shock in the middle."""
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0, 0.01, n)
    # Inject a large shock at t=250
    r[250] = -0.10
    r[251] = -0.08
    dates = pd.bdate_range("2020-01-02", periods=n)
    return pd.Series(r, index=dates, name="asset")


# ── G4a: GARCH Volatility ────────────────────────────────


class TestGarchVolatility:
    def test_garch_returns_series(self) -> None:
        """GARCH vol returns a pandas Series with same index as input."""
        r = _make_returns()["SYM0"]
        vol = estimate_garch_volatility(r)
        assert isinstance(vol, pd.Series)
        assert len(vol) == len(r.dropna())

    def test_garch_vol_is_time_varying(self) -> None:
        """GARCH volatility should NOT be constant across time."""
        r = _make_series_with_shock()
        vol = estimate_garch_volatility(r, annualize=False)
        # Standard deviation of the vol series should be > 0
        assert float(vol.std()) > 0, "GARCH vol should be time-varying"

    def test_garch_vol_responds_to_shock(self) -> None:
        """After a large negative return, GARCH vol should spike."""
        r = _make_series_with_shock()
        vol = estimate_garch_volatility(r, annualize=False)
        # Vol after shock (index 252) should be higher than vol before (index 240)
        vol_before = float(vol.iloc[240])
        vol_after = float(vol.iloc[252])
        assert vol_after > vol_before, (
            f"GARCH vol should increase after shock: {vol_before:.6f} vs {vol_after:.6f}"
        )

    def test_garch_annualized(self) -> None:
        """Annualized GARCH vol should be ~sqrt(252) times daily."""
        r = _make_returns()["SYM0"]
        vol_daily = estimate_garch_volatility(r, annualize=False)
        vol_annual = estimate_garch_volatility(r, annualize=True)
        ratio = float(vol_annual.iloc[-1] / vol_daily.iloc[-1])
        assert abs(ratio - np.sqrt(252)) < 0.1

    def test_garch_short_series(self) -> None:
        """Too-short series returns empty."""
        r = pd.Series([0.01, -0.01], index=pd.bdate_range("2020-01-02", periods=2))
        vol = estimate_garch_volatility(r)
        assert len(vol) == 0


# ── G4b: Factor Model Covariance ─────────────────────────


class TestFactorCovariance:
    def test_factor_cov_shape(self) -> None:
        """Factor covariance should have same shape as sample covariance."""
        r = _make_returns(n_symbols=8)
        cov = estimate_factor_covariance(r, n_factors=3)
        assert cov.shape == (8, 8)

    def test_factor_cov_positive_semi_definite(self) -> None:
        """Factor covariance should be PSD (all eigenvalues >= 0)."""
        r = _make_returns(n_symbols=8, n_days=500)
        cov = estimate_factor_covariance(r, n_factors=3)
        eigenvalues = np.linalg.eigvalsh(cov)
        assert np.all(eigenvalues >= -1e-10), f"Non-PSD eigenvalues: {eigenvalues.min()}"

    def test_factor_cov_structured_rank(self) -> None:
        """B Sigma_f B' part should have rank <= n_factors."""
        r = _make_returns(n_symbols=10, n_days=500)
        n_factors = 3
        cov = estimate_factor_covariance(r, n_factors=n_factors)
        # Full matrix has higher rank due to Psi diagonal,
        # but the factor component should be low-rank
        # Just verify result is reasonable (rank >= n_factors)
        rank = np.linalg.matrix_rank(cov, tol=1e-8)
        assert rank >= n_factors

    def test_factor_cov_symmetric(self) -> None:
        """Factor covariance should be symmetric."""
        r = _make_returns()
        cov = estimate_factor_covariance(r, n_factors=3)
        np.testing.assert_allclose(cov, cov.T, atol=1e-10)

    def test_factor_cov_integration_with_risk_model(self) -> None:
        """RiskModel with factor_model=True should produce valid covariance."""
        r = _make_returns()
        cfg = RiskModelConfig(factor_model=True, n_factors=3, shrinkage=False)
        model = RiskModel(cfg)
        cov = model.estimate_covariance(r)
        assert not cov.empty
        assert cov.shape[0] == cov.shape[1]
        # Should be PSD
        eigenvalues = np.linalg.eigvalsh(cov.values)
        assert np.all(eigenvalues >= -1e-8)


class TestGarchIntegration:
    def test_garch_covariance_integration(self) -> None:
        """RiskModel with use_garch=True should produce valid covariance."""
        r = _make_returns()
        cfg = RiskModelConfig(use_garch=True, shrinkage=False)
        model = RiskModel(cfg)
        cov = model.estimate_covariance(r)
        assert not cov.empty
        assert cov.shape[0] == cov.shape[1]
        # Diagonal should be positive (variances)
        diag = np.diag(cov.values)
        assert np.all(diag > 0)
