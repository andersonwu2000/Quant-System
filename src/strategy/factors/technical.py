"""
技術因子 — 基於價量資料的純函式。
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


def short_term_reversal(prices: pd.DataFrame, lookback: int = 5) -> pd.Series:
    """
    短期反轉因子：過去 lookback 天報酬的負值。
    短期漲幅越大→預期反轉越強 (Jegadeesh 1990)。
    """
    close = prices["close"]
    if len(close) < lookback + 1:
        return pd.Series(dtype=float)

    ret = close.iloc[-1] / close.iloc[-lookback - 1] - 1
    return pd.Series({"reversal": float(-ret)})


def amihud_illiquidity(prices: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """
    Amihud 非流動性因子：avg(|日報酬| / 成交金額) (Amihud 2002)。
    高值 = 低流動性 = 預期溢價。
    """
    if len(prices) < lookback + 1:
        return pd.Series(dtype=float)

    recent = prices.iloc[-(lookback + 1) :]
    ret = recent["close"].pct_change().dropna().abs()
    dollar_vol = (recent["close"] * recent["volume"]).iloc[1:]

    # 避免除以零
    valid = dollar_vol > 0
    if valid.sum() == 0:
        return pd.Series({"illiquidity": 0.0})

    ratio = ret[valid] / dollar_vol[valid]
    return pd.Series({"illiquidity": float(ratio.mean())})


def idiosyncratic_vol(
    prices: pd.DataFrame,
    lookback: int = 60,
    market_returns: pd.Series | None = None,
) -> pd.Series:
    """
    特質波動率因子：去除市場 beta 後的殘差波動率 (Ang et al. 2006)。
    低特質波動率 → 預期超額報酬。
    """
    close = prices["close"]
    if len(close) < lookback + 1:
        return pd.Series(dtype=float)

    stock_ret = close.pct_change().dropna().iloc[-lookback:]

    if market_returns is None or market_returns.empty:
        # 無市場代理時退化為普通波動率
        ivol = float(stock_ret.std() * np.sqrt(252))
        return pd.Series({"ivol": ivol})

    # 對齊日期
    common = stock_ret.index.intersection(market_returns.index)
    if len(common) < 20:
        return pd.Series(dtype=float)

    y = np.array(stock_ret.loc[common].values, dtype=np.float64)
    x = np.array(market_returns.loc[common].values, dtype=np.float64)

    # OLS: y = alpha + beta * x + epsilon
    x_with_const = np.column_stack([np.ones(len(x)), x])
    result = np.linalg.lstsq(x_with_const, y, rcond=None)
    residuals = y - x_with_const @ result[0]
    ivol = float(np.std(residuals, ddof=1) * np.sqrt(252))
    return pd.Series({"ivol": ivol})


def skewness(prices: pd.DataFrame, lookback: int = 60) -> pd.Series:
    """
    報酬偏度因子 (Bali et al. 2011)。
    高正偏度（彩票效應）→ 預期報酬較低。
    """
    close = prices["close"]
    if len(close) < lookback + 1:
        return pd.Series(dtype=float)

    ret = close.pct_change().dropna().iloc[-lookback:]
    raw_skew: float = float(ret.skew())  # type: ignore[arg-type]
    skew_val = raw_skew if not np.isnan(raw_skew) else 0.0
    return pd.Series({"skew": skew_val})


def max_return(prices: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """
    最大日報酬因子 (Bali et al. 2011)。
    過去 lookback 天的最大單日報酬。高值 → 預期報酬較低。
    """
    close = prices["close"]
    if len(close) < lookback + 1:
        return pd.Series(dtype=float)

    ret = close.pct_change().dropna().iloc[-lookback:]
    return pd.Series({"max_ret": float(ret.max())})


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
