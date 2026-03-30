"""Backfill TWSE institutional investor data (T86) — per-date, full market.

Downloads 三大法人 buy/sell data from TWSE traditional endpoint.
One request per trading day, each returns ALL stocks (~1,300 rows).
Rate limit: 2s between requests (TWSE blocks faster access).

Usage:
    python scripts/backfill_twse_institutional.py                    # 2024-01-01 to today
    python scripts/backfill_twse_institutional.py --start 2020-01-01 # custom start
    python scripts/backfill_twse_institutional.py --dry-run          # show plan only
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TWSE_DIR = Path("data/twse")
REQUEST_DELAY = 2.5  # TWSE blocks at <2s; use 2.5s for safety
URL = "https://www.twse.com.tw/rwd/zh/fund/T86"


def _safe_float(val: str) -> float:
    if val is None or val == "" or val == "--":
        return 0.0
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


def fetch_date(trade_date: date) -> pd.DataFrame:
    """Fetch institutional data for one trading day. Returns DataFrame or empty."""
    date_str = trade_date.strftime("%Y%m%d")
    try:
        resp = requests.get(
            URL,
            params={"response": "json", "date": date_str, "selectType": "ALLBUT0999"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:
        logger.debug("Fetch failed for %s: %s", date_str, e)
        return pd.DataFrame()

    if payload.get("stat") != "OK" or "data" not in payload:
        return pd.DataFrame()

    # Fields: [code, name, foreign_buy, foreign_sell, foreign_net, ...,
    #          trust_buy, trust_sell, trust_net, dealer_net, ..., total_net]
    # Indices: 0=code, 4=foreign_net, 10=trust_net, 11=dealer_net, 18=total_net
    rows = []
    for record in payload["data"]:
        try:
            code = record[0].strip().replace('"', '')
            if not code or not code[0].isdigit():
                continue
            rows.append({
                "symbol": f"{code}.TW",
                "date": trade_date.isoformat(),
                "foreign_buy": _safe_float(record[2]),
                "foreign_sell": _safe_float(record[3]),
                "foreign_net": _safe_float(record[4]),
                "trust_buy": _safe_float(record[8]),
                "trust_sell": _safe_float(record[9]),
                "trust_net": _safe_float(record[10]),
                "dealer_net": _safe_float(record[11]),
                "total_net": _safe_float(record[18]),
            })
        except (IndexError, ValueError):
            continue

    return pd.DataFrame(rows)


def get_trading_days(start: date, end: date) -> list[date]:
    """Generate weekday dates (approximate trading days)."""
    days = []
    d = start
    while d <= end:
        if d.weekday() < 5:  # Mon-Fri
            days.append(d)
        d += timedelta(days=1)
    return days


def save_per_symbol(all_data: pd.DataFrame) -> int:
    """Split full-market DataFrame into per-symbol parquet files in data/twse/."""
    TWSE_DIR.mkdir(parents=True, exist_ok=True)
    saved = 0

    for symbol, group in all_data.groupby("symbol"):
        path = TWSE_DIR / f"{symbol}_institutional.parquet"

        # Merge with existing
        if path.exists():
            try:
                existing = pd.read_parquet(path)
                group = pd.concat([existing, group], ignore_index=True)
                group["date"] = pd.to_datetime(group["date"])
                group = group.drop_duplicates(subset=["date"], keep="last")
                group = group.sort_values("date").reset_index(drop=True)
            except Exception:
                pass

        # Write with metadata
        table = pa.Table.from_pandas(group)
        meta = {
            b"source": b"twse",
            b"dataset": b"institutional",
            b"fetch_time": datetime.now().isoformat().encode(),
            b"row_count": str(len(group)).encode(),
        }
        table = table.replace_schema_metadata({**(table.schema.metadata or {}), **meta})
        pq.write_table(table, path)
        saved += 1

    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill TWSE institutional investor data")
    parser.add_argument("--start", default="2024-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=date.today().isoformat(), help="End date")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    trading_days = get_trading_days(start, end)

    est_minutes = len(trading_days) * REQUEST_DELAY / 60
    print(f"Plan: {len(trading_days)} trading days, {start} ~ {end}")
    print(f"Estimated time: {est_minutes:.0f} minutes")

    if args.dry_run:
        print("Dry run, exiting.")
        return

    all_frames = []
    success = 0
    empty = 0

    for i, d in enumerate(trading_days):
        time.sleep(REQUEST_DELAY)
        df = fetch_date(d)
        if df.empty:
            empty += 1
        else:
            all_frames.append(df)
            success += 1

        if (i + 1) % 50 == 0:
            logger.info("[%d/%d] %d success, %d empty", i + 1, len(trading_days), success, empty)
            # Intermediate save every 50 days to avoid losing progress
            if all_frames:
                combined = pd.concat(all_frames, ignore_index=True)
                n = save_per_symbol(combined)
                logger.info("  Intermediate save: %d symbols", n)
                all_frames = []

    # Final save
    if all_frames:
        combined = pd.concat(all_frames, ignore_index=True)
        n = save_per_symbol(combined)
        logger.info("Final save: %d symbols", n)

    print(f"\nDone: {success} days fetched, {empty} empty/holiday, saved to {TWSE_DIR}/")


if __name__ == "__main__":
    main()
