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

    # Fetch TWSE/TPEX daily snapshot (OHLCV + institutional)
    twse_result = await _fetch_twse_snapshot()

    # Yahoo daily price refresh (every trading day, not just rebalance days)
    yahoo_result = await _yahoo_daily_refresh()

    # ── Trading ──────────────────────────────────────────────────────
    pipeline_result = None
    if _is_rebalance_day(today, config):
        from src.scheduler.jobs import execute_pipeline
        pipeline_result = await execute_pipeline(config)
        n_trades = pipeline_result.n_trades if pipeline_result else 0
        await heartbeat("trade", f"Pipeline 完成：{n_trades} 筆交易")
    else:
        await heartbeat("skip", f"非再平衡日，跳過交易")

    # ── Deployed strategies (daily — paper trading with independent NAV) ──
    try:
        from src.alpha.auto.paper_deployer import PaperDeployer
        from src.alpha.auto.deployed_executor import (
            process_deploy_queue, execute_deployed_strategies,
        )
        deployer = PaperDeployer.get_instance()
        n_queued = len(process_deploy_queue(deployer))
        deploy_results = execute_deployed_strategies(deployer)
        n_active = len(deploy_results)
        if n_queued or n_active:
            logger.info("Deployed strategies: %d queued, %d active executed", n_queued, n_active)
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
        # Rebalance on first trading day of each ISO week.
        # Check if any earlier weekday this week was a trading day — if not, today is first.
        from src.core.calendar import get_tw_calendar
        cal = get_tw_calendar()
        from datetime import timedelta
        for d in range(today.weekday()):
            earlier = today - timedelta(days=today.weekday() - d)
            if cal.is_trading_day(earlier):
                return False  # an earlier day this week was a trading day
        return True  # today is the first trading day of this week
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
    """Fetch today's TWSE+TPEX OHLCV + institutional to data/twse/."""
    import asyncio

    def _do_fetch() -> str:
        from src.data.sources.twse import fetch_all_daily, fetch_twse_institutional
        from src.data.registry import write_path
        from src.data.refresh import _atomic_write
        import pandas as pd
        from datetime import date as d

        results = []

        # ── OHLCV snapshot ───────────────────────────────────────
        try:
            ohlcv = fetch_all_daily()
            if not ohlcv.empty:
                saved = 0
                for sym, group in ohlcv.groupby("symbol"):
                    path = write_path(str(sym), "price", "twse")
                    group_df = group.set_index(pd.DatetimeIndex(pd.to_datetime(group["date"])))
                    group_df = group_df[["open", "high", "low", "close", "volume"]]
                    if path.exists():
                        try:
                            existing = pd.read_parquet(path)
                            combined = pd.concat([existing, group_df])
                            combined = combined[~combined.index.duplicated(keep="last")].sort_index()
                            _atomic_write(combined, path, source="twse", dataset="price")
                        except Exception:
                            pass
                    else:
                        _atomic_write(group_df, path, source="twse", dataset="price")
                    saved += 1
                results.append(f"OHLCV: {saved}")
            else:
                results.append("OHLCV: no data")
        except Exception as e:
            logger.warning("TWSE OHLCV failed: %s", e)
            results.append(f"OHLCV: failed")

        # ── Institutional (三大法人) ─────────────────────────────
        try:
            inst = fetch_twse_institutional()
            if not inst.empty:
                import pyarrow as pa
                import pyarrow.parquet as pq
                from datetime import datetime

                saved = 0
                for sym, group in inst.groupby("symbol"):
                    path = write_path(str(sym), "institutional", "twse")
                    if path.exists():
                        try:
                            existing = pd.read_parquet(path)
                            combined = pd.concat([existing, group], ignore_index=True)
                            combined["date"] = pd.to_datetime(combined["date"])
                            combined = combined.drop_duplicates(subset=["date"], keep="last")
                            combined = combined.sort_values("date").reset_index(drop=True)
                        except Exception:
                            combined = group
                    else:
                        combined = group

                    table = pa.Table.from_pandas(combined)
                    meta = {b"source": b"twse", b"dataset": b"institutional",
                            b"fetch_time": datetime.now().isoformat().encode()}
                    table = table.replace_schema_metadata({**(table.schema.metadata or {}), **meta})
                    path.parent.mkdir(parents=True, exist_ok=True)
                    pq.write_table(table, path)
                    saved += 1
                results.append(f"Institutional: {saved}")
            else:
                results.append("Institutional: no data")
        except Exception as e:
            logger.warning("TWSE institutional failed: %s", e)
            results.append("Institutional: failed")

        return " | ".join(results)

    return await asyncio.to_thread(_do_fetch)


async def _yahoo_daily_refresh() -> str:
    """Incremental Yahoo price update for all existing symbols."""
    import asyncio

    def _do_refresh() -> str:
        try:
            from src.data.refresh import refresh_dataset_sync
            report = refresh_dataset_sync("price")
            return f"Yahoo: {report.updated} updated, {report.skipped} fresh"
        except Exception as e:
            logger.warning("Yahoo daily refresh failed: %s", e)
            return f"Yahoo: failed ({e})"

    return await asyncio.to_thread(_do_refresh)


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
