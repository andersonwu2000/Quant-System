"""
因子函式庫 — 純函式，無狀態，可獨立測試。

每個因子：DataFrame → Series（因子值）
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def momentum(prices: pd.DataFrame, lookback: int = 252, skip: int = 21) -> pd.Series:
    """
    動量因子：過去 lookback 天的報酬，跳過最近 skip 天。

    經典的 12-1 動量：lookback=252, skip=21
    """
    close = prices["close"]
    if len(close) < lookback:
        return pd.Series(dtype=float)

    ret = close.iloc[-skip] / close.iloc[-lookback] - 1
    return pd.Series({"momentum": float(ret)})


def mean_reversion(prices: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """
    均值回歸因子：當前價格相對於 lookback 天均線的偏離度 (Z-score)。
    """
    close = prices["close"]
    if len(close) < lookback:
        return pd.Series(dtype=float)

    ma = close.iloc[-lookback:].mean()
    std = close.iloc[-lookback:].std()

    if std == 0:
        return pd.Series({"z_score": 0.0})

    z = (close.iloc[-1] - ma) / std
    return pd.Series({"z_score": float(-z)})  # 負號：偏低→買入信號


def volatility(prices: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """
    波動率因子：過去 lookback 天的年化波動率。
    低波動率因子（反向使用）。
    """
    close = prices["close"]
    if len(close) < lookback + 1:
        return pd.Series(dtype=float)

    returns = close.pct_change().dropna().iloc[-lookback:]
    vol = returns.std() * np.sqrt(252)
    return pd.Series({"volatility": float(vol)})


def rsi(prices: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    相對強弱指標 (RSI)。
    """
    close = prices["close"]
    if len(close) < period + 1:
        return pd.Series(dtype=float)

    delta = close.diff().iloc[-period:]
    gain = delta.where(delta > 0, 0.0).mean()
    loss = (-delta.where(delta < 0, 0.0)).mean()

    if loss == 0:
        return pd.Series({"rsi": 100.0})

    rs = gain / loss
    rsi_value = 100 - (100 / (1 + rs))
    return pd.Series({"rsi": float(rsi_value)})


def moving_average_crossover(
    prices: pd.DataFrame,
    fast: int = 10,
    slow: int = 50,
) -> pd.Series:
    """
    均線交叉因子：快線/慢線的比值。
    > 1 = 多頭訊號, < 1 = 空頭訊號
    """
    close = prices["close"]
    if len(close) < slow:
        return pd.Series(dtype=float)

    ma_fast = close.iloc[-fast:].mean()
    ma_slow = close.iloc[-slow:].mean()

    if ma_slow == 0:
        return pd.Series({"ma_cross": 0.0})

    signal = ma_fast / ma_slow - 1
    return pd.Series({"ma_cross": float(signal)})


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


def revenue_momentum(revenues: pd.Series, periods: int = 3) -> float:
    """Revenue momentum: average MoM growth over recent periods.

    Args:
        revenues: Series of revenue values (chronologically ordered)
        periods: Number of recent periods to average

    Returns:
        Average month-over-month growth rate (as decimal, e.g., 0.05 = 5%)
    """
    if len(revenues) < periods + 1:
        return 0.0

    recent = revenues.iloc[-(periods + 1) :]
    growths = recent.pct_change().dropna()

    if growths.empty:
        return 0.0

    return float(growths.mean())


def volume_price_trend(prices: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """
    量價趨勢因子：價格上漲且成交量放大 = 正信號。
    """
    if len(prices) < lookback + 1:
        return pd.Series(dtype=float)

    recent = prices.iloc[-lookback:]
    price_ret = recent["close"].pct_change()
    vol_change = recent["volume"].pct_change()

    # 價格報酬與成交量變化的相關性
    corr = price_ret.corr(vol_change)
    return pd.Series({"vpt": float(corr) if not np.isnan(corr) else 0.0})
