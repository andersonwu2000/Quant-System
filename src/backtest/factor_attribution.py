"""Factor Attribution — Fama-French style factor decomposition for Taiwan stocks.

Decomposes strategy returns into loadings on known risk factors:
- MKT: market excess return (0050.TW - risk-free)
- SMB: small minus big (size premium)
- HML: high minus low book-to-market (value premium)
- MOM: winners minus losers (momentum premium)

Usage:
    from src.backtest.factor_attribution import compute_factor_attribution
    attr = compute_factor_attribution(strategy_daily_returns, start, end)
    print(attr.summary())
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class AttributionResult:
    """Factor attribution result."""
    alpha: float          # annualized alpha (intercept)
    alpha_t: float        # t-stat of alpha
    beta_mkt: float       # market beta
    beta_smb: float       # size loading
    beta_hml: float       # value loading
    beta_mom: float       # momentum loading
    r_squared: float      # R² of regression
    n_days: int

    def summary(self) -> str:
        sig = lambda t: "***" if abs(t) > 2.58 else "**" if abs(t) > 1.96 else "*" if abs(t) > 1.65 else ""
        lines = [
            "--- Factor Attribution (TW Fama-French + MOM) ---",
            f"  Alpha:  {self.alpha:+.2%}/yr (t={self.alpha_t:+.2f}{sig(self.alpha_t)})",
            f"  MKT:    {self.beta_mkt:+.3f}",
            f"  SMB:    {self.beta_smb:+.3f} ({'small-cap tilt' if self.beta_smb > 0.1 else 'large-cap tilt' if self.beta_smb < -0.1 else 'neutral'})",
            f"  HML:    {self.beta_hml:+.3f} ({'value tilt' if self.beta_hml > 0.1 else 'growth tilt' if self.beta_hml < -0.1 else 'neutral'})",
            f"  MOM:    {self.beta_mom:+.3f} ({'momentum' if self.beta_mom > 0.1 else 'reversal' if self.beta_mom < -0.1 else 'neutral'})",
            f"  R²:     {self.r_squared:.3f}  ({self.n_days} days)",
        ]
        return "\n".join(lines)


def _build_tw_factors(universe: list[str], start: str, end: str) -> pd.DataFrame | None:
    """Build daily SMB/HML/MOM factor returns from local data.

    Simple construction (not full Fama-French methodology):
    - SMB: bottom 30% market cap return - top 30% market cap return
    - HML: top 30% PBR-inverse return - bottom 30% PBR-inverse return
    - MOM: top 30% 12-1 month return - bottom 30% 12-1 month return
    - MKT: equal-weight universe return
    """
    from src.data.registry import parquet_path

    # Load close prices
    close_dict: dict[str, pd.Series] = {}
    for sym in universe:
        path = parquet_path(sym, "price")
        if not path.exists():
            continue
        try:
            df = pd.read_parquet(path)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date").sort_index()
            if "close" in df.columns:
                s = df.loc[start:end]["close"]
                if len(s.dropna()) > 20:  # Relaxed from 60 to allow shorter periods
                    close_dict[sym] = s
        except Exception:
            continue

    if len(close_dict) < 20:
        return None

    close_df = pd.DataFrame(close_dict).sort_index().ffill()
    returns_df = close_df.pct_change().replace([np.inf, -np.inf], 0.0).fillna(0.0)

    # Size proxy: close × average_volume (liquidity-weighted, better than price alone)
    vol_dict: dict[str, pd.Series] = {}
    for sym in close_dict:
        path = parquet_path(sym, "price")
        try:
            df = pd.read_parquet(path)
            if "date" in df.columns:
                df = df.set_index(pd.to_datetime(df["date"])).sort_index()
            if "volume" in df.columns:
                vol_dict[sym] = df.loc[start:end]["volume"]
        except Exception:
            continue

    # Load PBR data for HML if available
    pbr_dict: dict[str, pd.Series] = {}
    for sym in close_dict:
        path = parquet_path(sym, "per_history")
        if not path.exists():
            continue
        try:
            df = pd.read_parquet(path)
            if "date" in df.columns:
                df = df.set_index(pd.to_datetime(df["date"])).sort_index()
            if "pbr" in df.columns:
                s = df.loc[start:end]["pbr"].dropna()
                if len(s) > 0:
                    pbr_dict[sym] = s
        except Exception:
            continue

    # Monthly rebalance dates
    monthly_dates = returns_df.resample("MS").first().index

    factor_records = []

    for i, rebal_date in enumerate(monthly_dates):
        if i == 0:
            continue
        next_rebal = monthly_dates[i + 1] if i + 1 < len(monthly_dates) else returns_df.index[-1]
        period_rets = returns_df.loc[rebal_date:next_rebal]
        if len(period_rets) < 5:
            continue

        # Sort stocks at rebalance date
        prices_at_rebal = close_df.loc[:rebal_date].iloc[-1].dropna()
        available = [s for s in prices_at_rebal.index if s in returns_df.columns]
        if len(available) < 20:
            continue

        n = len(available)
        top_pct = max(int(n * 0.3), 5)

        # SMB: close × avg_volume as liquidity-weighted size proxy
        size_scores = {}
        for sym in available:
            price = prices_at_rebal[sym]
            if sym in vol_dict:
                vol_s = vol_dict[sym].loc[:rebal_date]
                avg_vol = vol_s.iloc[-60:].mean() if len(vol_s) >= 60 else vol_s.mean()
                if avg_vol > 0 and np.isfinite(avg_vol):
                    size_scores[sym] = price * avg_vol
                    continue
            size_scores[sym] = price  # fallback to price if no volume
        sorted_by_size = pd.Series(size_scores).sort_values()
        small_stocks = list(sorted_by_size.index[:top_pct])
        big_stocks = list(sorted_by_size.index[-top_pct:])

        # HML: use PBR if available (low PBR = high book-to-market = value)
        hml_available: list[str] = []
        hml_scores: dict[str, float] = {}
        if pbr_dict:
            for sym in available:
                if sym in pbr_dict:
                    pbr_s = pbr_dict[sym].loc[:rebal_date]
                    if len(pbr_s) > 0:
                        pbr_val = pbr_s.iloc[-1]
                        if pbr_val > 0 and np.isfinite(pbr_val):
                            hml_scores[sym] = 1.0 / pbr_val  # book-to-market = 1/PBR
                            hml_available.append(sym)
        if len(hml_available) >= top_pct * 2:
            sorted_by_btm = pd.Series(hml_scores).sort_values()
            growth_stocks = list(sorted_by_btm.index[:top_pct])  # low B/M = growth
            value_stocks = list(sorted_by_btm.index[-top_pct:])  # high B/M = value
        else:
            # Fallback: use price as rough value proxy (low price ≈ value)
            value_stocks = small_stocks
            growth_stocks = big_stocks

        # MOM: 12-month return
        lookback = close_df.loc[:rebal_date]
        if len(lookback) > 252:
            mom_ret = (lookback.iloc[-1] / lookback.iloc[-252] - 1).dropna()
            mom_available = [s for s in available if s in mom_ret.index]
            sorted_by_mom = mom_ret[mom_available].sort_values()
            loser_stocks = list(sorted_by_mom.index[:top_pct])
            winner_stocks = list(sorted_by_mom.index[-top_pct:])
        else:
            loser_stocks = small_stocks  # fallback
            winner_stocks = big_stocks

        # Daily factor returns for this period
        for date, row in period_rets.iterrows():
            mkt = float(row[available].mean())
            smb = float(row[small_stocks].mean() - row[big_stocks].mean()) if small_stocks and big_stocks else 0.0
            hml = float(row[value_stocks].mean() - row[growth_stocks].mean()) if value_stocks and growth_stocks else 0.0
            mom = float(row[winner_stocks].mean() - row[loser_stocks].mean()) if winner_stocks and loser_stocks else 0.0

            factor_records.append({
                "date": date, "MKT": mkt, "SMB": smb, "HML": hml, "MOM": mom,
            })

    if not factor_records:
        return None

    return pd.DataFrame(factor_records).set_index("date").sort_index()


def compute_factor_attribution(
    strategy_returns: pd.Series,
    universe: list[str],
    start: str,
    end: str,
) -> AttributionResult | None:
    """Run factor attribution regression on strategy returns."""
    factors_df = _build_tw_factors(universe, start, end)
    if factors_df is None or len(factors_df) < 60:
        return None

    # Align
    common = strategy_returns.index.intersection(factors_df.index)
    if len(common) < 60:
        return None

    y = strategy_returns.loc[common].values
    X = factors_df.loc[common][["MKT", "SMB", "HML", "MOM"]].values

    # Add intercept
    X_with_const = np.column_stack([np.ones(len(X)), X])

    # OLS
    try:
        beta, residuals, _, _ = np.linalg.lstsq(X_with_const, y, rcond=None)
    except Exception:
        return None

    y_hat = X_with_const @ beta
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r_sq = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    # Standard errors
    n, k = X_with_const.shape
    if n <= k:
        return None
    mse = ss_res / (n - k)
    try:
        cov_beta = mse * np.linalg.inv(X_with_const.T @ X_with_const)
        se = np.sqrt(np.diag(cov_beta))
    except Exception:
        se = np.ones(k)

    alpha_daily = beta[0]
    alpha_annual = float(alpha_daily * 252)
    alpha_t = float(beta[0] / se[0]) if se[0] > 0 else 0.0

    return AttributionResult(
        alpha=alpha_annual,
        alpha_t=alpha_t,
        beta_mkt=float(beta[1]),
        beta_smb=float(beta[2]),
        beta_hml=float(beta[3]),
        beta_mom=float(beta[4]),
        r_squared=float(r_sq),
        n_days=len(common),
    )
