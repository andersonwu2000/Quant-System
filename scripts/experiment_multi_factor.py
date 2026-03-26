"""實驗 #13：多因子組合 IC 分析。

測試所有營收因子的兩兩/三因子/四因子組合，以及不同加權方式。

用法: python -u -m scripts.experiment_multi_factor
"""

from __future__ import annotations

import sys
import time
import warnings
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

warnings.filterwarnings("ignore")
import logging
logging.disable(logging.CRITICAL)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FUND_DIR = Path("data/fundamental")
MARKET_DIR = Path("data/market")


def load_panels():
    """Load close, volume, forward returns, and revenue factor panels."""
    close_d = {}; vol_d = {}
    for p in MARKET_DIR.glob("*.TW_1d.parquet"):
        sym = p.stem.replace("_1d", "")
        if sym.startswith("00"):
            continue
        try:
            df = pd.read_parquet(p)
            if df.empty:
                continue
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            close_d[sym] = df["close"]
            vol_d[sym] = df["volume"].astype(float)
        except Exception:
            continue

    close = pd.DataFrame(close_d)
    close.index = pd.to_datetime(close.index.date)
    close = close[~close.index.duplicated(keep="first")].sort_index().ffill(limit=5)

    vol = pd.DataFrame(vol_d)
    vol.index = pd.to_datetime(vol.index.date)
    vol = vol[~vol.index.duplicated(keep="first")].sort_index().ffill(limit=5)

    fwd_20 = close.pct_change(20).shift(-20)

    # Revenue factors
    factor_data = {
        "rev_yoy": {},
        "rev_accel": {},
        "rev_new_high": {},
        "rev_momentum": {},
    }

    for sym in close.columns:
        p = FUND_DIR / f"{sym}_revenue.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if df.empty or "revenue" not in df.columns or len(df) < 12:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").set_index("date")
        rev = df["revenue"].astype(float)

        factor_data["rev_yoy"][sym] = rev.pct_change(12) * 100
        a3 = rev.rolling(3).mean()
        a12 = rev.rolling(12).mean()
        factor_data["rev_accel"][sym] = a3 / a12.replace(0, np.nan)
        factor_data["rev_new_high"][sym] = (a3 >= a3.rolling(12).max() * 0.99).astype(float)
        streak = pd.Series(0.0, index=rev.index)
        yoy = rev.pct_change(12)
        count = 0.0
        for i, val in enumerate(yoy):
            count = count + 1 if (pd.notna(val) and val > 0) else 0
            streak.iloc[i] = min(count, 12)
        factor_data["rev_momentum"][sym] = streak

    # Price factors for comparison
    price_factors = {
        "mom_6m": close.pct_change(120),
        "mom_1m": close.pct_change(20),
        "volatility": close.pct_change().rolling(20).std() * np.sqrt(252),
    }

    factors = {}
    for name, data in factor_data.items():
        if data:
            panel = pd.DataFrame(data).sort_index()
            factors[name] = panel.reindex(close.index, method="ffill", limit=60)
    for name, panel in price_factors.items():
        factors[name] = panel

    return close, fwd_20, factors


def compute_ic_series(factor_panel, fwd_ret, sample_every=10):
    """Compute IC series."""
    common_syms = factor_panel.columns.intersection(fwd_ret.columns)
    if len(common_syms) < 5:
        return pd.Series(dtype=float)

    ics = []
    dates = []
    for i in range(0, len(factor_panel.index), sample_every):
        dt = factor_panel.index[i]
        if dt not in fwd_ret.index:
            continue
        f = factor_panel.loc[dt, common_syms].dropna()
        r = fwd_ret.loc[dt, common_syms].dropna()
        c = f.index.intersection(r.index)
        if len(c) < 10:
            continue
        corr, _ = sp_stats.spearmanr(f[c], r[c])
        if not np.isnan(corr):
            ics.append(corr)
            dates.append(dt)
    return pd.Series(ics, index=dates)


def rank_normalize(panel):
    """Cross-sectional rank normalize (0~1)."""
    return panel.rank(axis=1, pct=True)


def combine_factors(panels, weights=None):
    """Combine multiple factor panels with optional weights."""
    if weights is None:
        weights = {name: 1.0 / len(panels) for name in panels}
    # Rank normalize each, then weighted sum
    ranked = {name: rank_normalize(panel) for name, panel in panels.items()}
    combined = None
    for name, rpanel in ranked.items():
        w = weights[name]
        if combined is None:
            combined = rpanel * w
        else:
            combined = combined.add(rpanel * w, fill_value=0)
    return combined


