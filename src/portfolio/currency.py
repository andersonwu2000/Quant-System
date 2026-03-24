"""
幣別暴露管理與對沖決策。

根據組合的幣別暴露、對沖成本、和風險偏好，建議最佳對沖比例。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class HedgeConfig:
    """幣別對沖配置。"""

    base_currency: str = "TWD"
    hedge_cost_annual_bps: float = 50.0   # 年化對沖成本（bps）
    max_unhedged_pct: float = 0.40        # 最大未對沖比例
    min_hedge_amount: float = 10000.0     # 低於此不對沖


@dataclass
class HedgeRecommendation:
    """對沖建議。"""

    currency: str
    gross_exposure: float          # 原始暴露金額
    hedge_ratio: float             # 建議對沖比例 (0~1)
    hedged_amount: float           # 對沖金額
    unhedged_amount: float         # 未對沖金額
    annual_cost_bps: float         # 年化對沖成本
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "currency": self.currency,
            "gross_exposure": round(self.gross_exposure, 2),
            "hedge_ratio": round(self.hedge_ratio, 4),
            "hedged_amount": round(self.hedged_amount, 2),
            "unhedged_amount": round(self.unhedged_amount, 2),
            "annual_cost_bps": round(self.annual_cost_bps, 1),
            "reason": self.reason,
        }


class CurrencyHedger:
    """幣別對沖決策引擎。"""

    def __init__(self, config: HedgeConfig | None = None):
        self._config = config or HedgeConfig()

    def analyze(
        self,
        currency_exposure: dict[str, Decimal],
        total_nav: Decimal,
    ) -> list[HedgeRecommendation]:
        """分析幣別暴露並產出對沖建議。

        Args:
            currency_exposure: 各幣別暴露金額 {"USD": Decimal("150000"), "TWD": ...}
            total_nav: 組合總 NAV（base currency 計價）

        Returns:
            每個非 base 幣別的對沖建議
        """
        cfg = self._config
        recommendations: list[HedgeRecommendation] = []

        nav_float = float(total_nav) if total_nav > 0 else 1.0

        for cur, exposure in currency_exposure.items():
            if cur == cfg.base_currency:
                continue

            exp_float = float(exposure)
            exp_pct = abs(exp_float) / nav_float if nav_float > 0 else 0.0

            # 金額太小不值得對沖
            if abs(exp_float) < cfg.min_hedge_amount:
                recommendations.append(HedgeRecommendation(
                    currency=cur,
                    gross_exposure=exp_float,
                    hedge_ratio=0.0,
                    hedged_amount=0.0,
                    unhedged_amount=exp_float,
                    annual_cost_bps=0.0,
                    reason="Exposure below minimum threshold",
                ))
                continue

            # 計算建議對沖比例
            hedge_ratio = self._compute_hedge_ratio(exp_pct)
            hedged = abs(exp_float) * hedge_ratio
            cost = cfg.hedge_cost_annual_bps * hedge_ratio

            recommendations.append(HedgeRecommendation(
                currency=cur,
                gross_exposure=exp_float,
                hedge_ratio=hedge_ratio,
                hedged_amount=hedged,
                unhedged_amount=abs(exp_float) - hedged,
                annual_cost_bps=cost,
                reason=self._hedge_reason(exp_pct, hedge_ratio),
            ))

        return recommendations

    def _compute_hedge_ratio(self, exposure_pct: float) -> float:
        """根據暴露比例計算建議對沖比例。

        規則：
        - 暴露 < 10%: 不對沖（成本不划算）
        - 暴露 10~40%: 對沖 50%（平衡成本與風險）
        - 暴露 > 40%: 對沖至剩下 max_unhedged_pct
        """
        cfg = self._config

        if exposure_pct < 0.10:
            return 0.0
        elif exposure_pct <= cfg.max_unhedged_pct:
            return 0.5
        else:
            # 對沖至 max_unhedged_pct
            target_unhedged = cfg.max_unhedged_pct
            hedge = 1.0 - (target_unhedged / exposure_pct)
            return min(max(hedge, 0.0), 1.0)

    @staticmethod
    def _hedge_reason(exposure_pct: float, hedge_ratio: float) -> str:
        if hedge_ratio == 0.0:
            return "Low exposure, hedging cost exceeds benefit"
        elif hedge_ratio <= 0.5:
            return f"Moderate exposure ({exposure_pct:.0%}), partial hedge"
        else:
            return f"High exposure ({exposure_pct:.0%}), hedge to reduce currency risk"
