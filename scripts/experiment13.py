"""Experiment 13: Full 59-factor stratified IC scan with pre-computed panels."""
import warnings; warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import pickle
import time

with open("data/market/experiment_data.pkl", "rb") as f:
    all_data = pickle.load(f)
data = {s: df for s, df in all_data.items() if s.endswith(".TW") and len(df) >= 500}
for sym in data: data[sym].index = data[sym].index.normalize()

all_close = pd.DataFrame({s: data[s]["close"] for s in data})
all_close = all_close.dropna(axis=1, thresh=int(len(all_close) * 0.5))
syms = all_close.columns.tolist()
N = len(syms)

mcap = pd.DataFrame({s: data[s]["close"].rolling(20).mean() * data[s]["volume"].rolling(20).mean() for s in syms})
size_pct = mcap.rank(axis=1, pct=True)

fwd20 = all_close.pct_change(20).shift(-20)
fwd20 = fwd20[fwd20.index >= pd.Timestamp("2020-06-01")]

large_mask = (size_pct >= 0.67).reindex(fwd20.index).reindex(columns=fwd20.columns)
small_mask = (size_pct <= 0.33).reindex(fwd20.index).reindex(columns=fwd20.columns)

print(f"Panel: {N} stocks, {len(fwd20)} fwd dates")

# Step 1: Pre-compute all factor panels
from src.strategy.research import VECTORIZED_FACTORS

t0 = time.time()
factor_panels = {}
for name, fn in sorted(VECTORIZED_FACTORS.items()):
    try:
        fp = pd.DataFrame({s: fn(data[s]) for s in syms if s in data})
        if fp.shape[1] >= 15:
            factor_panels[name] = fp
    except:
        pass
print(f"Computed {len(factor_panels)} factor panels in {time.time()-t0:.1f}s")

# Step 2: Compute IC for each factor × stratum
# Use monthly sampling (every 20th date) for speed
sampled_dates = fwd20.index[::20]
print(f"IC dates: {len(sampled_dates)} (sampled every 20d)")

results = []
t0 = time.time()
for name, fp in sorted(factor_panels.items()):
    cols = fp.columns.intersection(fwd20.columns)
    idx = fp.index.intersection(sampled_dates)
    if len(idx) < 10 or len(cols) < 10:
        continue

    fp_s = fp.loc[idx, cols]
    fwd_s = fwd20.loc[idx, cols]
    lm = large_mask.loc[idx, cols] if large_mask is not None else None
    sm = small_mask.loc[idx, cols] if small_mask is not None else None

    def row_ic(f_panel, r_panel, mask=None):
        ics = []
        for i in range(len(f_panel)):
            if mask is not None:
                m = mask.iloc[i]
                f_row = f_panel.iloc[i].where(m).dropna()
                r_row = r_panel.iloc[i].where(m).dropna()
            else:
                f_row = f_panel.iloc[i].dropna()
                r_row = r_panel.iloc[i].dropna()
            common = f_row.index.intersection(r_row.index)
            if len(common) >= 8:
                ic = f_row[common].rank().corr(r_row[common].rank())
                if not np.isnan(ic):
                    ics.append(ic)
        if len(ics) < 8:
            return np.nan, np.nan
        m = np.mean(ics)
        s = np.std(ics)
        return m / s if s > 0 else 0, np.mean(np.array(ics) > 0)

    ia, ha = row_ic(fp_s, fwd_s)
    il, hl = row_ic(fp_s, fwd_s, lm)
    ism, hsm = row_ic(fp_s, fwd_s, sm)

    results.append({
        "name": name, "all": ia, "large": il, "small": ism,
        "hit_all": ha, "hit_large": hl, "hit_small": hsm,
    })

print(f"IC computed in {time.time()-t0:.1f}s\n")

df = pd.DataFrame(results).dropna(subset=["all"])
df["best"] = df[["all", "large", "small"]].abs().max(axis=1)
df = df.sort_values("best", ascending=False)

print(f"{'Factor':<20} {'ALL':>6} {'LARGE':>6} {'SMALL':>6}")
print("-" * 42)
for _, r in df.iterrows():
    def f(v):
        if pd.isna(v): return "  N/A"
        return f"{v:>+5.2f}"
    lg = "***" if not pd.isna(r["large"]) and abs(r["large"]) >= 0.5 else ("**" if not pd.isna(r["large"]) and abs(r["large"]) >= 0.3 else "")
    sm = "***" if not pd.isna(r["small"]) and abs(r["small"]) >= 0.5 else ("**" if not pd.isna(r["small"]) and abs(r["small"]) >= 0.3 else "")
    print(f"{r['name']:<20} {f(r['all']):>6} {f(r['large']):>6} {lg:<3} {f(r['small']):>6} {sm}")

p5 = df[(df["large"].abs() >= 0.5) | (df["small"].abs() >= 0.5)]
p3 = df[((df["large"].abs() >= 0.3) & (df["large"].abs() < 0.5)) | ((df["small"].abs() >= 0.3) & (df["small"].abs() < 0.5))]
print(f"\nPassed >= 0.5 (any stratum): {len(p5)}")
for _, r in p5.iterrows():
    print(f"  {r['name']}: large={r['large']:+.2f} small={r['small']:+.2f}")
print(f"Near 0.3~0.5: {len(p3)}")
for _, r in p3.iterrows():
    print(f"  {r['name']}: large={r['large']:+.2f} small={r['small']:+.2f}")

df.to_csv("docs/dev/test/experiment13_factor_scan.csv", index=False)
print("\nSaved to docs/dev/test/experiment13_factor_scan.csv")
