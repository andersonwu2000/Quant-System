"""
Kakushadze 101 Formulaic Alphas — selected implementations.

Reference: Kakushadze (2016) "101 Formulaic Alphas".
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ── Helpers ──────────────────────────────────────────────────


def _rank(x: pd.Series) -> pd.Series:
    """Cross-sectional percentile rank (0 to 1)."""
    return x.rank(pct=True)


def _ts_rank(x: pd.Series, window: int) -> pd.Series:
    """Time-series rank within rolling window."""
    return x.rolling(window).apply(lambda s: s.rank().iloc[-1] / len(s), raw=False)


def _decay_linear(x: pd.Series, window: int) -> pd.Series:
    """Linearly-weighted moving average (recent = higher weight)."""
    weights = np.arange(1, window + 1, dtype=float)
    weights /= weights.sum()
    return x.rolling(window).apply(lambda s: (s * weights).sum(), raw=True)


def _ts_argmax(x: pd.Series, window: int) -> pd.Series:
    """Position of max within rolling window."""
    return x.rolling(window).apply(lambda s: s.argmax(), raw=True)


# ── Selected Alphas ──────────────────────────────────────────


def kakushadze_alpha_2(bars: pd.DataFrame) -> dict[str, float]:
    """-corr(rank(delta(log(volume), 2)), rank((close-open)/open), 6).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #2.
    """
    if len(bars) < 10:
        return {}
    close = bars["close"]
    open_ = bars["open"]
    volume = bars["volume"]

    delta_log_vol = np.log(volume).diff(2)
    intraday_ret = (close - open_) / open_

    corr = _rank(delta_log_vol).rolling(6).corr(_rank(intraday_ret))
    val = corr.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_2": float(-val)}


def kakushadze_alpha_3(bars: pd.DataFrame) -> dict[str, float]:
    """-corr(rank(open), rank(volume), 10).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #3.
    """
    if len(bars) < 12:
        return {}
    open_ = bars["open"]
    volume = bars["volume"]

    corr = _rank(open_).rolling(10).corr(_rank(volume))
    val = corr.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_3": float(-val)}


def kakushadze_alpha_6(bars: pd.DataFrame) -> dict[str, float]:
    """-corr(open, volume, 10).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #6.
    """
    if len(bars) < 12:
        return {}
    open_ = bars["open"]
    volume = bars["volume"]

    corr = open_.rolling(10).corr(volume)
    val = corr.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_6": float(-val)}


def kakushadze_alpha_12(bars: pd.DataFrame) -> dict[str, float]:
    """sign(delta(volume, 1)) * (-delta(close, 1)).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #12.
    """
    if len(bars) < 3:
        return {}
    close = bars["close"]
    volume = bars["volume"]

    sign_delta_vol = np.sign(volume.diff(1))
    neg_delta_close = -close.diff(1)
    signal = sign_delta_vol * neg_delta_close
    val = signal.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_12": float(val)}


def kakushadze_alpha_33(bars: pd.DataFrame) -> dict[str, float]:
    """rank(-(1 - (open / close))).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #33.
    """
    if len(bars) < 2:
        return {}
    open_ = bars["open"]
    close = bars["close"]

    raw = -(1 - (open_ / close))
    ranked = _rank(raw)
    val = ranked.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_33": float(val)}


def kakushadze_alpha_34(bars: pd.DataFrame) -> dict[str, float]:
    """rank((1 - rank(std(returns,2)/std(returns,5))) + (1 - rank(delta(close,1)))).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #34.
    """
    if len(bars) < 8:
        return {}
    close = bars["close"]
    returns = close.pct_change()

    std2 = returns.rolling(2).std()
    std5 = returns.rolling(5).std()
    ratio = std2 / std5.replace(0, np.nan)
    delta_close = close.diff(1)

    component = (1 - _rank(ratio)) + (1 - _rank(delta_close))
    ranked = _rank(component)
    val = ranked.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_34": float(val)}


def kakushadze_alpha_38(bars: pd.DataFrame) -> dict[str, float]:
    """-rank(ts_rank(close, 10)) * rank(close / open).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #38.
    """
    if len(bars) < 12:
        return {}
    close = bars["close"]
    open_ = bars["open"]

    ts_r = _ts_rank(close, 10)
    ratio_rank = _rank(close / open_)
    signal = -_rank(ts_r) * ratio_rank
    val = signal.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_38": float(val)}


def kakushadze_alpha_44(bars: pd.DataFrame) -> dict[str, float]:
    """-corr(high, rank(volume), 5).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #44.
    """
    if len(bars) < 8:
        return {}
    high = bars["high"]
    volume = bars["volume"]

    corr = high.rolling(5).corr(_rank(volume))
    val = corr.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_44": float(-val)}


def kakushadze_alpha_53(bars: pd.DataFrame) -> dict[str, float]:
    """-delta(((close-low)-(high-close))/(close-low), 9).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #53.
    """
    if len(bars) < 12:
        return {}
    close = bars["close"]
    high = bars["high"]
    low = bars["low"]

    denom = close - low
    denom = denom.replace(0, np.nan)
    williams = ((close - low) - (high - close)) / denom
    delta = williams.diff(9)
    val = delta.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_53": float(-val)}


def kakushadze_alpha_101(bars: pd.DataFrame) -> dict[str, float]:
    """(close - open) / ((high - low) + 0.001).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #101.
    """
    if len(bars) < 1:
        return {}
    close = bars["close"]
    open_ = bars["open"]
    high = bars["high"]
    low = bars["low"]

    signal = (close - open_) / ((high - low) + 0.001)
    val = signal.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_101": float(val)}
