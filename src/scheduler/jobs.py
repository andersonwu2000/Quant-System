"""Scheduled job implementations — 連接策略引擎與執行服務。

Jobs:
- execute_pipeline: 統一交易管線（Phase S）
- execute_rebalance: [deprecated] 通用排程再平衡
- monthly_revenue_rebalance: [deprecated] 月度營收策略專用
- monthly_revenue_update: 月度營收數據更新
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.config import TradingConfig

logger = logging.getLogger(__name__)

# ── Pipeline execution record helpers ──────────────────────────

PIPELINE_RUNS_DIR = Path("data/paper_trading/pipeline_runs")


def _write_pipeline_record(
    run_id: str,
    status: str,
    strategy: str = "",
    error: str = "",
    n_trades: int = 0,
) -> Path:
    """Write or update a pipeline execution record as JSON."""
    PIPELINE_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = PIPELINE_RUNS_DIR / f"{run_id}.json"
    record = {
        "run_id": run_id,
        "status": status,
        "strategy": strategy,
        "started_at": datetime.now().isoformat() if status == "started" else None,
        "finished_at": datetime.now().isoformat() if status != "started" else None,
        "n_trades": n_trades,
        "error": error,
    }
    # Merge with existing record to preserve started_at
    if path.exists() and status != "started":
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            record["started_at"] = existing.get("started_at")
        except Exception:
            pass
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _today_run_id() -> str:
    """Generate a run ID for the current execution: YYYY-MM-DD_HHMM."""
    return datetime.now().strftime("%Y-%m-%d_%H%M")


def _has_completed_run_today() -> bool:
    """Check if a completed pipeline run already exists for today (idempotency)."""
    today_prefix = datetime.now().strftime("%Y-%m-%d")
    if not PIPELINE_RUNS_DIR.exists():
        return False
    for path in PIPELINE_RUNS_DIR.glob(f"{today_prefix}*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("status") in ("completed", "ok"):
                return True
        except Exception:
            continue
    return False


def check_crashed_runs() -> list[dict]:
    """Check for pipeline runs with status='started' (indicates a crash).

    Returns list of crashed run records. Called on scheduler startup.
    """
    crashed: list[dict] = []
    if not PIPELINE_RUNS_DIR.exists():
        return crashed
    for path in PIPELINE_RUNS_DIR.glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("status") == "started":
                crashed.append(record)
                # Mark as crashed so we don't warn again next time
                record["status"] = "crashed"
                record["finished_at"] = datetime.now().isoformat()
                record["error"] = "Process terminated unexpectedly (detected on startup)"
                path.write_text(
                    json.dumps(record, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
        except Exception:
            continue
    return crashed


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

    使用 asyncio.to_thread 避免 subprocess.run 阻塞 event loop。
    """
    import asyncio
    import subprocess
    import sys
    from datetime import datetime, timedelta

    start_date = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")
    logger.info("Monthly revenue data update triggered (start=%s)", start_date)

    def _run_sync() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "scripts.download_finmind_data",
             "--symbols-from-market", "--dataset", "revenue", "--start", start_date],
            capture_output=True, text=True, timeout=600,
        )

    for attempt in range(max_retries + 1):
        try:
            result = await asyncio.to_thread(_run_sync)
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


def _save_selection_log_legacy(weights: dict[str, float]) -> None:
    """[deprecated] 舊版 selection log。"""
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
                "symbol": str(getattr(t, "symbol", getattr(getattr(t, "instrument", None), "symbol", "?"))),
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


# ── Phase S: 統一交易管線 ─────────────────────────────────────


@dataclass
class PipelineResult:
    """交易管線執行結果。"""
    status: str  # "ok" | "data_failed" | "no_weights" | "no_orders" | "error"
    n_trades: int = 0
    strategy_name: str = ""
    error: str = ""


