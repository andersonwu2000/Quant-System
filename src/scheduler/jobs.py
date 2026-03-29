"""Scheduled job implementations — 連接策略引擎與執行服務。

Jobs:
- execute_pipeline: 統一交易管線（Phase S）
- execute_daily_reconcile: 收盤後自動對帳（broker vs system）
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
    """#2: 月度策略用 — 檢查本月是否已完成過 pipeline（防重啟後重複再平衡）。

    P-2 fix: 只擋有實際交易的 completed，不擋 0-trade 的結果（可能是數據問題）。
    """
    month_prefix = datetime.now().strftime("%Y-%m")
    if not PIPELINE_RUNS_DIR.exists():
        return False
    for path in PIPELINE_RUNS_DIR.glob(f"{month_prefix}*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("status") in ("completed", "ok") and record.get("n_trades", 0) > 0:
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



# execute_rebalance() removed — replaced by execute_pipeline() (Phase S)


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



# monthly_revenue_rebalance() removed — replaced by execute_pipeline() (Phase S)


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


def _save_trade_log(
    trades: list[Any],
    strategy_name: str,
    signal_prices: dict[str, Any] | None = None,
) -> None:
    """記錄每次 rebalance 的交易結果（含 run_id + 滑價追蹤）。

    signal_prices: 策略計算時的價格（最新收盤價）。
    fill_price vs signal_price 的差距 = implementation shortfall。
    """
    out_dir = Path("data/paper_trading/trades")
    out_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d_%H%M")
    trade_records = []
    total_shortfall_bps = 0.0
    n_with_prices = 0

    for t in trades:
        sym = str(getattr(t, "symbol", getattr(getattr(t, "instrument", None), "symbol", "?")))
        fill_price = float(getattr(t, "price", 0))
        sig_price = float(signal_prices.get(sym, 0)) if signal_prices else 0
        side = str(getattr(t, "side", ""))
        commission = float(getattr(t, "commission", 0))
        qty = float(getattr(t, "quantity", 0))

        # Implementation shortfall: (fill - signal) / signal × 10000 bps
        shortfall_bps = 0.0
        if sig_price > 0 and fill_price > 0:
            if "BUY" in side.upper():
                shortfall_bps = (fill_price - sig_price) / sig_price * 10000
            else:
                shortfall_bps = (sig_price - fill_price) / sig_price * 10000
            total_shortfall_bps += shortfall_bps
            n_with_prices += 1

        trade_records.append({
            "symbol": sym,
            "side": side,
            "quantity": str(getattr(t, "quantity", "")),
            "fill_price": f"{fill_price:.4f}",
            "signal_price": f"{sig_price:.4f}" if sig_price > 0 else "",
            "shortfall_bps": round(shortfall_bps, 2),
            "commission": f"{commission:.2f}",
            "notional": f"{fill_price * qty:.0f}" if fill_price > 0 else "",
        })

    avg_shortfall = total_shortfall_bps / n_with_prices if n_with_prices > 0 else 0.0
    total_commission = sum(float(r["commission"]) for r in trade_records)

    log = {
        "date": today,
        "run_id": _today_run_id(),
        "strategy": strategy_name,
        "n_trades": len(trades),
        "avg_shortfall_bps": round(avg_shortfall, 2),
        "total_commission": round(total_commission, 2),
        "trades": trade_records,
    }

    path = out_dir / f"{today}.json"
    with open(path, "w") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    logger.info(
        "Trade log saved: %s (%d trades, avg shortfall=%.1f bps, commission=%.0f)",
        path, len(trades), avg_shortfall, total_commission,
    )


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

    # T1 + P6: 市場時段檢查（live mode only — paper mode 模擬成交不需要）
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
        import json as _json
        _params = _json.loads(config.active_strategy_params) if config.active_strategy_params else None
        strategy = resolve_strategy(config.active_strategy, _params)
    except (ValueError, _json.JSONDecodeError) as e:
        return PipelineResult(status="error", error=f"Strategy resolution failed: {e}")

    # 1. 數據更新（失敗則中止，不用舊數據交易）
    if config.pipeline_data_update:
        # 1a. 價格數據增量更新（所有策略都需要）
        logger.info("Updating price data...")
        price_ok = await _async_price_update()
        if not price_ok:
            logger.warning("Price data update failed — continuing with cached data")

        # 1b. 營收數據更新（營收策略需要）
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
        has_positions = bool(state.portfolio.positions)
        if has_positions:
            # PT-3: empty weights with existing positions → sell all (strategy wants 0% exposure)
            logger.warning(
                "Strategy %s returned empty weights but portfolio has %d positions — will liquidate.",
                strategy.name(), len(state.portfolio.positions),
            )
            target_weights = {}  # proceed to execute_from_weights which will generate SELL orders
        else:
            logger.warning(
                "Strategy %s returned empty weights (universe=%d symbols, date=%s). "
                "Possible causes: no stocks pass filters, revenue data stale, or data feed issue.",
                strategy.name(), len(universe), ctx.now().strftime("%Y-%m-%d") if ctx.now() else "unknown",
            )
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
        logger.warning(
            "Missing prices for %d/%d symbols (will not be traded): %s",
            len(missing_prices), len(all_needed), missing_prices[:10],
        )

    # U1: 使用統一執行路徑（和回測共用 execute_from_weights）
    from src.core.trading_pipeline import execute_from_weights

    # Paper mode: use SimBroker (same as backtest) for realistic fills
    # Live mode: use SinopacBroker (real orders)
    if config.mode == "paper":
        from src.execution.broker.simulated import SimBroker, SimConfig
        _sim_config = SimConfig(
            commission_rate=config.commission_rate,
            tax_rate=config.tax_rate,
            slippage_bps=config.default_slippage_bps,
        )
        _broker = SimBroker(_sim_config)
        # Build current_bars from feed (SimBroker needs OHLCV for each symbol)
        current_bars: dict[str, dict] = {}
        for s in set(target_weights.keys()) | set(state.portfolio.positions.keys()):
            try:
                b = feed.get_bars(s, start=None, end=None)
                if b is not None and len(b) >= 1:
                    last = b.iloc[-1]
                    current_bars[s] = {
                        "open": float(last.get("open", last["close"])),
                        "high": float(last.get("high", last["close"])),
                        "low": float(last.get("low", last["close"])),
                        "close": float(last["close"]),
                        "volume": float(last.get("volume", 0)),
                    }
            except Exception:
                pass
    else:
        _broker = state.execution_service
        current_bars = None

    async with state.mutation_lock:
        # H-6: kill switch 可能在策略計算期間觸發，重新檢查
        if hasattr(state, 'kill_switch_fired') and state.kill_switch_fired:
            logger.warning("Kill switch fired during strategy calculation — aborting trade execution")
            try:
                from src.alpha.auto.paper_deployer import PaperDeployer
                deployer = PaperDeployer.get_instance()
                for d in deployer.get_active():
                    deployer.stop(d.name, reason="main_kill_switch")
                    logger.warning("Auto strategy %s stopped due to main kill switch", d.name)
            except Exception:
                pass
            return PipelineResult(status="aborted", strategy_name=strategy.name(), error="Kill switch fired")
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
        )
        if trades:
            _save_trade_log(trades, strategy.name(), signal_prices=prices)
        # nav_sod + persistence inside lock (prevent race with realtime monitor)
        state.portfolio.nav_sod = state.portfolio.nav
        from src.api.state import save_portfolio
        save_portfolio(state.portfolio)

    n_trades = len(trades) if trades else 0
    n_targets = len(target_weights)
    logger.info("Pipeline done: %d trades (of %d targets), NAV=%s", n_trades, n_targets, state.portfolio.nav)
    if n_trades < n_targets:
        skipped = n_targets - n_trades
        logger.warning(
            "Pipeline: %d/%d targets skipped (likely stock price > per-stock allocation, "
            "or missing price data). Consider reducing max_holdings or increasing capital.",
            skipped, n_targets,
        )

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

    # P3: Write human-readable daily report
    _write_daily_report(state.portfolio, strategy.name(), n_trades, target_weights)

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


def _write_daily_report(
    portfolio: "Portfolio",
    strategy_name: str,
    n_trades: int,
    target_weights: dict[str, float],
) -> None:
    """P3: Write human-readable daily report to docs/paper-trading/daily/."""
    report_dir = Path("docs/paper-trading/daily")
    report_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    path = report_dir / f"{today}.md"

    nav = float(portfolio.nav)
    cash = float(portfolio.cash)
    n_pos = len(portfolio.positions)
    cash_pct = cash / nav * 100 if nav > 0 else 0

    # NAV history for return calc
    snap_dir = Path("data/paper_trading/snapshots")
    prev_nav = nav  # fallback
    snaps = sorted(snap_dir.glob("*.json")) if snap_dir.exists() else []
    if len(snaps) >= 2:
        try:
            prev = json.loads(snaps[-2].read_text(encoding="utf-8"))
            prev_nav = prev.get("nav", nav)
        except Exception:
            pass
    daily_ret = (nav / prev_nav - 1) * 100 if prev_nav > 0 else 0

    # First snapshot for cumulative return
    first_nav = nav
    if snaps:
        try:
            first = json.loads(snaps[0].read_text(encoding="utf-8"))
            first_nav = first.get("nav", nav)
        except Exception:
            pass
    cum_ret = (nav / first_nav - 1) * 100 if first_nav > 0 else 0

    lines = [
        f"# Paper Trading Daily Report — {today}",
        "",
        f"**Strategy**: {strategy_name}",
        f"**Trades today**: {n_trades}",
        "",
        "## Portfolio",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| NAV | {nav:,.0f} |",
        f"| Cash | {cash:,.0f} ({cash_pct:.1f}%) |",
        f"| Positions | {n_pos} |",
        f"| Daily Return | {daily_ret:+.2f}% |",
        f"| Cumulative Return | {cum_ret:+.2f}% |",
        "",
        "## Holdings",
        "",
        "| Symbol | Qty | Price | Value | Weight |",
        "|--------|----:|------:|------:|-------:|",
    ]

    for sym, pos in sorted(portfolio.positions.items(), key=lambda x: -float(x[1].market_price * x[1].quantity)):
        mv = float(pos.quantity * pos.market_price)
        w = mv / nav * 100 if nav > 0 else 0
        target = target_weights.get(sym, 0) * 100
        lines.append(f"| {sym} | {float(pos.quantity):.0f} | {float(pos.market_price):,.1f} | {mv:,.0f} | {w:.1f}% (target {target:.1f}%) |")

    lines.extend(["", f"---", f"*Generated at {datetime.now().strftime('%H:%M:%S')}*"])

    try:
        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Daily report written: %s", path)
    except Exception:
        logger.debug("Daily report write failed", exc_info=True)


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


async def _async_price_update() -> bool:
    """增量更新價格數據：讀現有 parquet 最後日期，下載之後的數據，append。"""
    import asyncio

    def _do_price_update() -> bool:
        import pandas as pd
        import yfinance as yf
        market_dir = Path("data/market")
        if not market_dir.exists():
            return False

        today = datetime.now().strftime("%Y-%m-%d")
        updated = 0
        failed = 0

        for parquet_path in sorted(market_dir.glob("*_1d.parquet")):
            try:
                existing = pd.read_parquet(parquet_path)
                if existing.empty:
                    continue

                last_date = existing.index.max()
                # If already up to date (within 3 days), skip
                days_behind = (pd.Timestamp(today) - pd.Timestamp(last_date)).days
                if days_behind <= 1:
                    continue

                sym = parquet_path.stem.replace("_1d", "")
                start = (pd.Timestamp(last_date) + pd.DateOffset(days=1)).strftime("%Y-%m-%d")
                df = yf.Ticker(sym).history(start=start, end=today, auto_adjust=True)

                if df is None or df.empty:
                    continue

                df.columns = [c.lower() for c in df.columns]
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
                df = df[cols]
                df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1)]

                if df.empty:
                    continue

                combined = pd.concat([existing, df])
                combined = combined[~combined.index.duplicated(keep="last")]
                combined = combined.sort_index()
                combined.to_parquet(parquet_path)
                updated += 1

            except Exception:
                failed += 1
                continue

        logger.info("Price update: %d updated, %d failed", updated, failed)
        return True

    try:
        return await asyncio.to_thread(_do_price_update)
    except Exception:
        logger.exception("Price update failed")
        return False


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