def main():
    t0 = time.time()
    print("=" * 80, flush=True)
    print("實驗 #13：多因子組合 IC 分析", flush=True)
    print("=" * 80, flush=True)

    close, fwd_20, factors = load_panels()
    print(f"\nData: {close.shape[1]} symbols, {close.shape[0]} dates", flush=True)
    print(f"Factors: {list(factors.keys())}", flush=True)

    # ── Part 1: Single factor baseline ──
    print(f"\n{'─'*80}", flush=True)
    print("Part 1: 單因子基線", flush=True)
    print(f"{'─'*80}", flush=True)

    single_results = {}
    print(f"\n{'Factor':20s} {'IC':>8s} {'ICIR':>8s} {'Hit%':>6s} {'N':>5s}", flush=True)
    print("-" * 50, flush=True)
    for fname, fpanel in sorted(factors.items()):
        ic_s = compute_ic_series(fpanel, fwd_20)
        if len(ic_s) == 0:
            continue
        m = ic_s.mean()
        s = ic_s.std()
        icir = m / s if s > 0 else 0
        hit = (ic_s > 0).mean()
        single_results[fname] = {"ic": m, "icir": icir, "hit": hit, "n": len(ic_s), "series": ic_s}
        tag = " ***" if abs(icir) >= 0.5 else (" **" if abs(icir) >= 0.3 else "")
        print(f"{fname:20s} {m:>+8.4f} {icir:>+8.4f} {hit:>5.0%} {len(ic_s):>5d}{tag}", flush=True)

    # ── Part 2: All 2-factor combinations ──
    revenue_factors = ["rev_yoy", "rev_accel", "rev_new_high", "rev_momentum"]
    all_factors = revenue_factors + ["mom_6m", "mom_1m", "volatility"]

    print(f"\n{'─'*80}", flush=True)
    print("Part 2: 兩因子組合（等權 rank）", flush=True)
    print(f"{'─'*80}", flush=True)

    combo_results = {}
    print(f"\n{'Combination':35s} {'IC':>8s} {'ICIR':>8s} {'Hit%':>6s} {'vs best single':>15s}", flush=True)
    print("-" * 70, flush=True)

    for f1, f2 in combinations(all_factors, 2):
        if f1 not in factors or f2 not in factors:
            continue
        combined = combine_factors({f1: factors[f1], f2: factors[f2]})
        ic_s = compute_ic_series(combined, fwd_20)
        if len(ic_s) == 0:
            continue
        m = ic_s.mean()
        s = ic_s.std()
        icir = m / s if s > 0 else 0
        hit = (ic_s > 0).mean()
        # Compare to best single
        best_single = max(
            single_results.get(f1, {}).get("icir", 0),
            single_results.get(f2, {}).get("icir", 0),
        )
        improvement = icir - best_single
        combo_results[(f1, f2)] = {"ic": m, "icir": icir, "hit": hit, "n": len(ic_s), "improvement": improvement}

    # Sort by ICIR
    for combo, r in sorted(combo_results.items(), key=lambda x: -x[1]["icir"]):
        name = f"{combo[0]} + {combo[1]}"
        imp = r["improvement"]
        tag = f"{imp:>+.3f}" if imp != 0 else ""
        print(f"{name:35s} {r['ic']:>+8.4f} {r['icir']:>+8.4f} {r['hit']:>5.0%} {tag:>15s}", flush=True)

    # ── Part 3: All 3-factor combinations (revenue only) ──
    print(f"\n{'─'*80}", flush=True)
    print("Part 3: 三因子組合（營收因子，等權 rank）", flush=True)
    print(f"{'─'*80}", flush=True)

    triple_results = {}
    print(f"\n{'Combination':45s} {'IC':>8s} {'ICIR':>8s} {'Hit%':>6s}", flush=True)
    print("-" * 65, flush=True)

    for combo in combinations(revenue_factors, 3):
        panels = {f: factors[f] for f in combo if f in factors}
        if len(panels) < 3:
            continue
        combined = combine_factors(panels)
        ic_s = compute_ic_series(combined, fwd_20)
        if len(ic_s) == 0:
            continue
        m = ic_s.mean()
        s = ic_s.std()
        icir = m / s if s > 0 else 0
        hit = (ic_s > 0).mean()
        triple_results[combo] = {"ic": m, "icir": icir, "hit": hit, "n": len(ic_s)}
        name = " + ".join(combo)
        print(f"{name:45s} {m:>+8.4f} {icir:>+8.4f} {hit:>5.0%}", flush=True)

    # Also test revenue + price combos
    print(f"\n{'Combination':45s} {'IC':>8s} {'ICIR':>8s} {'Hit%':>6s}", flush=True)
    print("-" * 65, flush=True)
    for rev_combo in combinations(revenue_factors, 2):
        for price_f in ["mom_6m", "mom_1m"]:
            combo = rev_combo + (price_f,)
            panels = {f: factors[f] for f in combo if f in factors}
            if len(panels) < 3:
                continue
            combined = combine_factors(panels)
            ic_s = compute_ic_series(combined, fwd_20)
            if len(ic_s) == 0:
                continue
            m = ic_s.mean()
            s = ic_s.std()
            icir = m / s if s > 0 else 0
            name = " + ".join(combo)
            triple_results[combo] = {"ic": m, "icir": icir, "hit": (ic_s > 0).mean(), "n": len(ic_s)}
            print(f"{name:45s} {m:>+8.4f} {icir:>+8.4f} {(ic_s > 0).mean():>5.0%}", flush=True)

    # ── Part 4: Four-factor (all revenue) ──
    print(f"\n{'─'*80}", flush=True)
    print("Part 4: 四因子組合（全營收）", flush=True)
    print(f"{'─'*80}", flush=True)

    panels_all = {f: factors[f] for f in revenue_factors if f in factors}
    combined_all = combine_factors(panels_all)
    ic_s = compute_ic_series(combined_all, fwd_20)
    if len(ic_s) > 0:
        m = ic_s.mean(); s = ic_s.std(); icir = m / s if s > 0 else 0
        print(f"{'rev_yoy+accel+new_high+momentum':45s} {m:>+8.4f} {icir:>+8.4f} {(ic_s > 0).mean():>5.0%}", flush=True)

    # ── Part 5: IC-weighted combination ──
    print(f"\n{'─'*80}", flush=True)
    print("Part 5: 加權方式比較（最佳兩因子組合）", flush=True)
    print(f"{'─'*80}", flush=True)

    # Find best 2-factor combo
    best_2 = max(combo_results.items(), key=lambda x: x[1]["icir"])
    f1, f2 = best_2[0]
    print(f"\n最佳兩因子：{f1} + {f2} (等權 ICIR={best_2[1]['icir']:+.4f})", flush=True)

    print(f"\n{'Method':25s} {'IC':>8s} {'ICIR':>8s} {'Hit%':>6s}", flush=True)
    print("-" * 50, flush=True)

    # Equal weight
    eq = combine_factors({f1: factors[f1], f2: factors[f2]})
    ic_eq = compute_ic_series(eq, fwd_20)
    print(f"{'Equal weight':25s} {ic_eq.mean():>+8.4f} {ic_eq.mean()/ic_eq.std():>+8.4f} {(ic_eq>0).mean():>5.0%}", flush=True)

    # IC-weighted (use single factor ICIR as weight)
    w1 = single_results.get(f1, {}).get("icir", 1)
    w2 = single_results.get(f2, {}).get("icir", 1)
    total = abs(w1) + abs(w2)
    ic_wt = combine_factors({f1: factors[f1], f2: factors[f2]}, weights={f1: w1/total, f2: w2/total})
    ic_icw = compute_ic_series(ic_wt, fwd_20)
    print(f"{'IC-weighted':25s} {ic_icw.mean():>+8.4f} {ic_icw.mean()/ic_icw.std():>+8.4f} {(ic_icw>0).mean():>5.0%}", flush=True)

    # Concentration (70/30)
    ic_conc = combine_factors({f1: factors[f1], f2: factors[f2]}, weights={f1: 0.7, f2: 0.3})
    ic_c = compute_ic_series(ic_conc, fwd_20)
    print(f"{'70/30 concentrated':25s} {ic_c.mean():>+8.4f} {ic_c.mean()/ic_c.std():>+8.4f} {(ic_c>0).mean():>5.0%}", flush=True)

    ic_conc2 = combine_factors({f1: factors[f1], f2: factors[f2]}, weights={f1: 0.3, f2: 0.7})
    ic_c2 = compute_ic_series(ic_conc2, fwd_20)
    print(f"{'30/70 concentrated':25s} {ic_c2.mean():>+8.4f} {ic_c2.mean()/ic_c2.std():>+8.4f} {(ic_c2>0).mean():>5.0%}", flush=True)

    # ── Summary ──
    print(f"\n{'='*80}", flush=True)
    print("SUMMARY", flush=True)
    print(f"{'='*80}", flush=True)

    # Top 5 combinations overall
    all_combos = {**{k: v for k, v in combo_results.items()}, **{k: v for k, v in triple_results.items()}}
    top5 = sorted(all_combos.items(), key=lambda x: -x[1]["icir"])[:5]
    print(f"\nTop 5 組合（by ICIR）：", flush=True)
    for i, (combo, r) in enumerate(top5, 1):
        name = " + ".join(combo) if isinstance(combo, tuple) else str(combo)
        print(f"  {i}. {name:45s} ICIR={r['icir']:+.4f} Hit={r['hit']:.0%}", flush=True)

    # Best single for comparison
    best_single_name = max(single_results, key=lambda x: single_results[x]["icir"])
    best_single_icir = single_results[best_single_name]["icir"]
    print(f"\n最佳單因子：{best_single_name} ICIR={best_single_icir:+.4f}", flush=True)
    print(f"最佳組合 vs 最佳單因子：{top5[0][1]['icir'] - best_single_icir:+.4f}", flush=True)

    print(f"\nTotal time: {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
