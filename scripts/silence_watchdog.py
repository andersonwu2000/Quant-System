#!/usr/bin/env python3
"""AL-9: Silence-is-P0 watchdog.

During market hours, if the system produces no log output for 10 minutes,
send a P0 alert. Run this as a separate process (cron or systemd).

Usage:
    python scripts/silence_watchdog.py                    # one-shot check
    python scripts/silence_watchdog.py --loop --interval 300  # continuous (every 5 min)
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("silence_watchdog")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Files that should be updated during active trading
WATCHED_FILES = [
    "data/paper_trading/ledger",     # Trade ledger directory
    "data/paper_trading",            # Paper trading state
]

TW_TZ = timezone(timedelta(hours=8))
SILENCE_THRESHOLD_MINUTES = 10


def is_market_hours() -> bool:
    """Check if currently within Taiwan market hours (09:00-13:30 weekdays)."""
    now = datetime.now(TW_TZ)
    if now.weekday() >= 5:
        return False
    hour = now.hour
    minute = now.minute
    if hour < 9 or (hour == 13 and minute > 30) or hour > 13:
        return False
    return True


def check_silence() -> str | None:
    """Check if system is silent. Returns alert message or None."""
    if not is_market_hours():
        return None

    now = time.time()
    newest_mtime = 0

    for path_str in WATCHED_FILES:
        p = PROJECT_ROOT / path_str
        if p.is_dir():
            for f in p.rglob("*"):
                if f.is_file():
                    newest_mtime = max(newest_mtime, f.stat().st_mtime)
        elif p.is_file():
            newest_mtime = max(newest_mtime, p.stat().st_mtime)

    if newest_mtime == 0:
        return "No watched files found — system may not be running"

    silence_minutes = (now - newest_mtime) / 60

    if silence_minutes > SILENCE_THRESHOLD_MINUTES:
        return (
            f"System silent for {silence_minutes:.0f} minutes during market hours. "
            f"Last file update: {datetime.fromtimestamp(newest_mtime, TW_TZ).strftime('%H:%M:%S')}"
        )

    return None


def send_alert(message: str) -> None:
    """Send P0 alert via configured notifier."""
    try:
        from src.core.config import get_config
        from src.notifications.factory import create_notifier
        import asyncio

        config = get_config()
        notifier = create_notifier(config)
        if notifier.is_configured():
            asyncio.run(notifier.send("SILENCE P0", message))
            logger.critical("P0 ALERT SENT: %s", message)
        else:
            logger.critical("P0 (no notifier): %s", message)
    except Exception as e:
        logger.critical("P0 (notify failed): %s — %s", message, e)


def main() -> None:
    parser = argparse.ArgumentParser(description="Silence watchdog")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=300, help="Check interval (seconds)")
    parser.add_argument("--stop-after", type=int, default=0,
                        help="Auto-stop after N minutes (0 = run forever)")
    args = parser.parse_args()

    if args.loop:
        logger.info("Starting silence watchdog (interval=%ds, threshold=%dmin, stop-after=%dmin)",
                     args.interval, SILENCE_THRESHOLD_MINUTES, args.stop_after)
        start = time.monotonic()
        while True:
            if args.stop_after > 0:
                elapsed_min = (time.monotonic() - start) / 60
                if elapsed_min >= args.stop_after:
                    logger.info("Stop-after limit reached (%.0f min). Exiting.", elapsed_min)
                    break
            alert = check_silence()
            if alert:
                send_alert(alert)
            time.sleep(args.interval)
    else:
        alert = check_silence()
        if alert:
            send_alert(alert)
            sys.exit(1)
        else:
            logger.info("System is active (or outside market hours)")


if __name__ == "__main__":
    main()
