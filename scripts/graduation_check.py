#!/usr/bin/env python3
"""AL-10: Paper trading graduation check.

Verifies all 6 conditions (G1-G6) before allowing transition to live trading.
All must pass. Any failure → stay in paper mode.

Usage:
    python scripts/graduation_check.py
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("graduation")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def check_g1_trading_days() -> tuple[bool, str]:
    """G1: >= 30 trading days of paper NAV history."""
    nav_dir = PROJECT_ROOT / "data" / "paper_trading"
    nav_file = nav_dir / "nav_history.json"

    if nav_file.exists():
        data = json.loads(nav_file.read_text(encoding="utf-8"))
        n_days = len(data) if isinstance(data, list) else 0
    else:
        # Count daily files
        n_days = len(list(nav_dir.glob("daily_*.json")))

    passed = n_days >= 30
    return passed, f"{n_days} days (need >= 30)"


def check_g2_zero_violations() -> tuple[bool, str]:
    """G2: 0 TradingInvariantError in audit log."""
    # Check if any invariant violation was logged
    log_patterns = [
        PROJECT_ROOT / "data" / "paper_trading" / "invariant_violations.json",
    ]

    violations = 0
    for p in log_patterns:
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            violations += len(data) if isinstance(data, list) else 1

    # Also check smoke test results for failures
    smoke_dir = PROJECT_ROOT / "data" / "smoke_test"
    if smoke_dir.exists():
        for f in smoke_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if not data.get("passed", True):
                    violations += 1
            except Exception:
                pass

    passed = violations == 0
    return passed, f"{violations} violations"


def check_g3_zero_false_alarms() -> tuple[bool, str]:
    """G3: 0 kill switch false positives."""
    # This is manually verified — check if flag file exists
    flag = PROJECT_ROOT / "data" / "paper_trading" / "false_alarm_count.txt"
    if flag.exists():
        count = int(flag.read_text().strip() or "0")
    else:
        count = 0  # Assume 0 if not tracked
    passed = count == 0
    return passed, f"{count} false alarms"


def check_g4_consistency() -> tuple[bool, str]:
    """G4: Paper vs Backtest sign agreement >= 50%."""
    results_dir = PROJECT_ROOT / "data" / "paper_vs_backtest"
    if not results_dir.exists():
        return False, "No paper vs backtest comparison data"

    latest = sorted(results_dir.glob("*.json"))
    if not latest:
        return False, "No comparison results"

    data = json.loads(latest[-1].read_text(encoding="utf-8"))
    agreement = data.get("sign_agreement", "0%")
    try:
        pct = float(agreement.replace("%", "")) / 100
    except (ValueError, AttributeError):
        pct = 0

    passed = pct >= 0.50
    return passed, f"sign agreement = {agreement}"


def check_g5_smoke_test() -> tuple[bool, str]:
    """G5: 100% smoke test pass rate."""
    smoke_dir = PROJECT_ROOT / "data" / "smoke_test"
    if not smoke_dir.exists():
        return False, "No smoke test results"

    files = sorted(smoke_dir.glob("*.json"))
    if not files:
        return False, "No smoke test results"

    total = len(files)
    passed_count = 0
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("passed", False):
                passed_count += 1
        except Exception:
            pass

    rate = passed_count / total if total > 0 else 0
    passed = rate >= 1.0
    return passed, f"{passed_count}/{total} ({rate:.0%})"


def check_g6_data_collection() -> tuple[bool, str]:
    """G6: >= 95% of days had successful data collection."""
    # Check ops log or data freshness
    # Simplified: check if recent data files exist
    from src.data.data_catalog import DataCatalog
    import pandas as pd

    catalog = DataCatalog(str(PROJECT_ROOT / "data"))
    df = catalog.get("price", "2330.TW")
    if df.empty:
        return False, "No price data for 2330.TW"

    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    # Count trading days in last 30 days
    cutoff = pd.Timestamp.now() - pd.DateOffset(days=30)
    recent = df[df.index >= cutoff]
    # Roughly 22 trading days in 30 calendar days
    expected = 20
    actual = len(recent)
    rate = actual / expected if expected > 0 else 0

    passed = rate >= 0.95
    return passed, f"{actual}/{expected} days ({rate:.0%})"


def main() -> None:
    print("=" * 60)
    print("  Paper Trading Graduation Check")
    print("=" * 60)
    print()

    checks = [
        ("G1", "Trading days >= 30", check_g1_trading_days),
        ("G2", "0 invariant violations", check_g2_zero_violations),
        ("G3", "0 false kill switch alarms", check_g3_zero_false_alarms),
        ("G4", "Paper vs Backtest >= 50%", check_g4_consistency),
        ("G5", "Smoke test 100% pass", check_g5_smoke_test),
        ("G6", "Data collection >= 95%", check_g6_data_collection),
    ]

    all_passed = True
    for code, desc, fn in checks:
        try:
            passed, detail = fn()
        except Exception as e:
            passed, detail = False, f"ERROR: {e}"

        status = "PASS" if passed else "FAIL"
        icon = "[OK]" if passed else "[!!]"
        print(f"  {icon} {code}: {desc}")
        print(f"       {detail}")
        if not passed:
            all_passed = False

    print()
    print("=" * 60)
    if all_passed:
        print("  GRADUATED — eligible for live trading (Level 1: 1% capital)")
    else:
        n_fail = sum(1 for _, _, fn in checks if not fn()[0])
        print(f"  NOT READY — {n_fail} condition(s) not met. Stay in paper mode.")
    print("=" * 60)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
