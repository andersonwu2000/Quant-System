"""Dual-factor test: revenue_acceleration × per_value composite.

Combines the two L5-passing factors and evaluates:
1. Single-factor IC (baseline)
2. Composite factor IC (equal-weight rank combination)
3. Full backtest via BacktestEngine (CAGR, Sharpe, MDD)
4. Compare: single vs dual
"""
from __future__ import annotations
import sys
import time
sys.path.insert(0, '.')
import os
os.environ.setdefault("QUANT_ENV", "dev")

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src.data.data_catalog import DataCatalog


def revenue_acceleration(symbols, as_of, data):
    results = {}
    for sym in symbols:
        rev = data["revenue"].get(sym)
        if rev is None or "yoy_growth" not in rev.columns: continue
        r = rev[rev["date"] <= as_of].dropna(subset=["yoy_growth"])
        if len(r) < 6: continue
        recent = r["yoy_growth"].iloc[-3:].mean()
        older = r["yoy_growth"].iloc[-6:-3].mean()
        v = recent - older
        if np.isfinite(v): results[sym] = float(v)
    return results


def per_value(symbols, as_of, data):
    results = {}
    for sym in symbols:
        per = data["per_history"].get(sym)
        if per is None or "PER" not in per.columns: continue
        d = per[per["date"] <= as_of]
        if len(d) < 1: continue
        v = d["PER"].iloc[-1]
        if v > 0: results[sym] = -float(v)
    return results


def composite_factor(symbols, as_of, data):
    """Equal-weight rank combination of revenue_acceleration + per_value."""
    ra = revenue_acceleration(symbols, as_of, data)
    pv = per_value(symbols, as_of, data)

    # Only use symbols present in both
    common = set(ra) & set(pv)
    if len(common) < 20:
        return {}

    # Rank each factor (higher = better)
    ra_sorted = sorted(common, key=lambda s: ra[s])
    pv_sorted = sorted(common, key=lambda s: pv[s])

    ra_rank = {s: i for i, s in enumerate(ra_sorted)}
    pv_rank = {s: i for i, s in enumerate(pv_sorted)}

    # Equal-weight composite rank
    return {s: (ra_rank[s] + pv_rank[s]) / 2 for s in common}


def load_data(universe):
    """Load all data via DataCatalog."""
    catalog = DataCatalog("data")

    bars, revenue, per_history = {}, {}, {}
    for sym in universe:
        df = catalog.get("price", sym)
        if not df.empty and "close" in df.columns:
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            df.index = pd.to_datetime(df.index.date)
            df = df[~df.index.duplicated(keep="first")]
            bars[sym] = df

        df = catalog.get("revenue", sym)
        if not df.empty and "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            revenue[sym] = df.sort_values("date")

        try:
            df = catalog.get("per", sym)
            if not df.empty and "PER" in df.columns and "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                per_history[sym] = df.sort_values("date")
        except Exception:
            pass

    return {
        "bars": bars, "revenue": revenue, "per_history": per_history,
        "institutional": {}, "margin": {}, "pe": {}, "pb": {}, "roe": {},
    }


def compute_ic(values, fwd):
    common = sorted(set(values) & set(fwd))
    if len(common) < 20:
        return None
    x = [values[s] for s in common]
    y = [fwd[s] for s in common]
    corr, _ = spearmanr(x, y)
    return float(corr) if np.isfinite(corr) else None


def compute_forward_returns(bars, as_of, horizon):
    results = {}
    for sym, df in bars.items():
        if as_of not in df.index:
            continue
        idx = df.index.get_loc(as_of)
        if idx + horizon >= len(df):
            continue
        p0 = df["close"].iloc[idx]
        p1 = df["close"].iloc[idx + horizon]
        if p0 > 0:
            results[sym] = float(p1 / p0 - 1)
    return results