async def execute_pipeline(config: TradingConfig) -> PipelineResult:
    """統一交易管線 — 更新數據 → 執行策略 → 風控 → 下單 → 持久化 → 通知。

    取代 execute_rebalance() 和 monthly_revenue_rebalance()。
    根據 config.active_strategy 決定跑哪個策略和需要哪些數據。
    """
    from src.api.state import get_app_state
    from src.core.models import Order
    from src.data.sources import create_feed, create_fundamentals
    from src.execution.oms import apply_trades
    from src.notifications.factory import create_notifier
    from src.strategy.base import Context
    from src.strategy.engine import weights_to_orders
    from src.strategy.registry import resolve_strategy

    logger.info("Pipeline triggered: strategy=%s", config.active_strategy)

    state = get_app_state()
    notifier = create_notifier(config)

    # #8: 確保 nav_sod 有設定（實盤管線不像回測引擎會自動設）
    if state.portfolio.nav_sod == 0 and state.portfolio.nav > 0:
        state.portfolio.nav_sod = state.portfolio.nav

    if not state.execution_service.is_initialized:
        logger.error("ExecutionService not initialized, skipping pipeline")
        return PipelineResult(status="error", error="ExecutionService not initialized")

    try:
        strategy = resolve_strategy(config.active_strategy)
    except ValueError as e:
        return PipelineResult(status="error", error=f"Unknown strategy: {e}")

    # 1. 數據更新（失敗則中止，不用舊數據交易）
    if config.pipeline_data_update:
        revenue_strategies = {"revenue_momentum", "revenue_momentum_hedged", "trust_follow"}
        if strategy.name() in revenue_strategies:
            logger.info("Updating revenue data for %s...", strategy.name())
            ok = await _async_revenue_update()
            if not ok:
                msg = "Revenue data update failed — pipeline aborted"
                logger.error(msg)
                if notifier.is_configured():
                    try:
                        await notifier.send("Pipeline Error", msg)
                    except Exception:
                        pass
                return PipelineResult(status="data_failed", strategy_name=strategy.name(), error=msg)

    # 2. 建立 Context
    # 策略需要全市場 universe 才能掃描和發現新標的（不只是現有持倉）
    # 例如 revenue_momentum 需要掃描 800+ 支再篩選 15 支
    universe = _get_tw_universe_fallback()
    if not universe:
        # Fallback: 至少用現有持倉
        universe = list(state.portfolio.positions.keys())
    if not universe:
        return PipelineResult(status="error", strategy_name=strategy.name(), error="Empty universe")

    feed = create_feed(config.data_source, universe)
    fundamentals = create_fundamentals(config.data_source)
    ctx = Context(feed=feed, portfolio=state.portfolio, fundamentals_provider=fundamentals)

    # 3. 執行策略
    target_weights = strategy.on_bar(ctx)
    if not target_weights:
        logger.info("Strategy %s returned empty weights", strategy.name())
        return PipelineResult(status="no_weights", strategy_name=strategy.name())

    logger.info("Strategy %s: %d targets", strategy.name(), len(target_weights))
    _save_selection_log(target_weights, strategy.name())

    # 4. 風控 + 下單
    prices = {}
    volumes = {}
    for s in target_weights:
        try:
            prices[s] = feed.get_latest_price(s)
            bars = feed.get_bars(s, start=None, end=None)
            if bars is not None and len(bars) >= 20:
                volumes[s] = Decimal(str(int(bars["volume"].iloc[-20:].mean())))
        except Exception:
            pass

    orders = weights_to_orders(
        target_weights, state.portfolio, prices,
        market_lot_sizes=config.market_lot_sizes,
        fractional_shares=config.fractional_shares,
        volumes=volumes if volumes else None,
    )
    if not orders:
        return PipelineResult(status="no_orders", strategy_name=strategy.name())

    approved: list[Order] = []
    for order in orders:
        decision = state.risk_engine.check_order(order, state.portfolio)
        if decision.approved:
            if decision.modified_qty is not None:
                order.quantity = decision.modified_qty
            approved.append(order)
        else:
            logger.warning("Rejected: %s — %s", order.instrument.symbol, decision.reason)

    if not approved:
        logger.info("All orders rejected by risk engine")
        return PipelineResult(status="no_orders", strategy_name=strategy.name())

    trades = state.execution_service.submit_orders(approved, state.portfolio)
    if trades:
        apply_trades(state.portfolio, trades)
        _save_trade_log(trades, strategy.name())

    logger.info("Pipeline done: %d trades, NAV=%s", len(trades) if trades else 0, state.portfolio.nav)

    # 5. 通知
    if notifier.is_configured():
        summary = (
            f"Pipeline [{strategy.name()}]: {len(trades) if trades else 0} trades, "
            f"{len(target_weights)} targets, NAV={float(state.portfolio.nav):,.0f}"
        )
        try:
            await notifier.send("Trading Pipeline", summary)
        except Exception:
            logger.debug("Notification failed", exc_info=True)

    return PipelineResult(status="ok", n_trades=len(trades) if trades else 0, strategy_name=strategy.name())


async def _async_revenue_update() -> bool:
    """非同步包裝 monthly_revenue_update。"""
    try:
        result = await monthly_revenue_update()
        return result  # monthly_revenue_update 回傳 bool
    except Exception:
        logger.exception("Revenue update failed")
        return False


def _save_selection_log(weights: dict[str, float], strategy_name: str = "") -> None:
    """記錄選股結果。"""
    import json
    from pathlib import Path

    out_dir = Path("data/paper_trading/selections")
    out_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    log = {
        "date": today,
        "strategy": strategy_name,
        "n_targets": len(weights),
        "weights": {k: round(v, 4) for k, v in sorted(weights.items(), key=lambda x: -x[1])},
    }

    path = out_dir / f"{today}.json"
    with open(path, "w") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    logger.info("Selection log saved: %s", path)
