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


# ── Technical Indicators ──────────────────────────────────────────


def bollinger_position(prices: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """布林帶位置：(close - lower) / (upper - lower)，範圍 0~1。

    Measures where current price sits within Bollinger Bands.
    Reference: Bollinger (2001) "Bollinger on Bollinger Bands".
    """
    close = prices["close"]
    if len(close) < lookback:
        return pd.Series(dtype=float)
    ma = close.iloc[-lookback:].mean()
    std = close.iloc[-lookback:].std()
    if std == 0:
        return pd.Series({"bollinger_pos": 0.5})
    upper = ma + 2 * std
    lower = ma - 2 * std
    band_width = upper - lower
    if band_width == 0:
        return pd.Series({"bollinger_pos": 0.5})
    pos = (close.iloc[-1] - lower) / band_width
    return pd.Series({"bollinger_pos": float(np.clip(pos, 0, 1))})


def macd_signal(
    prices: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.Series:
    """MACD 柱狀圖（信號強度）。

    MACD histogram = MACD line - signal line.
    Reference: Appel (2005) "Technical Analysis: Power Tools for Active Investors".
    """
    close = prices["close"]
    if len(close) < slow + signal:
        return pd.Series(dtype=float)
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    # Normalize by close for comparability
    val = histogram.iloc[-1] / close.iloc[-1] if close.iloc[-1] != 0 else 0.0
    return pd.Series({"macd_hist": float(val)})


def obv_trend(prices: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """OBV 趨勢：On-Balance Volume 斜率（標準化）。

    Reference: Granville (1963) "Granville's New Key to Stock Market Profits".
    """
    close = prices["close"]
    volume = prices["volume"]
    if len(close) < lookback + 1:
        return pd.Series(dtype=float)
    # Compute OBV
    price_change = close.diff()
    obv = (np.sign(price_change) * volume).cumsum()
    # Slope via linear regression over lookback
    obv_window = obv.iloc[-lookback:]
    x = np.arange(lookback, dtype=float)
    x_mean = x.mean()
    obv_vals = obv_window.values.astype(float)
    obv_mean = obv_vals.mean()
    denom = ((x - x_mean) ** 2).sum()
    if denom == 0:
        return pd.Series({"obv_trend": 0.0})
    slope = ((x - x_mean) * (obv_vals - obv_mean)).sum() / denom
    # Normalize by mean absolute OBV
    mean_abs_obv = np.abs(obv_vals).mean()
    normalized = slope / mean_abs_obv if mean_abs_obv > 0 else 0.0
    return pd.Series({"obv_trend": float(normalized)})


def adx(prices: pd.DataFrame, period: int = 14) -> pd.Series:
    """平均方向指數 (ADX)：趨勢強度，0~100。

    Reference: Wilder (1978) "New Concepts in Technical Trading Systems".
    """
    high = prices["high"]
    low = prices["low"]
    close = prices["close"]
    if len(close) < period * 2 + 1:
        return pd.Series(dtype=float)
    # True Range
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    # +DM / -DM
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=close.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=close.index,
    )
    # Smoothed via EWM (Wilder smoothing ≈ EMA with alpha=1/period)
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_val = dx.ewm(alpha=1.0 / period, adjust=False).mean()
    val = adx_val.iloc[-1]
    if np.isnan(val):
        return pd.Series(dtype=float)
    return pd.Series({"adx": float(val)})


def cci(prices: pd.DataFrame, period: int = 20) -> pd.Series:
    """商品通道指數 (CCI)。

    Reference: Lambert (1980) "Commodity Channel Index".
    """
    high = prices["high"]
    low = prices["low"]
    close = prices["close"]
    if len(close) < period:
        return pd.Series(dtype=float)
    tp = (high + low + close) / 3
    tp_window = tp.iloc[-period:]
    ma = tp_window.mean()
    md = (tp_window - ma).abs().mean()
    if md == 0:
        return pd.Series({"cci": 0.0})
    val = (tp.iloc[-1] - ma) / (0.015 * md)
    return pd.Series({"cci": float(val)})


def williams_r(prices: pd.DataFrame, period: int = 14) -> pd.Series:
    """威廉指標 (Williams %R)：-100 到 0。

    Reference: Williams (1979) "How I Made One Million Dollars Last Year Trading Commodities".
    """
    high = prices["high"]
    low = prices["low"]
    close = prices["close"]
    if len(close) < period:
        return pd.Series(dtype=float)
    highest = high.iloc[-period:].max()
    lowest = low.iloc[-period:].min()
    denom = highest - lowest
    if denom == 0:
        return pd.Series({"williams_r": -50.0})
    val = -100 * (highest - close.iloc[-1]) / denom
    return pd.Series({"williams_r": float(val)})


def stochastic_k(prices: pd.DataFrame, period: int = 14) -> pd.Series:
    """隨機指標 %K：0~100。

    Reference: Lane (1984) "Lane's Stochastics".
    """
    high = prices["high"]
    low = prices["low"]
    close = prices["close"]
    if len(close) < period:
        return pd.Series(dtype=float)
    highest = high.iloc[-period:].max()
    lowest = low.iloc[-period:].min()
    denom = highest - lowest
    if denom == 0:
        return pd.Series({"stochastic_k": 50.0})
    val = 100 * (close.iloc[-1] - lowest) / denom
    return pd.Series({"stochastic_k": float(val)})


def atr_ratio(prices: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR / close：標準化波動性。

    Reference: Wilder (1978) "New Concepts in Technical Trading Systems".
    """
    high = prices["high"]
    low = prices["low"]
    close = prices["close"]
    if len(close) < period + 1:
        return pd.Series(dtype=float)
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_val = tr.iloc[-period:].mean()
    last_close = close.iloc[-1]
    if last_close == 0:
        return pd.Series({"atr_ratio": 0.0})
    return pd.Series({"atr_ratio": float(atr_val / last_close)})


def price_acceleration(prices: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """價格加速度：報酬的二次微分（動量變化率）。

    Second derivative of log-price, capturing momentum changes.
    Reference: Gu, Kelly, Xiu (2020) "Empirical Asset Pricing via Machine Learning".
    """
    close = prices["close"]
    if len(close) < lookback + 2:
        return pd.Series(dtype=float)
    returns = close.pct_change()
    # First derivative = returns, second derivative = change in returns
    accel = returns.diff()
    # Average recent acceleration
    val = accel.iloc[-lookback:].mean()
    if np.isnan(val):
        return pd.Series({"price_accel": 0.0})
    return pd.Series({"price_accel": float(val)})


def volume_momentum(prices: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """成交量動量：成交量變化率。

    Reference: Gervais, Kaniel, Mingelgrin (2001) "The High-Volume Return Premium".
    """
    volume = prices["volume"]
    if len(volume) < lookback + 1:
        return pd.Series(dtype=float)
    recent_avg = volume.iloc[-lookback:].mean()
    prior_avg = volume.iloc[-(2 * lookback) : -lookback].mean() if len(volume) >= 2 * lookback else volume.iloc[: -lookback].mean()
    if prior_avg == 0:
        return pd.Series({"vol_momentum": 0.0})
    val = recent_avg / prior_avg - 1
    return pd.Series({"vol_momentum": float(val)})


def high_low_range(prices: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """高低幅度：avg(high-low)/close（已實現範圍）。

    Reference: Parkinson (1980) "The Extreme Value Method for Estimating the Variance of the Rate of Return".
    """
    high = prices["high"]
    low = prices["low"]
    close = prices["close"]
    if len(close) < lookback:
        return pd.Series(dtype=float)
    hl_range = (high.iloc[-lookback:] - low.iloc[-lookback:]) / close.iloc[-lookback:].replace(0, np.nan)
    val = hl_range.mean()
    if np.isnan(val):
        return pd.Series({"hl_range": 0.0})
    return pd.Series({"hl_range": float(val)})


def close_to_high(prices: pd.DataFrame, lookback: int = 5) -> pd.Series:
    """收盤相對高點：close / rolling_max(high)（距峰值距離）。

    Reference: George, Hwang (2004) "The 52-Week High and Momentum Investing".
    """
    high = prices["high"]
    close = prices["close"]
    if len(close) < lookback:
        return pd.Series(dtype=float)
    rolling_high = high.iloc[-lookback:].max()
    if rolling_high == 0:
        return pd.Series({"close_to_high": 0.0})
    val = close.iloc[-1] / rolling_high
    return pd.Series({"close_to_high": float(val)})


def gap_factor(prices: pd.DataFrame) -> pd.Series:
    """隔夜跳空因子：open/prev_close - 1。

    Reference: Branch, Ma (2012) "Overnight Return, the Invisible Hand Behind Intraday Returns?".
    """
    open_ = prices["open"]
    close = prices["close"]
    if len(close) < 2:
        return pd.Series(dtype=float)
    prev_close = close.iloc[-2]
    if prev_close == 0:
        return pd.Series({"gap": 0.0})
    val = open_.iloc[-1] / prev_close - 1
    return pd.Series({"gap": float(val)})


def intraday_return(prices: pd.DataFrame) -> pd.Series:
    """日內報酬因子：close/open - 1。

    Reference: Heston, Sadka, Thorson (2010) "Intraday Patterns in the Cross-section of Stock Returns".
    """
    open_ = prices["open"]
    close = prices["close"]
    if len(close) < 1:
        return pd.Series(dtype=float)
    if open_.iloc[-1] == 0:
        return pd.Series({"intraday_ret": 0.0})
    val = close.iloc[-1] / open_.iloc[-1] - 1
    return pd.Series({"intraday_ret": float(val)})


def overnight_return(prices: pd.DataFrame) -> pd.Series:
    """隔夜報酬因子：open/prev_close - 1。

    Reference: Berkman, Koch, Tuttle, Zhang (2012) "Paying Attention: Overnight Returns and the Hidden Cost of Buying at the Open".
    """
    open_ = prices["open"]
    close = prices["close"]
    if len(close) < 2:
        return pd.Series(dtype=float)
    prev_close = close.iloc[-2]
    if prev_close == 0:
        return pd.Series({"overnight_ret": 0.0})
    val = open_.iloc[-1] / prev_close - 1
    return pd.Series({"overnight_ret": float(val)})


# ── Academic Factors (Gu-Kelly-Xiu 2020, Fama-French) ──────────────


def momentum_1m(prices: pd.DataFrame) -> pd.Series:
    """1 個月動量（短期）。

    Reference: Jegadeesh, Titman (1993) "Returns to Buying Winners and Selling Losers".
    """
    close = prices["close"]
    if len(close) < 22:
        return pd.Series(dtype=float)
    ret = close.iloc[-1] / close.iloc[-21] - 1
    return pd.Series({"momentum_1m": float(ret)})


def momentum_6m(prices: pd.DataFrame) -> pd.Series:
    """6 個月動量。

    Reference: Jegadeesh, Titman (1993) "Returns to Buying Winners and Selling Losers".
    """
    close = prices["close"]
    if len(close) < 127:
        return pd.Series(dtype=float)
    ret = close.iloc[-1] / close.iloc[-126] - 1
    return pd.Series({"momentum_6m": float(ret)})


def momentum_12m(prices: pd.DataFrame) -> pd.Series:
    """12 個月動量（經典 12-1）。

    Reference: Jegadeesh, Titman (1993) "Returns to Buying Winners and Selling Losers".
    """
    close = prices["close"]
    if len(close) < 253:
        return pd.Series(dtype=float)
    # Skip most recent month (21 trading days)
    ret = close.iloc[-22] / close.iloc[-252] - 1
    return pd.Series({"momentum_12m": float(ret)})


def long_term_reversal(prices: pd.DataFrame, lookback: int = 756) -> pd.Series:
    """長期反轉因子：3 年反轉。

    Reference: De Bondt, Thaler (1985) "Does the Stock Market Overreact?".
    """
    close = prices["close"]
    if len(close) < lookback + 1:
        return pd.Series(dtype=float)
    ret = close.iloc[-1] / close.iloc[-lookback] - 1
    return pd.Series({"lt_reversal": float(-ret)})


def beta_market(
    prices: pd.DataFrame,
    market_returns: pd.Series | None = None,
    lookback: int = 252,
) -> pd.Series:
    """市場 Beta（CAPM）。

    Reference: Sharpe (1964) "Capital Asset Prices: A Theory of Market Equilibrium Under Conditions of Risk".
    """
    close = prices["close"]
    if len(close) < lookback + 1:
        return pd.Series(dtype=float)
    stock_ret = close.pct_change().dropna().iloc[-lookback:]
    if market_returns is None or market_returns.empty:
        return pd.Series({"beta": 1.0})
    common = stock_ret.index.intersection(market_returns.index)
    if len(common) < 60:
        return pd.Series(dtype=float)
    y = np.array(stock_ret.loc[common].values, dtype=np.float64)
    x = np.array(market_returns.loc[common].values, dtype=np.float64)
    var_x = float(np.var(x, ddof=1))
    if var_x == 0:
        return pd.Series({"beta": 1.0})
    cov_matrix = np.cov(y, x, ddof=1)
    beta_val = float(cov_matrix[0, 1]) / var_x
    return pd.Series({"beta": beta_val})


def idiosyncratic_skewness(
    prices: pd.DataFrame,
    market_returns: pd.Series | None = None,
    lookback: int = 60,
) -> pd.Series:
    """特質偏度：殘差的偏度。

    Reference: Harvey, Siddique (2000) "Conditional Skewness in Asset Pricing Tests".
    """
    close = prices["close"]
    if len(close) < lookback + 1:
        return pd.Series(dtype=float)
    stock_ret = close.pct_change().dropna().iloc[-lookback:]
    if market_returns is None or market_returns.empty:
        raw_skew: float = float(stock_ret.skew())  # type: ignore[arg-type]
        skew_val = raw_skew if not np.isnan(raw_skew) else 0.0
        return pd.Series({"idio_skew": skew_val})
    common = stock_ret.index.intersection(market_returns.index)
    if len(common) < 20:
        return pd.Series(dtype=float)
    y = np.array(stock_ret.loc[common].values, dtype=np.float64)
    x = np.array(market_returns.loc[common].values, dtype=np.float64)
    x_with_const = np.column_stack([np.ones(len(x)), x])
    lstsq_result = np.linalg.lstsq(x_with_const, y, rcond=None)
    residuals = y - x_with_const @ lstsq_result[0]
    n = len(residuals)
    if n < 3:
        return pd.Series({"idio_skew": 0.0})
    mean_r = residuals.mean()
    std_r = residuals.std(ddof=1)
    if std_r == 0:
        return pd.Series({"idio_skew": 0.0})
    skew_val = (n / ((n - 1) * (n - 2))) * np.sum(((residuals - mean_r) / std_r) ** 3)
    return pd.Series({"idio_skew": float(skew_val)})


def max_daily_return(prices: pd.DataFrame, lookback: int = 21) -> pd.Series:
    """最大單日報酬（彩票效應）。

    Reference: Bali, Cakici, Whitelaw (2011) "Maxing Out: Stocks as Lotteries".
    """
    close = prices["close"]
    if len(close) < lookback + 1:
        return pd.Series(dtype=float)
    ret = close.pct_change().dropna().iloc[-lookback:]
    return pd.Series({"max_daily_ret": float(ret.max())})


def turnover_volatility(prices: pd.DataFrame, lookback: int = 60) -> pd.Series:
    """成交量波動率：turnover 的波動率。

    Reference: Chordia, Subrahmanyam, Anshuman (2001) "Trading Activity and Expected Stock Returns".
    """
    volume = prices["volume"]
    if len(volume) < lookback:
        return pd.Series(dtype=float)
    vol_window = volume.iloc[-lookback:]
    mean_vol = vol_window.mean()
    if mean_vol == 0:
        return pd.Series({"turnover_vol": 0.0})
    # Coefficient of variation of volume
    val = vol_window.std() / mean_vol
    return pd.Series({"turnover_vol": float(val) if not np.isnan(val) else 0.0})


def price_delay(prices: pd.DataFrame, lookback: int = 5) -> pd.Series:
    """價格延遲：報酬自相關（價格延遲代理）。

    Higher autocorrelation indicates slower price adjustment.
    Reference: Hou, Moskowitz (2005) "Market Frictions, Price Delay, and the Cross-Section of Expected Returns".
    """
    close = prices["close"]
    if len(close) < 60:
        return pd.Series(dtype=float)
    returns = close.pct_change().dropna().iloc[-60:]
    # Sum of squared autocorrelations at lags 1..lookback
    total_ac = 0.0
    for lag in range(1, lookback + 1):
        ac = returns.autocorr(lag)
        if not np.isnan(ac):
            total_ac += ac ** 2
    return pd.Series({"price_delay": float(total_ac)})


def zero_trading_days(prices: pd.DataFrame, lookback: int = 60) -> pd.Series:
    """零交易日比例（非流動性代理）。

    Reference: Lesmond, Ogden, Trzcinka (1999) "A New Estimate of Transaction Costs".
    """
    volume = prices["volume"]
    if len(volume) < lookback:
        return pd.Series(dtype=float)
    vol_window = volume.iloc[-lookback:]
    zero_frac = (vol_window == 0).sum() / len(vol_window)
    return pd.Series({"zero_days": float(zero_frac)})
