"""Scheduled job implementations — 連接策略引擎與執行服務。

Jobs:
- execute_pipeline: 統一交易管線（Phase S）
- execute_daily_reconcile: 收盤後自動對帳（broker vs system）
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
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.config import TradingConfig
    from src.core.models import Portfolio

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


def _has_completed_run_this_month() -> bool:
    """#2: 月度策略用 — 檢查本月是否已完成過 pipeline（防重啟後重複再平衡）。"""
    month_prefix = datetime.now().strftime("%Y-%m")
    if not PIPELINE_RUNS_DIR.exists():
        return False
    for path in PIPELINE_RUNS_DIR.glob(f"{month_prefix}*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("status") in ("completed", "ok"):
                return True
        except Exception:
            continue
    return False


def check_crashed_runs() -> list[dict[str, Any]]:
    """Check for pipeline runs with status='started' (indicates a crash).

    Returns list of crashed run records. Called on scheduler startup.
    """
    crashed: list[dict[str, Any]] = []
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

        # Acquire mutation lock to prevent race with kill switch / pipeline
        async with state.mutation_lock:
            # 透過 ExecutionService 下單
            trades = exec_svc.submit_orders(approved_orders, state.portfolio)

            # 更新 Portfolio — trade log BEFORE apply (crash recovery #40)
            if trades:
                _save_trade_log(trades, active_strategy_name)
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

        # Acquire mutation lock to prevent race with kill switch / pipeline
        async with state.mutation_lock:
            # 下單
            trades = exec_svc.submit_orders(approved, state.portfolio)
            if trades:
                _save_trade_log(trades, "revenue_momentum_hedged")  # crash recovery #40
                apply_trades(state.portfolio, trades)
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
    def _clean_sym(stem: str) -> str:
        s = stem.replace("_1d", "")
        if s.startswith("finmind_"):
            s = s[len("finmind_"):]
        return s
    universe = sorted({
        _clean_sym(p.stem)
        for p in market_dir.glob("*_1d.parquet")
        if ".TW" in p.stem and not p.stem.replace("finmind_", "").startswith("00")
    })
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


def _save_trade_log(trades: list[Any], strategy_name: str) -> None:
    """記錄每次 rebalance 的交易結果（含 run_id）。"""
    out_dir = Path("data/paper_trading/trades")
    out_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d_%H%M")
    log = {
        "date": today,
        "run_id": _today_run_id(),  # P3: 關聯 selection → trade → reconciliation
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

    Features:
    - Timeout: enforced via asyncio.wait_for (default: config.backtest_timeout)
    - Execution records: written to data/paper_trading/pipeline_runs/
    - Idempotency: skips if a completed run already exists for today
    """
    import asyncio

    # #2: 月度策略防重複再平衡（crash recovery 後不會重跑）
    monthly_strategies = {"revenue_momentum", "revenue_momentum_hedged", "trust_follow"}
    if config.active_strategy in monthly_strategies:
        if _has_completed_run_this_month():
            logger.info("Pipeline already completed this month — skipping (monthly idempotency)")
            return PipelineResult(status="ok", strategy_name=config.active_strategy)
    elif _has_completed_run_today():
        logger.info("Pipeline already completed today — skipping (daily idempotency)")
        return PipelineResult(status="ok", strategy_name=config.active_strategy)

    run_id = _today_run_id()
    timeout_secs = config.backtest_timeout  # default 1800s

    # Write "started" record before doing anything
    _write_pipeline_record(run_id, status="started", strategy=config.active_strategy)
    logger.info("Pipeline triggered: strategy=%s, run_id=%s, timeout=%ds",
                config.active_strategy, run_id, timeout_secs)

    try:
        result = await asyncio.wait_for(
            _execute_pipeline_inner(config),
            timeout=timeout_secs,
        )
        # Write completion record
        _write_pipeline_record(
            run_id,
            status="completed" if result.status == "ok" else result.status,
            strategy=result.strategy_name,
            n_trades=result.n_trades,
            error=result.error,
        )
        return result

    except asyncio.TimeoutError:
        msg = f"Pipeline timed out after {timeout_secs}s"
        logger.error(msg)
        _write_pipeline_record(run_id, status="failed", strategy=config.active_strategy, error=msg)
        # Best-effort notification
        try:
            from src.notifications.factory import create_notifier
            notifier = create_notifier(config)
            if notifier.is_configured():
                await notifier.send("Pipeline Timeout", msg)
        except Exception:
            pass
        return PipelineResult(status="error", strategy_name=config.active_strategy, error=msg)

    except Exception as exc:
        msg = f"Pipeline crashed: {exc}"
        logger.exception("Pipeline failed")
        _write_pipeline_record(run_id, status="failed", strategy=config.active_strategy, error=msg)
        return PipelineResult(status="error", strategy_name=config.active_strategy, error=msg)


async def _execute_pipeline_inner(config: TradingConfig) -> PipelineResult:
    """Core pipeline logic (extracted for timeout wrapping).

    P2: Also writes pipeline_runs record (not just execute_pipeline outer wrapper).
    """
    # H1 fix: 不在內層重複寫 "started"（外層 execute_pipeline 已寫）
    run_id = _today_run_id()
    from src.api.state import get_app_state
    from src.data.sources import create_feed, create_fundamentals
    from src.notifications.factory import create_notifier
    from src.strategy.base import Context
    from src.strategy.registry import resolve_strategy

    # T1 + P6: 市場時段檢查（用台灣時間 UTC+8，不依賴系統時區）
    if config.mode in ("paper", "live"):
        from datetime import timedelta as _td, timezone as _tz
        _tw_tz = _tz(_td(hours=8))
        now = datetime.now(_tw_tz)
        try:
            from src.core.calendar import get_tw_calendar
            cal = get_tw_calendar()
            if not cal.is_trading_day(now.date()):
                logger.info("Pipeline skipped: non-trading day (%s)", now.date())
                return PipelineResult(status="skipped", strategy_name=config.active_strategy,
                                     error=f"Non-trading day: {now.date()}")
        except Exception:
            logger.debug("Calendar check failed, proceeding anyway", exc_info=True)
        # 台股 09:00-13:30，允許 08:00-14:00 的寬鬆時段
        if not (8 <= now.hour <= 14):
            logger.info("Pipeline skipped: outside trading hours (%d:00)", now.hour)
            return PipelineResult(status="skipped", strategy_name=config.active_strategy,
                                 error=f"Outside trading hours: {now.hour}:00")

    state = get_app_state()
    notifier = create_notifier(config)

    # #8: 確保 nav_sod 有設定（實盤管線不像回測引擎會自動設）
    # Acquire mutation_lock for portfolio mutation to prevent race with kill switch
    async with state.mutation_lock:
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

    # #5: 數據更新後建立新 feed（不用可能快取舊 parquet 的 feed）
    # create_feed 在下面呼叫，確保用更新後的數據

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
    # 用 tz-naive 當前時間（和 backtest Context 一致，避免 tz-aware vs tz-naive 衝突）
    import datetime as _dt
    ctx = Context(
        feed=feed, portfolio=state.portfolio,
        fundamentals_provider=fundamentals,
        current_time=_dt.datetime.now(),  # tz-naive, consistent with backtest
    )

    # 3. 執行策略
    target_weights = strategy.on_bar(ctx)
    if not target_weights:
        logger.info("Strategy %s returned empty weights", strategy.name())
        return PipelineResult(status="no_weights", strategy_name=strategy.name())

    logger.info("Strategy %s: %d targets", strategy.name(), len(target_weights))
    _save_selection_log(target_weights, strategy.name())

    # 4. 風控 + 下單
    # 取 target + 現有持倉的價格（持倉不在 target 時需要 price 才能產生 SELL 訂單）
    all_needed = set(target_weights.keys()) | set(state.portfolio.positions.keys())
    prices = {}
    volumes = {}
    missing_prices: list[str] = []
    for s in all_needed:
        try:
            p = feed.get_latest_price(s)
            if p and p > 0:
                prices[s] = p
            else:
                missing_prices.append(s)
            bars = feed.get_bars(s, start=None, end=None)
            if bars is not None and len(bars) >= 20:
                volumes[s] = Decimal(str(int(bars["volume"].iloc[-20:].mean())))
        except Exception:
            missing_prices.append(s)
    if missing_prices:
        logger.warning("Missing prices for %d symbols: %s", len(missing_prices), missing_prices[:10])

    # U1: 使用統一執行路徑（和回測共用 execute_from_weights）
    from src.core.trading_pipeline import execute_from_weights

    async with state.mutation_lock:
        trades = execute_from_weights(
            target_weights=target_weights,
            portfolio=state.portfolio,
            risk_engine=state.risk_engine,
            prices=prices,
            volumes=volumes if volumes else None,
            broker=state.execution_service,
            market_lot_sizes=config.market_lot_sizes,
            fractional_shares=config.fractional_shares,
        )
        if trades:
            _save_trade_log(trades, strategy.name())

    n_trades = len(trades) if trades else 0
    logger.info("Pipeline done: %d trades, NAV=%s", n_trades, state.portfolio.nav)

    # 5. T3: 自動對帳 — 比對策略目標 vs 實際持倉
    deviations = _reconcile(target_weights, state.portfolio)
    if deviations:
        logger.warning(
            "Reconciliation: %d deviations > 2%%: %s",
            len(deviations),
            [(d["symbol"], f"{d['deviation']:.1%}") for d in deviations[:5]],
        )
        # 偏差過多時發送告警通知
        if len(deviations) >= 5:
            try:
                if notifier.is_configured():
                    import asyncio as _aio
                    _aio.ensure_future(notifier.send(
                        "Reconciliation Alert",
                        f"{len(deviations)} positions deviate > 2% from target. "
                        f"Top: {', '.join(d['symbol'] for d in deviations[:3])}",
                    ))
            except Exception:
                logger.debug("Reconciliation notification failed", exc_info=True)

    # 6. T2: 記錄回測比較數據（用於未來 R² 計算）
    _record_backtest_comparison(
        strategy_name=strategy.name(),
        paper_nav=float(state.portfolio.nav),
        paper_trades=n_trades,
        target_weights=target_weights,
    )

    # 7. 通知（含對帳結果）
    if notifier.is_configured():
        deviation_text = ""
        if deviations:
            deviation_text = f"\nDeviations: {len(deviations)} symbols > 2%"
        summary = (
            f"Pipeline [{strategy.name()}]: {n_trades} trades, "
            f"{len(target_weights)} targets, NAV={float(state.portfolio.nav):,.0f}"
            f"{deviation_text}"
        )
        try:
            await notifier.send("Trading Pipeline", summary)
        except Exception:
            logger.debug("Notification failed", exc_info=True)

    # P1: 主動存 NAV snapshot（不依賴 asyncio task 的時間窗口）
    _save_nav_snapshot(state.portfolio)

    # P2: Write completion record
    _write_pipeline_record(run_id, status="completed", strategy=strategy.name(), n_trades=n_trades)

    return PipelineResult(status="ok", n_trades=n_trades, strategy_name=strategy.name())


def _save_nav_snapshot(portfolio: "Portfolio") -> None:
    """P1: Pipeline 執行後主動存一次 NAV snapshot。"""
    snap_dir = Path("data/paper_trading/snapshots")
    snap_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = snap_dir / f"{today}.json"
    if path.exists():
        return  # 今天已存過
    snap = {
        "date": today,
        "nav": float(portfolio.nav),
        "cash": float(portfolio.cash),
        "n_positions": len(portfolio.positions),
        "positions": {
            s: {"qty": float(p.quantity), "price": float(p.market_price)}
            for s, p in portfolio.positions.items()
        },
    }
    try:
        path.write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("NAV snapshot saved: %s (NAV=%s)", today, snap["nav"])
    except Exception:
        logger.debug("NAV snapshot save failed", exc_info=True)


def _reconcile(
    target_weights: dict[str, float],
    portfolio: "Portfolio",
    threshold: float = 0.02,
) -> list[dict[str, Any]]:
    """T3: 比對策略目標 vs 實際持倉，回傳偏差 > threshold 的股票。"""
    deviations: list[dict[str, Any]] = []
    all_symbols = set(target_weights.keys()) | set(portfolio.positions.keys())
    for sym in all_symbols:
        target_w = target_weights.get(sym, 0.0)
        actual_w = float(portfolio.get_position_weight(sym))
        diff = abs(target_w - actual_w)
        if diff > threshold:
            deviations.append({
                "symbol": sym,
                "target": round(target_w, 4),
                "actual": round(actual_w, 4),
                "deviation": round(diff, 4),
            })
    deviations.sort(key=lambda d: d["deviation"], reverse=True)

    # 存檔（含 run_id）
    recon_dir = Path("data/paper_trading/reconciliation")
    recon_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    recon_record = {
        "date": today,
        "run_id": _today_run_id(),  # P3: 關聯
        "n_deviations": len(deviations),
        "deviations": deviations,
    }
    path = recon_dir / f"{today}.json"
    path.write_text(json.dumps(recon_record, indent=2, ensure_ascii=False), encoding="utf-8")

    return deviations


def _record_backtest_comparison(
    strategy_name: str,
    paper_nav: float,
    paper_trades: int,
    target_weights: dict[str, float],
) -> None:
    """T2: 記錄每次 pipeline 的 NAV，供未來計算回測 vs Paper Trading R²。"""
    comp_dir = Path("data/paper_trading/backtest_comparison")
    comp_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    record = {
        "date": today,
        "strategy": strategy_name,
        "paper_nav": paper_nav,
        "paper_trades": paper_trades,
        "n_targets": len(target_weights),
        "top_targets": dict(sorted(target_weights.items(), key=lambda x: -x[1])[:5]),
    }
    path = comp_dir / f"{today}.json"
    try:
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Backtest comparison record: %s", path)
    except Exception:
        logger.warning("Failed to save backtest comparison", exc_info=True)


async def _async_revenue_update() -> bool:
    """非同步包裝 monthly_revenue_update。"""
    try:
        result = await monthly_revenue_update()
        return result  # monthly_revenue_update 回傳 bool
    except Exception:
        logger.exception("Revenue update failed")
        return False


def _save_selection_log(weights: dict[str, float], strategy_name: str = "") -> None:
    """記錄選股結果（含 run_id 用於追溯）。"""
    out_dir = Path("data/paper_trading/selections")
    out_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    log = {
        "date": today,
        "run_id": _today_run_id(),  # P3: 關聯 selection → trade → reconciliation
        "strategy": strategy_name,
        "n_targets": len(weights),
        "weights": {k: round(v, 4) for k, v in sorted(weights.items(), key=lambda x: -x[1])},
    }

    path = out_dir / f"{today}.json"
    path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Selection log saved: %s", path)


async def execute_daily_reconcile(config: TradingConfig) -> dict[str, Any]:
    """收盤後自動對帳：比對系統持倉與券商端持倉。

    只在 paper/live mode 且 broker 已初始化時執行。
    如有差異，透過通知系統（Discord/LINE/Telegram）告警。
    """
    from src.api.state import get_app_state
    from src.execution.reconcile import reconcile
    from src.notifications.factory import create_notifier

    state = get_app_state()
    notifier = create_notifier(config)

    # 只有 paper/live mode 才需要對帳
    if config.mode not in ("paper", "live"):
        logger.debug("Daily reconcile skipped: mode=%s", config.mode)
        return {"status": "skipped", "reason": "not paper/live mode"}

    # 確認 broker 可用
    exec_svc = state.execution_service
    if not exec_svc.is_initialized or exec_svc.broker is None:
        logger.warning("Daily reconcile skipped: broker not initialized")
        return {"status": "skipped", "reason": "broker not initialized"}

    try:
        broker_positions = exec_svc.broker.query_positions()
        result = reconcile(state.portfolio, broker_positions)

        summary = result.summary()
        logger.info("Daily reconcile completed:\n%s", summary)

        status = "clean" if result.is_clean else "discrepancy"
        try:
            from src.metrics import RECONCILE_RUNS, RECONCILE_MISMATCHES
            RECONCILE_RUNS.labels(status=status).inc()
            RECONCILE_MISMATCHES.set(len(result.mismatched))
        except Exception:
            pass

        if not result.is_clean and notifier.is_configured():
            await notifier.send(
                "Reconciliation Discrepancy",
                f"{len(result.mismatched)} mismatched, "
                f"{len(result.system_only)} system-only, "
                f"{len(result.broker_only)} broker-only positions.\n\n"
                + summary,
            )

        return {
            "status": status,
            "matched": len(result.matched),
            "mismatched": len(result.mismatched),
            "system_only": len(result.system_only),
            "broker_only": len(result.broker_only),
        }
    except Exception as exc:
        logger.exception("Daily reconcile failed")
        try:
            from src.metrics import RECONCILE_RUNS
            RECONCILE_RUNS.labels(status="error").inc()
        except Exception:
            pass
        if notifier.is_configured():
            try:
                await notifier.send(
                    "Reconcile Error",
                    f"Daily reconciliation failed.\n"
                    f"Error: {type(exc).__name__}: {exc}\n"
                    f"Mode: {config.mode}\n"
                    f"Positions: {len(state.portfolio.positions)}",
                )
            except Exception:
                pass
        return {"status": "error"}
