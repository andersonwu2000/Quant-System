"""
基本面因子 — 基於財務指標的純函式。
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def value_pe(pe_ratio: float) -> float:
    """PE value factor: lower PE = higher score.

    Returns inverted normalized score. Negative PE (losses) returns 0.
    Typical PE range 5-50; score is 1/PE normalized.
    """
    if pe_ratio <= 0:
        return 0.0
    # Inverse: lower PE -> higher score. Cap at PE=5 for safety.
    return 1.0 / max(pe_ratio, 5.0)


def value_pb(pb_ratio: float) -> float:
    """PB value factor: lower PB = higher score.

    Returns inverted normalized score. Negative PB returns 0.
    """
    if pb_ratio <= 0:
        return 0.0
    # Inverse: lower PB -> higher score. Cap at PB=0.5 for safety.
    return 1.0 / max(pb_ratio, 0.5)


def quality_roe(roe: float) -> float:
    """Quality factor: higher ROE = higher score.

    ROE is typically in percentage (e.g., 15.0 means 15%).
    Returns normalized score in [0, 1] range.
    """
    if roe <= 0:
        return 0.0
    # Normalize: 30%+ ROE = max score
    return min(roe / 30.0, 1.0)


def size_factor(
    bars: pd.DataFrame, market_cap: float | None = None
) -> dict[str, float]:
    """Size factor: -log(market_cap) so small cap gets high score (SMB direction).

    If market_cap is not provided, use price * average volume as proxy.
    This is a cross-sectional factor — actual ranking happens in the pipeline.

    References:
        Fama-French (1993) SMB factor.
    """
    if market_cap is not None and market_cap > 0:
        return {"size": -np.log(market_cap)}

    # Proxy: close[-1] * mean(volume[-20:])
    close = bars["close"]
    volume = bars["volume"]
    if len(close) < 1 or len(volume) < 1:
        return {}
    last_close = float(close.iloc[-1])
    avg_vol = float(volume.iloc[-20:].mean()) if len(volume) >= 20 else float(volume.mean())
    proxy = last_close * avg_vol
    if proxy <= 0:
        return {}
    return {"size": -np.log(proxy)}


def investment_factor(
    total_assets_current: float, total_assets_prev: float
) -> float:
    """Investment factor: negative asset growth (CMA direction).

    Conservative firms (low investment) get high score.

    Returns:
        -(total_assets_current / total_assets_prev - 1)

    References:
        Fama-French (2015) CMA factor.
    """
    if total_assets_prev <= 0:
        return 0.0
    return -(total_assets_current / total_assets_prev - 1)


def gross_profitability_factor(
    revenue: float, cogs: float, total_assets: float
) -> float:
    """Gross profitability factor: (revenue - cogs) / total_assets.

    Higher gross profitability predicts higher returns.

    References:
        Novy-Marx (2013): gross profitability has predictive power
        comparable to HML.
    """
    if total_assets <= 0:
        return 0.0
    return (revenue - cogs) / total_assets
