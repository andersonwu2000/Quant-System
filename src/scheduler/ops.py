"""Daily operations orchestrator — unified entry point for all daily tasks.

Replaces scattered cron jobs with a single daily_ops flow:
  trading day check → heartbeat → TWSE data → execute_pipeline → heartbeat → EOD

execute_pipeline is called as-is (refresh + QG + strategy + broker + reconcile).
daily_ops adds: trading day awareness, TWSE snapshot, heartbeat, EOD summary.

daily_ops < 100 lines (audit condition).
"""

from __future__ import annotations

import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)


async def daily_ops(config: object) -> dict:
    """每日運營統一入口。非交易日自動跳過。

    Flow:
      1. Trading day check
      2. Heartbeat: "系統啟動"
      3. TWSE/TPEX daily snapshot (data execute_pipeline doesn't fetch)
      4. execute_pipeline (refresh + QG + strategy + broker) — unchanged
      5. Heartbeat: "交易完成" or "非再平衡日"
      6. Schedule EOD at 13:30
    """
    from src.core.calendar import get_tw_calendar
    from src.scheduler.heartbeat import heartbeat

    cal = get_tw_calendar()
    today = date.today()

    # ── Gate: trading day ────────────────────────────────────────────
    if not cal.is_trading_day(today):
        await heartbeat("rest", f"今日休市 ({today})")
        return {"status": "holiday", "date": str(today)}

    # ── Pre-market ───────────────────────────────────────────────────
    await heartbeat("start", f"系統啟動，準備交易日 ({today})")

    # Fetch TWSE/TPEX daily snapshot (execute_pipeline only does Yahoo/FinMind)
    twse_result = await _fetch_twse_snapshot()

    # ── Trading ──────────────────────────────────────────────────────
    pipeline_result = None
    if _is_rebalance_day(today, config):
        from src.scheduler.jobs import execute_pipeline
        pipeline_result = await execute_pipeline(config)
        n_trades = pipeline_result.n_trades if pipeline_result else 0
        await heartbeat("trade", f"Pipeline 完成：{n_trades} 筆交易")
    else:
        await heartbeat("skip", f"非再平衡日，跳過交易")

    # ── Deployed strategies (Phase AG, monthly 12th) ─────────────────
    if today.day == 12:
        try:
            from src.scheduler import _pipeline_lock
            if not _pipeline_lock.locked():
                async with _pipeline_lock:
                    from src.alpha.auto.paper_deployer import PaperDeployer
                    from src.alpha.auto.deployed_executor import (
                        process_deploy_queue, execute_deployed_strategies,
                    )
                    deployer = PaperDeployer.get_instance()
                    process_deploy_queue(deployer)
                    execute_deployed_strategies(deployer)
                    logger.info("Deployed strategies executed (monthly)")
        except Exception:
            logger.exception("Deployed strategies failed")

    return {
        "status": "completed",
        "date": str(today),
        "twse": twse_result,
        "pipeline": pipeline_result.status if pipeline_result else "skipped",
    }


async def eod_ops(config: object) -> dict:
    """收盤後流程。由 SchedulerService 在 13:30 觸發。"""
    from src.scheduler.heartbeat import heartbeat

    results = {}

    # 1. Broker reconcile (existing)
    try:
        from src.scheduler.jobs import execute_daily_reconcile
        results["reconcile"] = await execute_daily_reconcile(config)
    except Exception as e:
        logger.exception("Daily reconcile failed")
        results["reconcile"] = {"status": "error", "error": str(e)}

    # 2. Backtest reconcile (G1)
    try:
        from src.scheduler.jobs import execute_backtest_reconcile
        results["backtest_reconcile"] = await execute_backtest_reconcile()
    except Exception as e:
        logger.exception("Backtest reconcile failed")
        results["backtest_reconcile"] = {"status": "error"}

    # 3. Daily summary
    summary = await _generate_daily_summary()
    results["summary"] = summary

    await heartbeat("eod", f"EOD 完成 | {summary}")

    return results


def _is_rebalance_day(today: date, config: object) -> bool:
    """Check if today is a rebalance day based on config frequency."""
    freq = getattr(config, "rebalance_frequency", "monthly")
    cron = getattr(config, "trading_pipeline_cron", "3 9 11 * *")

    if freq == "daily":
        return True
    elif freq == "weekly":
        return today.weekday() == 0  # Monday
    elif freq == "biweekly":
        return today.day in (1, 15) or (today.day == 2 and today.weekday() == 0)
    else:
        # monthly: extract day from cron (e.g. "3 9 11 * *" → day 11)
        parts = cron.split()
        if len(parts) >= 3:
            try:
                rebalance_day = int(parts[2])
                return today.day == rebalance_day
            except ValueError:
                pass
        return today.day == 11  # fallback


async def _fetch_twse_snapshot() -> str:
    """Fetch today's TWSE+TPEX full-market snapshot to data/twse/."""
    import asyncio

    def _do_fetch() -> str:
        try:
            from src.data.sources.twse import fetch_all_daily, fetch_twse_institutional
            from src.data.registry import write_path
            from src.data.refresh import _atomic_write
            import pandas as pd
            from datetime import date as d

            # OHLCV snapshot
            ohlcv = fetch_all_daily()
            if not ohlcv.empty:
                today_str = ohlcv["date"].iloc[0] if "date" in ohlcv.columns else str(d.today())
                saved = 0
                for sym, group in ohlcv.groupby("symbol"):
                    path = write_path(str(sym), "price", "twse")
                    # Append to existing
                    if path.exists():
                        try:
                            existing = pd.read_parquet(path)
                            group_df = group.set_index(pd.DatetimeIndex(pd.to_datetime(group["date"])))
                            group_df = group_df[["open", "high", "low", "close", "volume"]]
                            combined = pd.concat([existing, group_df])
                            combined = combined[~combined.index.duplicated(keep="last")].sort_index()
                            _atomic_write(combined, path, source="twse", dataset="price")
                        except Exception:
                            pass
                    else:
                        group_df = group.set_index(pd.DatetimeIndex(pd.to_datetime(group["date"])))
                        group_df = group_df[["open", "high", "low", "close", "volume"]]
                        _atomic_write(group_df, path, source="twse", dataset="price")
                    saved += 1
                return f"TWSE+TPEX: {saved} symbols"
            return "TWSE: no data"
        except Exception as e:
            logger.warning("TWSE snapshot failed: %s", e)
            return f"TWSE: failed ({e})"

    return await asyncio.to_thread(_do_fetch)


async def _generate_daily_summary() -> str:
    """Generate daily summary string for Discord notification."""
    try:
        from src.api.state import get_app_state
        state = get_app_state()
        nav = float(state.portfolio.nav) if state.portfolio.nav else 0
        n_pos = len(state.portfolio.positions)
        cash = float(state.portfolio.cash) if state.portfolio.cash else 0
        return f"NAV={nav:,.0f} | {n_pos} positions | cash={cash:,.0f}"
    except Exception:
        return "Summary unavailable"
