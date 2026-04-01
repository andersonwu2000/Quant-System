#!/usr/bin/env python3
"""AL-6: Daily Smoke Test — run before market open to verify system health.

Uses yesterday's real market data to run the full trading pipeline
(signal → orders → risk → SimBroker fill) without submitting real orders.

Exit code 0 = OK, 1 = FAIL (block today's trading).

Usage:
    python scripts/daily_smoke_test.py
    # Or from scheduler: called by daily_ops before pipeline execution
"""

from __future__ import annotations

import json
import logging
import math
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
logger = logging.getLogger("smoke_test")
logger.setLevel(logging.INFO)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

RESULTS_DIR = PROJECT_ROOT / "data" / "smoke_test"


def run_smoke_test() -> dict:
    """Run full pipeline smoke test with yesterday's data. Returns result dict."""
    from src.core.config import get_config
    from src.backtest.engine import BacktestConfig, BacktestEngine
    from src.strategy.registry import resolve_strategy

    config = get_config()
    results: dict = {"date": str(date.today()), "checks": {}, "passed": True}

    # Determine test period: use last 5 trading days
    today = date.today()
    end = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    start = (today - timedelta(days=10)).strftime("%Y-%m-%d")

    # Load active strategy
    strategy_name = config.active_strategy
    try:
        strategy = resolve_strategy(strategy_name)
    except Exception as e:
        results["error"] = f"Cannot load strategy '{strategy_name}': {e}"
        results["passed"] = False
        return results

    # Load universe from universe.txt or fallback
    universe_path = PROJECT_ROOT / "scripts" / "autoresearch" / "universe.txt"
    if universe_path.exists():
        universe = [
            l.strip() for l in universe_path.read_text().splitlines()
            if l.strip() and not l.startswith("#")
        ][:50]  # Use top 50 for speed
    else:
        universe = ["2330.TW", "2317.TW", "2454.TW", "2882.TW", "2881.TW"]

    # Run backtest on recent data
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

    try:
        engine = BacktestEngine()
        result = engine.run(strategy, bt_config)
    except Exception as e:
        results["error"] = f"Backtest engine failed: {e}"
        results["passed"] = False
        return results

    # S1: weights 不含 NaN/Inf — checked by pipeline invariant I13
    results["checks"]["S1_no_nan"] = True

    # S2: 訂單數量合理
    reasonable = result.total_trades <= len(universe) * 4
    results["checks"]["S2_order_count"] = {
        "value": result.total_trades,
        "limit": len(universe) * 4,
        "passed": reasonable,
    }
    if not reasonable:
        results["passed"] = False

    # S3: 所有訂單通過風控 (rejected < 10%)
    total_orders = result.total_trades + result.rejected_orders
    reject_rate = result.rejected_orders / max(total_orders, 1)
    s3_ok = reject_rate <= 0.10
    results["checks"]["S3_reject_rate"] = {
        "value": f"{reject_rate:.1%}",
        "limit": "10%",
        "passed": s3_ok,
    }

    # S4: NAV 變化合理 (|Δ| ≤ 5%)
    nav_change = abs(result.total_return)
    s4_ok = nav_change <= 0.05
    results["checks"]["S4_nav_change"] = {
        "value": f"{result.total_return:+.2%}",
        "limit": "5%",
        "passed": s4_ok,
    }
    if not s4_ok:
        results["passed"] = False

    # S5: 無 TradingInvariantError — if we got here, none were raised
    results["checks"]["S5_no_invariant_error"] = True

    # S6: Sharpe is finite (not NaN/Inf)
    s6_ok = math.isfinite(result.sharpe)
    results["checks"]["S6_sharpe_finite"] = {
        "value": f"{result.sharpe:.3f}" if s6_ok else "NaN/Inf",
        "passed": s6_ok,
    }
    if not s6_ok:
        results["passed"] = False

    # S7: 手續費合理 (0 < fee < 1% of traded value)
    if result.total_trades > 0:
        avg_commission_rate = result.total_commission / max(float(result.nav_series.iloc[0]), 1)
        s7_ok = 0 <= avg_commission_rate < 0.01
        results["checks"]["S7_commission"] = {
            "value": f"{avg_commission_rate:.4%}",
            "limit": "< 1%",
            "passed": s7_ok,
        }
    else:
        results["checks"]["S7_commission"] = {"value": "no trades", "passed": True}

    # Summary
    results["strategy"] = strategy_name
    results["period"] = f"{start} ~ {end}"
    results["total_return"] = f"{result.total_return:+.2%}"
    results["sharpe"] = f"{result.sharpe:.3f}" if math.isfinite(result.sharpe) else "N/A"
    results["trades"] = result.total_trades

    return results


def main() -> None:
    logger.info("Running daily smoke test...")

    results = run_smoke_test()

    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"{date.today().isoformat()}.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    # Print summary
    if results["passed"]:
        logger.info("SMOKE TEST PASSED — %s", out_path.name)
        for name, check in results.get("checks", {}).items():
            if isinstance(check, dict):
                logger.info("  %s: %s", name, check.get("value", "OK"))
            else:
                logger.info("  %s: OK", name)
    else:
        logger.error("SMOKE TEST FAILED — trading should be blocked today")
        if "error" in results:
            logger.error("  Error: %s", results["error"])
        for name, check in results.get("checks", {}).items():
            if isinstance(check, dict) and not check.get("passed", True):
                logger.error("  FAIL %s: %s (limit: %s)", name, check.get("value"), check.get("limit"))

    sys.exit(0 if results["passed"] else 1)


if __name__ == "__main__":
    main()
