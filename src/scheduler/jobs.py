"""Scheduled job implementations — 連接策略引擎與執行服務。

Jobs:
- execute_rebalance: 通用排程再平衡（任何 active 策略）
- monthly_revenue_rebalance: 月度營收策略專用（每月 11 日觸發）
- monthly_revenue_update: 月度營收數據更新（每月 11 日 08:30）
"""

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
        universe = list(state.portfolio.positions.keys())
        if not universe:
            universe = _get_tw_universe_fallback()  # R10.4
            if not universe:
                logger.error("No universe available, skipping rebalance")
                return
        feed = create_feed(config.data_source, universe)

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
            _save_trade_log(trades, active_strategy_name)  # R10.5
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


async def monthly_revenue_update(max_retries: int = 1) -> bool:
    """每月營收數據更新。回傳 True 表示成功。

    修正：
    - 動態計算 --start（當前 - 2 年），不再硬編碼 (R10.2)
    - 失敗重試 1 次 (R10.6)
    - 回傳成功/失敗狀態供 caller 決定是否繼續 rebalance (R10.1)
    """
    import subprocess
    import sys
    from datetime import datetime, timedelta

    start_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
    logger.info("Monthly revenue data update triggered (start=%s)", start_date)

    for attempt in range(max_retries + 1):
        try:
            result = subprocess.run(
                [sys.executable, "-m", "scripts.download_finmind_data",
                 "--symbols-from-market", "--dataset", "revenue", "--start", start_date],
                capture_output=True, text=True, timeout=600,
            )
            if result.returncode == 0:
                logger.info("Revenue data update completed successfully (attempt %d)", attempt + 1)
                return True
            else:
                logger.error(
                    "Revenue data update failed (attempt %d/%d): %s",
                    attempt + 1, max_retries + 1,
                    result.stderr[-500:] if result.stderr else "unknown",
                )
        except Exception:
            logger.exception("Revenue data update exception (attempt %d/%d)", attempt + 1, max_retries + 1)

    logger.error("Revenue data update exhausted all retries")
    return False


async def monthly_revenue_rebalance(config: TradingConfig) -> None:
    """每月 11 日 09:05 用 revenue_momentum_hedged 策略執行再平衡。

    排程：cron = "5 9 11 * *"

    與 execute_rebalance 的差異：
    - 固定使用 revenue_momentum_hedged（不看 active strategy）
    - 提供 FinMind fundamentals provider 給 Context
    - 下單前記錄選股結果到 data/paper_trading/
    """
    from src.api.state import get_app_state
    from src.core.models import Order
    from src.data.sources import create_feed, create_fundamentals
    from src.execution.oms import apply_trades
    from src.notifications.factory import create_notifier
    from src.strategy.base import Context
    from src.strategy.engine import weights_to_orders
    from src.strategy.registry import resolve_strategy

    logger.info("Monthly revenue rebalance triggered at %s", datetime.now())

    state = get_app_state()
    notifier = create_notifier(config)
    exec_svc = state.execution_service

    if not exec_svc.is_initialized:
        logger.error("ExecutionService not initialized, skipping")
        return

    try:
        strategy = resolve_strategy("revenue_momentum_hedged")

        # 建立 DataFeed + FundamentalsProvider
        universe = list(state.portfolio.positions.keys())
        if not universe:
            universe = _get_tw_universe_fallback()  # R10.4
            if not universe:
                logger.error("No universe available, skipping")
                return

        feed = create_feed(config.data_source, universe)
        fundamentals = create_fundamentals(config.data_source)

        ctx = Context(
            feed=feed,
            portfolio=state.portfolio,
            fundamentals_provider=fundamentals,
        )

        target_weights = strategy.on_bar(ctx)

        if not target_weights:
            logger.info("revenue_momentum_hedged returned empty weights (possibly bear regime)")
            return

        logger.info(
            "revenue_momentum_hedged: %d targets, top: %s",
            len(target_weights),
            sorted(target_weights.items(), key=lambda x: -x[1])[:5],
        )

        # 記錄選股結果
        _save_selection_log(target_weights)

        # 產生訂單
        prices = {}
        for s in target_weights:
            try:
                prices[s] = feed.get_latest_price(s)
            except Exception:
                pass

        orders = weights_to_orders(
            target_weights=target_weights,
            portfolio=state.portfolio,
            prices=prices,
        )

        if not orders:
            logger.info("No orders generated")
            return

        # 風控
        approved: list[Order] = []
        for order in orders:
            decision = state.risk_engine.check_order(order, state.portfolio)
            if decision.approved:
                if decision.modified_qty is not None:
                    order.quantity = decision.modified_qty
                approved.append(order)
            else:
                logger.warning("Order rejected: %s — %s", order.instrument.symbol, decision.reason)

        if not approved:
            logger.info("All orders rejected by risk engine")
            return

        # 下單
        trades = exec_svc.submit_orders(approved, state.portfolio)
        if trades:
            apply_trades(state.portfolio, trades)
            _save_trade_log(trades, "revenue_momentum_hedged")  # R10.5
            logger.info("Monthly rebalance: %d trades, NAV=%s", len(trades), state.portfolio.nav)

        # 通知
        if notifier.is_configured():
            summary = (
                f"Monthly Revenue Rebalance: {len(trades)} trades, "
                f"{len(target_weights)} targets, NAV={float(state.portfolio.nav):,.0f}"
            )
            try:
                await notifier.send("Monthly Rebalance", summary)
            except Exception:
                logger.debug("Notification failed", exc_info=True)

    except Exception:
        logger.exception("Monthly revenue rebalance failed")


def _get_tw_universe_fallback() -> list[str]:
    """從 data/market/ 建立台股 universe（排除 ETF 00xx）。(R10.4)"""
    from pathlib import Path

    market_dir = Path("data/market")
    if not market_dir.exists():
        logger.error("data/market/ directory not found")
        return []
    universe = sorted(
        p.stem.replace("_1d", "")
        for p in market_dir.glob("*.TW_1d.parquet")
        if not p.stem.startswith("00")
    )
    return universe


def _save_selection_log(weights: dict[str, float]) -> None:
    """記錄每月選股結果到 data/paper_trading/selections/。"""
    import json
    from pathlib import Path

    out_dir = Path("data/paper_trading/selections")
    out_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    log = {
        "date": today,
        "strategy": "revenue_momentum_hedged",
        "n_targets": len(weights),
        "weights": {k: round(v, 4) for k, v in sorted(weights.items(), key=lambda x: -x[1])},
    }

    path = out_dir / f"{today}.json"
    with open(path, "w") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    logger.info("Selection log saved: %s", path)


def _save_trade_log(trades: list, strategy_name: str) -> None:
    """記錄每次 rebalance 的交易結果。(R10.5)"""
    import json
    from pathlib import Path

    out_dir = Path("data/paper_trading/trades")
    out_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d_%H%M")
    log = {
        "date": today,
        "strategy": strategy_name,
        "n_trades": len(trades),
        "trades": [
            {
                "symbol": str(getattr(t, "symbol", getattr(t, "instrument", {}))),
                "side": str(getattr(t, "side", "")),
                "quantity": str(getattr(t, "quantity", "")),
                "price": str(getattr(t, "price", "")),
            }
            for t in trades
        ],
    }

    path = out_dir / f"{today}.json"
    with open(path, "w") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    logger.info("Trade log saved: %s (%d trades)", path, len(trades))
