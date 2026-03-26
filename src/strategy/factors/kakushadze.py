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


def _delta(x: pd.Series, period: int = 1) -> pd.Series:
    """Difference: x[t] - x[t-period]."""
    return x.diff(period)


def _correlation(x: pd.Series, y: pd.Series, window: int) -> pd.Series:
    """Rolling correlation."""
    return x.rolling(window).corr(y)


def _covariance(x: pd.Series, y: pd.Series, window: int) -> pd.Series:
    """Rolling covariance."""
    return x.rolling(window).cov(y)


def _stddev(x: pd.Series, window: int) -> pd.Series:
    """Rolling standard deviation."""
    return x.rolling(window).std()


def _ts_min(x: pd.Series, window: int) -> pd.Series:
    """Rolling min."""
    return x.rolling(window).min()


def _ts_max(x: pd.Series, window: int) -> pd.Series:
    """Rolling max."""
    return x.rolling(window).max()


def _ts_sum(x: pd.Series, window: int) -> pd.Series:
    """Rolling sum."""
    return x.rolling(window).sum()


def _ts_argmin(x: pd.Series, window: int) -> pd.Series:
    """Position of min within rolling window."""
    return x.rolling(window).apply(lambda s: s.argmin(), raw=True)


def _sma(x: pd.Series, window: int) -> pd.Series:
    """Simple moving average."""
    return x.rolling(window).mean()


# ── Existing Alphas ──────────────────────────────────────────


def kakushadze_alpha_1(bars: pd.DataFrame) -> dict[str, float]:
    """rank(ts_argmax(signedpower(returns < 0 ? stddev(returns, 20) : close, 2), 5)) - 0.5.

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #1.
    """
    if len(bars) < 26:
        return {}
    close = bars["close"]
    returns = close.pct_change()
    std20 = _stddev(returns, 20)
    # Where returns < 0 use stddev, else use close
    inner = pd.Series(np.where(returns < 0, std20, close), index=close.index)
    signed_power = inner ** 2
    argmax5 = _ts_argmax(signed_power, 5)
    ranked = _rank(argmax5)
    val = ranked.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_1": float(val - 0.5)}


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


def kakushadze_alpha_4(bars: pd.DataFrame) -> dict[str, float]:
    """-ts_rank(rank(low), 9).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #4.
    """
    if len(bars) < 11:
        return {}
    low = bars["low"]
    ranked = _rank(low)
    ts_r = _ts_rank(ranked, 9)
    val = ts_r.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_4": float(-val)}


def kakushadze_alpha_7(bars: pd.DataFrame) -> dict[str, float]:
    """where(adv20 < volume, -ts_rank(abs(delta(close, 7)), 60) * sign(delta(close, 7)), -1).

    Simplified: -ts_rank(abs(delta(close,7)), 60) * sign(delta(close,7)).
    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #7.
    """
    if len(bars) < 68:
        return {}
    close = bars["close"]
    volume = bars["volume"]
    adv20 = volume.rolling(20).mean()
    delta7 = close.diff(7)
    abs_delta7 = delta7.abs()
    ts_r = _ts_rank(abs_delta7, 60)
    signal = pd.Series(
        np.where(adv20 < volume, -ts_r * np.sign(delta7), -1.0),
        index=close.index,
    )
    val = signal.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_7": float(val)}


def kakushadze_alpha_8(bars: pd.DataFrame) -> dict[str, float]:
    """-rank(((sum(open, 5) * sum(returns, 5)) - delay((sum(open, 5) * sum(returns, 5)), 10))).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #8.
    """
    if len(bars) < 16:
        return {}
    open_ = bars["open"]
    returns = bars["close"].pct_change()
    sum_open5 = _ts_sum(open_, 5)
    sum_ret5 = _ts_sum(returns, 5)
    product = sum_open5 * sum_ret5
    signal = -(product - product.shift(10))
    ranked = _rank(signal)
    val = ranked.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_8": float(val)}


def kakushadze_alpha_9(bars: pd.DataFrame) -> dict[str, float]:
    """where(0 < ts_min(delta(close,1), 5), delta(close,1), where(ts_max(delta(close,1), 5) < 0, delta(close,1), -delta(close,1))).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #9.
    """
    if len(bars) < 7:
        return {}
    close = bars["close"]
    delta1 = close.diff(1)
    min5 = _ts_min(delta1, 5)
    max5 = _ts_max(delta1, 5)
    signal = pd.Series(
        np.where(min5 > 0, delta1, np.where(max5 < 0, delta1, -delta1)),
        index=close.index,
    )
    val = signal.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_9": float(val)}


