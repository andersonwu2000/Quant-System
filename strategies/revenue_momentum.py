"""
營收動能策略 — 基於 FinLab 研究 + 真實性修正。

修正後核心：revenue_acceleration（3M/12M 比率）取代 revenue_yoy 作為排序因子。
原因：acceleration ICIR 0.476 > yoy 0.188（含 40 天營收公布延遲後）。

篩選邏輯：
1. 營收 3M avg > 12M avg（acceleration > 1）
2. 營收 YoY > 15%
3. 股價 > MA60 + 近 60 日漲幅 > 0（趨勢確認）
4. 20 日均量 > 300 張（流動性）

排序：revenue_acceleration（3M/12M 比率）取前 15 檔。
再平衡：每月 11 日後（營收公布完成）。

營收延遲：+40 天（台灣月營收於次月 10 日前公布）。
"""

from __future__ import annotations

import logging
from typing import Any
from pathlib import Path

import numpy as np
import pandas as pd

from src.strategy.base import Context, Strategy
from src.strategy.optimizer import equal_weight, signal_weight, risk_parity, OptConstraints

logger = logging.getLogger(__name__)

# ── 營收預載快取 ───────────────────────────────────────────────────

_revenue_cache: dict[str, pd.DataFrame] | None = None


def _preload_revenue(fund_dir: str = "data/fundamental") -> dict[str, pd.DataFrame]:
    """一次性預載所有營收 parquet 到記憶體。

    回傳 dict: symbol → DataFrame[date, revenue, yoy_growth]
    """
    global _revenue_cache
    if _revenue_cache is not None:
        return _revenue_cache

    cache: dict[str, pd.DataFrame] = {}
    fund_path = Path(fund_dir)
    if not fund_path.exists():
        _revenue_cache = cache
        return cache

    for p in sorted(fund_path.glob("*_revenue.parquet")):
        sym = p.stem.replace("_revenue", "")
        try:
            df = pd.read_parquet(p)
            if df.empty or "revenue" not in df.columns:
                continue
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")

            # 向量化 YoY：shift(12) 月份對齊（月頻數據直接 shift 12 行 = 去年同月）
            if "yoy_growth" not in df.columns or df["yoy_growth"].isna().all():
                prev_year_rev = df["revenue"].shift(12)
                prev_year_rev = prev_year_rev.where(prev_year_rev > 0, np.nan)
                df["yoy_growth"] = ((df["revenue"] / prev_year_rev) - 1) * 100

            cache[sym] = df
        except Exception:
            continue

    logger.info("Preloaded revenue data: %d symbols", len(cache))
    _revenue_cache = cache
    return cache


def _get_revenue_at(
    cache: dict[str, pd.DataFrame],
    symbol: str,
    as_of: pd.Timestamp,
) -> tuple[float, float, float] | None:
    """從預載快取取得截至 as_of 的營收指標。

    Returns:
        (rev_3m_avg, rev_12m_avg, latest_yoy) 或 None（數據不足）
    """
    df = cache.get(symbol)
    if df is None:
        return None

    # 只用已公開的數據（避免 look-ahead）
    # 台灣月營收於次月 10 日前公布，例如 1 月營收最晚 2/10 公布
    # 保守使用 40 天 lag：date 欄位為營收月份（如 2024-01-01），
    # 實際公布約在 2024-02-10，距 2024-01-01 約 40 天
    # Strip timezone to avoid tz-naive vs tz-aware comparison errors
    as_of_naive = as_of.tz_localize(None) if as_of.tzinfo is not None else as_of
    usable_cutoff = as_of_naive - pd.DateOffset(days=40)
    mask = df["date"] <= usable_cutoff
    available = df[mask]
    if len(available) < 12:
        return None

    revenues = available["revenue"].values
    rev_3m = float(np.mean(np.asarray(revenues[-3:]))) if len(revenues) >= 3 else 0
    rev_12m = float(np.mean(np.asarray(revenues[-12:]))) if len(revenues) >= 12 else 0

    yoy_vals = available["yoy_growth"].dropna().values
    latest_yoy = float(yoy_vals[-1]) if len(yoy_vals) > 0 else 0

    return (rev_3m, rev_12m, latest_yoy)


