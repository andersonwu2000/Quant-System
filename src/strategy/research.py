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
}


def compute_market_returns(data: dict[str, pd.DataFrame]) -> pd.Series:
    """計算等權市場報酬代理。"""
    all_close = pd.DataFrame({s: data[s]["close"] for s in sorted(data.keys())})
    return all_close.pct_change().mean(axis=1).dropna()


# ── 基本面因子註冊表 ────────────────────────────────────────────────


@dataclass
class FundamentalFactorDef:
    """基本面因子定義。"""

    name: str
    fn: Callable[..., float]
    metric_key: str  # get_financials() 回傳 dict 中的 key


FUNDAMENTAL_REGISTRY: dict[str, FundamentalFactorDef] = {
    "value_pe": FundamentalFactorDef(name="value_pe", fn=flib.value_pe, metric_key="pe_ratio"),
    "value_pb": FundamentalFactorDef(name="value_pb", fn=flib.value_pb, metric_key="pb_ratio"),
    "quality_roe": FundamentalFactorDef(name="quality_roe", fn=flib.quality_roe, metric_key="roe"),
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
            metric_val = financials.get(fdef.metric_key)
            if metric_val is not None:
                row[sym] = fdef.fn(metric_val)
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


def compute_factor_values(
    data: dict[str, pd.DataFrame],
    factor_name: str,
    dates: list[pd.Timestamp] | None = None,
    **kwargs: object,
) -> pd.DataFrame:
    """
    對多檔標的在多個日期計算因子值。

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
    fn_kwargs = {**reg["default_kwargs"], **kwargs}

    symbols = sorted(data.keys())

    # ivol 需要市場報酬代理（等權平均）
    if factor_name == "ivol" and "market_returns" not in fn_kwargs:
        fn_kwargs["market_returns"] = compute_market_returns(data)

    if dates is None:
        # 取所有標的的共有日期
        all_dates: set[pd.Timestamp] | None = None
        for sym in symbols:
            sym_dates = set(data[sym].index)
            all_dates = sym_dates if all_dates is None else all_dates & sym_dates
        dates = sorted(all_dates or set())

    # 只保留有足夠前置數據的日期
    result_rows: list[dict[str, float | pd.Timestamp]] = []
    for dt in dates:
        row: dict[str, float | pd.Timestamp] = {"date": dt}
        for sym in symbols:
            df = data[sym]
            mask = df.index <= dt
            bars = df.loc[mask].iloc[-max(min_bars * 2, 300) :]
            if len(bars) < min_bars:
                continue
            val = fn(bars, **fn_kwargs)
            if not val.empty:
                row[sym] = float(val[key])
        if len(row) > 1:  # 至少有一個 symbol
            result_rows.append(row)

    if not result_rows:
        return pd.DataFrame()

    result_df = pd.DataFrame(result_rows).set_index("date")
    return result_df


def compute_forward_returns(
    data: dict[str, pd.DataFrame],
    horizon: int = 5,
    dates: list[pd.Timestamp] | None = None,
) -> pd.DataFrame:
    """
    計算未來 N 天報酬。

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

    result_rows: list[dict[str, float | pd.Timestamp]] = []
    for dt in dates:
        row: dict[str, float | pd.Timestamp] = {"date": dt}
        for sym in symbols:
            df = data[sym]
            future = df.loc[df.index > dt]
            current = df.loc[df.index <= dt]
            if current.empty or len(future) < horizon:
                continue
            price_now = float(current["close"].iloc[-1])
            price_future = float(future["close"].iloc[horizon - 1])
            if price_now > 0:
                row[sym] = price_future / price_now - 1
        if len(row) > 1:
            result_rows.append(row)

    if not result_rows:
        return pd.DataFrame()
    return pd.DataFrame(result_rows).set_index("date")


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


def combine_factors(
    data: dict[str, pd.DataFrame],
    factor_names: list[str],
    weights: dict[str, float] | None = None,
    method: str = "equal",
    horizon: int = 5,
    dates: list[pd.Timestamp] | None = None,
) -> CompositeResult:
    """
    因子合成：將多個因子加權組合為複合因子。

    Args:
        data: {symbol: OHLCV DataFrame}
        factor_names: 要合成的因子名稱列表
        weights: 自定義權重（None = 使用 method 決定）
        method: "equal"（等權）或 "ic"（IC 加權）
        horizon: 用於 IC 加權的報酬週期
    """
    individual_fv: dict[str, pd.DataFrame] = {}
    individual_ics: dict[str, float] = {}

    for fname in factor_names:
        fv = compute_factor_values(data, fname, dates=dates)
        if fv.empty:
            continue
        # 標準化（橫截面 Z-score）
        fv_ranked = fv.rank(axis=1, pct=True)
        individual_fv[fname] = fv_ranked

        # 計算 IC
        fwd = compute_forward_returns(data, horizon=horizon, dates=list(fv.index))
        ic_result = compute_ic(fv, fwd)
        individual_ics[fname] = ic_result.ic_mean

    if not individual_fv:
        return CompositeResult(
            factor_names=factor_names,
            weights={},
            composite_ic=0.0,
            individual_ics=individual_ics,
        )

    # 決定權重
    if weights is not None:
        final_weights = weights
    elif method == "ic":
        # IC 加權：按 IC 絕對值分配
        total_ic = sum(abs(v) for v in individual_ics.values())
        if total_ic > 0:
            final_weights = {k: abs(v) / total_ic for k, v in individual_ics.items()}
        else:
            final_weights = {k: 1.0 / len(individual_ics) for k in individual_ics}
    else:
        # 等權
        final_weights = {k: 1.0 / len(individual_fv) for k in individual_fv}

    # 合成複合因子
    common_dates: set[Any] | None = None
    common_symbols: set[str] | None = None
    for fv in individual_fv.values():
        if common_dates is None or common_symbols is None:
            common_dates = set(fv.index)
            common_symbols = set(fv.columns)
        else:
            common_dates &= set(fv.index)
            common_symbols &= set(fv.columns)

    if not common_dates or not common_symbols:
        return CompositeResult(
            factor_names=factor_names,
            weights=final_weights,
            composite_ic=0.0,
            individual_ics=individual_ics,
        )

    sorted_dates = sorted(common_dates)
    sorted_symbols = sorted(common_symbols)

    composite_df = pd.DataFrame(0.0, index=sorted_dates, columns=sorted_symbols)
    for fname, fv in individual_fv.items():
        w = final_weights.get(fname, 0.0)
        composite_df += fv.reindex(index=sorted_dates, columns=sorted_symbols).fillna(0) * w

    # 評估複合因子的 IC
    fwd = compute_forward_returns(data, horizon=horizon, dates=sorted_dates)
    composite_ic_result = compute_ic(composite_df, fwd)

    return CompositeResult(
        factor_names=factor_names,
        weights=final_weights,
        composite_ic=composite_ic_result.ic_mean,
        individual_ics=individual_ics,
    )


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
