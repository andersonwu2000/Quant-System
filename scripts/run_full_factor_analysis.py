"""Run all known factors through autoresearch L1-L5 pipeline.

Usage: python -m scripts.run_full_factor_analysis
"""
from __future__ import annotations
import sys
import time
import json
sys.path.insert(0, '.')
import os
os.environ.setdefault("QUANT_ENV", "dev")

import pandas as pd
import numpy as np
import scripts.autoresearch.evaluate as ev
from scripts.autoresearch.evaluate import (
    _load_all_data, _load_universe, _compute_forward_returns,
    _compute_ic, _mask_data, IS_END, OOS_START, EVAL_END,
    MIN_IC_L1, MIN_ICIR_L2, MIN_POSITIVE_YEARS
)

# ── Factor definitions ──

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

def revenue_yoy(symbols, as_of, data):
    results = {}
    for sym in symbols:
        rev = data["revenue"].get(sym)
        if rev is None or "yoy_growth" not in rev.columns: continue
        r = rev[rev["date"] <= as_of].dropna(subset=["yoy_growth"])
        if len(r) < 1: continue
        results[sym] = float(r["yoy_growth"].iloc[-1])
    return results

def momentum_12_1(symbols, as_of, data):
    results = {}
    for sym in symbols:
        b = data["bars"].get(sym)
        if b is None: continue
        d = b.loc[:as_of]
        if len(d) < 252: continue
        results[sym] = float(d["close"].iloc[-21] / d["close"].iloc[-252] - 1)
    return results

def momentum_1m(symbols, as_of, data):
    results = {}
    for sym in symbols:
        b = data["bars"].get(sym)
        if b is None: continue
        d = b.loc[:as_of]
        if len(d) < 21: continue
        results[sym] = float(d["close"].iloc[-1] / d["close"].iloc[-21] - 1)
    return results

def low_volatility_120d(symbols, as_of, data):
    results = {}
    for sym in symbols:
        b = data["bars"].get(sym)
        if b is None: continue
        d = b.loc[:as_of]
        if len(d) < 120: continue
        vol = d["close"].pct_change().iloc[-120:].std()
        if vol > 0: results[sym] = -float(vol)
    return results

def trust_net_20d(symbols, as_of, data):
    results = {}
    for sym in symbols:
        inst = data["institutional"].get(sym)
        if inst is None or "trust_net" not in inst.columns: continue
        d = inst[inst["date"] <= as_of]
        if len(d) < 20: continue
        results[sym] = float(d["trust_net"].iloc[-20:].sum())
    return results

def foreign_net_20d(symbols, as_of, data):
    results = {}
    for sym in symbols:
        inst = data["institutional"].get(sym)
        if inst is None or "foreign_net" not in inst.columns: continue
        d = inst[inst["date"] <= as_of]
        if len(d) < 20: continue
        results[sym] = float(d["foreign_net"].iloc[-20:].sum())
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

def overnight_return_60d(symbols, as_of, data):
    results = {}
    for sym in symbols:
        b = data["bars"].get(sym)
        if b is None or "open" not in b.columns: continue
        d = b.loc[:as_of]
        if len(d) < 60: continue
        overnight = d["open"].iloc[-59:].values / d["close"].iloc[-60:-1].values - 1
        results[sym] = float(np.mean(overnight))
    return results

def pbr_value(symbols, as_of, data):
    results = {}
    for sym in symbols:
        per = data["per_history"].get(sym)
        if per is None or "PBR" not in per.columns: continue
        d = per[per["date"] <= as_of]
        if len(d) < 1: continue
        v = d["PBR"].iloc[-1]
        if v > 0: results[sym] = -float(v)
    return results

def margin_usage(symbols, as_of, data):
    results = {}
    for sym in symbols:
        m = data["margin"].get(sym)
        if m is None or "margin_usage" not in m.columns: continue
        d = m[m["date"] <= as_of]
        if len(d) < 1: continue
        results[sym] = -float(d["margin_usage"].iloc[-1])  # negative = low margin is contrarian
    return results

