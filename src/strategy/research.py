"""
因子研究框架 — IC 分析、因子衰減、因子合成。

提供量化因子的統計分析工具，幫助評估因子的預測能力與有效性。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.data.fundamentals import FundamentalsProvider
from src.strategy import factors as flib

logger = logging.getLogger(__name__)


# ── 向量化因子函式 ────────────────────────────────────────────────
# 每個函式接收完整 OHLCV DataFrame，回傳完整 Series（每個日期一個值）。
# 用於取代逐日窗口呼叫，將 O(N_dates) 降至 O(1) pandas 向量化操作。


def _vec_momentum(df: pd.DataFrame, lookback: int = 252, skip: int = 21, **_: object) -> pd.Series:
    # Per-window version uses iloc[-skip] and iloc[-lookback] on a window ending
    # at the current date (inclusive). iloc[-1] is current, so iloc[-skip] is
    # (skip-1) positions back, and iloc[-lookback] is (lookback-1) positions back.
    close = df["close"]
    return close.shift(skip - 1) / close.shift(lookback - 1) - 1


def _vec_mean_reversion(df: pd.DataFrame, lookback: int = 20, **_: object) -> pd.Series:
    close = df["close"]
    ma = close.rolling(lookback).mean()
    std = close.rolling(lookback).std()
    z = (close - ma) / std.replace(0, np.nan)
    return -z


def _vec_volatility(df: pd.DataFrame, lookback: int = 20, **_: object) -> pd.Series:
    returns = df["close"].pct_change()
    result: pd.Series = returns.rolling(lookback).std() * np.sqrt(252)
    return result


def _vec_rsi(df: pd.DataFrame, period: int = 14, **_: object) -> pd.Series:
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta.where(delta < 0, 0.0))
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _vec_ma_cross(df: pd.DataFrame, fast: int = 10, slow: int = 50, **_: object) -> pd.Series:
    close = df["close"]
    ma_fast = close.rolling(fast).mean()
    ma_slow = close.rolling(slow).mean()
    return ma_fast / ma_slow.replace(0, np.nan) - 1


def _vec_vpt(df: pd.DataFrame, lookback: int = 20, **_: object) -> pd.Series:
    price_ret = df["close"].pct_change()
    vol_change = df["volume"].pct_change()
    return price_ret.rolling(lookback).corr(vol_change)


def _vec_reversal(df: pd.DataFrame, lookback: int = 5, **_: object) -> pd.Series:
    close = df["close"]
    return -(close / close.shift(lookback) - 1)


def _vec_illiquidity(df: pd.DataFrame, lookback: int = 20, **_: object) -> pd.Series:
    ret_abs = df["close"].pct_change().abs()
    dollar_vol = df["close"] * df["volume"]
    dollar_vol = dollar_vol.replace(0, np.nan)
    ratio = ret_abs / dollar_vol
    return ratio.rolling(lookback).mean()


def _vec_ivol(
    df: pd.DataFrame,
    lookback: int = 60,
    market_returns: pd.Series | None = None,
    **_: object,
) -> pd.Series:
    """向量化特質波動率：使用 rolling beta 去除市場因子後的殘差波動率。"""
    close = df["close"]
    stock_ret = close.pct_change()

    if market_returns is None or market_returns.empty:
        result: pd.Series = stock_ret.rolling(lookback).std() * np.sqrt(252)
        return result

    # 對齊
    aligned = pd.DataFrame({"stock": stock_ret, "market": market_returns}).dropna()
    if len(aligned) < lookback:
        return pd.Series(dtype=float, index=df.index)

    s = aligned["stock"]
    m = aligned["market"]

    # Rolling beta = cov(s, m) / var(m)
    cov_sm = s.rolling(lookback).cov(m)
    var_m = m.rolling(lookback).var()
    beta = cov_sm / var_m.replace(0, np.nan)
    alpha = s.rolling(lookback).mean() - beta * m.rolling(lookback).mean()

    # Residual = stock - alpha - beta * market
    residual = s - alpha - beta * m

    # Rolling std of residuals
    ivol: pd.Series = residual.rolling(lookback).std() * np.sqrt(252)
    return ivol.reindex(df.index)


def _vec_skewness(df: pd.DataFrame, lookback: int = 60, **_: object) -> pd.Series:
    ret = df["close"].pct_change()
    return ret.rolling(lookback).skew()


def _vec_max_ret(df: pd.DataFrame, lookback: int = 20, **_: object) -> pd.Series:
    ret = df["close"].pct_change()
    return ret.rolling(lookback).max()


# ── Kakushadze vectorized versions ──────────────────────────────────


def _vec_bollinger_pos(df: pd.DataFrame, lookback: int = 20, **_: object) -> pd.Series:
    close = df["close"]
    ma = close.rolling(lookback).mean()
    std = close.rolling(lookback).std()
    upper = ma + 2 * std
    lower = ma - 2 * std
    band_width = (upper - lower).replace(0, np.nan)
    return ((close - lower) / band_width).clip(0, 1)


def _vec_macd_hist(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9, **_: object) -> pd.Series:
    close = df["close"]
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return histogram / close.replace(0, np.nan)


def _vec_obv_trend(df: pd.DataFrame, lookback: int = 20, **_: object) -> pd.Series:
    close = df["close"]
    volume = df["volume"]
    obv = (np.sign(close.diff()) * volume).cumsum()
    # Rolling slope via linear regression approximation
    obv_ma = obv.rolling(lookback).mean()
    # Simplified: (obv - obv_ma) / abs(obv_ma) as trend proxy
    result: pd.Series = (obv - obv_ma) / obv_ma.abs().replace(0, np.nan)
    return result


def _vec_gap(df: pd.DataFrame, **_: object) -> pd.Series:
    return df["open"] / df["close"].shift(1) - 1


def _vec_intraday_ret(df: pd.DataFrame, **_: object) -> pd.Series:
    return df["close"] / df["open"].replace(0, np.nan) - 1


def _vec_overnight_ret(df: pd.DataFrame, **_: object) -> pd.Series:
    return df["open"] / df["close"].shift(1) - 1


def _vec_momentum_1m(df: pd.DataFrame, **_: object) -> pd.Series:
    close = df["close"]
    return close / close.shift(21) - 1


def _vec_momentum_6m(df: pd.DataFrame, **_: object) -> pd.Series:
    close = df["close"]
    return close / close.shift(126) - 1


def _vec_momentum_12m(df: pd.DataFrame, **_: object) -> pd.Series:
    close = df["close"]
    return close.shift(21) / close.shift(252) - 1


def _vec_lt_reversal(df: pd.DataFrame, lookback: int = 756, **_: object) -> pd.Series:
    close = df["close"]
    return -(close / close.shift(lookback) - 1)


def _vec_max_daily_ret(df: pd.DataFrame, lookback: int = 21, **_: object) -> pd.Series:
    ret = df["close"].pct_change()
    return ret.rolling(lookback).max()


def _vec_turnover_vol(df: pd.DataFrame, lookback: int = 60, **_: object) -> pd.Series:
    volume = df["volume"]
    vol_std = volume.rolling(lookback).std()
    vol_mean = volume.rolling(lookback).mean().replace(0, np.nan)
    return vol_std / vol_mean


def _vec_zero_days(df: pd.DataFrame, lookback: int = 60, **_: object) -> pd.Series:
    zero = (df["volume"] == 0).astype(float)
    return zero.rolling(lookback).mean()


def _vec_close_to_high(df: pd.DataFrame, lookback: int = 5, **_: object) -> pd.Series:
    close = df["close"]
    rolling_high = df["high"].rolling(lookback).max()
    return close / rolling_high.replace(0, np.nan)


def _vec_hl_range(df: pd.DataFrame, lookback: int = 20, **_: object) -> pd.Series:
    hl = (df["high"] - df["low"]) / df["close"].replace(0, np.nan)
    return hl.rolling(lookback).mean()


def _vec_atr_ratio(df: pd.DataFrame, period: int = 14, **_: object) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return atr / close.replace(0, np.nan)


def _vec_vol_momentum(df: pd.DataFrame, lookback: int = 20, **_: object) -> pd.Series:
    volume = df["volume"]
    recent = volume.rolling(lookback).mean()
    prior = volume.shift(lookback).rolling(lookback).mean()
    return recent / prior.replace(0, np.nan) - 1


def _vec_price_accel(df: pd.DataFrame, lookback: int = 20, **_: object) -> pd.Series:
    returns = df["close"].pct_change()
    accel = returns.diff()
    return accel.rolling(lookback).mean()


# ── Kakushadze vectorized — new alphas ──────────────────────────────


def _vec_alpha_1(df: pd.DataFrame, **_: object) -> pd.Series:
    close = df["close"]
    returns = close.pct_change()
    std20 = returns.rolling(20).std()
    inner = pd.Series(np.where(returns < 0, std20, close), index=close.index)
    signed_power = inner ** 2
    argmax5 = flib._ts_argmax(signed_power, 5)
    result: pd.Series = argmax5.rank(pct=True) - 0.5
    return result


def _vec_alpha_4(df: pd.DataFrame, **_: object) -> pd.Series:
    return -flib._ts_rank(df["low"].rank(pct=True), 9)


def _vec_alpha_7(df: pd.DataFrame, **_: object) -> pd.Series:
    close = df["close"]
    volume = df["volume"]
    adv20 = volume.rolling(20).mean()
    delta7 = close.diff(7)
    abs_delta7 = delta7.abs()
    ts_r = flib._ts_rank(abs_delta7, 60)
    return pd.Series(
        np.where(adv20 < volume, -ts_r * np.sign(delta7), -1.0),
        index=close.index,
    )


def _vec_alpha_8(df: pd.DataFrame, **_: object) -> pd.Series:
    open_ = df["open"]
    returns = df["close"].pct_change()
    sum_open5 = open_.rolling(5).sum()
    sum_ret5 = returns.rolling(5).sum()
    product = sum_open5 * sum_ret5
    return -(product - product.shift(10)).rank(pct=True)


def _vec_alpha_9(df: pd.DataFrame, **_: object) -> pd.Series:
    close = df["close"]
    delta1 = close.diff(1)
    min5 = delta1.rolling(5).min()
    max5 = delta1.rolling(5).max()
    return pd.Series(
        np.where(min5 > 0, delta1, np.where(max5 < 0, delta1, -delta1)),
        index=close.index,
    )


def _vec_alpha_10(df: pd.DataFrame, **_: object) -> pd.Series:
    close = df["close"]
    delta1 = close.diff(1)
    min4 = delta1.rolling(4).min()
    max4 = delta1.rolling(4).max()
    inner = pd.Series(
        np.where(min4 > 0, delta1, np.where(max4 < 0, delta1, -delta1)),
        index=close.index,
    )
    return inner.rank(pct=True)


def _vec_alpha_13(df: pd.DataFrame, **_: object) -> pd.Series:
    close, volume = df["close"], df["volume"]
    cov = close.rank(pct=True).rolling(5).cov(volume.rank(pct=True))
    return -cov.rank(pct=True)


def _vec_alpha_14(df: pd.DataFrame, **_: object) -> pd.Series:
    close, open_, volume = df["close"], df["open"], df["volume"]
    returns = close.pct_change()
    delta_ret3 = returns.diff(3)
    corr = open_.rolling(10).corr(volume)
    return -delta_ret3.rank(pct=True) * corr


def _vec_alpha_15(df: pd.DataFrame, **_: object) -> pd.Series:
    high, volume = df["high"], df["volume"]
    corr = high.rank(pct=True).rolling(3).corr(volume.rank(pct=True))
    ranked_corr = corr.rank(pct=True)
    return -ranked_corr.rolling(3).sum()


def _vec_alpha_16(df: pd.DataFrame, **_: object) -> pd.Series:
    high, volume = df["high"], df["volume"]
    cov = high.rank(pct=True).rolling(5).cov(volume.rank(pct=True))
    return -cov.rank(pct=True)


def _vec_alpha_17(df: pd.DataFrame, **_: object) -> pd.Series:
    close, volume = df["close"], df["volume"]
    adv20 = volume.rolling(20).mean()
    ts_r_close = flib._ts_rank(close, 10)
    delta_delta = close.diff(1).diff(1)
    vol_ratio = volume / adv20.replace(0, np.nan)
    ts_r_vol = flib._ts_rank(vol_ratio, 5)
    return -ts_r_close.rank(pct=True) * delta_delta.rank(pct=True) * ts_r_vol.rank(pct=True)


def _vec_alpha_18(df: pd.DataFrame, **_: object) -> pd.Series:
    close, open_ = df["close"], df["open"]
    diff = close - open_
    std_abs = diff.abs().rolling(5).std()
    corr = close.rolling(10).corr(open_)
    return -(std_abs + diff + corr).rank(pct=True)


def _vec_alpha_19(df: pd.DataFrame, **_: object) -> pd.Series:
    close = df["close"]
    returns = close.pct_change()
    delta7 = close.diff(7)
    delay7 = close.shift(7)
    sign_part = np.sign((close - delay7) + delta7)
    sum_ret = returns.rolling(250).sum()
    raw = -sign_part * (1 + (1 + sum_ret).rank(pct=True))
    return pd.Series(raw, index=df.index)


def _vec_alpha_20(df: pd.DataFrame, **_: object) -> pd.Series:
    open_, high, close, low = df["open"], df["high"], df["close"], df["low"]
    r1 = (open_ - high.shift(1)).rank(pct=True)
    r2 = (open_ - close.shift(1)).rank(pct=True)
    r3 = (open_ - low.shift(1)).rank(pct=True)
    return r1 * r2 * r3


def _vec_alpha_22(df: pd.DataFrame, **_: object) -> pd.Series:
    high, close, volume = df["high"], df["close"], df["volume"]
    corr = high.rolling(5).corr(volume)
    delta_corr = corr.diff(5)
    std_rank = close.rolling(20).std().rank(pct=True)
    return -delta_corr * std_rank


def _vec_alpha_23(df: pd.DataFrame, **_: object) -> pd.Series:
    high = df["high"]
    sma20 = high.rolling(20).mean()
    delta2 = high.diff(2)
    return pd.Series(
        np.where(sma20 < high, -delta2, 0.0),
        index=high.index,
    )


def _vec_alpha_24(df: pd.DataFrame, **_: object) -> pd.Series:
    close = df["close"]
    sma100 = close.rolling(100).mean()
    delta_sma = sma100.diff(100)
    delay100 = close.shift(100)
    ratio = delta_sma / delay100.replace(0, np.nan)
    ts_min100 = close.rolling(100).min()
    delta3 = close.diff(3)
    return pd.Series(
        np.where(ratio <= 0.05, -(close - ts_min100), -delta3),
        index=close.index,
    )


def _vec_alpha_30(df: pd.DataFrame, **_: object) -> pd.Series:
    close = df["close"]
    s1 = np.sign(close.diff(1))
    s2 = np.sign(close.shift(1).diff(1))
    s3 = np.sign(close.shift(2).diff(1))
    result: pd.Series = s1 * s2 * s3
    return result


def _vec_alpha_35(df: pd.DataFrame, **_: object) -> pd.Series:
    close, high, low, volume = df["close"], df["high"], df["low"], df["volume"]
    returns = close.pct_change()
    tr1 = flib._ts_rank(volume, 32)
    tr2 = flib._ts_rank(close + high - low, 16)
    tr3 = flib._ts_rank(returns, 32)
    return tr1 * (1 - tr2) * (1 - tr3)


def _vec_alpha_40(df: pd.DataFrame, **_: object) -> pd.Series:
    high, volume = df["high"], df["volume"]
    std_high = high.rolling(10).std()
    corr = high.rolling(10).corr(volume)
    return -std_high.rank(pct=True) * corr


def _vec_alpha_2(df: pd.DataFrame, **_: object) -> pd.Series:
    close, open_, volume = df["close"], df["open"], df["volume"]
    delta_log_vol = np.log(volume).diff(2)
    intraday_ret = (close - open_) / open_
    corr: pd.Series = delta_log_vol.rank(pct=True).rolling(6).corr(intraday_ret.rank(pct=True))
    return -corr


def _vec_alpha_3(df: pd.DataFrame, **_: object) -> pd.Series:
    open_, volume = df["open"], df["volume"]
    return -open_.rank(pct=True).rolling(10).corr(volume.rank(pct=True))


def _vec_alpha_6(df: pd.DataFrame, **_: object) -> pd.Series:
    return -df["open"].rolling(10).corr(df["volume"])


def _vec_alpha_12(df: pd.DataFrame, **_: object) -> pd.Series:
    result: pd.Series = np.sign(df["volume"].diff(1)) * (-df["close"].diff(1))
    return result


def _vec_alpha_33(df: pd.DataFrame, **_: object) -> pd.Series:
    raw = -(1 - (df["open"] / df["close"]))
    return raw.rank(pct=True)


def _vec_alpha_34(df: pd.DataFrame, **_: object) -> pd.Series:
    returns = df["close"].pct_change()
    std2 = returns.rolling(2).std()
    std5 = returns.rolling(5).std()
    ratio = std2 / std5.replace(0, np.nan)
    delta_close = df["close"].diff(1)
    component = (1 - ratio.rank(pct=True)) + (1 - delta_close.rank(pct=True))
    return component.rank(pct=True)


def _vec_alpha_38(df: pd.DataFrame, **_: object) -> pd.Series:
    close, open_ = df["close"], df["open"]
    ts_r = flib._ts_rank(close, 10)
    ratio_rank = (close / open_).rank(pct=True)
    return -ts_r.rank(pct=True) * ratio_rank


def _vec_alpha_44(df: pd.DataFrame, **_: object) -> pd.Series:
    return -df["high"].rolling(5).corr(df["volume"].rank(pct=True))


def _vec_alpha_53(df: pd.DataFrame, **_: object) -> pd.Series:
    close, high, low = df["close"], df["high"], df["low"]
    denom = (close - low).replace(0, np.nan)
    williams = ((close - low) - (high - close)) / denom
    return -williams.diff(9)


def _vec_alpha_101(df: pd.DataFrame, **_: object) -> pd.Series:
    return (df["close"] - df["open"]) / ((df["high"] - df["low"]) + 0.001)


VECTORIZED_FACTORS: dict[str, Callable[..., pd.Series]] = {
    # Original technical
    "momentum": _vec_momentum,
    "mean_reversion": _vec_mean_reversion,
    "volatility": _vec_volatility,
    "rsi": _vec_rsi,
    "ma_cross": _vec_ma_cross,
    "vpt": _vec_vpt,
    "reversal": _vec_reversal,
    "illiquidity": _vec_illiquidity,
    "ivol": _vec_ivol,
    "skewness": _vec_skewness,
    "max_ret": _vec_max_ret,
    # New technical — vectorizable
    "bollinger_pos": _vec_bollinger_pos,
    "macd_hist": _vec_macd_hist,
    "obv_trend": _vec_obv_trend,
    "atr_ratio": _vec_atr_ratio,
    "price_accel": _vec_price_accel,
    "vol_momentum": _vec_vol_momentum,
    "hl_range": _vec_hl_range,
    "close_to_high": _vec_close_to_high,
    "gap": _vec_gap,
    "intraday_ret": _vec_intraday_ret,
    "overnight_ret": _vec_overnight_ret,
    # Academic momentum variants
    "momentum_1m": _vec_momentum_1m,
    "momentum_6m": _vec_momentum_6m,
    "momentum_12m": _vec_momentum_12m,
    "lt_reversal": _vec_lt_reversal,
    "max_daily_ret": _vec_max_daily_ret,
    "turnover_vol": _vec_turnover_vol,
    "zero_days": _vec_zero_days,
    # Original Kakushadze
    "alpha_2": _vec_alpha_2,
    "alpha_3": _vec_alpha_3,
    "alpha_6": _vec_alpha_6,
    "alpha_12": _vec_alpha_12,
    "alpha_33": _vec_alpha_33,
    "alpha_34": _vec_alpha_34,
    "alpha_38": _vec_alpha_38,
    "alpha_44": _vec_alpha_44,
    "alpha_53": _vec_alpha_53,
    "alpha_101": _vec_alpha_101,
    # New Kakushadze
    "alpha_1": _vec_alpha_1,
    "alpha_4": _vec_alpha_4,
    "alpha_7": _vec_alpha_7,
    "alpha_8": _vec_alpha_8,
    "alpha_9": _vec_alpha_9,
    "alpha_10": _vec_alpha_10,
    "alpha_13": _vec_alpha_13,
    "alpha_14": _vec_alpha_14,
    "alpha_15": _vec_alpha_15,
    "alpha_16": _vec_alpha_16,
    "alpha_17": _vec_alpha_17,
    "alpha_18": _vec_alpha_18,
    "alpha_19": _vec_alpha_19,
    "alpha_20": _vec_alpha_20,
    "alpha_22": _vec_alpha_22,
    "alpha_23": _vec_alpha_23,
    "alpha_24": _vec_alpha_24,
    "alpha_30": _vec_alpha_30,
    "alpha_35": _vec_alpha_35,
    "alpha_40": _vec_alpha_40,
}

# ── 因子註冊表 ──────────────────────────────────────────────────

FACTOR_REGISTRY: dict[str, dict[str, Any]] = {
    "momentum": {
        "fn": flib.momentum,
        "key": "momentum",
        "default_kwargs": {"lookback": 252, "skip": 21},
        "min_bars": 252,
    },
    "mean_reversion": {
        "fn": flib.mean_reversion,
        "key": "z_score",
        "default_kwargs": {"lookback": 20},
        "min_bars": 20,
    },
    "volatility": {
        "fn": flib.volatility,
        "key": "volatility",
        "default_kwargs": {"lookback": 20},
        "min_bars": 21,
    },
    "rsi": {
        "fn": flib.rsi,
        "key": "rsi",
        "default_kwargs": {"period": 14},
        "min_bars": 15,
    },
    "ma_cross": {
        "fn": flib.moving_average_crossover,
        "key": "ma_cross",
        "default_kwargs": {"fast": 10, "slow": 50},
        "min_bars": 50,
    },
    "vpt": {
        "fn": flib.volume_price_trend,
        "key": "vpt",
        "default_kwargs": {"lookback": 20},
        "min_bars": 21,
    },
    "reversal": {
        "fn": flib.short_term_reversal,
        "key": "reversal",
        "default_kwargs": {"lookback": 5},
        "min_bars": 6,
    },
    "illiquidity": {
        "fn": flib.amihud_illiquidity,
        "key": "illiquidity",
        "default_kwargs": {"lookback": 20},
        "min_bars": 21,
    },
    "ivol": {
        "fn": flib.idiosyncratic_vol,
        "key": "ivol",
        "default_kwargs": {"lookback": 60},
        "min_bars": 61,
    },
    "skewness": {
        "fn": flib.skewness,
        "key": "skew",
        "default_kwargs": {"lookback": 60},
        "min_bars": 61,
    },
    "max_ret": {
        "fn": flib.max_return,
        "key": "max_ret",
        "default_kwargs": {"lookback": 20},
        "min_bars": 21,
    },
    "alpha_2": {
        "fn": flib.kakushadze_alpha_2,
        "key": "alpha_2",
        "default_kwargs": {},
        "min_bars": 10,
    },
    "alpha_3": {
        "fn": flib.kakushadze_alpha_3,
        "key": "alpha_3",
        "default_kwargs": {},
        "min_bars": 12,
    },
    "alpha_6": {
        "fn": flib.kakushadze_alpha_6,
        "key": "alpha_6",
        "default_kwargs": {},
        "min_bars": 12,
    },
    "alpha_12": {
        "fn": flib.kakushadze_alpha_12,
        "key": "alpha_12",
        "default_kwargs": {},
        "min_bars": 3,
    },
    "alpha_33": {
        "fn": flib.kakushadze_alpha_33,
        "key": "alpha_33",
        "default_kwargs": {},
        "min_bars": 2,
    },
    "alpha_34": {
        "fn": flib.kakushadze_alpha_34,
        "key": "alpha_34",
        "default_kwargs": {},
        "min_bars": 8,
    },
    "alpha_38": {
        "fn": flib.kakushadze_alpha_38,
        "key": "alpha_38",
        "default_kwargs": {},
        "min_bars": 12,
    },
    "alpha_44": {
        "fn": flib.kakushadze_alpha_44,
        "key": "alpha_44",
        "default_kwargs": {},
        "min_bars": 8,
    },
    "alpha_53": {
        "fn": flib.kakushadze_alpha_53,
        "key": "alpha_53",
        "default_kwargs": {},
        "min_bars": 12,
    },
    "alpha_101": {
        "fn": flib.kakushadze_alpha_101,
        "key": "alpha_101",
        "default_kwargs": {},
        "min_bars": 1,
    },
    # ── New Technical Indicators ──────────────────────────────────
    "bollinger_pos": {
        "fn": flib.bollinger_position,
        "key": "bollinger_pos",
        "default_kwargs": {"lookback": 20},
        "min_bars": 20,
    },
    "macd_hist": {
        "fn": flib.macd_signal,
        "key": "macd_hist",
        "default_kwargs": {"fast": 12, "slow": 26, "signal": 9},
        "min_bars": 35,
    },
    "obv_trend": {
        "fn": flib.obv_trend,
        "key": "obv_trend",
        "default_kwargs": {"lookback": 20},
        "min_bars": 21,
    },
    "adx": {
        "fn": flib.adx,
        "key": "adx",
        "default_kwargs": {"period": 14},
        "min_bars": 29,
    },
    "cci": {
        "fn": flib.cci,
        "key": "cci",
        "default_kwargs": {"period": 20},
        "min_bars": 20,
    },
    "williams_r": {
        "fn": flib.williams_r,
        "key": "williams_r",
        "default_kwargs": {"period": 14},
        "min_bars": 14,
    },
    "stochastic_k": {
        "fn": flib.stochastic_k,
        "key": "stochastic_k",
        "default_kwargs": {"period": 14},
        "min_bars": 14,
    },
    "atr_ratio": {
        "fn": flib.atr_ratio,
        "key": "atr_ratio",
        "default_kwargs": {"period": 14},
        "min_bars": 15,
    },
    "price_accel": {
        "fn": flib.price_acceleration,
        "key": "price_accel",
        "default_kwargs": {"lookback": 20},
        "min_bars": 22,
    },
    "vol_momentum": {
        "fn": flib.volume_momentum,
        "key": "vol_momentum",
        "default_kwargs": {"lookback": 20},
        "min_bars": 21,
    },
    "hl_range": {
        "fn": flib.high_low_range,
        "key": "hl_range",
        "default_kwargs": {"lookback": 20},
        "min_bars": 20,
    },
    "close_to_high": {
        "fn": flib.close_to_high,
        "key": "close_to_high",
        "default_kwargs": {"lookback": 5},
        "min_bars": 5,
    },
    "gap": {
        "fn": flib.gap_factor,
        "key": "gap",
        "default_kwargs": {},
        "min_bars": 2,
    },
    "intraday_ret": {
        "fn": flib.intraday_return,
        "key": "intraday_ret",
        "default_kwargs": {},
        "min_bars": 1,
    },
    "overnight_ret": {
        "fn": flib.overnight_return,
        "key": "overnight_ret",
        "default_kwargs": {},
        "min_bars": 2,
    },
    # ── Academic Factors ──────────────────────────────────────────
    "momentum_1m": {
        "fn": flib.momentum_1m,
        "key": "momentum_1m",
        "default_kwargs": {},
        "min_bars": 22,
    },
    "momentum_6m": {
        "fn": flib.momentum_6m,
        "key": "momentum_6m",
        "default_kwargs": {},
        "min_bars": 127,
    },
    "momentum_12m": {
        "fn": flib.momentum_12m,
        "key": "momentum_12m",
        "default_kwargs": {},
        "min_bars": 253,
    },
    "lt_reversal": {
        "fn": flib.long_term_reversal,
        "key": "lt_reversal",
        "default_kwargs": {"lookback": 756},
        "min_bars": 757,
    },
    "beta": {
        "fn": flib.beta_market,
        "key": "beta",
        "default_kwargs": {"lookback": 252},
        "min_bars": 253,
    },
    "idio_skew": {
        "fn": flib.idiosyncratic_skewness,
        "key": "idio_skew",
        "default_kwargs": {"lookback": 60},
        "min_bars": 61,
    },
    "max_daily_ret": {
        "fn": flib.max_daily_return,
        "key": "max_daily_ret",
        "default_kwargs": {"lookback": 21},
        "min_bars": 22,
    },
    "turnover_vol": {
        "fn": flib.turnover_volatility,
        "key": "turnover_vol",
        "default_kwargs": {"lookback": 60},
        "min_bars": 60,
    },
    "price_delay": {
        "fn": flib.price_delay,
        "key": "price_delay",
        "default_kwargs": {"lookback": 5},
        "min_bars": 60,
    },
    "zero_days": {
        "fn": flib.zero_trading_days,
        "key": "zero_days",
        "default_kwargs": {"lookback": 60},
        "min_bars": 60,
    },
    # ── New Kakushadze Alphas ─────────────────────────────────────
    "alpha_1": {
        "fn": flib.kakushadze_alpha_1,
        "key": "alpha_1",
        "default_kwargs": {},
        "min_bars": 26,
    },
    "alpha_4": {
        "fn": flib.kakushadze_alpha_4,
        "key": "alpha_4",
        "default_kwargs": {},
        "min_bars": 11,
    },
    "alpha_7": {
        "fn": flib.kakushadze_alpha_7,
        "key": "alpha_7",
        "default_kwargs": {},
        "min_bars": 68,
    },
    "alpha_8": {
        "fn": flib.kakushadze_alpha_8,
        "key": "alpha_8",
        "default_kwargs": {},
        "min_bars": 16,
    },
    "alpha_9": {
        "fn": flib.kakushadze_alpha_9,
        "key": "alpha_9",
        "default_kwargs": {},
        "min_bars": 7,
    },
    "alpha_10": {
        "fn": flib.kakushadze_alpha_10,
        "key": "alpha_10",
        "default_kwargs": {},
        "min_bars": 6,
    },
    "alpha_13": {
        "fn": flib.kakushadze_alpha_13,
        "key": "alpha_13",
        "default_kwargs": {},
        "min_bars": 7,
    },
    "alpha_14": {
        "fn": flib.kakushadze_alpha_14,
        "key": "alpha_14",
        "default_kwargs": {},
        "min_bars": 15,
    },
    "alpha_15": {
        "fn": flib.kakushadze_alpha_15,
        "key": "alpha_15",
        "default_kwargs": {},
        "min_bars": 8,
    },
    "alpha_16": {
        "fn": flib.kakushadze_alpha_16,
        "key": "alpha_16",
        "default_kwargs": {},
        "min_bars": 7,
    },
    "alpha_17": {
        "fn": flib.kakushadze_alpha_17,
        "key": "alpha_17",
        "default_kwargs": {},
        "min_bars": 22,
    },
    "alpha_18": {
        "fn": flib.kakushadze_alpha_18,
        "key": "alpha_18",
        "default_kwargs": {},
        "min_bars": 12,
    },
    "alpha_19": {
        "fn": flib.kakushadze_alpha_19,
        "key": "alpha_19",
        "default_kwargs": {},
        "min_bars": 252,
    },
    "alpha_20": {
        "fn": flib.kakushadze_alpha_20,
        "key": "alpha_20",
        "default_kwargs": {},
        "min_bars": 3,
    },
    "alpha_22": {
        "fn": flib.kakushadze_alpha_22,
        "key": "alpha_22",
        "default_kwargs": {},
        "min_bars": 30,
    },
    "alpha_23": {
        "fn": flib.kakushadze_alpha_23,
        "key": "alpha_23",
        "default_kwargs": {},
        "min_bars": 22,
    },
    "alpha_24": {
        "fn": flib.kakushadze_alpha_24,
        "key": "alpha_24",
        "default_kwargs": {},
        "min_bars": 104,
    },
    "alpha_30": {
        "fn": flib.kakushadze_alpha_30,
        "key": "alpha_30",
        "default_kwargs": {},
        "min_bars": 6,
    },
    "alpha_35": {
        "fn": flib.kakushadze_alpha_35,
        "key": "alpha_35",
        "default_kwargs": {},
        "min_bars": 34,
    },
    "alpha_40": {
        "fn": flib.kakushadze_alpha_40,
        "key": "alpha_40",
        "default_kwargs": {},
        "min_bars": 12,
    },
}


def compute_market_returns(data: dict[str, pd.DataFrame]) -> pd.Series:
    """計算等權市場報酬代理。"""
    all_close = pd.DataFrame({s: data[s]["close"] for s in sorted(data.keys())})
    return all_close.pct_change().mean(axis=1).dropna()


# ── 基本面因子註冊表 ────────────────────────────────────────────────


@dataclass
class FundamentalFactorDef:
    """基本面因子定義。

    Single-metric factors use ``metric_key`` (e.g. value_pe).
    Multi-metric factors use ``metric_keys`` — the values are passed
    positionally to ``fn`` in the order listed.
    """

    name: str
    fn: Callable[..., float]
    metric_key: str = ""  # get_financials() 回傳 dict 中的 key (single-metric)
    metric_keys: list[str] = field(default_factory=list)  # multi-metric

    def compute(self, financials: dict[str, float]) -> float | None:
        """Compute factor value from a financials dict.

        Returns None if required metrics are missing.
        """
        if self.metric_keys:
            vals: list[float] = []
            for k in self.metric_keys:
                v = financials.get(k)
                if v is None:
                    return None
                vals.append(v)
            return self.fn(*vals)
        # Single metric
        metric_val = financials.get(self.metric_key)
        if metric_val is None:
            return None
        return self.fn(metric_val)


FUNDAMENTAL_REGISTRY: dict[str, FundamentalFactorDef] = {
    # ── Fama-French 風格因子 ──
    "value_pe": FundamentalFactorDef(name="value_pe", fn=flib.value_pe, metric_key="pe_ratio"),
    "value_pb": FundamentalFactorDef(name="value_pb", fn=flib.value_pb, metric_key="pb_ratio"),
    "quality_roe": FundamentalFactorDef(name="quality_roe", fn=flib.quality_roe, metric_key="roe"),
    "size": FundamentalFactorDef(
        name="size",
        fn=lambda market_cap: -np.log(market_cap) if market_cap > 0 else 0.0,
        metric_key="market_cap",
    ),
    "investment": FundamentalFactorDef(
        name="investment",
        fn=flib.investment_factor,
        metric_keys=["total_assets_current", "total_assets_prev"],
    ),
    "gross_profit": FundamentalFactorDef(
        name="gross_profit",
        fn=flib.gross_profitability_factor,
        metric_keys=["revenue", "cogs", "total_assets"],
    ),
    # ── 營收因子 ──
    "revenue_yoy": FundamentalFactorDef(
        name="revenue_yoy",
        fn=flib.revenue_yoy_factor,
        metric_key="revenue_yoy_growth",
    ),
    "revenue_momentum": FundamentalFactorDef(
        name="revenue_momentum",
        fn=flib.revenue_momentum_factor,
        metric_key="revenue_consecutive_growth",
    ),
    # ── 營收進階因子（FinLab 研究驅動）──
    "revenue_new_high": FundamentalFactorDef(
        name="revenue_new_high",
        fn=flib.revenue_new_high_factor,
        metric_key="revenue_3m_is_12m_high",
    ),
    "revenue_acceleration": FundamentalFactorDef(
        name="revenue_acceleration",
        fn=flib.revenue_acceleration_factor,
        metric_key="revenue_3m_over_12m_ratio",
    ),
    "trust_cumulative": FundamentalFactorDef(
        name="trust_cumulative",
        fn=flib.trust_cumulative_factor,
        metric_key="trust_10d_cumulative_net",
    ),
    # ── 殖利率因子 ──
    "dividend_yield": FundamentalFactorDef(
        name="dividend_yield",
        fn=flib.dividend_yield_factor,
        metric_key="dividend_yield",
    ),
    # ── 籌碼面因子 ──
    "foreign_net": FundamentalFactorDef(
        name="foreign_net",
        fn=flib.foreign_net_factor,
        metric_key="foreign_net_normalized",
    ),
    "trust_net": FundamentalFactorDef(
        name="trust_net",
        fn=flib.trust_net_factor,
        metric_key="trust_net_normalized",
    ),
    "director_change": FundamentalFactorDef(
        name="director_change",
        fn=flib.director_change_factor,
        metric_key="director_holding_change",
    ),
    "margin_change": FundamentalFactorDef(
        name="margin_change",
        fn=flib.margin_change_factor,
        metric_key="margin_balance_change_ratio",
    ),
    "daytrading_ratio": FundamentalFactorDef(
        name="daytrading_ratio",
        fn=flib.daytrading_ratio_factor,
        metric_key="daytrading_volume_ratio",
    ),
}


def compute_fundamental_factor_values(
    symbols: list[str],
    factor_name: str,
    provider: FundamentalsProvider,
    dates: list[pd.Timestamp],
) -> pd.DataFrame:
    """
    透過 FundamentalsProvider 計算基本面因子值。

    Returns:
        DataFrame，index=date，columns=symbols，values=factor values
    """
    if factor_name not in FUNDAMENTAL_REGISTRY:
        raise ValueError(f"Unknown fundamental factor: {factor_name}. Available: {list(FUNDAMENTAL_REGISTRY.keys())}")

    fdef = FUNDAMENTAL_REGISTRY[factor_name]

    result_rows: list[dict[str, float | pd.Timestamp]] = []
    for dt in dates:
        row: dict[str, float | pd.Timestamp] = {"date": dt}
        date_str = str(dt.date()) if hasattr(dt, "date") else str(dt)
        for sym in symbols:
            try:
                financials = provider.get_financials(sym, date_str)
            except Exception:
                logger.debug("Failed to get financials for %s on %s", sym, date_str, exc_info=True)
                continue
            val = fdef.compute(financials)
            if val is not None:
                row[sym] = val
        if len(row) > 1:
            result_rows.append(row)

    if not result_rows:
        return pd.DataFrame()

    return pd.DataFrame(result_rows).set_index("date")


# ── 結果資料結構 ─────────────────────────────────────────────────


@dataclass
class ICResult:
    """單因子 IC 分析結果。"""

    factor_name: str
    ic_mean: float  # 平均 IC
    ic_std: float  # IC 標準差
    icir: float  # IC / IC_std (Information Ratio)
    ic_series: pd.Series = field(repr=False, default_factory=pd.Series)
    hit_rate: float = 0.0  # IC > 0 的比率

    def summary(self) -> str:
        return (
            f"Factor: {self.factor_name}\n"
            f"  IC Mean:  {self.ic_mean:+.4f}\n"
            f"  IC Std:   {self.ic_std:.4f}\n"
            f"  ICIR:     {self.icir:+.4f}\n"
            f"  Hit Rate: {self.hit_rate:.1%}\n"
            f"  Periods:  {len(self.ic_series)}"
        )


@dataclass
class DecayResult:
    """因子衰減分析結果。"""

    factor_name: str
    horizons: list[int]
    ic_by_horizon: dict[int, float]  # horizon → IC

    def summary(self) -> str:
        lines = [f"Factor Decay: {self.factor_name}"]
        for h in self.horizons:
            ic = self.ic_by_horizon.get(h, 0.0)
            bar = "█" * max(0, int(abs(ic) * 100))
            sign = "+" if ic >= 0 else ""
            lines.append(f"  {h:>3}d: {sign}{ic:.4f} {bar}")
        return "\n".join(lines)


@dataclass
class CompositeResult:
    """因子合成結果。"""

    factor_names: list[str]
    weights: dict[str, float]
    composite_ic: float
    individual_ics: dict[str, float]


# ── 核心分析函式 ─────────────────────────────────────────────────


def _compute_vectorized(
    data: dict[str, pd.DataFrame],
    factor_name: str,
    dates: list[pd.Timestamp],
    fn_kwargs: dict[str, Any],
    min_bars: int,
) -> pd.DataFrame:
    """向量化快速路徑：每個標的只呼叫一次向量化函式，回傳完整 Series。"""
    vec_fn = VECTORIZED_FACTORS[factor_name]

    col_results: dict[str, pd.Series] = {}
    for sym in sorted(data.keys()):
        df = data[sym]
        if len(df) < min_bars:
            continue
        series = vec_fn(df, **fn_kwargs)
        if series is not None and not series.empty:
            col_results[sym] = series

    if not col_results:
        return pd.DataFrame()

    result_df = pd.DataFrame(col_results)
    result_df = result_df.reindex(dates).dropna(how="all")
    return result_df


def _compute_per_window(
    data: dict[str, pd.DataFrame],
    factor_name: str,
    dates: list[pd.Timestamp],
    fn: Callable[..., Any],
    key: str,
    fn_kwargs: dict[str, Any],
    min_bars: int,
) -> pd.DataFrame:
    """逐窗口慢速路徑：相容所有因子函式。"""
    symbols = sorted(data.keys())
    window = max(min_bars * 2, 300)

    col_results: dict[str, pd.Series] = {}

    for sym in symbols:
        df = data[sym]
        idx = df.index
        if len(idx) < min_bars:
            continue

        valid_dates = [dt for dt in dates if dt in idx or (len(idx) > 0 and idx[0] <= dt)]

        values: dict[pd.Timestamp, float] = {}
        for dt in valid_dates:
            pos = int(idx.searchsorted(dt, side="right"))
            if pos < min_bars:
                continue
            start = max(0, pos - window)
            bars = df.iloc[start:pos]
            if len(bars) < min_bars:
                continue
            val = fn(bars, **fn_kwargs)
            if isinstance(val, dict):
                val = pd.Series(val)
            if not val.empty and key in val.index:
                values[dt] = float(val[key])

        if values:
            col_results[sym] = pd.Series(values)

    if not col_results:
        return pd.DataFrame()

    result_df = pd.DataFrame(col_results)
    result_df = result_df.reindex(dates).dropna(how="all")
    return result_df


def compute_factor_values(
    data: dict[str, pd.DataFrame],
    factor_name: str,
    dates: list[pd.Timestamp] | None = None,
    **kwargs: object,
) -> pd.DataFrame:
    """
    對多檔標的在多個日期計算因子值。

    優先使用向量化快速路徑（每個標的一次 pandas 向量化呼叫），
    若該因子無向量化版本則退回逐窗口慢速路徑。

    Args:
        data: {symbol: OHLCV DataFrame}
        factor_name: 已註冊的因子名稱
        dates: 計算日期列表（None = 使用所有共有日期）
        **kwargs: 覆蓋因子預設參數

    Returns:
        DataFrame，index=date，columns=symbols，values=factor values
    """
    if factor_name not in FACTOR_REGISTRY:
        raise ValueError(f"Unknown factor: {factor_name}. Available: {list(FACTOR_REGISTRY.keys())}")

    reg = FACTOR_REGISTRY[factor_name]
    fn = reg["fn"]
    key = reg["key"]
    min_bars = reg["min_bars"]
    fn_kwargs: dict[str, Any] = {**reg["default_kwargs"], **kwargs}

    # ivol 需要市場報酬代理（等權平均）
    if factor_name == "ivol" and "market_returns" not in fn_kwargs:
        fn_kwargs["market_returns"] = compute_market_returns(data)

    if dates is None:
        all_dates: set[pd.Timestamp] | None = None
        for sym in sorted(data.keys()):
            sym_dates = set(data[sym].index)
            all_dates = sym_dates if all_dates is None else all_dates & sym_dates
        dates = sorted(all_dates or set())

    if not dates:
        return pd.DataFrame()

    # 嘗試向量化快速路徑
    if factor_name in VECTORIZED_FACTORS:
        return _compute_vectorized(data, factor_name, dates, fn_kwargs, min_bars)

    # 退回逐窗口慢速路徑
    return _compute_per_window(data, factor_name, dates, fn, key, fn_kwargs, min_bars)


def compute_forward_returns(
    data: dict[str, pd.DataFrame],
    horizon: int = 5,
    dates: list[pd.Timestamp] | None = None,
) -> pd.DataFrame:
    """
    計算未來 N 天報酬（向量化實作）。

    Returns:
        DataFrame，index=date，columns=symbols，values=forward return
    """
    symbols = sorted(data.keys())

    if dates is None:
        all_dates: set[pd.Timestamp] | None = None
        for sym in symbols:
            sym_dates = set(data[sym].index)
            all_dates = sym_dates if all_dates is None else all_dates & sym_dates
        dates = sorted(all_dates or set())

    if not dates:
        return pd.DataFrame()

    # 逐標的向量化計算 forward return
    col_results: dict[str, pd.Series] = {}

    for sym in symbols:
        df = data[sym]
        close = df["close"]

        if len(close) <= horizon:
            continue

        # 用 shift 向量化計算：future_price = close.shift(-horizon)
        future_price = close.shift(-horizon)
        fwd_ret = future_price / close - 1

        # 只保留在 dates 中的日期
        common = fwd_ret.index.intersection(dates)
        if not common.empty:
            valid = fwd_ret.loc[common].dropna()
            if not valid.empty:
                col_results[sym] = valid

    if not col_results:
        return pd.DataFrame()

    result_df = pd.DataFrame(col_results)
    result_df = result_df.reindex(dates).dropna(how="all")
    return result_df


def compute_ic(
    factor_values: pd.DataFrame,
    forward_returns: pd.DataFrame,
    method: str = "rank",
) -> ICResult:
    """
    計算 Information Coefficient（IC）。

    IC = 每期因子值與未來報酬的橫截面相關性（Spearman rank correlation）。

    Args:
        factor_values: index=date, columns=symbols
        forward_returns: 同上
        method: "rank" (Spearman) 或 "pearson"
    """
    common_dates = factor_values.index.intersection(forward_returns.index)
    common_symbols = factor_values.columns.intersection(forward_returns.columns)

    if len(common_dates) == 0 or len(common_symbols) < 3:
        return ICResult(factor_name="", ic_mean=0, ic_std=0, icir=0)

    ic_values: list[float] = []
    ic_dates: list[pd.Timestamp] = []

    for dt in common_dates:
        fv = factor_values.loc[dt, common_symbols].dropna()
        fr = forward_returns.loc[dt, common_symbols].dropna()
        common = fv.index.intersection(fr.index)
        if len(common) < 3:
            continue

        if method == "rank":
            fv_series = pd.Series(fv[common].rank())
            fr_series = pd.Series(fr[common].rank())
            corr_val: float = fv_series.corr(fr_series)
        else:
            fv_series = pd.Series(fv[common])
            fr_series = pd.Series(fr[common])
            corr_val = fv_series.corr(fr_series)

        if not np.isnan(corr_val):
            ic_values.append(corr_val)
            ic_dates.append(dt)

    if not ic_values:
        return ICResult(factor_name="", ic_mean=0, ic_std=0, icir=0)

    ic_series = pd.Series(ic_values, index=ic_dates)
    ic_mean = float(ic_series.mean())
    ic_std = float(ic_series.std())
    icir = ic_mean / ic_std if ic_std > 0 else 0.0
    hit_rate = float((ic_series > 0).mean())

    return ICResult(
        factor_name="",
        ic_mean=ic_mean,
        ic_std=ic_std,
        icir=icir,
        ic_series=ic_series,
        hit_rate=hit_rate,
    )


def factor_decay(
    data: dict[str, pd.DataFrame],
    factor_name: str,
    horizons: list[int] | None = None,
    dates: list[pd.Timestamp] | None = None,
    **kwargs: object,
) -> DecayResult:
    """
    因子衰減分析：在不同持倉週期下的 IC。

    Args:
        data: {symbol: OHLCV DataFrame}
        factor_name: 因子名稱
        horizons: 持倉週期列表（交易日數），預設 [1, 5, 10, 20, 40, 60]
    """
    if horizons is None:
        horizons = [1, 5, 10, 20, 40, 60]

    factor_values = compute_factor_values(data, factor_name, dates=dates, **kwargs)
    if factor_values.empty:
        return DecayResult(factor_name=factor_name, horizons=horizons, ic_by_horizon={})

    ic_by_horizon: dict[int, float] = {}
    for h in horizons:
        fwd = compute_forward_returns(data, horizon=h, dates=list(factor_values.index))
        if fwd.empty:
            ic_by_horizon[h] = 0.0
            continue
        ic_result = compute_ic(factor_values, fwd)
        ic_by_horizon[h] = ic_result.ic_mean

    return DecayResult(
        factor_name=factor_name,
        horizons=horizons,
        ic_by_horizon=ic_by_horizon,
    )


def compute_rolling_ic(
    factor_values: pd.DataFrame,
    forward_returns: pd.DataFrame,
    window: int = 60,
    method: str = "rank",
) -> pd.Series:
    """
    計算滾動 IC：在每個日期上取過去 window 期的平均 IC。

    Returns:
        Series, index=date, values=trailing average IC
    """
    common_dates = sorted(factor_values.index.intersection(forward_returns.index))
    common_symbols = factor_values.columns.intersection(forward_returns.columns)

    if len(common_dates) < window or len(common_symbols) < 3:
        return pd.Series(dtype=float)

    # 逐日計算橫截面 IC
    daily_ic: list[float] = []
    daily_dates: list[pd.Timestamp] = []
    for dt in common_dates:
        fv = factor_values.loc[dt, common_symbols].dropna()
        fr = forward_returns.loc[dt, common_symbols].dropna()
        common = fv.index.intersection(fr.index)
        if len(common) < 3:
            daily_ic.append(np.nan)
            daily_dates.append(dt)
            continue

        if method == "rank":
            corr = pd.Series(fv[common].rank()).corr(pd.Series(fr[common].rank()))
        else:
            corr = pd.Series(fv[common]).corr(pd.Series(fr[common]))

        daily_ic.append(float(corr) if not np.isnan(corr) else np.nan)
        daily_dates.append(dt)

    ic_series = pd.Series(daily_ic, index=daily_dates)
    rolling_mean = ic_series.rolling(window, min_periods=max(window // 2, 10)).mean()
    return rolling_mean.dropna()


# ── 便利函式 ─────────────────────────────────────────────────


def analyze_factor(
    data: dict[str, pd.DataFrame],
    factor_name: str,
    horizon: int = 5,
    **kwargs: object,
) -> ICResult:
    """單因子完整分析的便利函式。"""
    fv = compute_factor_values(data, factor_name, **kwargs)  # type: ignore[arg-type]
    if fv.empty:
        return ICResult(factor_name=factor_name, ic_mean=0, ic_std=0, icir=0)

    fwd = compute_forward_returns(data, horizon=horizon, dates=list(fv.index))
    result = compute_ic(fv, fwd)
    result.factor_name = factor_name
    return result
