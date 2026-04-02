"""Scheduled job implementations — 連接策略引擎與執行服務。

Jobs:
- execute_pipeline: 統一交易管線（Phase S）
- execute_daily_reconcile: 收盤後自動對帳（broker vs system）
- monthly_revenue_update: 月度營收數據更新

Implementation split (AN-3):
- pipeline/records.py: pipeline run records, trade logs, NAV snapshots
- pipeline/reconcile.py: daily/backtest reconciliation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from src.core.config import TradingConfig
    from src.core.models import Portfolio

logger = logging.getLogger(__name__)

# Re-export from submodules for backward compatibility
from src.scheduler.pipeline.records import (  # noqa: E402, F401
    PIPELINE_RUNS_DIR,
    _write_pipeline_record,
    _today_run_id,
    _has_completed_run_today,
    _has_completed_run_this_month,
    check_crashed_runs,
    monthly_revenue_update,
    _get_tw_universe_fallback,
    _save_selection_log_legacy,
    _save_trade_log,
    _save_selection_log,
    _save_nav_snapshot,
    _write_daily_report,
    _record_backtest_comparison,
)
from src.scheduler.pipeline.reconcile import (  # noqa: E402, F401
    _reconcile,
    update_portfolio_market_prices,
    execute_backtest_reconcile,
    execute_daily_reconcile,
)


# ── Phase S: 統一交易管線 ─────────────────────────────────────


@dataclass
class PipelineResult:
    """交易管線執行結果。"""
    status: str  # "ok" | "data_failed" | "no_weights" | "no_orders" | "error"
    n_trades: int = 0
    strategy_name: str = ""
    error: str = ""


async def execute_pipeline(config: "TradingConfig") -> PipelineResult:
    """統一交易管線 — 更新數據 → 執行策略 → 風控 → 下單 → 持久化 → 通知。

    Features:
    - Timeout: enforced via asyncio.wait_for (default: config.backtest_timeout)
    - Execution records: written to data/paper_trading/pipeline_runs/
    - Idempotency: skips if a completed run already exists for today
    """
    import asyncio

    # #2: 月度策略防重複再平衡
    monthly_strategies = {"revenue_momentum", "revenue_momentum_hedged", "trust_follow"}
    if config.active_strategy in monthly_strategies:
        if _has_completed_run_this_month():
            logger.info("Pipeline already completed this month — skipping (monthly idempotency)")
            return PipelineResult(status="ok", strategy_name=config.active_strategy)
    elif _has_completed_run_today():
        logger.info("Pipeline already completed today — skipping (daily idempotency)")
        return PipelineResult(status="ok", strategy_name=config.active_strategy)

    run_id = _today_run_id()
    timeout_secs = config.backtest_timeout

    _write_pipeline_record(run_id, status="started", strategy=config.active_strategy)
    logger.info("Pipeline triggered: strategy=%s, run_id=%s, timeout=%ds",
                config.active_strategy, run_id, timeout_secs)

    try:
        result = await asyncio.wait_for(
            _execute_pipeline_inner(config),
            timeout=timeout_secs,
        )
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
        try:
            from src.notifications.factory import create_notifier
            notifier = create_notifier(config)
            if notifier.is_configured():
                await notifier.send("Pipeline Timeout", msg)
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
        return PipelineResult(status="error", strategy_name=config.active_strategy, error=msg)

    except Exception as exc:
        msg = f"Pipeline crashed: {exc}"
        logger.exception("Pipeline failed")
        _write_pipeline_record(run_id, status="failed", strategy=config.active_strategy, error=msg)
        from src.core.models import TradingInvariantError
        if isinstance(exc, TradingInvariantError):
            logger.critical("INVARIANT VIOLATION in pipeline: %s — triggering kill switch", exc)
            try:
                from src.api.state import get_app_state
                state = get_app_state()
                state.kill_switch_fired = True
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
            try:
                from src.notifications.factory import create_notifier
                notifier = create_notifier(config)
                if notifier.is_configured():
                    await notifier.send("INVARIANT VIOLATION", f"Pipeline stopped: {exc}")
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
        return PipelineResult(status="error", strategy_name=config.active_strategy, error=msg)


async def _execute_pipeline_inner(config: "TradingConfig") -> PipelineResult:
    """Core pipeline logic (extracted for timeout wrapping)."""
    run_id = _today_run_id()
    from src.api.state import get_app_state
    from src.data.sources import create_fundamentals
    from src.notifications.factory import create_notifier
    from src.strategy.base import Context
    from src.strategy.registry import resolve_strategy

    # T1 + P6: 市場時段檢查（live mode only）
    if config.mode == "live":
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
        if not (8 <= now.hour <= 14):
            logger.info("Pipeline skipped: outside trading hours (%d:00)", now.hour)
            return PipelineResult(status="skipped", strategy_name=config.active_strategy,
                                 error=f"Outside trading hours: {now.hour}:00")

    state = get_app_state()
    notifier = create_notifier(config)

    async with state.mutation_lock:
        if state.portfolio.nav_sod == 0 and state.portfolio.nav > 0:
            state.portfolio.nav_sod = state.portfolio.nav

    if not state.execution_service.is_initialized:
        logger.error("ExecutionService not initialized, skipping pipeline")
        return PipelineResult(status="error", error="ExecutionService not initialized")

    try:
        import json as _json
        _params = _json.loads(config.active_strategy_params) if config.active_strategy_params else None
        strategy = resolve_strategy(config.active_strategy, _params)
    except (ValueError, _json.JSONDecodeError) as e:
        return PipelineResult(status="error", error=f"Strategy resolution failed: {e}")

    # 1. 數據更新 + 品質閘門
    universe = _get_tw_universe_fallback()
    if not universe:
        universe = list(state.portfolio.positions.keys())
    if not universe:
        return PipelineResult(status="error", strategy_name=strategy.name(), error="Empty universe")

    if config.pipeline_data_update:
        from src.data.refresh import refresh_all_trading_data

        datasets_to_refresh = ["price"]
        revenue_strategies = {"revenue_momentum", "revenue_momentum_hedged", "trust_follow"}
        if strategy.name() in revenue_strategies:
            datasets_to_refresh.append("revenue")

        logger.info("Refreshing datasets: %s", datasets_to_refresh)
        reports = await refresh_all_trading_data(symbols=universe, datasets=datasets_to_refresh)
        for r in reports:
            logger.info("Refresh: %s", r.summary())
            if not r.ok:
                msg = f"Data refresh failed: {r.summary()}"
                logger.error(msg)
                if notifier.is_configured():
                    try:
                        await notifier.send("Pipeline Error", msg)
                    except Exception:
                        logger.debug("Suppressed exception", exc_info=True)
                return PipelineResult(status="data_failed", strategy_name=strategy.name(), error=msg)

    from src.data.quality_gate import pre_trade_quality_gate
    gate = pre_trade_quality_gate(universe)
    if not gate.passed:
        msg = f"Quality gate BLOCKED: {'; '.join(gate.blocking)}"
        logger.error(msg)
        if notifier.is_configured():
            try:
                await notifier.send("Quality Gate BLOCKED", msg)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
        return PipelineResult(status="data_failed", strategy_name=strategy.name(), error=msg)
    if gate.warnings:
        logger.warning("Quality gate warnings: %s", gate.warnings)

    # 2. 建立 Context
    from src.data.data_catalog import get_catalog, require_df, DataNotAvailableError
    from src.data.feed import HistoricalFeed
    _catalog = get_catalog()
    feed = HistoricalFeed()
    for _sym in universe:
        try:
            _result = _catalog.get_result("price", _sym)
            _df = require_df(_result)
            if "close" not in _df.columns:
                logger.warning("Price data for %s has no 'close' column — skipping", _sym)
                continue
            if not isinstance(_df.index, pd.DatetimeIndex):
                _df.index = pd.to_datetime(_df.index)
            feed.load(_sym, _df)
        except DataNotAvailableError as exc:
            logger.warning("Price data unavailable for %s: %s — skipping", _sym, exc)
    fundamentals = create_fundamentals(config.data_source)
    import datetime as _dt
    ctx = Context(
        feed=feed, portfolio=state.portfolio,
        fundamentals_provider=fundamentals,
        current_time=_dt.datetime.now(),
    )

    # 3. 執行策略
    target_weights = strategy.on_bar(ctx)

    # AL-3: Pipeline invariant checks
    if target_weights:
        import math
        from src.core.models import TradingInvariantError

        for sym, w in target_weights.items():
            if math.isnan(w) or math.isinf(w):
                raise TradingInvariantError(f"I13: Weight for {sym} is {w}")
        total_weight = sum(abs(w) for w in target_weights.values())
        if total_weight > 1.05:
            raise TradingInvariantError(f"I12: Total weight {total_weight:.2f} > 1.05")

    if not target_weights:
        has_positions = bool(state.portfolio.positions)
        if has_positions:
            logger.warning(
                "Strategy %s returned empty weights but portfolio has %d positions — will liquidate.",
                strategy.name(), len(state.portfolio.positions),
            )
            target_weights = {}
        else:
            logger.warning(
                "Strategy %s returned empty weights (universe=%d symbols, date=%s).",
                strategy.name(), len(universe), ctx.now().strftime("%Y-%m-%d") if ctx.now() else "unknown",
            )
            return PipelineResult(status="no_weights", strategy_name=strategy.name())

    logger.info("Strategy %s: %d targets", strategy.name(), len(target_weights))
    _save_selection_log(target_weights, strategy.name())

    # 4. 風控 + 下單
    all_needed = set(target_weights.keys()) | set(state.portfolio.positions.keys())
    prices: dict[str, Any] = {}
    volumes: dict[str, Any] = {}
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
        logger.warning(
            "Missing prices for %d/%d symbols: %s",
            len(missing_prices), len(all_needed), missing_prices[:10],
        )

    from src.core.trading_pipeline import execute_from_weights

    if config.mode == "paper":
        from src.execution.broker.simulated import SimBroker, SimConfig
        _sim_config = SimConfig(
            commission_rate=config.commission_rate,
            tax_rate=config.tax_rate,
            slippage_bps=config.default_slippage_bps,
            price_limit_pct=0.10,
            partial_fill=True,
            check_odd_lot_session=True,
        )
        _broker = SimBroker(_sim_config)
        current_bars = _build_current_bars(all_needed, feed)
    else:
        _broker = state.execution_service
        current_bars = None

    async with state.mutation_lock:
        if hasattr(state, 'kill_switch_fired') and state.kill_switch_fired:
            logger.warning("Kill switch fired during strategy calculation — aborting")
            try:
                from src.alpha.auto.paper_deployer import PaperDeployer
                deployer = PaperDeployer.get_instance()
                for d in deployer.get_active():
                    deployer.stop(d.name, reason="main_kill_switch")
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
            return PipelineResult(status="aborted", strategy_name=strategy.name(), error="Kill switch fired")

        try:
            from src.execution.trade_ledger import log_intent
            for sym, weight in target_weights.items():
                if sym in prices and prices[sym] > 0:
                    log_intent(
                        symbol=sym,
                        side="BUY" if weight > 0 else "SELL",
                        quantity=0,
                        expected_price=float(prices[sym]),
                        strategy=strategy.name(),
                        run_id=run_id,
                    )
        except Exception:
            logger.debug("Intent logging failed (non-blocking)", exc_info=True)

        trades = execute_from_weights(
            target_weights=target_weights,
            portfolio=state.portfolio,
            risk_engine=state.risk_engine,
            prices=prices,
            volumes=volumes if volumes else None,
            broker=_broker,
            current_bars=current_bars,
            market_lot_sizes=config.market_lot_sizes,
            fractional_shares=config.fractional_shares,
            check_invariants=True,
        )
        if trades:
            _save_trade_log(trades, strategy.name(), signal_prices=prices)

        # Live mode: wait for async fills
        if config.mode == "live" and not trades:
            import asyncio as _aio
            n_orders = 0
            try:
                from src.execution.trade_ledger import get_today_entries
                n_orders = sum(1 for e in get_today_entries() if e.get("type") == "intent")
            except Exception:
                n_orders = len(target_weights)
            if n_orders > 0:
                logger.info("Live mode: waiting up to 60s for %d async fills...", n_orders)
                for _ in range(12):
                    await _aio.sleep(5)
                    try:
                        from src.execution.trade_ledger import get_today_entries
                        fills = [e for e in get_today_entries() if e.get("type") == "fill"]
                        if len(fills) >= n_orders:
                            logger.info("Live mode: %d/%d fills received", len(fills), n_orders)
                            break
                    except Exception:
                        logger.debug("Suppressed exception", exc_info=True)
                else:
                    logger.warning("Live mode: timeout waiting for fills (%d orders)", n_orders)

        if hasattr(_broker, 'rejected_log') and _broker.rejected_log:
            for rej in _broker.rejected_log:
                logger.warning("Order REJECTED: %s — %s", rej.instrument.symbol, rej.reject_reason)

        state.portfolio.nav_sod = state.portfolio.nav
        from src.api.state import save_portfolio
        save_portfolio(state.portfolio)

    n_trades = len(trades) if trades else 0
    n_targets = len(target_weights)
    logger.info("Pipeline done: %d trades (of %d targets), NAV=%s", n_trades, n_targets, state.portfolio.nav)
    if n_trades < n_targets:
        logger.warning(
            "Pipeline: %d/%d targets skipped (likely price > allocation or missing data).",
            n_targets - n_trades, n_targets,
        )

    deviations = _reconcile(target_weights, state.portfolio)
    if deviations:
        logger.warning("Reconciliation: %d deviations > 2%%", len(deviations))
        if len(deviations) >= 5 and notifier.is_configured():
            try:
                import asyncio as _aio
                _aio.ensure_future(notifier.send(
                    "Reconciliation Alert",
                    f"{len(deviations)} positions deviate > 2% from target.",
                ))
            except Exception:
                logger.debug("Reconciliation notification failed", exc_info=True)

    _record_backtest_comparison(
        strategy_name=strategy.name(),
        paper_nav=float(state.portfolio.nav),
        paper_trades=n_trades,
        target_weights=target_weights,
    )

    if notifier.is_configured():
        deviation_text = f"\nDeviations: {len(deviations)} symbols > 2%" if deviations else ""
        summary = (
            f"Pipeline [{strategy.name()}]: {n_trades} trades, "
            f"{len(target_weights)} targets, NAV={float(state.portfolio.nav):,.0f}"
            f"{deviation_text}"
        )
        try:
            await notifier.send("Trading Pipeline", summary)
        except Exception:
            logger.debug("Notification failed", exc_info=True)

    _save_nav_snapshot(state.portfolio)
    _write_daily_report(state.portfolio, strategy.name(), n_trades, target_weights)

    return PipelineResult(status="ok", n_trades=n_trades, strategy_name=strategy.name())


def _build_current_bars(symbols: set[str], feed: Any) -> dict[str, dict]:
    """Build current_bars for SimBroker: try realtime (yfinance) first, fall back to parquet."""
    current_bars: dict[str, dict] = {}
    _realtime_fetched = 0
    try:
        import yfinance as _yf
        for s in symbols:
            try:
                _t = _yf.Ticker(s)
                _d = _t.history(period="1d")
                if _d is not None and not _d.empty:
                    _r = _d.iloc[-1]
                    _prev = 0.0
                    try:
                        _pb = feed.get_bars(s, start=None, end=None)
                        if _pb is not None and len(_pb) >= 2:
                            _prev = float(_pb["close"].iloc[-2])
                        elif _pb is not None and len(_pb) >= 1:
                            _prev = float(_pb["close"].iloc[-1])
                    except Exception:
                        logger.debug("Suppressed exception", exc_info=True)
                    current_bars[s] = {
                        "open": float(_r.get("Open", _r.get("Close", 0))),
                        "high": float(_r.get("High", _r.get("Close", 0))),
                        "low": float(_r.get("Low", _r.get("Close", 0))),
                        "close": float(_r.get("Close", 0)),
                        "volume": float(_r.get("Volume", 0)),
                        "prev_close": _prev,
                    }
                    _realtime_fetched += 1
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
    except ImportError:
        logger.debug("Suppressed exception", exc_info=True)

    for s in symbols:
        if s not in current_bars:
            try:
                b = feed.get_bars(s, start=None, end=None)
                if b is not None and len(b) >= 1:
                    last = b.iloc[-1]
                    _prev = float(b["close"].iloc[-2]) if len(b) >= 2 else float(last["close"])
                    current_bars[s] = {
                        "open": float(last.get("open", last["close"])),
                        "high": float(last.get("high", last["close"])),
                        "low": float(last.get("low", last["close"])),
                        "close": float(last["close"]),
                        "volume": float(last.get("volume", 0)),
                        "prev_close": _prev,
                    }
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

    logger.info("Paper SimBroker: %d realtime + %d parquet = %d current_bars",
                _realtime_fetched, len(current_bars) - _realtime_fetched, len(current_bars))
    return current_bars
