"""Pipeline record-keeping and utility functions.

Extracted from jobs.py — pipeline run tracking, idempotency checks,
trade/selection/NAV logging, and daily reporting.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
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
            # data-quality: corrupted JSON in pipeline record — non-critical
            logger.debug("Suppressed exception", exc_info=True)
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
            # data-quality: corrupted run record — skip and check next
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
            # data-quality: corrupted run record — skip and check next
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
            # data-quality: corrupted run record — skip
            continue
    return crashed


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
            # expected: external subprocess / network failure
            logger.exception("Revenue data update exception (attempt %d/%d)", attempt + 1, max_retries + 1)

    logger.error("Revenue data update exhausted all retries")
    return False


def _get_tw_universe_fallback() -> list[str]:
    """從所有來源目錄建立台股 universe（排除 ETF 00xx）。(R10.4)"""
    from src.data.data_catalog import get_catalog

    catalog = get_catalog()
    all_syms = catalog.available_symbols("price")
    # Exclude ETFs (00xx)
    def bare_filter(s):
        return not s.replace(".TW", "").replace(".TWO", "").startswith("00")
    universe = sorted(s for s in all_syms if ".TW" in s and bare_filter(s))
    return universe


def _save_selection_log_legacy(weights: dict[str, float]) -> None:
    """[deprecated] 舊版 selection log。"""
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
        # data-quality: file write failure — non-critical logging
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

    # Daily return: compare with previous snapshot (same NAV scale only)
    snap_dir = Path("data/paper_trading/snapshots")
    prev_nav = nav
    snaps = sorted(snap_dir.glob("*.json")) if snap_dir.exists() else []
    if len(snaps) >= 2:
        try:
            prev = json.loads(snaps[-2].read_text(encoding="utf-8"))
            _prev_nav = prev.get("nav", 0)
            # Sanity: only use if same order of magnitude (prevents stale 10M vs new 10K)
            if _prev_nav > 0 and 0.1 < nav / _prev_nav < 10:
                prev_nav = _prev_nav
        except Exception:
            # data-quality: corrupted snapshot JSON
            logger.debug("Suppressed exception", exc_info=True)
    daily_ret = (nav / prev_nav - 1) * 100 if prev_nav > 0 else 0

    # Cumulative return: use configured initial cash
    try:
        from src.core.config import get_config
        initial_cash = get_config().backtest_initial_cash
    except Exception:
        # expected: config not available in isolated context
        initial_cash = nav  # fallback: assume starting from current NAV
    cum_ret = (nav / initial_cash - 1) * 100 if initial_cash > 0 else 0

    lines = [
        f"# Paper Trading Daily Report — {today}",
        "",
        f"**Strategy**: {strategy_name}",
        f"**Trades today**: {n_trades}",
        "",
        "## Portfolio",
        "",
        "| Metric | Value |",
        "|--------|-------|",
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

    lines.extend(["", "---", f"*Generated at {datetime.now().strftime('%H:%M:%S')}*"])

    try:
        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Daily report written: %s", path)
    except Exception:
        # data-quality: file write failure — non-critical reporting
        logger.debug("Daily report write failed", exc_info=True)


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
        # data-quality: file write failure — non-critical logging
        logger.warning("Failed to save backtest comparison", exc_info=True)
