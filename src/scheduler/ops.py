"""Daily operations orchestrator — unified entry point for all daily tasks.

Replaces scattered cron jobs with a single daily_ops flow:
  trading day check → heartbeat → TWSE data → execute_pipeline → heartbeat → EOD

execute_pipeline is called as-is (refresh + QG + strategy + broker + reconcile).
daily_ops adds: trading day awareness, TWSE snapshot, heartbeat, EOD summary.

daily_ops < 100 lines (audit condition).
"""

from __future__ import annotations

import logging
from datetime import date

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

    # Fetch TWSE/TPEX daily snapshot (OHLCV + institutional + PER + margin + market summary)
    twse_result = await _fetch_twse_snapshot()

    # Yahoo daily price refresh (every trading day, not just rebalance days)
    await _yahoo_daily_refresh()

    # FinMind incremental refresh — frequency-aware (daily/weekly/monthly/quarterly)
    data_refresh_result = await _finmind_scheduled_refresh(today)

    # TDCC weekly shareholder snapshot (every Friday or last trading day of week)
    if today.weekday() == 4:  # Friday
        await _tdcc_weekly_snapshot()

    # ── Trading ──────────────────────────────────────────────────────
    pipeline_result = None
    if _is_rebalance_day(today, config):
        from src.scheduler.jobs import execute_pipeline
        pipeline_result = await execute_pipeline(config)
        n_trades = pipeline_result.n_trades if pipeline_result else 0
        await heartbeat("trade", f"Pipeline 完成：{n_trades} 筆交易")
    else:
        await heartbeat("skip", "非再平衡日，跳過交易")

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
        "data_refresh": data_refresh_result,
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
    except Exception:
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
    """Fetch today's TWSE+TPEX snapshots: OHLCV, institutional, PER, margin, market summary."""
    import asyncio

    def _do_fetch() -> str:
        from src.data.sources.twse import (
            fetch_all_daily, fetch_twse_institutional,
            fetch_all_per, fetch_twse_margin_all, fetch_twse_market_summary,
        )
        from src.data.registry import write_path
        from src.data.refresh import _atomic_write
        import pandas as pd

        results = []

        def _append_per_symbol(df: pd.DataFrame, dataset: str, label: str,
                               date_col: str = "date", use_index: bool = False) -> None:
            """Save per-symbol data with append + dedup."""
            if df.empty:
                results.append(f"{label}: no data")
                return
            saved = 0
            for sym, group in df.groupby("symbol"):
                path = write_path(str(sym), dataset, "twse")
                if use_index:
                    new_data = group.set_index(pd.DatetimeIndex(pd.to_datetime(group[date_col])))
                    new_data = new_data.drop(columns=["symbol", date_col], errors="ignore")
                else:
                    new_data = group.drop(columns=["symbol"], errors="ignore")
                if path.exists():
                    try:
                        existing = pd.read_parquet(path)
                        if use_index:
                            combined = pd.concat([existing, new_data])
                            combined = combined[~combined.index.duplicated(keep="last")].sort_index()
                        else:
                            combined = pd.concat([existing, new_data], ignore_index=True)
                            if date_col in combined.columns:
                                combined[date_col] = pd.to_datetime(combined[date_col])
                                combined = combined.drop_duplicates(subset=[date_col], keep="last")
                                combined = combined.sort_values(date_col).reset_index(drop=True)
                    except Exception:
                        combined = new_data
                else:
                    combined = new_data
                _atomic_write(combined, path, source="twse", dataset=dataset)
                saved += 1
            results.append(f"{label}: {saved}")

        # OHLCV (DatetimeIndex format)
        try:
            _append_per_symbol(fetch_all_daily(), "price", "OHLCV", use_index=True)
        except Exception as e:
            logger.warning("TWSE OHLCV failed: %s", e)
            results.append("OHLCV: failed")

        # Institutional (date column format)
        try:
            _append_per_symbol(fetch_twse_institutional(), "institutional", "Institutional")
        except Exception as e:
            logger.warning("TWSE institutional failed: %s", e)
            results.append("Institutional: failed")

        # PER/PBR/Dividend Yield
        try:
            _append_per_symbol(fetch_all_per(), "per", "PER")
        except Exception as e:
            logger.warning("TWSE PER failed: %s", e)
            results.append("PER: failed")

        # Margin Trading
        try:
            _append_per_symbol(fetch_twse_margin_all(), "margin", "Margin")
        except Exception as e:
            logger.warning("TWSE margin failed: %s", e)
            results.append("Margin: failed")

        # Market Summary (single file, not per-symbol)
        try:
            mkt_df = fetch_twse_market_summary()
            if not mkt_df.empty:
                from pathlib import Path
                mkt_path = Path("data/twse/market_summary.parquet")
                mkt_path.parent.mkdir(parents=True, exist_ok=True)
                if mkt_path.exists():
                    try:
                        existing = pd.read_parquet(mkt_path)
                        mkt_df = pd.concat([existing, mkt_df], ignore_index=True)
                        mkt_df["date"] = pd.to_datetime(mkt_df["date"])
                        mkt_df = mkt_df.drop_duplicates(subset=["date"], keep="last")
                        mkt_df = mkt_df.sort_values("date").reset_index(drop=True)
                    except Exception:
                        pass
                _atomic_write(mkt_df, mkt_path, source="twse", dataset="market_summary")
                results.append(f"Market: {len(mkt_df)}d")
            else:
                results.append("Market: no data")
        except Exception as e:
            logger.warning("TWSE market summary failed: %s", e)
            results.append("Market: failed")

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


