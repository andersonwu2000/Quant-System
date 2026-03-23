"""Scheduled job implementations."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config import TradingConfig

logger = logging.getLogger(__name__)


async def execute_rebalance(config: TradingConfig) -> None:
    """Execute a scheduled rebalance.

    Steps:
    1. Load portfolio from DB (or use default)
    2. Fetch current prices
    3. Run strategy to get target weights
    4. Generate suggested trades
    5. Send notification
    """
    from src.notifications.factory import create_notifier

    logger.info("Executing scheduled rebalance")

    # Initialize notification provider from config
    notifier = create_notifier(config)

    if not notifier.is_configured():
        logger.warning(
            "No notification provider configured, rebalance results will only be logged"
        )

    # This is a framework — the actual portfolio loading and strategy execution
    # will be connected when Phase 3-1 (repository) is integrated
    logger.info("Scheduled rebalance completed at %s", datetime.now())