class RevenueMomentumStrategy(Strategy):
    """
    營收動能 + 價格確認策略。

    篩選條件：
    1. 營收 3M avg > 12M avg（營收動能）
    2. 營收 YoY > threshold（成長確認）
    3. 股價 > 60 日均線（趨勢確認）
    4. 近 60 日漲幅 > 0（動能確認）
    5. 20 日均量 > min_volume 張（流動性）

    排序：revenue_acceleration（3M/12M）取前 max_holdings 檔。
    """

    def __init__(
        self,
        max_holdings: int = 15,
        min_yoy_growth: float = 10.0,  # 降低門檻（修正後 15% 太嚴格）
        min_volume_lots: int = 300,
        max_weight: float = 0.10,
        weight_method: str = "signal",  # "equal" | "signal" | "risk_parity"
        enable_regime_hedge: bool = True,  # 空頭偵測 + 倉位調整
        bear_position_scale: float = 0.30,  # 空頭時持倉比例
        sideways_position_scale: float = 0.60,  # 盤整時持倉比例
        market_proxy: str = "0050.TW",  # 市場代理標的
        event_driven: bool = False,  # 事件驅動再平衡（營收公布 T+1）
    ):
        self.max_holdings = max_holdings
        self.min_yoy_growth = min_yoy_growth
        self.min_volume_lots = min_volume_lots
        self.max_weight = max_weight
        self.weight_method = weight_method
        self.enable_regime_hedge = enable_regime_hedge
        self.bear_position_scale = bear_position_scale
        self.sideways_position_scale = sideways_position_scale
        self.market_proxy = market_proxy
        self.event_driven = event_driven
        self._last_month: str = ""
        self._cached_weights: dict[str, float] = {}
        self._rev_cache: dict[str, pd.DataFrame] | None = None
        self._event_rebalancer: Any = None

    def name(self) -> str:
        return "revenue_momentum"

    def _market_regime(self, ctx: Context) -> str:
        """偵測市場環境：bull / bear / sideways。

        使用 0050.TW（台灣 50 ETF）作為大盤 proxy。
        - bear: 價格 < MA200 且 MA50 < MA200（死亡交叉）
        - bull: 價格 > MA200 且 MA50 > MA200（黃金交叉）
        - sideways: 其他
        """
        try:
            market_bars = ctx.bars(self.market_proxy, lookback=252)
            if len(market_bars) < 200:
                return "bull"  # 數據不足，預設多頭

            close = market_bars["close"]
            current = float(close.iloc[-1])
            ma200 = float(close.iloc[-200:].mean())
            ma50 = float(close.iloc[-50:].mean())

            if current < ma200 and ma50 < ma200:
                return "bear"
            elif current > ma200 and ma50 > ma200:
                return "bull"
            else:
                return "sideways"
        except Exception:
            return "bull"  # 無法取得大盤數據，預設多頭

    def on_bar(self, ctx: Context) -> dict[str, float]:
        current_date = ctx.now()

        # 再平衡判斷：事件驅動 or 月度
        if self.event_driven:
            if self._event_rebalancer is None:
                from src.alpha.event_rebalancer import EventDrivenRebalancer
                self._event_rebalancer = EventDrivenRebalancer()
            signal = self._event_rebalancer.check(current_date)
            if not signal.should_rebalance:
                return self._cached_weights
        else:
            # 月度再平衡（營收延遲已由 _get_revenue_at 的 +40 天 lag 處理）
            current_month = pd.Timestamp(current_date).strftime("%Y-%m")
            if current_month == self._last_month:
                return self._cached_weights

        # 懶載入營收快取
        if self._rev_cache is None:
            self._rev_cache = _preload_revenue()

        as_of = pd.Timestamp(current_date)
        candidates: list[tuple[str, float]] = []

        for symbol in ctx.universe():
            try:
                bars = ctx.bars(symbol, lookback=252)
                if len(bars) < 120:
                    continue

                close = bars["close"]
                volume = bars["volume"]

                # 條件 5: 流動性
                avg_vol_20 = float(volume.iloc[-20:].mean()) if len(volume) >= 20 else 0
                if avg_vol_20 < self.min_volume_lots * 1000:
                    continue

                # 條件 3: 股價 > 60 日均線
                if len(close) < 60:
                    continue
                ma60 = float(close.iloc[-60:].mean())
                if float(close.iloc[-1]) <= ma60:
                    continue

                # 條件 4: 近 60 日漲幅 > 0
                if float(close.iloc[-1]) / float(close.iloc[-60]) - 1 <= 0:
                    continue

                # 條件 1 & 2: 營收（從預載快取，零 I/O）
                rev_data = _get_revenue_at(self._rev_cache, symbol, as_of)
                if rev_data is None:
                    continue

                rev_3m, rev_12m, latest_yoy = rev_data
                if rev_12m <= 0 or rev_3m <= rev_12m:
                    continue
                if latest_yoy < self.min_yoy_growth:
                    continue

                # 排序用 acceleration（3M/12M 比率），不用 YoY
                # acceleration ICIR 0.476 > yoy 0.188（含 40 天延遲後）
                acceleration = rev_3m / rev_12m
                candidates.append((symbol, acceleration))

            except Exception as e:
                logger.debug("Skip %s: %s", symbol, e)
                continue

        current_month = pd.Timestamp(current_date).strftime("%Y-%m")

        if not candidates:
            self._last_month = current_month
            self._cached_weights = {}
            return {}

        candidates.sort(key=lambda x: x[1], reverse=True)
        selected = candidates[: self.max_holdings]
        signals = {sym: accel for sym, accel in selected}

        constraints = OptConstraints(
            max_weight=self.max_weight,
            max_total_weight=0.95,
        )

        if self.weight_method == "signal":
            weights = signal_weight(signals, constraints)
        elif self.weight_method == "risk_parity":
            # B-4 fix: compute 20d volatilities for risk_parity (was passing empty {})
            vols = {}
            for sym in signals:
                bars = ctx.bars(sym, lookback=25)
                if bars is not None and len(bars) >= 20:
                    rets = bars["close"].pct_change().dropna()
                    vols[sym] = float(rets.std()) if len(rets) > 1 else 0.20
                else:
                    vols[sym] = 0.20  # default vol
            weights = risk_parity(signals, vols, constraints)
        else:
            weights = equal_weight(signals, constraints)

        # Regime-aware position sizing（空頭偵測 + 倉位調整）
        if self.enable_regime_hedge and weights:
            regime = self._market_regime(ctx)
            if regime == "bear":
                weights = {k: v * self.bear_position_scale for k, v in weights.items()}
                logger.info("BEAR regime detected — scaling to %.0f%%", self.bear_position_scale * 100)
            elif regime == "sideways":
                weights = {k: v * self.sideways_position_scale for k, v in weights.items()}

        # Phase AA 4.2: no-trade zone — 偏離 < 1.5% 不調整（降低換手成本）
        # 4.6: 非對稱成本 — 賣出門檻更高（賣出成本是買入的 3 倍）
        NO_TRADE_BUY = 0.015   # 買入/加碼門檻 1.5%
        NO_TRADE_SELL = 0.030  # 賣出門檻 3%（賣出成本 0.4425% 是買入 0.1425% 的 3 倍）
        portfolio = ctx.portfolio()
        if portfolio is not None and portfolio.nav > 0:
            current_w: dict[str, float] = {}
            for sym in set(list(weights.keys()) + [p for p in portfolio.positions]):
                current_w[sym] = float(portfolio.get_position_weight(sym))
            adjusted: dict[str, float] = {}
            for sym in set(list(weights.keys()) + list(current_w.keys())):
                target = weights.get(sym, 0.0)
                current = current_w.get(sym, 0.0)
                diff = target - current
                if diff > NO_TRADE_BUY:       # 買入/加碼：偏離 > 1.5%
                    adjusted[sym] = target
                elif diff < -NO_TRADE_SELL:    # 賣出：偏離 > 3%
                    adjusted[sym] = target
                elif current > 0.001:          # 在 zone 內：保持不動
                    adjusted[sym] = current
                # else: 不持有且不買 → 不加入
            weights = adjusted

        self._last_month = current_month
        self._cached_weights = weights
        return weights
