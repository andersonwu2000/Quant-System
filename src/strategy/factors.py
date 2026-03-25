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


# ── Kakushadze 101 helpers ──────────────────────────────────────────────


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


# ── Kakushadze 101 selected alphas ──────────────────────────────────────


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
