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
