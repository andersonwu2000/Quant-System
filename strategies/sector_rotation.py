"""
板塊輪動策略 — 買入短期動量最強的 Top N 標的，風險平價配置。

When sector data is available (via FundamentalsProvider), groups symbols by sector
and selects top performers from each sector for diversification.
When sector data is unavailable, falls back to pure momentum ranking.
"""

from __future__ import annotations

from collections import defaultdict

from src.strategy.base import Context, Strategy
from src.strategy.factors import volatility
from src.strategy.optimizer import risk_parity, OptConstraints


class SectorRotationStrategy(Strategy):
    """
    板塊輪動策略：
    - 使用 60 日短期動量排名（無跳過期間）
    - 集中持倉：只買入前 N 名
    - 風險平價配置：按波動率倒數分配權重

    When sector data is available:
    - Groups symbols by sector
    - Selects top performer(s) from each sector
    - Ensures cross-sector diversification
    """

    def __init__(self, lookback: int = 60, top_n: int = 5, top_per_sector: int = 1):
        self.lookback = lookback
        self.top_n = top_n
        self.top_per_sector = top_per_sector

    def name(self) -> str:
        return "sector_rotation"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        momentum_scores: dict[str, float] = {}
        vol_data: dict[str, float] = {}
        sector_map: dict[str, str] = {}

        for symbol in ctx.universe():
            bars = ctx.bars(symbol, lookback=self.lookback + 30)
            if len(bars) < 80:
                continue

            close = bars["close"]
            # 短期動量：lookback 日報酬率，無跳過期間
            ret = close.iloc[-1] / close.iloc[-self.lookback] - 1
            momentum_scores[symbol] = float(ret)

            # 波動率
            vol = volatility(bars, lookback=self.lookback)
            if not vol.empty and vol["volatility"] > 0:
                vol_data[symbol] = vol["volatility"]

            # Sector classification (if available)
            sector = ctx.sector(symbol)
            if sector:
                sector_map[symbol] = sector

        if not momentum_scores:
            return {}

        # Select top symbols, with sector-aware diversification if data available
        if sector_map and len(sector_map) >= len(momentum_scores) * 0.5:
            # Enough sector data: group by sector, pick top from each
            top_signals = self._select_by_sector(
                momentum_scores, sector_map
            )
        else:
            # No sector data: fall back to pure momentum ranking
            top_signals = self._select_by_momentum(momentum_scores)

        if not top_signals:
            return {}

        # 確保所有 top 標的都有波動率數據
        valid_vols = {s: vol_data[s] for s in top_signals if s in vol_data}
        if not valid_vols:
            return {}

        return risk_parity(
            top_signals,
            valid_vols,
            OptConstraints(max_weight=0.25, max_total_weight=0.95),
        )

    def _select_by_momentum(
        self, momentum_scores: dict[str, float]
    ) -> dict[str, float]:
        """Select top N symbols by pure momentum ranking (no sector data)."""
        sorted_scores = sorted(
            momentum_scores.items(), key=lambda x: x[1], reverse=True
        )
        top_signals = {}
        for symbol, score in sorted_scores[: self.top_n]:
            if score > 0:
                top_signals[symbol] = score
        return top_signals

    def _select_by_sector(
        self,
        momentum_scores: dict[str, float],
        sector_map: dict[str, str],
    ) -> dict[str, float]:
        """Select top performers from each sector for diversification.

        Picks top_per_sector from each sector (by momentum), then fills
        remaining slots from overall ranking up to top_n.
        """
        # Group by sector
        sector_groups: dict[str, list[tuple[str, float]]] = defaultdict(list)
        unsectored: list[tuple[str, float]] = []

        for symbol, score in momentum_scores.items():
            if score <= 0:
                continue
            sector = sector_map.get(symbol, "")
            if sector:
                sector_groups[sector].append((symbol, score))
            else:
                unsectored.append((symbol, score))

        # Sort each sector by momentum (descending)
        for sector in sector_groups:
            sector_groups[sector].sort(key=lambda x: x[1], reverse=True)

        # Pick top from each sector
        top_signals: dict[str, float] = {}

        # Sort sectors by their best performer's momentum (strongest sector first)
        sorted_sectors = sorted(
            sector_groups.items(),
            key=lambda x: x[1][0][1] if x[1] else 0,
            reverse=True,
        )

        for _sector, members in sorted_sectors:
            for symbol, score in members[: self.top_per_sector]:
                if len(top_signals) >= self.top_n:
                    break
                top_signals[symbol] = score
            if len(top_signals) >= self.top_n:
                break

        # Fill remaining slots from unsectored or remaining sector members
        if len(top_signals) < self.top_n:
            remaining = sorted(
                [(s, sc) for s, sc in momentum_scores.items() if s not in top_signals and sc > 0],
                key=lambda x: x[1],
                reverse=True,
            )
            for symbol, score in remaining:
                if len(top_signals) >= self.top_n:
                    break
                top_signals[symbol] = score

        return top_signals