def kakushadze_alpha_10(bars: pd.DataFrame) -> dict[str, float]:
    """rank(where(0 < ts_min(delta(close,1), 4), delta(close,1), where(ts_max(delta(close,1), 4) < 0, delta(close,1), -delta(close,1)))).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #10.
    """
    if len(bars) < 6:
        return {}
    close = bars["close"]
    delta1 = close.diff(1)
    min4 = _ts_min(delta1, 4)
    max4 = _ts_max(delta1, 4)
    inner = pd.Series(
        np.where(min4 > 0, delta1, np.where(max4 < 0, delta1, -delta1)),
        index=close.index,
    )
    ranked = _rank(inner)
    val = ranked.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_10": float(val)}


def kakushadze_alpha_13(bars: pd.DataFrame) -> dict[str, float]:
    """-rank(covariance(rank(close), rank(volume), 5)).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #13.
    """
    if len(bars) < 7:
        return {}
    close = bars["close"]
    volume = bars["volume"]
    cov = _covariance(_rank(close), _rank(volume), 5)
    ranked = _rank(cov)
    val = ranked.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_13": float(-val)}


def kakushadze_alpha_14(bars: pd.DataFrame) -> dict[str, float]:
    """-rank(delta(returns, 3)) * correlation(open, volume, 10).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #14.
    """
    if len(bars) < 15:
        return {}
    close = bars["close"]
    open_ = bars["open"]
    volume = bars["volume"]
    returns = close.pct_change()
    delta_ret3 = returns.diff(3)
    corr = _correlation(open_, volume, 10)
    signal = -_rank(delta_ret3) * corr
    val = signal.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_14": float(val)}


def kakushadze_alpha_15(bars: pd.DataFrame) -> dict[str, float]:
    """-sum(rank(correlation(rank(high), rank(volume), 3)), 3).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #15.
    """
    if len(bars) < 8:
        return {}
    high = bars["high"]
    volume = bars["volume"]
    corr = _correlation(_rank(high), _rank(volume), 3)
    ranked_corr = _rank(corr)
    signal = -_ts_sum(ranked_corr, 3)
    val = signal.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_15": float(val)}


def kakushadze_alpha_16(bars: pd.DataFrame) -> dict[str, float]:
    """-rank(covariance(rank(high), rank(volume), 5)).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #16.
    """
    if len(bars) < 7:
        return {}
    high = bars["high"]
    volume = bars["volume"]
    cov = _covariance(_rank(high), _rank(volume), 5)
    ranked = _rank(cov)
    val = ranked.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_16": float(-val)}


def kakushadze_alpha_17(bars: pd.DataFrame) -> dict[str, float]:
    """-rank(ts_rank(close, 10)) * rank(delta(delta(close,1),1)) * rank(ts_rank(volume/adv20, 5)).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #17.
    """
    if len(bars) < 22:
        return {}
    close = bars["close"]
    volume = bars["volume"]
    adv20 = volume.rolling(20).mean()
    ts_r_close = _ts_rank(close, 10)
    delta_delta = close.diff(1).diff(1)
    vol_ratio = volume / adv20.replace(0, np.nan)
    ts_r_vol = _ts_rank(vol_ratio, 5)
    signal = -_rank(ts_r_close) * _rank(delta_delta) * _rank(ts_r_vol)
    val = signal.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_17": float(val)}


def kakushadze_alpha_18(bars: pd.DataFrame) -> dict[str, float]:
    """-rank((stddev(abs(close-open), 5) + (close-open)) + correlation(close, open, 10)).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #18.
    """
    if len(bars) < 12:
        return {}
    close = bars["close"]
    open_ = bars["open"]
    diff = close - open_
    std_abs = _stddev(diff.abs(), 5)
    corr = _correlation(close, open_, 10)
    signal = -(std_abs + diff + corr)
    ranked = _rank(signal)
    val = ranked.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_18": float(val)}


def kakushadze_alpha_19(bars: pd.DataFrame) -> dict[str, float]:
    """-sign(close - delay(close, 7) + delta(close, 7)) * (1 + rank(1 + sum(returns, 250))).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #19.
    """
    if len(bars) < 252:
        return {}
    close = bars["close"]
    returns = close.pct_change()
    delta7 = close.diff(7)
    delay7 = close.shift(7)
    sign_part = np.sign((close - delay7) + delta7)
    sum_ret = _ts_sum(returns, 250)
    signal = -sign_part * (1 + _rank(1 + sum_ret))
    val = signal.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_19": float(val)}


