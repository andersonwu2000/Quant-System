"""
營收動能 + 空頭偵測策略 — composite_b0% 正式版。

基於實驗 #10 驗證：OOS 2025 H1 從 -16% 改善到 -5.4%，牛市反增 +3.4pp。
StrategyValidator 10/13 通過。

空頭偵測：MA200 趨勢 OR vol_spike（複合偵測器）
- Bear: 大盤 < MA200×0.95 且 MA50 < MA200，或 20d vol > 25%
- Sideways: 大盤 < MA200，或 20d vol > 60d vol × 1.5
- Bull: 以上都不觸發 → 100% 倉位
"""

from __future__ import annotations

import logging

import numpy as np

from src.strategy.base import Context, Strategy
from src.strategy.registry import resolve_strategy

logger = logging.getLogger(__name__)


class RevenueMomentumHedgedStrategy(Strategy):
    """Revenue Momentum + 複合空頭偵測。

    包裝 revenue_momentum 策略，加入 regime-aware position sizing。
    """

    def __init__(
        self,
        market_proxy: str = "0050.TW",
        bear_scale: float = 0.0,
        sideways_scale: float = 0.3,
        ma_threshold: float = 0.95,
        vol_threshold: float = 0.25,
        vol_spike_ratio: float = 1.5,
        **inner_kwargs: object,
    ):
        self._inner = resolve_strategy("revenue_momentum", dict(inner_kwargs) if inner_kwargs else None)
        self.market_proxy = market_proxy
        self.bear_scale = bear_scale
        self.sideways_scale = sideways_scale
        self.ma_threshold = ma_threshold
        self.vol_threshold = vol_threshold
        self.vol_spike_ratio = vol_spike_ratio

    def name(self) -> str:
        return "revenue_momentum_hedged"

    def _detect_regime(self, ctx: Context) -> str:
        """複合偵測：MA200 趨勢 OR vol_spike。"""
        try:
            bars = ctx.bars(self.market_proxy, lookback=252)
            if len(bars) < 200:
                return "bull"
            close = bars["close"]
            returns = close.pct_change().dropna()
        except Exception:
            return "bull"

        current = float(close.iloc[-1])
        ma200 = float(close.iloc[-200:].mean())
        ma50 = float(close.iloc[-50:].mean())
        vol_20d = float(returns.iloc[-20:].std() * np.sqrt(252)) if len(returns) >= 20 else 0
        vol_60d = float(returns.iloc[-60:].std() * np.sqrt(252)) if len(returns) >= 60 else vol_20d

        # Bear: MA200 trend OR vol spike
        ma_bear = current < ma200 * self.ma_threshold and ma50 < ma200
        vol_bear = vol_20d > self.vol_threshold

        if ma_bear or vol_bear:
            return "bear"

        # Sideways: approaching MA200 OR vol rising
        ma_sideways = current < ma200
        vol_sideways = vol_20d > vol_60d * self.vol_spike_ratio

        if ma_sideways or vol_sideways:
            return "sideways"

        return "bull"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        weights = self._inner.on_bar(ctx)
        if not weights:
            return weights

        regime = self._detect_regime(ctx)

        if regime == "bear":
            return {k: v * self.bear_scale for k, v in weights.items()}
        elif regime == "sideways":
            return {k: v * self.sideways_scale for k, v in weights.items()}
        return weights
