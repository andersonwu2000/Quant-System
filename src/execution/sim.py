"""
模擬撮合器 — 回測和紙上交易共用。

模擬真實市場的滑價、手續費、部分成交。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal
from datetime import datetime, timezone
from decimal import Decimal

from src.domain.models import Order, OrderStatus, Side, Trade

logger = logging.getLogger(__name__)


@dataclass
class SimConfig:
    """模擬撮合配置。"""
    slippage_bps: float = 5.0               # 滑價 (basis points) — used by fixed model
    commission_rate: float = 0.001425       # 手續費率
    tax_rate: float = 0.003                 # 交易稅（賣出時）
    max_fill_pct_of_volume: float = 0.10    # 最多成交當日成交量的 10%
    partial_fill: bool = False              # 是否模擬部分成交

    # Slippage model config
    impact_model: Literal["fixed", "sqrt"] = "sqrt"
    impact_coeff: float = 50.0              # sqrt impact coefficient
    base_slippage_bps: float = 2.0          # base slippage for sqrt model

    # Price limit config (0 = disabled; 0.10 = +/-10% Taiwan default)
    price_limit_pct: float = 0.0


class SimBroker:
    """
    模擬券商：接受訂單，模擬成交。

    成交邏輯：
    1. 以 bar 的 close 價為基準
    2. 加上滑價 (買入加、賣出減)
    3. 計算手續費和交易稅
    """

    def __init__(self, config: SimConfig | None = None):
        self.config = config or SimConfig()
        self.trade_log: list[Trade] = []
        self.rejected_log: list[Order] = []

    def _calc_slippage(
        self, close_price: Decimal, order_qty: Decimal, adv: Decimal
    ) -> Decimal:
        """Calculate slippage based on configured impact model.

        Args:
            close_price: The bar close price.
            order_qty: Number of shares in the order.
            adv: Average daily volume (shares). Use 0 if unknown.

        Returns:
            Absolute slippage amount per share.
        """
        if self.config.impact_model == "fixed":
            return close_price * Decimal(str(self.config.slippage_bps)) / Decimal("10000")

        # sqrt model: base + coeff * sqrt(qty / adv)
        if adv > 0:
            participation = float(order_qty) / float(adv)
            impact_bps = self.config.base_slippage_bps + self.config.impact_coeff * (participation ** 0.5)
        else:
            impact_bps = self.config.slippage_bps  # fallback to fixed bps
        return close_price * Decimal(str(impact_bps)) / Decimal("10000")

    def execute(
        self,
        orders: list[Order],
        current_bars: dict[str, dict[str, Any]],
        timestamp: datetime | None = None,
    ) -> list[Trade]:
        """
        執行一批訂單，返回成交記錄。

        Args:
            orders: 待執行訂單
            current_bars: {symbol: {"close": x, "volume": y, "prev_close": z (optional), ...}}
            timestamp: 成交時間
        """
        ts = timestamp or datetime.now(timezone.utc)
        trades: list[Trade] = []

        for order in orders:
            symbol = order.instrument.symbol
            bar = current_bars.get(symbol)
            if bar is None:
                order.status = OrderStatus.REJECTED
                order.reject_reason = f"No market data for {symbol}"
                self.rejected_log.append(order)
                continue

            close_price = Decimal(str(bar.get("close", 0)))
            volume = Decimal(str(bar.get("volume", 0)))

            if close_price <= 0:
                order.status = OrderStatus.REJECTED
                order.reject_reason = "Invalid price"
                self.rejected_log.append(order)
                continue

            # Zero volume check — market may be halted
            if volume <= 0:
                order.status = OrderStatus.REJECTED
                order.reject_reason = f"Zero volume for {symbol} — market may be halted"
                self.rejected_log.append(order)
                continue

            # 數量限制（不超過當日成交量的一定比例）
            fill_qty = order.quantity
            if volume > 0 and self.config.max_fill_pct_of_volume > 0:
                max_qty = volume * Decimal(str(self.config.max_fill_pct_of_volume))
                if fill_qty > max_qty:
                    if self.config.partial_fill:
                        fill_qty = max_qty
                    else:
                        order.status = OrderStatus.REJECTED
                        order.reject_reason = f"Order qty {fill_qty} > max {max_qty}"
                        self.rejected_log.append(order)
                        continue

            # 滑價計算 (using configurable impact model)
            slippage = self._calc_slippage(close_price, fill_qty, volume)
            if order.side == Side.BUY:
                fill_price = close_price + slippage
            else:
                fill_price = close_price - slippage
                fill_price = max(fill_price, Decimal("0.01"))  # 不能為負

            # Price limit check
            if self.config.price_limit_pct > 0:
                prev_close_val = bar.get("prev_close")
                if prev_close_val is not None:
                    prev_close = Decimal(str(prev_close_val))
                    if prev_close > 0:
                        limit_pct = Decimal(str(self.config.price_limit_pct))
                        upper = prev_close * (1 + limit_pct)
                        lower = prev_close * (1 - limit_pct)
                        if fill_price > upper or fill_price < lower:
                            order.status = OrderStatus.REJECTED
                            order.reject_reason = (
                                f"Price {fill_price} exceeds limit [{lower}, {upper}]"
                            )
                            self.rejected_log.append(order)
                            continue

            # Compute actual slippage bps for record-keeping
            if close_price > 0:
                actual_slippage_bps = abs(fill_price - close_price) / close_price * Decimal("10000")
            else:
                actual_slippage_bps = Decimal("0")

            # 手續費
            notional = fill_qty * fill_price
            commission = notional * Decimal(str(self.config.commission_rate))

            # 交易稅（賣出時）
            if order.side == Side.SELL:
                commission += notional * Decimal(str(self.config.tax_rate))

            # 更新訂單狀態
            order.status = OrderStatus.FILLED
            order.filled_qty = fill_qty
            order.filled_avg_price = fill_price
            order.commission = commission
            order.slippage_bps = actual_slippage_bps

            # 記錄成交
            trade = Trade(
                timestamp=ts,
                symbol=symbol,
                side=order.side,
                quantity=fill_qty,
                price=fill_price,
                commission=commission,
                slippage_bps=actual_slippage_bps,
                strategy_id=order.strategy_id,
                order_id=order.id,
            )
            trades.append(trade)
            self.trade_log.append(trade)

            logger.debug(
                "FILL %s %s %s @ %s (slip=%sbps, comm=%s)",
                order.side.value, fill_qty, symbol, fill_price,
                actual_slippage_bps, commission,
            )

        return trades

    def reset(self) -> None:
        """重置成交記錄。"""
        self.trade_log.clear()
        self.rejected_log.clear()