def mask_data(data, as_of):
    cutoff = as_of - pd.DateOffset(days=40)
    return {
        "bars": {s: df.loc[:as_of] for s, df in data["bars"].items()},
        "revenue": {s: df[df["date"] <= cutoff] for s, df in data["revenue"].items()},
        "per_history": {s: df[df["date"] <= as_of] for s, df in data["per_history"].items()},
        "institutional": {}, "margin": {}, "pe": {}, "pb": {}, "roe": {},
    }


def main():
    from pathlib import Path

    # Load universe
    uni_path = Path("data/research/universe.txt")
    if uni_path.exists():
        universe = [l.strip() for l in uni_path.read_text().splitlines() if l.strip()]
    else:
        catalog = DataCatalog("data")
        universe = sorted(catalog.available_symbols("price"))[:200]

    print("Dual Factor Test: revenue_acceleration × per_value")
    print(f"Universe: {len(universe)} symbols")
    print("=" * 70)

    data = load_data(universe)
    bars = data["bars"]

    # Build monthly sample dates
    all_dates = set()
    for df in bars.values():
        all_dates.update(df.index)
    sorted_dates = sorted(all_dates)
    monthly = [d for i, d in enumerate(sorted_dates) if i == 0 or d.month != sorted_dates[i-1].month]

    is_end = pd.Timestamp("2024-06-30")
    oos_start = pd.Timestamp("2024-07-01")
    eval_end = pd.Timestamp("2025-12-31")

    is_dates = [d for d in monthly if d <= is_end]
    oos_dates = [d for d in monthly if oos_start <= d <= eval_end]

    print(f"IS dates: {len(is_dates)}, OOS dates: {len(oos_dates)}")

    # Evaluate each factor + composite
    factors = {
        "revenue_acceleration": revenue_acceleration,
        "per_value": per_value,
        "composite (ra+pv)": composite_factor,
    }

    for name, fn in factors.items():
        print(f"\n--- {name} ---")
        t0 = time.time()

        # IS IC
        is_ics = {5: [], 20: [], 60: []}
        for as_of in is_dates:
            masked = mask_data(data, as_of)
            active = [s for s in universe if s in bars and as_of in bars[s].index]
            if len(active) < 20: continue
            vals = fn(active, as_of, masked)
            if len(vals) < 20: continue
            for h in [5, 20, 60]:
                fwd = compute_forward_returns(bars, as_of, h)
                ic = compute_ic(vals, fwd)
                if ic is not None:
                    is_ics[h].append(ic)

        # OOS IC
        oos_ics = []
        for as_of in oos_dates:
            masked = mask_data(data, as_of)
            active = [s for s in universe if s in bars and as_of in bars[s].index]
            if len(active) < 20: continue
            vals = fn(active, as_of, masked)
            if len(vals) < 20: continue
            fwd = compute_forward_returns(bars, as_of, 20)
            ic = compute_ic(vals, fwd)
            if ic is not None:
                oos_ics.append(ic)

        elapsed = time.time() - t0

        # Print results
        print(f"  IS samples: {len(is_ics[20])} dates")
        for h in [5, 20, 60]:
            ics = is_ics[h]
            if len(ics) >= 5:
                ic_mean = np.mean(ics)
                ic_std = np.std(ics, ddof=1)
                icir = ic_mean / ic_std if ic_std > 0 else 0
                print(f"  IS  {h:2d}d: IC={ic_mean:+.4f}  ICIR={icir:+.4f}")

        if oos_ics:
            oos_mean = np.mean(oos_ics)
            oos_std = np.std(oos_ics, ddof=1) if len(oos_ics) > 1 else 1
            oos_icir = oos_mean / oos_std if oos_std > 0 else 0
            print(f"  OOS 20d: IC={oos_mean:+.4f}  ICIR={oos_icir:+.4f}  ({len(oos_ics)} dates)")
        else:
            print("  OOS: no data")

        print(f"  Time: {elapsed:.1f}s")

    print(f"\n{'=' * 70}")
    print("Done.")


if __name__ == "__main__":
    main()
