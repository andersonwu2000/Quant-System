"""Background monitoring tasks extracted from app.py lifespan."""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def start_background_tasks(state, config, ws_manager) -> tuple[list[asyncio.Task], object]:
    """Create and start monitoring loop, kill switch monitor, scheduler.

    Returns (list of background tasks, scheduler) for shutdown.
    """
    tasks: list[asyncio.Task] = []

    if config.mode in ("paper", "live"):
        tasks.append(asyncio.create_task(_monitoring_loop(state, ws_manager)))

    kill_switch_task = asyncio.create_task(_kill_switch_monitor(state, config, ws_manager))
    tasks.append(kill_switch_task)

    ws_manager.start_ping_task()

    scheduler = _start_scheduler(config)

    return tasks, scheduler


async def _monitoring_loop(state, ws_manager) -> None:
    """Paper trading integrated monitor -- runs inside API server."""
    import json as _json
    from pathlib import Path as _Path
    from datetime import datetime as _dt, timedelta as _tdelta, timezone as _tz

    _tw = _tz(_tdelta(hours=8))
    snap_dir = _Path("data/paper_trading/snapshots")
    snap_dir.mkdir(parents=True, exist_ok=True)
    report_dir = _Path("docs/paper-trading")
    report_dir.mkdir(parents=True, exist_ok=True)
    _daily_report_done: str = ""

    while True:
        await asyncio.sleep(3600)  # every hour
        try:
            now = _dt.now(_tw)
            ts = now.strftime("%Y-%m-%d_%H%M")
            nav = float(state.portfolio.nav)
            cash = float(state.portfolio.cash)
            n_pos = len(state.portfolio.positions)

            # 1. Snapshot
            snap = {
                "timestamp": now.isoformat(),
                "nav": nav,
                "cash": cash,
                "n_positions": n_pos,
                "position_symbols": sorted(state.portfolio.positions.keys()),
            }
            (snap_dir / f"{ts}.json").write_text(
                _json.dumps(snap, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            logger.info("Monitor snapshot: NAV=%.0f, positions=%d", nav, n_pos)

            # 2. Anomaly detection
            alerts = []
            prev_snaps = sorted(snap_dir.glob("*.json"))
            if len(prev_snaps) >= 2:
                try:
                    prev = _json.loads(prev_snaps[-2].read_text(encoding="utf-8"))
                    prev_nav = prev.get("nav", nav)
                    if prev_nav > 0:
                        change = (nav - prev_nav) / prev_nav
                        if change < -0.03:
                            alerts.append(f"NAV dropped {change:.1%}")
                except Exception:
                    # data-quality: corrupted snapshot JSON
                    logger.debug("Suppressed exception", exc_info=True)
            if n_pos == 0 and nav > 100000:
                alerts.append("No positions but significant NAV")

            for alert in alerts:
                logger.warning("MONITOR ANOMALY: %s", alert)
                await ws_manager.broadcast("alerts", {
                    "type": "monitor_anomaly",
                    "message": alert,
                })

            # 3. Daily report (after 14:00 TW market close)
            today = now.strftime("%Y-%m-%d")
            if now.hour >= 14 and _daily_report_done != today:
                _daily_report_done = today
                today_snaps = []
                for p in sorted(snap_dir.glob(f"{today}_*.json")):
                    try:
                        today_snaps.append(_json.loads(p.read_text(encoding="utf-8")))
                    except Exception:
                        # data-quality: corrupted snapshot file -- skip
                        continue
                if today_snaps:
                    first_nav = today_snaps[0]["nav"]
                    last_nav = today_snaps[-1]["nav"]
                    daily_ret = (last_nav - first_nav) / first_nav if first_nav > 0 else 0
                    try:
                        from src.core.config import get_config as _gc
                        _initial = _gc().backtest_initial_cash
                    except Exception:
                        _initial = 10_000_000
                    total_ret = (last_nav - _initial) / _initial if _initial > 0 else 0
                    report_lines = [
                        f"# Paper Trading Daily Report - {today}",
                        "",
                        "| Metric | Value |",
                        "|--------|-------|",
                        f"| NAV | ${last_nav:,.0f} |",
                        f"| Daily Return | {daily_ret:+.2%} |",
                        f"| Total Return | {total_ret:+.2%} |",
                        f"| Positions | {today_snaps[-1].get('n_positions', 0)} |",
                        f"| Snapshots | {len(today_snaps)} |",
                    ]
                    (report_dir / f"{today}_daily.md").write_text(
                        "\n".join(report_lines), encoding="utf-8"
                    )
                    logger.info("Daily report generated: %s", today)

        except Exception:
            # expected: monitor iteration failure -- non-critical, will retry next hour
            logger.debug("Monitor loop error", exc_info=True)


async def _kill_switch_monitor(state, config, ws_manager) -> None:
    """AL-4 heartbeat check, daily drawdown check, liquidation."""
    while True:
        await asyncio.sleep(5)
        try:
            # D2: skip if already fired (wait for manual reset via API)
            if state.kill_switch_fired:
                continue

            # AL-4: Heartbeat kill switch -- check tick data freshness
            _rtm = getattr(state, 'realtime_risk_monitor', None)
            if _rtm is not None:
                _hb_status = _rtm.check_heartbeat()
                if _hb_status == "kill_switch" and "heartbeat_kill" not in _rtm._alerts_sent:
                    _rtm._alerts_sent.add("heartbeat_kill")
                    _rtm._heartbeat_paused = True
                    logger.critical(
                        "HEARTBEAT KILL SWITCH: No valid tick for >15 minutes during market hours"
                    )
                    async with state.mutation_lock:
                        state.kill_switch_fired = True
                    await ws_manager.broadcast("alerts", {
                        "type": "heartbeat_kill_switch",
                        "message": "No valid tick data for >15 minutes — all trading stopped",
                    })
                    try:
                        from src.notifications.factory import create_notifier
                        _notifier = create_notifier(config)
                        if _notifier.is_configured():
                            await _notifier.send(
                                "HEARTBEAT KILL SWITCH",
                                "No valid tick data for >15 minutes during market hours. "
                                "All trading stopped. Manual restart required.",
                            )
                    except Exception:
                        # expected: external API failure (notification service)
                        logger.debug("Heartbeat notification failed", exc_info=True)
                    continue
                elif _hb_status == "paused" and not _rtm._heartbeat_paused:
                    _rtm._heartbeat_paused = True
                    logger.warning(
                        "HEARTBEAT WARNING: No valid tick for >5 minutes — new orders paused"
                    )
                    await ws_manager.broadcast("alerts", {
                        "type": "heartbeat_warning",
                        "message": "No valid tick data for >5 minutes — new orders paused",
                    })

            if state.risk_engine.kill_switch(state.portfolio, config.max_daily_drawdown_pct):
                # Sanity check: NAV vs SOD ratio must be reasonable
                _nav = float(state.portfolio.nav)
                _sod = float(state.portfolio.nav_sod) if state.portfolio.nav_sod > 0 else _nav
                if _sod > 0 and (_nav / _sod > 5.0 or _nav / _sod < 0.05):
                    logger.warning(
                        "Kill switch (path A) suppressed: NAV/SOD=%.1f unreasonable "
                        "(NAV=%s, SOD=%s) — likely bad price data",
                        _nav / _sod, _nav, _sod,
                    )
                    continue

                # B-7 fix: set flag and re-check inside lock to prevent double liquidation
                async with state.mutation_lock:
                    if state.kill_switch_fired:
                        continue  # another path already handled it
                    state.kill_switch_fired = True
                    for name in list(state.strategies):
                        state.strategies[name]["status"] = "stopped"
                    state.oms.cancel_all()

                    # Kill switch liquidation controlled by config (paper=alert only)
                    if config.enable_kill_switch_liquidation and state.execution_service.is_initialized:
                        liq_orders = state.risk_engine.generate_liquidation_orders(
                            state.portfolio
                        )
                        if liq_orders:
                            logger.critical(
                                "Kill switch: submitting %d liquidation orders",
                                len(liq_orders),
                            )
                            trades = state.execution_service.submit_orders(
                                liq_orders, state.portfolio
                            )
                            if trades:
                                from src.execution.oms import apply_trades
                                apply_trades(state.portfolio, trades, check_invariants=True)
                                logger.critical(
                                    "Kill switch: %d liquidation trades executed, NAV=%s",
                                    len(trades), state.portfolio.nav,
                                )
                    elif not config.enable_kill_switch_liquidation:
                        logger.warning(
                            "Kill switch triggered in %s mode — alert only, no liquidation",
                            config.mode,
                        )

                _dd_pct = float(state.portfolio.daily_drawdown) * 100
                _pos_list = ", ".join(
                    f"{s}({float(p.quantity):.0f})"
                    for s, p in list(state.portfolio.positions.items())[:5]
                )
                _ks_detail = (
                    f"Trigger: daily drawdown {_dd_pct:.1f}% > 5%\n"
                    f"NAV: {float(state.portfolio.nav):,.0f} "
                    f"(SOD: {float(state.portfolio.nav_sod):,.0f})\n"
                    f"Positions: {_pos_list or 'none'}"
                )

                await ws_manager.broadcast("alerts", {
                    "type": "kill_switch",
                    "message": f"Kill switch triggered — {_ks_detail}",
                })
                # Notify via Discord/LINE/Telegram
                try:
                    from src.notifications.factory import create_notifier
                    _notifier = create_notifier(config)
                    if _notifier.is_configured():
                        await _notifier.send(
                            "KILL SWITCH",
                            "All strategies stopped, positions liquidated.\n\n"
                            + _ks_detail,
                        )
                except Exception:
                    # expected: external API failure (notification service)
                    logger.debug("Kill switch notification failed", exc_info=True)
        except Exception:
            # invariant: kill switch monitor should not crash -- log and continue
            logger.warning("Kill switch monitor error", exc_info=True)


def _start_scheduler(config):
    """Start the scheduler service, with one retry on failure. Returns scheduler."""
    from src.scheduler import SchedulerService

    scheduler = SchedulerService()
    scheduler.start(config)
    if not scheduler.is_running and config.scheduler_enabled:
        logger.warning("Scheduler failed to start on first attempt, retrying...")
        import time as _time
        _time.sleep(1)
        scheduler.start(config)

    from src.api.state import get_app_state as _gs
    _gs().scheduler = scheduler

    if scheduler.is_running:
        logger.info("Scheduler confirmed running")
    else:
        logger.error("Scheduler failed to start — daily_ops/eod_ops will NOT run automatically")

    return scheduler


async def shutdown_app(state, config, scheduler, bg_tasks, ws_manager) -> None:
    """Graceful shutdown: cancel tasks, save state, close connections."""
    logger.info("Graceful shutdown initiated")
    try:
        if scheduler is not None:
            scheduler.stop()
        for task in bg_tasks:
            task.cancel()
        ws_manager.stop_ping_task()

        from src.api.state import get_app_state as _get_state, save_portfolio
        state = _get_state()

        # Log pending orders before shutdown
        try:
            if state.execution_service and state.execution_service.is_initialized:
                open_orders = state.oms.get_open_orders()
                if open_orders:
                    logger.warning(
                        "Shutting down with %d pending orders", len(open_orders),
                    )
                else:
                    logger.info("No pending orders at shutdown")
        except Exception:
            # expected: OMS/execution service partially torn down
            logger.warning("Failed to check pending orders", exc_info=True)

        # Save portfolio state before shutdown (crash recovery)
        try:
            if state.portfolio:
                save_portfolio(state.portfolio)
                logger.info(
                    "Portfolio saved on shutdown (%d positions)",
                    len(state.portfolio.positions),
                )
        except Exception:
            # invariant: portfolio save should not fail -- critical data loss risk
            logger.exception("Failed to save portfolio on shutdown")

        state.execution_service.shutdown()
        await ws_manager.close_all()
    except Exception:
        # invariant: shutdown should complete cleanly -- log full trace
        logger.exception("Error during shutdown sequence")
    logger.info("Shutdown complete")
