"""Experiment #25: Run StrategyValidator on L5-passed factors.

Factors: revenue_acceleration, per_value
Goal: Collect full 15-check Validator data (not just IC/ICIR from evaluate.py)
"""
from __future__ import annotations
import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, ".")
os.environ.setdefault("QUANT_ENV", "dev")
os.environ.setdefault("QUANT_MODE", "backtest")

import numpy as np
import pandas as pd
from decimal import Decimal

from src.backtest.validator import StrategyValidator, ValidationConfig
from src.strategy.base import Context, Strategy as StrategyBase


# ── Factor definitions (from run_full_factor_analysis.py) ──

def revenue_acceleration(symbols, as_of, data):
    results = {}
    for sym in symbols:
        rev = data["revenue"].get(sym)
        if rev is None or "yoy_growth" not in rev.columns:
            continue
        r = rev[rev["date"] <= as_of].dropna(subset=["yoy_growth"])
        if len(r) < 6:
            continue
        recent = r["yoy_growth"].iloc[-3:].mean()
        older = r["yoy_growth"].iloc[-6:-3].mean()
        v = recent - older
        if np.isfinite(v):
            results[sym] = float(v)
    return results


def per_value(symbols, as_of, data):
    results = {}
    for sym in symbols:
        per = data["per_history"].get(sym)
        if per is None or "PER" not in per.columns:
            continue
        d = per[per["date"] <= as_of]
        if len(d) < 1:
            continue
        v = d["PER"].iloc[-1]
        if v > 0:
            results[sym] = -float(v)
    return results


# ── Strategy wrapper (same pattern as evaluate.py) ──

def _build_strategy(factor_fn, factor_name: str, data: dict) -> StrategyBase:
    """Wrap a compute_factor function into a Strategy class."""

    class _FactorStrategy(StrategyBase):
        def __init__(self) -> None:
            self._last_month = ""
            self._cached: dict[str, float] = {}

        def name(self) -> str:
            return factor_name

        def on_bar(self, ctx: Context) -> dict[str, float]:
            now = ctx.now()
            month_key = now.strftime("%Y-%m") if now else ""
            if month_key == self._last_month and self._cached:
                return self._cached

            symbols = ctx.universe()
            as_of = pd.Timestamp(now)

            # Build data dict from Context
            from src.data.data_catalog import DataCatalog
            catalog = DataCatalog()

            local_data = {"bars": {}, "revenue": {}, "per_history": {}}
            for sym in symbols:
                try:
                    bars = ctx.bars(sym, 300)
                    if bars is not None and not bars.empty:
                        local_data["bars"][sym] = bars
                except Exception:
                    pass

            # Use pre-loaded data for fundamentals (faster)
            if data:
                local_data["revenue"] = data.get("revenue", {})
                local_data["per_history"] = data.get("per_history", {})

            try:
                values = factor_fn(symbols, as_of, local_data)
            except Exception:
                return {}

            if not values:
                return {}

            # Top-N equal weight
            top_n = 15
            sorted_items = sorted(values.items(), key=lambda x: x[1], reverse=True)
            selected = sorted_items[:top_n]
            weight = 1.0 / len(selected) if selected else 0.0
            weights = {sym: weight for sym, _ in selected}

            self._cached = weights
            self._last_month = month_key
            return weights

    return _FactorStrategy()


def run_validator(factor_fn, factor_name: str, n_trials: int):
    """Run full 15-check Validator on a factor."""
    print(f"\n{'='*70}")
    print(f"  VALIDATOR: {factor_name}")
    print(f"  n_trials={n_trials} (multiple testing correction)")
    print(f"{'='*70}\n")

    # Load data
    from scripts.autoresearch.evaluate import _load_all_data, _load_universe
    universe = _load_universe()
    data = _load_all_data(universe)

    # Build strategy
    strategy = _build_strategy(factor_fn, factor_name, data)

    # Config
    config = ValidationConfig(
        n_trials=n_trials,
        initial_cash=10_000_000,
        min_universe_size=50,
        wf_train_years=2,
    )

    # Run
    t0 = time.time()
    validator = StrategyValidator(config=config)
    report = validator.validate(
        strategy=strategy,
        universe=list(universe),
        start="2018-01-01",
        end="2025-12-31",
    )
    elapsed = time.time() - t0

    # Print results
    print(report.summary())
    print(f"\nElapsed: {elapsed:.1f}s")

    # Build result dict
    checks_detail = {}
    for c in report.checks:
        checks_detail[c.name] = {
            "passed": c.passed,
            "value": str(c.value),
            "threshold": str(c.threshold),
            "hard": c.hard,
            "detail": c.detail,
        }

    return {
        "factor": factor_name,
        "passed": report.passed,
        "hard_pass": sum(1 for c in report.checks if c.hard and c.passed),
        "hard_total": sum(1 for c in report.checks if c.hard),
        "soft_pass": sum(1 for c in report.checks if not c.hard and c.passed),
        "soft_total": sum(1 for c in report.checks if not c.hard),
        "total_pass": sum(1 for c in report.checks if c.passed),
        "total_checks": len(report.checks),
        "checks": checks_detail,
        "elapsed": round(elapsed, 1),
        "n_trials": n_trials,
        "timestamp": datetime.now().isoformat(),
    }


def main():
    print("=" * 70)
    print("  Experiment #25: Validator on L5-passed factors")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    # n_trials = independent directions (from factor_pbo.json), NOT total experiments
    n_trials = 15  # fallback
    pbo_path = Path("docker/autoresearch/watchdog_data/factor_pbo.json")
    if pbo_path.exists():
        import json as _j
        _pbo = _j.loads(pbo_path.read_text(encoding="utf-8"))
        _n = _pbo.get("n_independent", 15)
        if isinstance(_n, (int, float)) and _n >= 2:
            n_trials = int(_n)
    print(f"\nDSR n_trials: {n_trials} (independent directions)")

    factors = [
        ("revenue_acceleration", revenue_acceleration),
        ("per_value", per_value),
    ]

    all_results = []
    for name, fn in factors:
        result = run_validator(fn, name, n_trials)
        all_results.append(result)

    # Summary
    print(f"\n{'='*70}")
    print("  SUMMARY")
    print(f"{'='*70}")
    for r in all_results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  {r['factor']:<25} {status}  "
              f"Hard: {r['hard_pass']}/{r['hard_total']}  "
              f"Soft: {r['soft_pass']}/{r['soft_total']}  "
              f"({r['elapsed']:.0f}s)")
        if not r["passed"]:
            failed = [name for name, c in r["checks"].items()
                      if not c["passed"] and c["hard"]]
            if failed:
                print(f"    Hard FAIL: {', '.join(failed)}")

    # Save
    out_path = Path("docs/research/experiment_25_validator.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nResults saved: {out_path}")


if __name__ == "__main__":
    main()
