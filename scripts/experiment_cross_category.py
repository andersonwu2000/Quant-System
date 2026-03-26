"""實驗 #13b：跨類型因子組合（營收 × 籌碼 × 情緒 × 估值）。

用法: python -u -m scripts.experiment_cross_category
"""

from __future__ import annotations

import sys
import time
import warnings
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


def load_close():
    close_d = {}
    for p in MARKET_DIR.glob("*.TW_1d.parquet"):
        sym = p.stem.replace("_1d", "")
        if sym.startswith("00"):
            continue
        try:
            df = pd.read_parquet(p, columns=["close"])
            if not df.empty:
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)
                close_d[sym] = df["close"]
        except Exception:
            continue
    close = pd.DataFrame(close_d)
    close.index = pd.to_datetime(close.index.date)
    close = close[~close.index.duplicated(keep="first")].sort_index().ffill(limit=5)
    return close


def build_all_factors(close):
    factors = {}

    # 1. Revenue YoY
    data = {}
    for sym in close.columns:
        p = FUND_DIR / f"{sym}_revenue.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if df.empty or "revenue" not in df.columns or len(df) < 12:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").set_index("date")
        data[sym] = df["revenue"].astype(float).pct_change(12) * 100
    if data:
        panel = pd.DataFrame(data).sort_index()
        factors["rev_yoy"] = panel.reindex(close.index, method="ffill", limit=60)

    # 2. Trust 10d cumulative
    data = {}
    for sym in close.columns:
        p = FUND_DIR / f"{sym}_institutional.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if df.empty or "name" not in df.columns:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df["buy"] = pd.to_numeric(df["buy"], errors="coerce").fillna(0)
        df["sell"] = pd.to_numeric(df["sell"], errors="coerce").fillna(0)
        df["net"] = df["buy"] - df["sell"]
        trust = df[df["name"].str.contains("Investment_Trust", na=False)]
        if not trust.empty:
            tg = trust.groupby("date")["net"].sum()
            data[sym] = tg.rolling(10, min_periods=5).sum()
    if data:
        panel = pd.DataFrame(data).sort_index()
        panel.index = pd.to_datetime(panel.index.date)
        panel = panel[~panel.index.duplicated(keep="first")].sort_index()
        factors["trust_10d"] = panel.reindex(close.index, method="ffill", limit=5)

    # 3. Foreign 20d normalized
    data = {}
    for sym in close.columns:
        p = FUND_DIR / f"{sym}_institutional.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if df.empty or "name" not in df.columns:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df["buy"] = pd.to_numeric(df["buy"], errors="coerce").fillna(0)
        df["sell"] = pd.to_numeric(df["sell"], errors="coerce").fillna(0)
        df["net"] = df["buy"] - df["sell"]
        foreign = df[df["name"].str.contains("Foreign_Investor", na=False)]
        if not foreign.empty:
            fg = foreign.groupby("date")["net"].sum()
            fg_20 = fg.rolling(20, min_periods=5).sum()
            abs_sum = fg.abs().rolling(20, min_periods=5).sum()
            data[sym] = fg_20 / abs_sum.replace(0, np.nan)
    if data:
        panel = pd.DataFrame(data).sort_index()
        panel.index = pd.to_datetime(panel.index.date)
        panel = panel[~panel.index.duplicated(keep="first")].sort_index()
        factors["foreign_20d"] = panel.reindex(close.index, method="ffill", limit=5)

    # 4. Margin change (inverted)
    data = {}
    for sym in close.columns:
        p = FUND_DIR / f"{sym}_margin.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if df.empty or "MarginPurchaseTodayBalance" not in df.columns:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        bal = pd.to_numeric(df["MarginPurchaseTodayBalance"], errors="coerce")
        data[sym] = -bal.pct_change(20)
    if data:
        panel = pd.DataFrame(data).sort_index()
        factors["margin_chg"] = panel.reindex(close.index, method="ffill", limit=5)

    # 5. PE ratio
    data = {}
    for sym in close.columns:
        p = FUND_DIR / f"{sym}_per.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if df.empty or "PER" not in df.columns:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        data[sym] = pd.to_numeric(df["PER"], errors="coerce")
    if data:
        panel = pd.DataFrame(data).sort_index()
        factors["pe_ratio"] = panel.reindex(close.index, method="ffill", limit=5)

    # 6. Daytrading (inverted)
    data = {}
    for sym in close.columns:
        p_dt = FUND_DIR / f"{sym}_daytrading.parquet"
        p_pr = MARKET_DIR / f"{sym}_1d.parquet"
        if not p_dt.exists() or not p_pr.exists():
            continue
        df_dt = pd.read_parquet(p_dt)
        if df_dt.empty or "Volume" not in df_dt.columns:
            continue
        df_dt["date"] = pd.to_datetime(df_dt["date"])
        df_dt = df_dt.set_index("date").sort_index()
        dt_vol = pd.to_numeric(df_dt["Volume"], errors="coerce").fillna(0)
        df_p = pd.read_parquet(p_pr)
        if not isinstance(df_p.index, pd.DatetimeIndex):
            df_p.index = pd.to_datetime(df_p.index)
        df_p.index = pd.to_datetime(df_p.index.date)
        df_p = df_p[~df_p.index.duplicated(keep="first")]
        comb = pd.DataFrame({"dt": dt_vol, "total": df_p["volume"]}).dropna()
        if comb.empty:
            continue
        ratio = comb["dt"] / comb["total"].replace(0, np.nan)
        data[sym] = -ratio.rolling(20, min_periods=5).mean()
    if data:
        panel = pd.DataFrame(data).sort_index()
        factors["daytrading"] = panel.reindex(close.index, method="ffill", limit=5)

    return factors


