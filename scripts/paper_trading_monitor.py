"""Paper Trading Monitor — 自動化績效追蹤和異常偵測。

用法：
    # 單次快照
    python -m scripts.paper_trading_monitor

    # 持續監控（每小時）
    python -m scripts.paper_trading_monitor --daemon

    # 生成每日摘要
    python -m scripts.paper_trading_monitor --daily-report
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

API_BASE = "http://127.0.0.1:8000/api/v1"
API_KEY = "dev-key"
HEADERS = {"X-API-Key": API_KEY}
SNAPSHOT_DIR = Path("data/paper_trading/snapshots")
REPORT_DIR = Path("docs/dev/paper")
TW_TZ = timezone(timedelta(hours=8))


def _get(endpoint: str) -> dict | None:
    try:
        r = requests.get(f"{API_BASE}/{endpoint}", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json()
        logger.warning("API %s returned %d", endpoint, r.status_code)
    except Exception as e:
        logger.warning("API %s failed: %s", endpoint, e)
    return None


def take_snapshot() -> dict | None:
    """Take a point-in-time snapshot of paper trading state."""
    status = _get("execution/paper-trading/status")
    if not status:
        logger.error("Cannot reach paper trading API")
        return None

    selection = _get("strategy/selection/latest")
    regime = _get("strategy/regime")

    now = datetime.now(TW_TZ)
    snapshot = {
        "timestamp": now.isoformat(),
        "nav": status.get("portfolio_nav", 0),
        "open_orders": status.get("open_orders", 0),
        "broker_connected": status.get("broker_connected", False),
        "regime": regime.get("regime", "unknown") if regime else "unknown",
        "n_targets": selection.get("n_targets", 0) if selection else 0,
    }

    # Load portfolio state for position details
    state_path = Path("data/paper_trading/portfolio_state.json")
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            positions = state.get("positions", {})
            snapshot["n_positions"] = len(positions)
            snapshot["cash"] = float(Decimal(state.get("cash", "0")))
            snapshot["position_symbols"] = sorted(positions.keys())
        except Exception:
            pass

    # Save snapshot
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    filename = now.strftime("%Y-%m-%d_%H%M.json")
    (SNAPSHOT_DIR / filename).write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("Snapshot: NAV=%.0f, positions=%d, regime=%s",
                snapshot["nav"], snapshot.get("n_positions", 0), snapshot["regime"])
    return snapshot


def check_anomalies(snapshot: dict) -> list[str]:
    """Detect anomalies in the snapshot."""
    alerts = []
    nav = snapshot.get("nav", 0)

    # Load previous snapshots for comparison
    snapshots = sorted(SNAPSHOT_DIR.glob("*.json"))
    if len(snapshots) >= 2:
        try:
            prev = json.loads(snapshots[-2].read_text(encoding="utf-8"))
            prev_nav = prev.get("nav", nav)
            if prev_nav > 0:
                change = (nav - prev_nav) / prev_nav
                if change < -0.03:
                    alerts.append(f"NAV dropped {change:.1%} since last snapshot")
                if change > 0.05:
                    alerts.append(f"NAV jumped {change:.1%} since last snapshot (suspicious)")
        except Exception:
            pass

    if not snapshot.get("broker_connected"):
        alerts.append("Broker disconnected")

    if snapshot.get("n_positions", 0) == 0 and nav > 100000:
        alerts.append("No positions but significant NAV — strategy may not be running")

    return alerts


def load_benchmark_nav() -> float | None:
    """Load 0050.TW latest price for benchmark comparison."""
    try:
        import pandas as pd
        path = Path("data/market/0050.TW_1d.parquet")
        if path.exists():
            df = pd.read_parquet(path)
            return float(df["close"].iloc[-1])
    except Exception:
        pass
    return None


def generate_daily_report() -> str:
    """Generate markdown daily report from today's snapshots."""
    today = datetime.now(TW_TZ).strftime("%Y-%m-%d")
    snapshots_today = sorted(SNAPSHOT_DIR.glob(f"{today}_*.json"))

    if not snapshots_today:
        return f"# Paper Trading Daily Report — {today}\n\nNo snapshots available.\n"

    # Load all snapshots
    data = []
    for p in snapshots_today:
        try:
            data.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue

    if not data:
        return f"# Paper Trading Daily Report — {today}\n\nNo valid snapshots.\n"

    first = data[0]
    last = data[-1]
    nav_start = first["nav"]
    nav_end = last["nav"]
    daily_return = (nav_end - nav_start) / nav_start if nav_start > 0 else 0

    # Load initial cash for total return
    initial_cash = 10_000_000
    total_return = (nav_end - initial_cash) / initial_cash

    # Benchmark
    bench = load_benchmark_nav()

    lines = [
        f"# Paper Trading Daily Report — {today}",
        "",
        f"> Generated at {datetime.now(TW_TZ).strftime('%H:%M')} UTC+8",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| NAV | ${nav_end:,.0f} |",
        f"| Daily Return | {daily_return:+.2%} |",
        f"| Total Return | {total_return:+.2%} |",
        f"| Positions | {last.get('n_positions', 'N/A')} |",
        f"| Cash | ${last.get('cash', 0):,.0f} |",
        f"| Regime | {last.get('regime', 'N/A')} |",
        f"| Snapshots Today | {len(data)} |",
    ]

    if bench:
        lines.append(f"| 0050.TW Close | ${bench:,.2f} |")

    # Position list
    symbols = last.get("position_symbols", [])
    if symbols:
        lines.extend(["", "## Positions", ""])
        for sym in symbols:
            lines.append(f"- {sym}")

    # Anomalies
    alerts = check_anomalies(last)
    if alerts:
        lines.extend(["", "## Anomalies", ""])
        for a in alerts:
            lines.append(f"- [WARNING] {a}")

    # NAV history (all snapshots)
    if len(data) > 1:
        lines.extend(["", "## NAV History", "", "| Time | NAV |", "|------|-----|"])
        for d in data:
            ts = d.get("timestamp", "")
            if ts:
                t = ts[11:16]  # HH:MM
                lines.append(f"| {t} | ${d['nav']:,.0f} |")

    return "\n".join(lines) + "\n"


def save_daily_report() -> None:
    """Generate and save daily report."""
    report = generate_daily_report()
    today = datetime.now(TW_TZ).strftime("%Y-%m-%d")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{today}_daily.md"
    path.write_text(report, encoding="utf-8")
    logger.info("Daily report saved: %s", path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper Trading Monitor")
    parser.add_argument("--daemon", action="store_true", help="Run continuously (every hour)")
    parser.add_argument("--daily-report", action="store_true", help="Generate daily report")
    parser.add_argument("--interval", type=int, default=3600, help="Polling interval in seconds")
    args = parser.parse_args()

    if args.daily_report:
        save_daily_report()
        return

    if args.daemon:
        logger.info("Monitor daemon started (interval=%ds)", args.interval)
        while True:
            snapshot = take_snapshot()
            if snapshot:
                alerts = check_anomalies(snapshot)
                for alert in alerts:
                    logger.warning("ANOMALY: %s", alert)

                # Generate daily report at 14:00 (after market close)
                now = datetime.now(TW_TZ)
                if now.hour == 14 and now.minute < (args.interval // 60 + 1):
                    save_daily_report()

            time.sleep(args.interval)
    else:
        snapshot = take_snapshot()
        if snapshot:
            alerts = check_anomalies(snapshot)
            for alert in alerts:
                print(f"[WARNING] {alert}")


if __name__ == "__main__":
    main()
