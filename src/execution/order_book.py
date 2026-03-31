"""Persistent order book — pending orders survive restarts.

Stores non-terminal orders (PENDING, SUBMITTED, PARTIAL) in SQLite.
On startup, loads them so the system knows what's still outstanding.
Terminal orders (FILLED, CANCELLED, REJECTED) are removed from the book.

Used by live trading (SinopacBroker) where async callbacks mean
orders can be in-flight when the system crashes.
Paper trading (SimBroker) fills synchronously so rarely has pending orders.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import sqlalchemy as sa

from src.core.models import (
    Instrument, Order, OrderCondition, OrderStatus, OrderType, Side,
    StockOrderLot,
)
from src.data.store import metadata as db_metadata

logger = logging.getLogger(__name__)

# ── Table definition ─────────────────────────────────────────────────

pending_orders_table = sa.Table(
    "pending_orders",
    db_metadata,
    sa.Column("order_id", sa.Text, primary_key=True),
    sa.Column("symbol", sa.Text, nullable=False),
    sa.Column("side", sa.Text, nullable=False),
    sa.Column("order_type", sa.Text, nullable=False),
    sa.Column("quantity", sa.Text, nullable=False),
    sa.Column("price", sa.Text, nullable=True),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("filled_qty", sa.Text, nullable=False, server_default="0"),
    sa.Column("filled_avg_price", sa.Text, nullable=False, server_default="0"),
    sa.Column("strategy_id", sa.Text, nullable=True),
    sa.Column("created_at", sa.Text, nullable=False),
    sa.Column("updated_at", sa.Text, nullable=False),
    sa.Column("order_cond", sa.Text, nullable=False, server_default="CASH"),
    sa.Column("order_lot", sa.Text, nullable=False, server_default="COMMON"),
    sa.Column("metadata_json", sa.Text, nullable=True),
)


class PersistentOrderBook:
    """SQLite-backed order book for pending orders."""

    def __init__(self, engine: sa.Engine):
        self._engine = engine
        pending_orders_table.create(engine, checkfirst=True)

    def save(self, order: Order) -> None:
        """Insert or update an order."""
        now = datetime.now().isoformat()
        row = {
            "order_id": order.id,
            "symbol": order.instrument.symbol,
            "side": order.side.value,
            "order_type": order.order_type.value,
            "quantity": str(order.quantity),
            "price": str(order.price) if order.price is not None else None,
            "status": order.status.value,
            "filled_qty": str(order.filled_qty),
            "filled_avg_price": str(order.filled_avg_price),
            "strategy_id": order.strategy_id,
            "created_at": order.created_at.isoformat(),
            "updated_at": now,
            "order_cond": order.order_cond.value,
            "order_lot": order.order_lot.value,
        }

        with self._engine.begin() as conn:
            existing = conn.execute(
                sa.select(pending_orders_table.c.order_id).where(
                    pending_orders_table.c.order_id == order.id
                )
            ).fetchone()

            if existing:
                if order.is_terminal:
                    # Terminal orders: remove from book
                    conn.execute(
                        pending_orders_table.delete().where(
                            pending_orders_table.c.order_id == order.id
                        )
                    )
                else:
                    conn.execute(
                        pending_orders_table.update()
                        .where(pending_orders_table.c.order_id == order.id)
                        .values(**row)
                    )
            else:
                if not order.is_terminal:
                    conn.execute(pending_orders_table.insert().values(**row))

    def load_pending(self) -> list[Order]:
        """Load all non-terminal orders from the book."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                sa.select(pending_orders_table).where(
                    pending_orders_table.c.status.in_(["PENDING", "SUBMITTED", "PARTIAL"])
                )
            ).fetchall()

        orders = []
        for row in rows:
            try:
                order = Order(
                    id=row.order_id,
                    instrument=Instrument(symbol=row.symbol),
                    side=Side(row.side),
                    order_type=OrderType(row.order_type),
                    quantity=Decimal(row.quantity),
                    price=Decimal(row.price) if row.price else None,
                    status=OrderStatus(row.status),
                    filled_qty=Decimal(row.filled_qty),
                    filled_avg_price=Decimal(row.filled_avg_price),
                    strategy_id=row.strategy_id or "",
                    created_at=datetime.fromisoformat(row.created_at),
                    order_cond=OrderCondition(row.order_cond) if row.order_cond else OrderCondition.CASH,
                    order_lot=StockOrderLot(row.order_lot) if row.order_lot else StockOrderLot.COMMON,
                )
                orders.append(order)
            except Exception as e:
                logger.warning("Failed to load pending order %s: %s", row.order_id, e)

        if orders:
            logger.info("Loaded %d pending orders from order book", len(orders))
        return orders

    def clear_all(self) -> int:
        """Remove all orders from the book. Returns count removed."""
        with self._engine.begin() as conn:
            result = conn.execute(pending_orders_table.delete())
            return result.rowcount

    def count(self) -> int:
        """Count pending orders."""
        with self._engine.connect() as conn:
            result = conn.execute(
                sa.select(sa.func.count()).select_from(pending_orders_table)
            )
            return result.scalar() or 0
