"""統一成本模型 — 所有 broker 共用的交易成本計算。

解決問題：commission_rate 出現在 6 個 config 裡，手動傳遞容易不一致。
現在所有 broker（SimBroker、PaperBroker、SinopacBroker）都從 CostModel 讀取。

用法：
    from src.execution.cost_model import CostModel
    cost = CostModel.from_config(get_config())
    # 傳給任何 broker
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CostModel:
    """交易成本參數（不可變，確保一致性）。"""

    commission_rate: Decimal = Decimal("0.001425")  # 台股 0.1425%
    tax_rate: Decimal = Decimal("0.003")            # 證交稅 0.3%（僅賣出）
    min_commission: Decimal = Decimal("20")          # 最低手續費 NT$20
    slippage_bps: Decimal = Decimal("5")             # 滑價 5 bps
    slippage_model: str = "fixed"                    # "fixed" or "sqrt"

    @classmethod
    def from_config(cls, config: object) -> CostModel:
        """從 TradingConfig 建立（single source of truth）。"""
        return cls(
            commission_rate=Decimal(str(getattr(config, "commission_rate", 0.001425))),
            tax_rate=Decimal(str(getattr(config, "tax_rate", 0.003))),
            min_commission=Decimal(str(getattr(config, "min_commission", 20))),
            slippage_bps=Decimal(str(getattr(config, "default_slippage_bps", 5.0))),
        )

    def compute_commission(self, notional: Decimal) -> Decimal:
        """計算手續費（含最低門檻）。"""
        comm = notional * self.commission_rate
        return max(comm, self.min_commission)

    def compute_tax(self, notional: Decimal, is_sell: bool) -> Decimal:
        """計算交易稅（僅賣出）。"""
        return notional * self.tax_rate if is_sell else Decimal("0")

    def compute_slippage(self, price: Decimal, is_buy: bool) -> Decimal:
        """計算滑價後的成交價。"""
        slip = price * self.slippage_bps / Decimal("10000")
        if is_buy:
            return price + slip
        return max(price - slip, Decimal("0.01"))

    def total_cost(self, notional: Decimal, is_sell: bool) -> Decimal:
        """總成本 = 手續費 + 稅。"""
        return self.compute_commission(notional) + self.compute_tax(notional, is_sell)
