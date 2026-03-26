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


# ── 營收因子 ───────────────────────────────────────────────────────


def revenue_yoy_factor(yoy_growth: float) -> float:
    """營收 YoY 成長率因子：高成長 = 高分。

    yoy_growth 為百分比（如 15.0 表示 15%）。
    Clip 到 [-100, 500] 防止極端值。
    """
    return max(-100.0, min(yoy_growth, 500.0))


def revenue_momentum_factor(consecutive_growth_months: float) -> float:
    """營收動能因子：連續 N 月 YoY > 0 的月數。

    Range: 0~12。連續成長越多月 = 動能越強。
    """
    return max(0.0, min(consecutive_growth_months, 12.0))


def revenue_new_high_factor(is_new_high: float) -> float:
    """營收創新高因子：3M avg 營收達 12M 新高 = 1.0。

    FinLab 研究顯示營收創新高是台股最強單因子（CAGR 14.7%）。
    is_new_high: 1.0 if 3-month avg revenue >= 12-month max, else 0.0
    """
    return 1.0 if is_new_high > 0.5 else 0.0


def revenue_acceleration_factor(acceleration: float) -> float:
    """營收加速度因子：3M avg / 12M avg 比率。

    比率 > 1 表示近期營收高於長期平均，動能加速中。
    FinLab 對標：cond_revgro = (revenue.average(3) / revenue.average(12)).rank > 0.7
    Clip to [0, 5]。
    """
    return max(0.0, min(acceleration, 5.0))


def trust_cumulative_factor(cumulative_net: float) -> float:
    """投信累計買超因子：10 日累計淨買超股數。

    FinLab 研究：投信買超 + 營收成長 = CAGR 31.7%。
    投信專注台股中小型股，比外資更有效（外資逆向策略 CAGR -11.2%）。
    """
    return max(-1e9, min(cumulative_net, 1e9))


# ── 殖利率因子 ─────────────────────────────────────────────────────


def dividend_yield_factor(dividend_yield: float) -> float:
    """股利殖利率因子：高殖利率 = 高分。

    dividend_yield 為百分比（如 5.0 表示 5%）。
    Clip 到 [0, 20]。
    """
    if dividend_yield <= 0:
        return 0.0
    return min(dividend_yield, 20.0)


# ── 籌碼面因子 ─────────────────────────────────────────────────────


def foreign_net_factor(net_buy_normalized: float) -> float:
    """外資淨買超因子：正值 = 外資買進 = 正面信號。

    net_buy_normalized 為淨買金額除以成交金額的比率。
    """
    return max(-1.0, min(net_buy_normalized, 1.0))


def trust_net_factor(net_buy_normalized: float) -> float:
    """投信淨買超因子：投信連續買入 = 基金經理人 alpha 信號。"""
    return max(-1.0, min(net_buy_normalized, 1.0))


def director_change_factor(ratio_change: float) -> float:
    """董監持股變化因子：減持 = 負面信號（反向）。

    ratio_change 為持股比例的變化（百分點）。
    負值（減持）→ 負分。
    """
    return max(-10.0, min(ratio_change, 10.0))


def margin_change_factor(margin_change_ratio: float) -> float:
    """融資餘額變化因子（反向）：融資增加 = 散戶追漲 = 負面信號。

    反轉方向：margin_change 越高 → 分數越低。
    """
    return -max(-1.0, min(margin_change_ratio, 1.0))


def daytrading_ratio_factor(dt_ratio: float) -> float:
    """當沖比率因子（反向）：高當沖 = 投機 = 負面信號。

    dt_ratio 為當沖成交量 / 總成交量。
    反轉方向。
    """
    return -max(0.0, min(dt_ratio, 1.0))
