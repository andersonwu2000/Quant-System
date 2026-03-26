"""
營收動能策略 — 基於 FinLab 研究的台股最強公開因子。

FinLab 對標：月營收動能策略（CAGR 33.5%）+ AI 因子挖掘最佳迭代（CAGR 18.6%）
核心邏輯：營收 3M avg > 12M avg + 營收 YoY > 15% + 股價趨勢確認 + 流動性篩選

效能優化：啟動時一次預載所有營收 parquet 到記憶體，回測中不再逐支讀檔。
"""

from __future__ import annotations

import logging
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
                df["yoy_growth"] = ((df["revenue"] / prev_year_rev) - 1) * 100
                df.loc[prev_year_rev <= 0, "yoy_growth"] = np.nan

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

    # 只用 as_of 之前的數據（避免 look-ahead）
    mask = df["date"] <= as_of
    available = df[mask]
    if len(available) < 12:
        return None

    revenues = available["revenue"].values
    rev_3m = float(np.mean(revenues[-3:])) if len(revenues) >= 3 else 0
    rev_12m = float(np.mean(revenues[-12:])) if len(revenues) >= 12 else 0

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

    排序：營收 YoY 取前 max_holdings 檔。
    """

    def __init__(
        self,
        max_holdings: int = 15,
        min_yoy_growth: float = 15.0,
        min_volume_lots: int = 300,
        max_weight: float = 0.10,
        weight_method: str = "signal",  # "equal" | "signal" | "risk_parity"
        enable_regime_hedge: bool = True,  # 空頭偵測 + 倉位調整
        bear_position_scale: float = 0.30,  # 空頭時持倉比例
        sideways_position_scale: float = 0.60,  # 盤整時持倉比例
        market_proxy: str = "0050.TW",  # 市場代理標的
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
        self._last_month: str = ""
        self._cached_weights: dict[str, float] = {}
        self._rev_cache: dict[str, pd.DataFrame] | None = None

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

                candidates.append((symbol, latest_yoy))

            except Exception as e:
                logger.debug("Skip %s: %s", symbol, e)
                continue

        if not candidates:
            self._last_month = current_month
            self._cached_weights = {}
            return {}

        candidates.sort(key=lambda x: x[1], reverse=True)
        selected = candidates[: self.max_holdings]
        signals = {sym: yoy for sym, yoy in selected}

        constraints = OptConstraints(
            max_weight=self.max_weight,
            max_total_weight=0.95,
        )

        if self.weight_method == "signal":
            weights = signal_weight(signals, constraints)
        elif self.weight_method == "risk_parity":
            weights = risk_parity(signals, constraints)
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

        self._last_month = current_month
        self._cached_weights = weights
        return weights