FACTORS = {
    "revenue_acceleration": revenue_acceleration,
    "revenue_yoy": revenue_yoy,
    "momentum_12_1": momentum_12_1,
    "momentum_1m": momentum_1m,
    "low_volatility_120d": low_volatility_120d,
    "trust_net_20d": trust_net_20d,
    "foreign_net_20d": foreign_net_20d,
    "per_value": per_value,
    "pbr_value": pbr_value,
    "overnight_return_60d": overnight_return_60d,
    "margin_usage": margin_usage,
}


def run_factor(factor_name, factor_fn, universe, data, bars, sample_dates, oos_dates):
    """Run one factor through L1-L5."""
    ev._fwd_return_cache.clear()
    t0 = time.monotonic()

    # L1: Quick IC (last 30 IS dates)
    early_ics = []
    for as_of in sample_dates[-30:]:
        masked = _mask_data(data, as_of)
        active = [s for s in universe if s in bars and as_of in bars[s].index]
        if len(active) < 20: continue
        try:
            vals = factor_fn(active, as_of, masked)
        except Exception:
            continue
        vals = {k: v for k, v in (vals or {}).items() if isinstance(v, (int, float)) and np.isfinite(v)}
        if len(vals) < 20: continue
        fwd = _compute_forward_returns(bars, as_of, 20)
        ic = _compute_ic(vals, fwd)
        if ic is not None: early_ics.append(ic)

    if not early_ics:
        return {"name": factor_name, "level": "L0", "ic_20d": 0, "icir": 0, "status": "no_data"}

    mean_ic = abs(np.mean(early_ics))
    if mean_ic < MIN_IC_L1:
        return {"name": factor_name, "level": "L1", "ic_20d": float(mean_ic), "icir": 0, "status": "fail"}

    # L2-L4: Full IS
    ic_by_horizon = {5: [], 20: [], 60: []}
    for as_of in sample_dates:
        masked = _mask_data(data, as_of)
        active = [s for s in universe if s in bars and as_of in bars[s].index]
        if len(active) < 20: continue
        try:
            vals = factor_fn(active, as_of, masked)
        except Exception:
            continue
        vals = {k: v for k, v in (vals or {}).items() if isinstance(v, (int, float)) and np.isfinite(v)}
        if len(vals) < 20: continue
        for h in [5, 20, 60]:
            fwd = _compute_forward_returns(bars, as_of, h)
            ic = _compute_ic(vals, fwd)
            if ic is not None: ic_by_horizon[h].append(ic)

    icirs = {}
    for h, ics in ic_by_horizon.items():
        if len(ics) >= 5:
            std = np.std(ics, ddof=1)
            icirs[h] = float(np.mean(ics) / std) if std > 0 else 0.0
        else:
            icirs[h] = 0.0

    median_icir = float(np.median([abs(v) for v in icirs.values()]))
    best_icir = float(max(abs(v) for v in icirs.values()))

    if median_icir < MIN_ICIR_L2:
        return {"name": factor_name, "level": "L2", "ic_20d": float(mean_ic),
                "icir": best_icir, "icirs": icirs, "status": "fail"}

    # L3: Yearly stability
    ic_20d_list = ic_by_horizon[20]
    dates_used = [d for d in sample_dates if len(ic_20d_list) > 0]
    yearly_ics = {}
    for ic_val, d in zip(ic_20d_list, dates_used[:len(ic_20d_list)]):
        y = d.year
        if y not in yearly_ics: yearly_ics[y] = []
        yearly_ics[y].append(ic_val)
    positive_years = sum(1 for ics in yearly_ics.values() if np.mean(ics) > 0)

    if positive_years < MIN_POSITIVE_YEARS:
        return {"name": factor_name, "level": "L3", "ic_20d": float(mean_ic),
                "icir": best_icir, "icirs": icirs, "pos_years": positive_years, "status": "fail"}

    # L5: OOS
    oos_ics = []
    for as_of in oos_dates:
        masked = _mask_data(data, as_of)
        active = [s for s in universe if s in bars and as_of in bars[s].index]
        if len(active) < 20: continue
        try:
            vals = factor_fn(active, as_of, masked)
        except Exception:
            continue
        vals = {k: v for k, v in (vals or {}).items() if isinstance(v, (int, float)) and np.isfinite(v)}
        if len(vals) < 20: continue
        fwd = _compute_forward_returns(bars, as_of, 20)
        ic = _compute_ic(vals, fwd)
        if ic is not None: oos_ics.append(ic)

    oos_mean_ic = float(np.mean(oos_ics)) if oos_ics else 0.0
    oos_icir = 0.0
    if len(oos_ics) >= 3:
        oos_std = np.std(oos_ics, ddof=1)
        oos_icir = float(oos_mean_ic / oos_std) if oos_std > 0 else 0.0

    elapsed = time.monotonic() - t0
    oos_pass = oos_mean_ic > 0 and len(oos_ics) >= 3

    return {
        "name": factor_name,
        "level": "L5_PASS" if oos_pass else "L5_FAIL",
        "ic_20d": float(mean_ic),
        "icir": best_icir,
        "icirs": icirs,
        "pos_years": positive_years,
        "oos_ic": oos_mean_ic,
        "oos_icir": oos_icir,
        "oos_n": len(oos_ics),
        "status": "PASS" if oos_pass else "fail",
        "time": round(elapsed, 1),
    }


