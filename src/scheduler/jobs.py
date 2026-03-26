"""Scheduled job implementations — 連接策略引擎與執行服務。"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.config import TradingConfig

logger = logging.getLogger(__name__)


async def execute_rebalance(config: TradingConfig) -> None:
    """Execute a scheduled rebalance.

    完整流程：
    1. 取得當前 Portfolio 和策略
    2. 取得最新價格
    3. 執行策略產生目標權重
    4. 風控檢查 → weights_to_orders
    5. 透過 ExecutionService 下單
    6. 發送通知
    """
    from src.api.state import get_app_state
    from src.data.sources import create_feed
    from src.core.models import Order
    from src.execution.oms import apply_trades
    from src.notifications.factory import create_notifier
    from src.strategy.engine import weights_to_orders

    logger.info("Scheduled rebalance triggered at %s", datetime.now())

    state = get_app_state()
    notifier = create_notifier(config)
    exec_svc = state.execution_service

    if not exec_svc.is_initialized:
        logger.error("ExecutionService not initialized, skipping rebalance")
        return

    # 找到第一個 running 的策略
    active_strategy_name = None
    for name, info in state.strategies.items():
        if info.get("status") == "running":
            active_strategy_name = name
            break

    if active_strategy_name is None:
        logger.info("No active strategy, skipping rebalance")
        return

    try:
        from src.strategy.registry import resolve_strategy

        strategy = resolve_strategy(active_strategy_name)

        # 建立 DataFeed 取得最新行情
        feed = create_feed(config.data_source, list(state.portfolio.positions.keys()))

        # 取得策略目標權重
        from src.strategy.base import Context

        ctx = Context(feed=feed, portfolio=state.portfolio)
        target_weights = strategy.on_bar(ctx)

        if not target_weights:
            logger.info("Strategy %s returned empty weights", active_strategy_name)
            return

        logger.info(
            "Strategy %s produced %d target weights",
            active_strategy_name, len(target_weights),
        )

        # 產生訂單
        orders = weights_to_orders(
            target_weights=target_weights,
            portfolio=state.portfolio,
            prices={
                s: feed.get_latest_price(s) for s in target_weights
            },
        )

        if not orders:
            logger.info("No orders generated after weight conversion")
            return

        # 風控檢查
        approved_orders: list[Order] = []
        for order in orders:
            decision = state.risk_engine.check_order(order, state.portfolio)
            if decision.approved:
                if decision.modified_qty is not None:
                    order.quantity = decision.modified_qty
                approved_orders.append(order)
            else:
                logger.warning(
                    "Order rejected by risk: %s %s — %s",
                    order.instrument.symbol, order.quantity, decision.reason,
                )

        if not approved_orders:
            logger.info("All orders rejected by risk engine")
            return

        # 透過 ExecutionService 下單
        trades = exec_svc.submit_orders(approved_orders, state.portfolio)

        # 更新 Portfolio
        if trades:
            apply_trades(state.portfolio, trades)
            logger.info("Rebalance completed: %d trades executed", len(trades))

        # 發送通知
        if notifier.is_configured():
            summary = (
                f"Rebalance completed: {len(trades)} trades, "
                f"NAV={float(state.portfolio.nav):,.0f}"
            )
            try:
                await notifier.send("Rebalance", summary)
            except Exception:
                logger.debug("Notification failed", exc_info=True)

    except Exception:
        logger.exception("Scheduled rebalance failed")
        if notifier.is_configured():
            try:
                await notifier.send("Rebalance Error", "Scheduled rebalance failed — check logs")
            except Exception:
                pass
