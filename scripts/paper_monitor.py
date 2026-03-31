"""Paper Trading Monitor — 第一週密集監控用臨時腳本。

用法：
  python scripts/paper_monitor.py              # 持續監控，每 60 秒檢查
  python scripts/paper_monitor.py --once       # 檢查一次就退出
  python scripts/paper_monitor.py --interval 30  # 每 30 秒

監控內容：
  1. Portfolio 狀態（NAV、持倉數、現金比例）
  2. 新成交偵測（比對上次持倉快照）
  3. 異常偵測（NAV 劇變、持倉消失、kill switch）
  4. Pipeline 執行記錄（最後一次跑的結果）
  5. 系統健康（API 是否活著）

輸出：
  - 每次檢查印一行 status line
  - 異常時印完整報告
  - 每次成交印交易細節
  - 所有輸出同時寫入 docs/paper-trading/monitor.log
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

LOG_PATH = Path("docs/paper-trading/monitor.log")
SNAPSHOT_PATH = Path("data/paper_trading/monitor_snapshot.json")
PIPELINE_DIR = Path("data/paper_trading/pipeline_runs")
PORTFOLIO_STATE = Path("data/paper_trading/portfolio_state.json")


def log(msg: str, level: str = "INFO") -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_portfolio() -> dict | None:
    if not PORTFOLIO_STATE.exists():
        return None
    try:
        return json.loads(PORTFOLIO_STATE.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_prev_snapshot() -> dict | None:
    if not SNAPSHOT_PATH.exists():
        return None
    try:
        return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_snapshot(data: dict) -> None:
    try:
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_latest_pipeline_record() -> dict | None:
    if not PIPELINE_DIR.exists():
        return None
    records = sorted(PIPELINE_DIR.glob("*.json"))
    if not records:
        return None
    try:
        return json.loads(records[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def check_api_health() -> bool:
    try:
        import urllib.request
        resp = urllib.request.urlopen("http://localhost:8000/api/v1/system/health", timeout=5)
        return resp.status == 200
    except Exception:
        return False


def detect_changes(current: dict, prev: dict | None) -> list[str]:
    """Compare current portfolio with previous snapshot, return list of changes."""
    changes: list[str] = []
    if prev is None:
        return ["FIRST CHECK — no previous snapshot"]

    # NAV change
    cur_nav = current.get("nav", 0)
    prev_nav = prev.get("nav", 0)
    if prev_nav > 0:
        nav_pct = (cur_nav - prev_nav) / prev_nav * 100
        if abs(nav_pct) > 0.01:
            changes.append(f"NAV: {prev_nav:,.0f} -> {cur_nav:,.0f} ({nav_pct:+.2f}%)")
        if abs(nav_pct) > 3:
            changes.append(f"ALERT: NAV changed {nav_pct:+.2f}% — possible error or kill switch")

    # Position changes
    cur_pos = set(current.get("positions", {}).keys())
    prev_pos = set(prev.get("positions", {}).keys())
    added = cur_pos - prev_pos
    removed = prev_pos - cur_pos

    for sym in added:
        p = current["positions"][sym]
        changes.append(f"BUY: {sym} qty={p.get('qty', '?')} price={p.get('price', '?')}")
    for sym in removed:
        p = prev["positions"][sym]
        changes.append(f"SELL: {sym} (was qty={p.get('qty', '?')})")

    # Quantity changes (partial fills or additional buys)
    for sym in cur_pos & prev_pos:
        cur_qty = current["positions"][sym].get("qty", 0)
        prev_qty = prev["positions"][sym].get("qty", 0)
        if cur_qty != prev_qty:
            diff = cur_qty - prev_qty
            side = "ADD" if diff > 0 else "REDUCE"
            changes.append(f"{side}: {sym} qty {prev_qty} -> {cur_qty} ({diff:+.0f})")

    # Kill switch
    cur_cash_pct = current.get("cash", 0) / cur_nav * 100 if cur_nav > 0 else 0
    prev_cash_pct = prev.get("cash", 0) / prev_nav * 100 if prev_nav > 0 else 0
    if cur_cash_pct > 90 and prev_cash_pct < 50:
        changes.append("ALERT: Cash jumped to >90% — possible KILL SWITCH fired")

    return changes


def format_status_line(portfolio: dict, api_ok: bool) -> str:
    nav = portfolio.get("nav", 0)
    cash = portfolio.get("cash", 0)
    n_pos = len(portfolio.get("positions", {}))
    cash_pct = cash / nav * 100 if nav > 0 else 0
    api_str = "API:OK" if api_ok else "API:DOWN"
    return f"NAV={nav:>10,.0f} | Cash={cash_pct:>5.1f}% | Pos={n_pos:>2} | {api_str}"


def check_once() -> None:
    """Run one monitoring check."""
    portfolio_raw = load_portfolio()
    if portfolio_raw is None:
        log("Portfolio state not found — paper trading may not have started", "WARN")
        return

    # Parse portfolio
    positions = {}
    for sym, pos_data in portfolio_raw.get("positions", {}).items():
        positions[sym] = {
            "qty": pos_data.get("quantity", pos_data.get("qty", 0)),
            "price": pos_data.get("market_price", pos_data.get("price", 0)),
        }

    current = {
        "nav": float(portfolio_raw.get("nav", portfolio_raw.get("cash", 0))),
        "cash": float(portfolio_raw.get("cash", 0)),
        "positions": positions,
        "checked_at": datetime.now().isoformat(),
    }

    # Recalculate NAV if not in raw
    if current["nav"] == current["cash"] and positions:
        mv = sum(float(p["qty"]) * float(p["price"]) for p in positions.values())
        current["nav"] = current["cash"] + mv

    api_ok = check_api_health()
    prev = load_prev_snapshot()
    changes = detect_changes(current, prev)

    # Status line (always print)
    status = format_status_line(current, api_ok)
    log(status)

    # Changes (print if any)
    if changes:
        for c in changes:
            level = "ALERT" if "ALERT" in c else "TRADE" if any(k in c for k in ("BUY", "SELL", "ADD", "REDUCE")) else "INFO"
            log(f"  {c}", level)

    # Pipeline record
    pipeline = load_latest_pipeline_record()
    if pipeline:
        p_status = pipeline.get("status", "?")
        p_trades = pipeline.get("n_trades", "?")
        p_time = pipeline.get("timestamp", "?")
        if prev is None or prev.get("last_pipeline_time") != p_time:
            log(f"  Pipeline: status={p_status}, trades={p_trades}, time={p_time}", "PIPELINE")

    # API down alert
    if not api_ok:
        log("  API server not responding at localhost:8000", "ALERT")

    # Save snapshot for next comparison
    current["last_pipeline_time"] = pipeline.get("timestamp", "") if pipeline else ""
    save_snapshot(current)


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper Trading Monitor")
    parser.add_argument("--once", action="store_true", help="Check once and exit")
    parser.add_argument("--interval", type=int, default=60, help="Seconds between checks (default: 60)")
    args = parser.parse_args()

    log(f"Paper Trading Monitor started (interval={args.interval}s)")
    log(f"Log: {LOG_PATH.absolute()}")

    if args.once:
        check_once()
        return

    try:
        while True:
            check_once()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        log("Monitor stopped (Ctrl+C)")


if __name__ == "__main__":
    main()