def kakushadze_alpha_20(bars: pd.DataFrame) -> dict[str, float]:
    """rank(open - delay(high, 1)) * rank(open - delay(close, 1)) * rank(open - delay(low, 1)).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #20.
    """
    if len(bars) < 3:
        return {}
    open_ = bars["open"]
    high = bars["high"]
    close = bars["close"]
    low = bars["low"]
    r1 = _rank(open_ - high.shift(1))
    r2 = _rank(open_ - close.shift(1))
    r3 = _rank(open_ - low.shift(1))
    signal = r1 * r2 * r3
    val = signal.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_20": float(val)}


def kakushadze_alpha_22(bars: pd.DataFrame) -> dict[str, float]:
    """-delta(correlation(high, volume, 5), 5) * rank(stddev(close, 20)).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #22.
    """
    if len(bars) < 30:
        return {}
    high = bars["high"]
    close = bars["close"]
    volume = bars["volume"]
    corr = _correlation(high, volume, 5)
    delta_corr = corr.diff(5)
    std_rank = _rank(_stddev(close, 20))
    signal = -delta_corr * std_rank
    val = signal.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_22": float(val)}


def kakushadze_alpha_23(bars: pd.DataFrame) -> dict[str, float]:
    """where(sma(high, 20) < high, -delta(high, 2), 0).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #23.
    """
    if len(bars) < 22:
        return {}
    high = bars["high"]
    sma20 = _sma(high, 20)
    delta2 = high.diff(2)
    signal = pd.Series(
        np.where(sma20 < high, -delta2, 0.0),
        index=high.index,
    )
    val = signal.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_23": float(val)}


def kakushadze_alpha_24(bars: pd.DataFrame) -> dict[str, float]:
    """where(delta(sma(close, 100), 100)/delay(close, 100) <= 0.05, -(close - ts_min(close, 100)), -delta(close, 3)).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #24.
    """
    if len(bars) < 104:
        return {}
    close = bars["close"]
    sma100 = _sma(close, 100)
    delta_sma = sma100.diff(100)
    delay100 = close.shift(100)
    ratio = delta_sma / delay100.replace(0, np.nan)
    ts_min100 = _ts_min(close, 100)
    delta3 = close.diff(3)
    signal = pd.Series(
        np.where(ratio <= 0.05, -(close - ts_min100), -delta3),
        index=close.index,
    )
    val = signal.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_24": float(val)}


def kakushadze_alpha_30(bars: pd.DataFrame) -> dict[str, float]:
    """(1/close_count) * sum(sign(close - delay(close, 1)) * sign(delay(close, 1) - delay(close, 2)) * sign(delay(close, 2) - delay(close, 3))).

    Simplified rolling sign-chain (momentum persistence).
    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #30.
    """
    if len(bars) < 6:
        return {}
    close = bars["close"]
    s1 = np.sign(close.diff(1))
    s2 = np.sign(close.shift(1).diff(1))
    s3 = np.sign(close.shift(2).diff(1))
    product = s1 * s2 * s3
    # Average over a short window for stability
    val = float(product.iloc[-1])
    if np.isnan(val):
        return {}
    return {"alpha_30": val}


def kakushadze_alpha_35(bars: pd.DataFrame) -> dict[str, float]:
    """ts_rank(volume, 32) * (1 - ts_rank(close + high - low, 16)) * (1 - ts_rank(returns, 32)).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #35.
    """
    if len(bars) < 34:
        return {}
    close = bars["close"]
    high = bars["high"]
    low = bars["low"]
    volume = bars["volume"]
    returns = close.pct_change()
    tr1 = _ts_rank(volume, 32)
    tr2 = _ts_rank(close + high - low, 16)
    tr3 = _ts_rank(returns, 32)
    signal = tr1 * (1 - tr2) * (1 - tr3)
    val = signal.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_35": float(val)}


def kakushadze_alpha_40(bars: pd.DataFrame) -> dict[str, float]:
    """-rank(stddev(high, 10)) * correlation(high, volume, 10).

    Reference: Kakushadze (2016) "101 Formulaic Alphas", Alpha #40.
    """
    if len(bars) < 12:
        return {}
    high = bars["high"]
    volume = bars["volume"]
    std_high = _stddev(high, 10)
    corr = _correlation(high, volume, 10)
    signal = -_rank(std_high) * corr
    val = signal.iloc[-1]
    if np.isnan(val):
        return {}
    return {"alpha_40": float(val)}
