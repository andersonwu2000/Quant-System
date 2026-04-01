#!/usr/bin/env python3
"""AL-7: Paper vs Backtest consistency check.

Compares paper trading daily returns with same-period backtest daily returns.
Uses sign agreement rate (% of days where both go same direction).

Usage:
    python scripts/paper_vs_backtest.py
    python scripts/paper_vs_backtest.py --days 30

Requirements:
    - Paper trading NAV history in data/paper_trading/nav_history.json
    - Market data available for backtest
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("paper_vs_backtest")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_paper_nav(days: int = 30) -> pd.Series | None:
    """Load paper trading NAV history."""
    nav_dir = PROJECT_ROOT / "data" / "paper_trading"

    # Try nav_history.json (daily snapshots)
    nav_file = nav_dir / "nav_history.json"
    if nav_file.exists():
        data = json.loads(nav_file.read_text(encoding="utf-8"))
        if isinstance(data, list):
            df = pd.DataFrame(data)
            if "date" in df.columns and "nav" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date").sort_index()
                return df["nav"].tail(days)

    # Try daily summary files
    summaries = sorted(nav_dir.glob("daily_*.json"))
    if summaries:
        records = []
        for f in summaries[-days:]:
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                records.append({"date": d.get("date"), "nav": d.get("nav", d.get("eod_nav"))})
            except Exception:
                continue
        if records:
            df = pd.DataFrame(records)
            df["date"] = pd.to_datetime(df["date"])
            return df.set_index("date")["nav"].sort_index()

    logger.warning("No paper trading NAV history found in %s", nav_dir)
    return None


def run_backtest_for_period(start: str, end: str) -> pd.Series | None:
    """Run backtest for the same period as paper trading."""
    from src.core.config import get_config
    from src.backtest.engine import BacktestConfig, BacktestEngine
    from src.strategy.registry import resolve_strategy

    config = get_config()

    universe_path = PROJECT_ROOT / "scripts" / "autoresearch" / "universe.txt"
    if universe_path.exists():
        universe = [l.strip() for l in universe_path.read_text().splitlines()
                    if l.strip() and not l.startswith("#")][:100]
    else:
        universe = ["2330.TW", "2317.TW", "2454.TW", "2882.TW", "2881.TW"]

    strategy = resolve_strategy(config.active_strategy)

    bt_config = BacktestConfig(
        universe=universe,
        start=start,
        end=end,
        initial_cash=config.backtest_initial_cash,
        commission_rate=config.commission_rate,
        tax_rate=config.tax_rate,
        rebalance_freq=config.rebalance_frequency,
        enable_kill_switch=False,
        fractional_shares=False,
    )

    engine = BacktestEngine()
    result = engine.run(strategy, bt_config)
    return result.nav_series


def compare(paper_nav: pd.Series, bt_nav: pd.Series) -> dict:
    """Compare paper vs backtest daily returns using sign agreement."""
    paper_ret = paper_nav.pct_change().dropna()
    bt_ret = bt_nav.pct_change().dropna()

    # Align dates
    common = paper_ret.index.intersection(bt_ret.index)
    if len(common) < 5:
        return {"error": f"Only {len(common)} common dates (need >= 5)", "passed": False}

    p = paper_ret.loc[common]
    b = bt_ret.loc[common]

    # Sign agreement: both positive or both negative
    same_sign = ((p > 0) & (b > 0)) | ((p < 0) & (b < 0)) | ((p == 0) & (b == 0))
    agreement = float(same_sign.mean())

    # Correlation
    corr = float(np.corrcoef(p.values, b.values)[0, 1]) if len(common) >= 10 else 0

    # Mean absolute deviation
    mad = float(np.abs(p.values - b.values).mean())

    result = {
        "common_days": len(common),
        "sign_agreement": f"{agreement:.1%}",
        "correlation": f"{corr:.3f}",
        "mean_abs_deviation": f"{mad:.4%}",
        "paper_total_return": f"{(paper_nav.iloc[-1] / paper_nav.iloc[0] - 1):+.2%}",
        "bt_total_return": f"{(bt_nav.iloc[-1] / bt_nav.iloc[0] - 1):+.2%}",
    }

    if agreement >= 0.70:
        result["status"] = "OK"
        result["passed"] = True
    elif agreement >= 0.50:
        result["status"] = "WARNING"
        result["passed"] = True
    else:
        result["status"] = "FAIL — system behavior inconsistent with backtest"
        result["passed"] = False

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper vs Backtest consistency check")
    parser.add_argument("--days", type=int, default=30, help="Number of days to compare")
    args = parser.parse_args()

    paper_nav = load_paper_nav(args.days)
    if paper_nav is None or len(paper_nav) < 5:
        logger.error("Insufficient paper trading NAV data (need >= 5 days, have %d)",
                     len(paper_nav) if paper_nav is not None else 0)
        logger.info("Paper trading needs to run for at least %d days before this check.", args.days)
        sys.exit(0)  # Not a failure — just not enough data yet

    start = paper_nav.index.min().strftime("%Y-%m-%d")
    end = paper_nav.index.max().strftime("%Y-%m-%d")
    logger.info("Comparing paper vs backtest: %s ~ %s (%d days)", start, end, len(paper_nav))

    bt_nav = run_backtest_for_period(start, end)
    if bt_nav is None or bt_nav.empty:
        logger.error("Backtest produced no results")
        sys.exit(1)

    result = compare(paper_nav, bt_nav)

    # Save
    out_dir = PROJECT_ROOT / "data" / "paper_vs_backtest"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date.today().isoformat()}.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    logger.info("Result: %s", json.dumps(result, indent=2))

    if not result.get("passed", True):
        logger.error("PAPER VS BACKTEST CHECK FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