async def _finmind_scheduled_refresh(today: date) -> str:
    """Refresh FinMind datasets based on their configured frequency.

    Only refreshes datasets that are due today:
    - daily: every trading day (per, institutional, margin, securities_lending)
    - weekly: Monday (shareholding)
    - monthly: day 11 (revenue), day 1 (dividend)
    - quarterly: day 16 of May/Aug/Nov (financial_statement, cash_flows, balance_sheet)
    """
    import asyncio

    def _do_refresh() -> str:
        from src.data.registry import REGISTRY
        from src.data.refresh import refresh_dataset_sync

        due: list[str] = []
        for name, ds in REGISTRY.items():
            if not ds.source_dirs or not ds.finmind_method:
                continue  # finlab-only or no provider
            if name == "price":
                continue  # handled by _yahoo_daily_refresh + _fetch_twse_snapshot

            if ds.frequency == "daily":
                due.append(name)
            elif ds.frequency == "weekly" and today.weekday() == 0:  # Monday
                due.append(name)
            elif ds.frequency == "monthly":
                # revenue on day 11, dividend on day 1
                if name == "revenue" and today.day == 11:
                    due.append(name)
                elif name == "dividend" and today.day == 1:
                    due.append(name)
            elif ds.frequency == "quarterly" and today.day == 16 and today.month in (5, 8, 11):
                due.append(name)

        if not due:
            return "no datasets due"

        results = []
        for name in due:
            try:
                report = refresh_dataset_sync(name)
                results.append(f"{name}:{report.updated}u/{report.skipped}s")
            except Exception as e:
                results.append(f"{name}:ERR")
                logger.warning("Refresh %s failed: %s", name, e)

        summary = " | ".join(results)
        logger.info("FinMind refresh: %s", summary)
        return summary

    return await asyncio.to_thread(_do_refresh)


async def _tdcc_weekly_snapshot() -> str:
    """Download TDCC shareholder distribution weekly snapshot."""
    import asyncio

    def _do_tdcc() -> str:
        import io
        import requests
        import pandas as pd
        from pathlib import Path

        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(
                "https://opendata.tdcc.com.tw/getOD.ashx?id=1-5",
                headers=headers, timeout=30, allow_redirects=False,
            )
            if r.status_code != 200 or len(r.content) < 1000:
                return "TDCC: no data"

            text = r.content.decode("utf-8-sig")
            df = pd.read_csv(io.StringIO(text))
            df.columns = ["date", "stock_id", "level", "holders", "shares", "pct"]
            df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
            df["stock_id"] = df["stock_id"].str.strip()

            report_date = df["date"].iloc[0].strftime("%Y%m%d")
            out_dir = Path("data/tdcc")
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"shareholding_{report_date}.parquet"

            if out_path.exists():
                return f"TDCC: {report_date} already exists"

            df.to_parquet(out_path, index=False)
            logger.info("TDCC snapshot saved: %s (%d rows)", out_path, len(df))
            return f"TDCC: {report_date} ({df['stock_id'].nunique()} stocks)"
        except Exception as e:
            logger.warning("TDCC download failed: %s", e)
            return f"TDCC: failed ({e})"

    return await asyncio.to_thread(_do_tdcc)


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