def main():
    print(f"Full Factor Analysis — {len(FACTORS)} factors through L1-L5")
    print("=" * 85)

    ev._data_cache = None
    ev._fwd_return_cache.clear()

    universe = _load_universe()
    data = _load_all_data(universe)
    bars = data["bars"]

    all_dates = set()
    for df in bars.values():
        all_dates.update(df.index)
    sorted_dates = sorted(all_dates)
    monthly = [d for i, d in enumerate(sorted_dates) if i == 0 or d.month != sorted_dates[i-1].month]
    is_dates = [d for d in monthly if d <= pd.Timestamp(IS_END)]
    oos_dates = [d for d in monthly if pd.Timestamp(OOS_START) <= d <= pd.Timestamp(EVAL_END)]

    print(f"Universe: {len(universe)} symbols, IS dates: {len(is_dates)}, OOS dates: {len(oos_dates)}")

    results = []
    for i, (name, fn) in enumerate(FACTORS.items()):
        print(f"\n[{i+1}/{len(FACTORS)}] {name}...", end=" ", flush=True)
        r = run_factor(name, fn, universe, data, bars, is_dates, oos_dates)
        print(f"{r['level']} (ICIR={r.get('icir',0):.3f})")
        results.append(r)

    # Sort
    level_order = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L5_FAIL": 4, "L5_PASS": 5}
    results.sort(key=lambda r: (-level_order.get(r["level"], 0), -r.get("icir", 0)))

    # Print summary
    print(f"\n{'='*85}")
    print(f"{'Factor':<30} {'Level':<10} {'IC_20d':>8} {'BestICIR':>9} {'OOS_IC':>8} {'Status':<6}")
    print("-" * 85)
    for r in results:
        oos = f"{r.get('oos_ic', 0):>+7.3f}" if "oos_ic" in r else "    N/A"
        print(f"{r['name']:<30} {r['level']:<10} {r['ic_20d']:>8.4f} {r.get('icir',0):>9.4f} {oos} {r['status']:<6}")

    print(f"\n{'='*85}")
    print("ICIR BY HORIZON (L2+ factors)")
    print(f"{'='*85}")
    for r in results:
        if "icirs" in r:
            icirs = r["icirs"]
            extra = f"  pos_yrs={r.get('pos_years','?')}" if "pos_years" in r else ""
            oos_extra = f"  OOS_ICIR={r.get('oos_icir',0):+.3f}({r.get('oos_n',0)}d)" if "oos_icir" in r else ""
            print(f"  {r['name']:<28} 5d={icirs.get(5,0):>+.3f}  20d={icirs.get(20,0):>+.3f}  60d={icirs.get(60,0):>+.3f}{extra}{oos_extra}")

    # Save results as JSON
    with open("docs/research/full_factor_analysis_20260331.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    return results


if __name__ == "__main__":
    main()
