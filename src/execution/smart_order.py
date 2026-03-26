"""
TWAP 拆單引擎 — 將大單拆為 N 筆等量子單，降低 market impact。

設計理念：
- 回測中 1,809 筆交易 / 手續費占初始資金 20%，拆單可降低滑點衝擊
- 零股模式下撮合間隔 3 分鐘，大單一次送出會衝擊價格
- TWAP (Time-Weighted Average Price) 是最簡單有效的拆單策略
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from src.core.models import Instrument, Order, OrderType, Side

logger = logging.getLogger(__name__)


@dataclass
class ChildOrder:
    """TWAP 子單。"""

    parent_id: str
    instrument: Instrument
    side: Side
    quantity: Decimal
    price: Decimal | None = None
    order_type: OrderType = OrderType.LIMIT
    scheduled_time: datetime | None = None
    slice_index: int = 0
    total_slices: int = 1


@dataclass
class TWAPConfig:
    """TWAP 配置。"""

    n_slices: int = 5  # 拆成幾筆
    interval_minutes: int = 30  # 每筆間隔（分鐘）
    min_order_value: Decimal = Decimal("50000")  # 低於此金額不拆


class TWAPSplitter:
    """時間加權均價 — 將大單拆為 N 筆等量子單。"""

    def __init__(self, config: TWAPConfig | None = None) -> None:
        self._config = config or TWAPConfig()

    @property
    def config(self) -> TWAPConfig:
        return self._config

    def should_split(self, order: Order, price: Decimal) -> bool:
        """判斷是否需要拆單。"""
        notional = order.quantity * price
        return notional >= self._config.min_order_value

    def split(
        self, order: Order, start_time: datetime | None = None
    ) -> list[ChildOrder]:
        """將母單拆為 n_slices 筆等量子單。

        如果 n_slices <= 1，返回只含一筆的 list。
        餘數分配給最後一筆子單。
        """
        cfg = self._config
        start = start_time or datetime.now()

        if cfg.n_slices <= 1:
            return [self._to_child(order, 0, 1, start)]

        # 整數除法拆分，餘數歸尾單
        slice_qty = order.quantity // cfg.n_slices
        remainder = order.quantity - slice_qty * cfg.n_slices

        children: list[ChildOrder] = []
        for i in range(cfg.n_slices):
            qty = slice_qty
            if i == cfg.n_slices - 1:
                qty += remainder  # 尾單吸收餘數

            scheduled = start + timedelta(minutes=i * cfg.interval_minutes)
            child = ChildOrder(
                parent_id=order.id,
                instrument=order.instrument,
                side=order.side,
                quantity=qty,
                price=order.price,
                order_type=order.order_type,
                scheduled_time=scheduled,
                slice_index=i,
                total_slices=cfg.n_slices,
            )
            children.append(child)

        logger.info(
            "TWAP split: %s %s %s → %d slices of %s, interval=%dmin",
            order.side.value,
            order.quantity,
            order.instrument.symbol,
            cfg.n_slices,
            slice_qty,
            cfg.interval_minutes,
        )
        return children

    def _to_child(
        self, order: Order, idx: int, total: int, time: datetime
    ) -> ChildOrder:
        return ChildOrder(
            parent_id=order.id,
            instrument=order.instrument,
            side=order.side,
            quantity=order.quantity,
            price=order.price,
            order_type=order.order_type,
            scheduled_time=time,
            slice_index=idx,
            total_slices=total,
        )