def compute_ic(fpanel, fwd, sample_every=10):
    common = fpanel.columns.intersection(fwd.columns)
    if len(common) < 5:
        return pd.Series(dtype=float)
    ics = []
    dates = []
    for i in range(0, len(fpanel.index), sample_every):
        dt = fpanel.index[i]
        if dt not in fwd.index:
            continue
        f = fpanel.loc[dt, common].dropna()
        r = fwd.loc[dt, common].dropna()
        v = f.index.intersection(r.index)
        if len(v) < 10:
            continue
        c, _ = sp_stats.spearmanr(f[v], r[v])
        if not np.isnan(c):
            ics.append(c)
            dates.append(dt)
    return pd.Series(ics, index=dates)


def rank_norm(panel):
    return panel.rank(axis=1, pct=True)


def combine(panels, weights=None):
    if weights is None:
        weights = {n: 1 / len(panels) for n in panels}
    ranked = {n: rank_norm(p) for n, p in panels.items()}
    out = None
    for n, rp in ranked.items():
        if out is None:
            out = rp * weights[n]
        else:
            out = out.add(rp * weights[n], fill_value=0)
    return out


def main():
    t0 = time.time()
    print("=" * 80, flush=True)
    print("實驗 #13b：跨類型因子組合（營收 × 籌碼 × 情緒 × 估值）", flush=True)
    print("=" * 80, flush=True)

    close = load_close()
    fwd_20 = close.pct_change(20).shift(-20)
    factors = build_all_factors(close)

    print(f"\nData: {close.shape[1]} symbols, {close.shape[0]} dates", flush=True)
    for name, panel in factors.items():
        n = panel.count().gt(0).sum()
        print(f"  {name:15s}: {n} symbols", flush=True)

    # ── Single factor baseline ──
    print(f"\n--- 單因子基線 ---", flush=True)
    print(f"{'Factor':15s} {'IC':>8s} {'ICIR':>8s} {'Hit':>5s} {'N':>5s} {'Type':>10s}", flush=True)
    print("-" * 55, flush=True)

    type_map = {
        "rev_yoy": "營收", "trust_10d": "籌碼", "foreign_20d": "籌碼",
        "margin_chg": "情緒", "daytrading": "情緒", "pe_ratio": "估值",
    }
    single = {}
    for fname in sorted(factors.keys()):
        ic_s = compute_ic(factors[fname], fwd_20)
        if len(ic_s) == 0:
            continue
        m = ic_s.mean()
        s = ic_s.std()
        icir = m / s if s > 0 else 0
        single[fname] = icir
        ftype = type_map.get(fname, "?")
        tag = " ***" if abs(icir) >= 0.5 else (" **" if abs(icir) >= 0.3 else "")
        print(f"{fname:15s} {m:>+8.4f} {icir:>+8.4f} {(ic_s > 0).mean():>4.0%} {len(ic_s):>5d} {ftype:>10s}{tag}", flush=True)

    # ── rev_yoy + each other ──
    print(f"\n--- rev_yoy + 各類型因子 ---", flush=True)
    print(f"{'Combination':30s} {'IC':>8s} {'ICIR':>8s} {'Hit':>5s} {'vs single':>10s} {'Type':>8s}", flush=True)
    print("-" * 75, flush=True)

    base_icir = single.get("rev_yoy", 0)
    pair_results = {}
    for other in sorted(factors.keys()):
        if other == "rev_yoy":
            continue
        combined = combine({"rev_yoy": factors["rev_yoy"], other: factors[other]})
        ic_s = compute_ic(combined, fwd_20)
        if len(ic_s) == 0:
            continue
        m = ic_s.mean()
        s = ic_s.std()
        icir = m / s if s > 0 else 0
        diff = icir - base_icir
        ftype = type_map.get(other, "?")
        tag = " +++" if diff > 0.02 else (" ++" if diff > 0 else "  --")
        pair_results[other] = icir
        print(f"rev_yoy + {other:19s} {m:>+8.4f} {icir:>+8.4f} {(ic_s > 0).mean():>4.0%} {diff:>+9.4f} {ftype:>8s}{tag}", flush=True)

    # ── Best cross-category combos ──
    print(f"\n--- 跨類型三因子組合 ---", flush=True)
    print(f"{'Combination':45s} {'IC':>8s} {'ICIR':>8s} {'Hit':>5s}", flush=True)
    print("-" * 65, flush=True)

    cross_combos = [
        ("rev_yoy", "trust_10d", "foreign_20d"),
        ("rev_yoy", "trust_10d", "margin_chg"),
        ("rev_yoy", "trust_10d", "pe_ratio"),
        ("rev_yoy", "trust_10d", "daytrading"),
        ("rev_yoy", "foreign_20d", "pe_ratio"),
        ("rev_yoy", "foreign_20d", "margin_chg"),
        ("rev_yoy", "margin_chg", "daytrading"),
        ("rev_yoy", "margin_chg", "pe_ratio"),
    ]

    for combo in cross_combos:
        panels = {f: factors[f] for f in combo if f in factors}
        if len(panels) < len(combo):
            continue
        combined = combine(panels)
        ic_s = compute_ic(combined, fwd_20)
        if len(ic_s) == 0:
            continue
        m = ic_s.mean()
        s = ic_s.std()
        icir = m / s if s > 0 else 0
        name = " + ".join(combo)
        print(f"{name:45s} {m:>+8.4f} {icir:>+8.4f} {(ic_s > 0).mean():>4.0%}", flush=True)

    # ── IC-weighted best cross combo ──
    print(f"\n--- 加權測試（最佳跨類型組合） ---", flush=True)

    # Find which pair was best
    if pair_results:
        best_other = max(pair_results, key=pair_results.get)
        best_icir = pair_results[best_other]
        print(f"最佳配對: rev_yoy + {best_other} (ICIR={best_icir:+.4f})", flush=True)

        # Test different weightings
        print(f"\n{'Weight (rev_yoy:other)':25s} {'ICIR':>8s}", flush=True)
        for w_rev in [0.3, 0.5, 0.6, 0.7, 0.8, 0.9]:
            w_other = 1 - w_rev
            combined = combine(
                {"rev_yoy": factors["rev_yoy"], best_other: factors[best_other]},
                weights={"rev_yoy": w_rev, best_other: w_other},
            )
            ic_s = compute_ic(combined, fwd_20)
            if len(ic_s) == 0:
                continue
            icir = ic_s.mean() / ic_s.std() if ic_s.std() > 0 else 0
            print(f"  {w_rev:.0%}:{w_other:.0%}                    {icir:>+8.4f}", flush=True)

    # ── Summary ──
    print(f"\n{'='*80}", flush=True)
    print("SUMMARY", flush=True)
    print(f"{'='*80}", flush=True)
    print(f"rev_yoy 單因子 ICIR: {base_icir:+.4f}", flush=True)
    if pair_results:
        for other, icir in sorted(pair_results.items(), key=lambda x: -x[1]):
            diff = icir - base_icir
            print(f"  + {other:15s} → {icir:+.4f} ({diff:+.4f})", flush=True)

    print(f"\nTotal: {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
