"""
條件篩選策略框架 — 替代 cross-sectional ranking 的通用篩選邏輯。

.. deprecated::
    This module is a **research / prototyping tool**, not intended for
    production scheduling.  For production use, prefer the dedicated
    strategy files:

    - ``strategies/revenue_momentum.py`` (RevenueMomentumStrategy)
    - ``strategies/revenue_momentum_hedged.py`` (RevenueMomentumHedgedStrategy)
    - ``strategies/trust_follow.py`` (TrustFollowStrategy)

    Those strategies are registered in the strategy registry and wired
    into the scheduler.  This ``FilterStrategy`` class remains available
    for ad-hoc research and rapid prototyping of new filter combinations.

設計依據：FinLab 研究證實台股 alpha 來自「營收動能 + 投信籌碼」的條件組合，
而非 cross-sectional factor ranking。此框架支援任意 boolean 條件組合 + 排序取前 N。

用法：
    config = FilterStrategyConfig(
        filters=[
            FilterCondition("revenue_yoy", "gt", 15.0),
            FilterCondition("price_vs_ma60", "gt", 0.0),
        ],
        rank_by="revenue_yoy",
        top_n=15,
    )
    strategy = FilterStrategy(config)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from src.strategy.base import Context, Strategy
from src.strategy.optimizer import equal_weight, OptConstraints

logger = logging.getLogger(__name__)


@dataclass
class FilterCondition:
    """單一篩選條件。"""
    factor_name: str          # 因子名稱（對應 factor_calculators 的 key）
    operator: str             # "gt" | "lt" | "gte" | "lte" | "eq" | "between"
    threshold: float | tuple[float, float] = 0.0  # 閾值（between 時為 tuple）

    def evaluate(self, value: float) -> bool:
        """Evaluate if value passes this condition."""
        if self.operator == "gt":
            return value > self.threshold
        elif self.operator == "lt":
            return value < self.threshold
        elif self.operator == "gte":
            return value >= self.threshold
        elif self.operator == "lte":
            return value <= self.threshold
        elif self.operator == "eq":
            return abs(value - self.threshold) < 1e-9
        elif self.operator == "between":
            lo, hi = self.threshold
            return lo <= value <= hi
        else:
            raise ValueError(f"Unknown operator: {self.operator}")


@dataclass
class FilterStrategyConfig:
    """條件篩選策略配置。"""
    filters: list[FilterCondition]       # 篩選條件列表（AND 邏輯）
    rank_by: str                         # 排序依據的因子
    rank_ascending: bool = False         # True = 越小越好, False = 越大越好
    top_n: int = 15                      # 取前 N 檔
    max_weight: float = 0.10             # 單一持股上限
    min_volume_lots: int = 300           # 20 日均量最低門檻（張）
    lookback_bars: int = 252             # 需要的歷史 K 線數
    name: str = "filter_strategy"        # 策略名稱


# ── Built-in factor calculators ───────────────────────────────

def _calc_price_vs_ma(bars: pd.DataFrame, period: int = 60) -> float | None:
    """Stock price relative to moving average: close / MA(period) - 1."""
    close = bars["close"]
    if len(close) < period:
        return None
    ma = float(close.iloc[-period:].mean())
    if ma <= 0:
        return None
    return float(close.iloc[-1]) / ma - 1.0


def _calc_momentum(bars: pd.DataFrame, period: int = 60) -> float | None:
    """Price momentum over period days."""
    close = bars["close"]
    if len(close) < period + 1:
        return None
    return float(close.iloc[-1]) / float(close.iloc[-period - 1]) - 1.0


def _calc_volume_avg(bars: pd.DataFrame, period: int = 20) -> float | None:
    """Average daily volume in lots (shares / 1000)."""
    vol = bars["volume"]
    if len(vol) < period:
        return None
    return float(vol.iloc[-period:].mean()) / 1000.0


def _calc_rsi(bars: pd.DataFrame, period: int = 14) -> float | None:
    """RSI indicator."""
    close = bars["close"]
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] > 0 else 100.0
    return float(100.0 - 100.0 / (1.0 + rs))


# Revenue + institutional factors need fundamentals provider
def _calc_revenue_yoy(ctx: Context, symbol: str) -> float | None:
    """Latest revenue YoY growth (%)."""
    if ctx._fundamentals is None:
        return None
    end = pd.Timestamp(ctx.now()).strftime("%Y-%m-%d")
    start = (pd.Timestamp(ctx.now()) - pd.DateOffset(years=2)).strftime("%Y-%m-%d")
    rev_df = ctx._fundamentals.get_revenue(symbol, start, end)
    if rev_df.empty:
        return None
    yoy_vals = rev_df["yoy_growth"].values
    return float(yoy_vals[-1]) if len(yoy_vals) > 0 else None


def _calc_revenue_acceleration(ctx: Context, symbol: str) -> float | None:
    """Revenue 3M avg / 12M avg ratio."""
    if ctx._fundamentals is None:
        return None
    end = pd.Timestamp(ctx.now()).strftime("%Y-%m-%d")
    start = (pd.Timestamp(ctx.now()) - pd.DateOffset(years=2)).strftime("%Y-%m-%d")
    rev_df = ctx._fundamentals.get_revenue(symbol, start, end)
    if rev_df.empty or len(rev_df) < 12:
        return None
    revenues = rev_df["revenue"].values
    avg_3m = float(revenues[-3:].mean())
    avg_12m = float(revenues[-12:].mean())
    if avg_12m <= 0:
        return None
    return avg_3m / avg_12m


def _calc_revenue_new_high(ctx: Context, symbol: str) -> float | None:
    """1.0 if 3M avg revenue hits 12M high, else 0.0."""
    if ctx._fundamentals is None:
        return None
    end = pd.Timestamp(ctx.now()).strftime("%Y-%m-%d")
    start = (pd.Timestamp(ctx.now()) - pd.DateOffset(years=2)).strftime("%Y-%m-%d")
    rev_df = ctx._fundamentals.get_revenue(symbol, start, end)
    if rev_df.empty or len(rev_df) < 12:
        return None
    revenues = rev_df["revenue"].values
    avg_3m = float(revenues[-3:].mean())
    # Rolling 3M avg max over last 12 months
    rev_series = pd.Series(revenues[-12:])
    rolling_max = float(rev_series.rolling(3).mean().max())
    if rolling_max <= 0:
        return None
    return 1.0 if avg_3m >= rolling_max * 0.99 else 0.0


def _calc_trust_cumulative(ctx: Context, symbol: str, days: int = 10) -> float | None:
    """Trust (investment trust) cumulative net buy over N days."""
    if ctx._fundamentals is None:
        return None
    end = pd.Timestamp(ctx.now()).strftime("%Y-%m-%d")
    start = (pd.Timestamp(ctx.now()) - pd.DateOffset(days=days + 30)).strftime("%Y-%m-%d")
    inst_df = ctx._fundamentals.get_institutional(symbol, start, end)
    if inst_df.empty:
        return None
    recent = inst_df.tail(days)
    return float(recent["trust_net"].sum())


# Registry of factor calculators
# Two types:
# 1. Bar-based: fn(bars) -> float | None
# 2. Context-based: fn(ctx, symbol) -> float | None  (needs fundamentals)

PRICE_FACTORS: dict[str, Callable] = {
    "price_vs_ma60": lambda bars: _calc_price_vs_ma(bars, 60),
    "price_vs_ma20": lambda bars: _calc_price_vs_ma(bars, 20),
    "price_vs_ma120": lambda bars: _calc_price_vs_ma(bars, 120),
    "momentum_60d": lambda bars: _calc_momentum(bars, 60),
    "momentum_20d": lambda bars: _calc_momentum(bars, 20),
    "momentum_120d": lambda bars: _calc_momentum(bars, 120),
    "volume_20d_avg": lambda bars: _calc_volume_avg(bars, 20),
    "rsi": _calc_rsi,
}

FUNDAMENTAL_FACTORS: dict[str, Callable] = {
    "revenue_yoy": _calc_revenue_yoy,
    "revenue_acceleration": _calc_revenue_acceleration,
    "revenue_new_high": _calc_revenue_new_high,
    "trust_10d_cumulative": lambda ctx, sym: _calc_trust_cumulative(ctx, sym, 10),
    "trust_20d_cumulative": lambda ctx, sym: _calc_trust_cumulative(ctx, sym, 20),
}


class FilterStrategy(Strategy):
    """
    條件篩選策略 — 通用版。

    Flow:
    1. 對 universe 每支股票計算所有需要的因子值
    2. 流動性篩選（20 日均量 > min_volume_lots 張）
    3. 逐一檢查 FilterCondition（AND 邏輯），通過所有條件的入選
    4. 按 rank_by 排序，取前 top_n 檔
    5. 等權配置
    """

    def __init__(self, config: FilterStrategyConfig):
        self._config = config

    def name(self) -> str:
        return self._config.name

    def on_bar(self, ctx: Context) -> dict[str, float]:
        cfg = self._config
        candidates: list[tuple[str, float]] = []  # (symbol, rank_value)

        # Collect all needed factor names
        needed_factors = {f.factor_name for f in cfg.filters}
        needed_factors.add(cfg.rank_by)

        for symbol in ctx.universe():
            try:
                bars = ctx.bars(symbol, lookback=cfg.lookback_bars)
                if len(bars) < 60:
                    continue

                # Calculate all factor values for this symbol
                factor_values: dict[str, float] = {}

                for fn_name in needed_factors:
                    val = None
                    if fn_name in PRICE_FACTORS:
                        val = PRICE_FACTORS[fn_name](bars)
                    elif fn_name in FUNDAMENTAL_FACTORS:
                        val = FUNDAMENTAL_FACTORS[fn_name](ctx, symbol)

                    if val is not None:
                        factor_values[fn_name] = val

                # Liquidity check
                vol_avg = factor_values.get("volume_20d_avg")
                if vol_avg is None:
                    vol_avg_calc = _calc_volume_avg(bars, 20)
                    if vol_avg_calc is None or vol_avg_calc < cfg.min_volume_lots:
                        continue
                elif vol_avg < cfg.min_volume_lots:
                    continue

                # Check all filter conditions (AND logic)
                passed = True
                for filt in cfg.filters:
                    if filt.factor_name not in factor_values:
                        passed = False
                        break
                    if not filt.evaluate(factor_values[filt.factor_name]):
                        passed = False
                        break

                if not passed:
                    continue

                # Get rank value
                rank_val = factor_values.get(cfg.rank_by)
                if rank_val is None:
                    continue

                candidates.append((symbol, rank_val))

            except Exception as e:
                logger.debug("FilterStrategy skip %s: %s", symbol, e)
                continue

        if not candidates:
            return {}

        # Sort and select top N
        candidates.sort(key=lambda x: x[1], reverse=not cfg.rank_ascending)
        selected = candidates[:cfg.top_n]

        signals = {sym: rank for sym, rank in selected}
        return equal_weight(
            signals,
            OptConstraints(
                max_weight=cfg.max_weight,
                max_total_weight=0.95,
            ),
        )


# ── Pre-configured strategy instances ─────────────────────────

def revenue_momentum_filter() -> FilterStrategy:
    """營收動能 + 價格確認策略（FinLab CAGR 33.5% 對標）。"""
    return FilterStrategy(FilterStrategyConfig(
        filters=[
            FilterCondition("revenue_acceleration", "gt", 1.0),
            FilterCondition("revenue_yoy", "gt", 15.0),
            FilterCondition("price_vs_ma60", "gt", 0.0),
            FilterCondition("momentum_60d", "gt", 0.0),
        ],
        rank_by="revenue_yoy",
        top_n=15,
        max_weight=0.10,
        name="filter_revenue_momentum",
    ))


def trust_follow_filter() -> FilterStrategy:
    """投信跟單 + 營收成長策略（FinLab CAGR 31.7% 對標）。"""
    return FilterStrategy(FilterStrategyConfig(
        filters=[
            FilterCondition("trust_10d_cumulative", "gt", 15000),
            FilterCondition("revenue_new_high", "eq", 1.0),
            FilterCondition("revenue_yoy", "gt", 20.0),
        ],
        rank_by="trust_10d_cumulative",
        top_n=10,
        max_weight=0.15,
        name="filter_trust_follow",
    ))
