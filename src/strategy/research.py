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


def compute_factor_values(
    data: dict[str, pd.DataFrame],
    factor_name: str,
    dates: list[pd.Timestamp] | None = None,
    **kwargs: object,
) -> pd.DataFrame:
    """
    對多檔標的在多個日期計算因子值。

    使用逐標的向量化策略：對每個標的只遍歷一次其價格序列，
    而非原本的逐日×逐標的雙層迴圈。

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
        all_dates: set[pd.Timestamp] | None = None
        for sym in symbols:
            sym_dates = set(data[sym].index)
            all_dates = sym_dates if all_dates is None else all_dates & sym_dates
        dates = sorted(all_dates or set())

    if not dates:
        return pd.DataFrame()

    window = max(min_bars * 2, 300)

    # 逐標的計算（外層迴圈是 symbol，內層用 searchsorted 快速定位）
    # 這樣每個標的只需一次 index 對齊，避免 N_dates × N_symbols 的雙層迴圈
    col_results: dict[str, pd.Series] = {}

    for sym in symbols:
        df = data[sym]
        idx = df.index
        if len(idx) < min_bars:
            continue

        # 找出此標的在 dates 中有數據的日期
        valid_dates = [dt for dt in dates if dt in idx or (len(idx) > 0 and idx[0] <= dt)]

        values: dict[pd.Timestamp, float] = {}
        # 使用 searchsorted 批量定位，避免逐日 boolean mask
        for dt in valid_dates:
            pos = idx.searchsorted(dt, side="right")
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
    # 只保留請求的日期，且至少有一個標的有值
    result_df = result_df.reindex(dates).dropna(how="all")
    return result_df


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
