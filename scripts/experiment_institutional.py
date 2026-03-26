"""Experiment: Institutional + Margin + Revenue factors on Taiwan stocks."""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, pickle, time, os
from scipy.stats import spearmanr
from FinMind.data import DataLoader
from src.strategy.research import VECTORIZED_FACTORS

# Load price data
with open("data/market/experiment_data.pkl", "rb") as f:
    all_data = pickle.load(f)
data = {s: df for s, df in all_data.items() if s.endswith(".TW") and len(df) >= 500}
codes = sorted(set(s.replace(".TW", "") for s in data.keys()))
print(f"Price data: {len(data)} symbols")

dl = DataLoader()

# 1. Institutional investors
print("\n=== 1. Institutional Investors ===")
inst_raw = {}
for i, code in enumerate(codes[:100]):
    try:
        df = dl.taiwan_stock_institutional_investors(stock_id=code, start_date="2019-01-01", end_date="2025-12-31")
        if not df.empty: inst_raw[code] = df
        time.sleep(0.3)
    except: pass
    if (i+1) % 25 == 0: print(f"  {i+1}/100... ({len(inst_raw)} OK)")
print(f"  Downloaded: {len(inst_raw)}")

# 2. Margin trading
print("\n=== 2. Margin Trading ===")
margin_raw = {}
for i, code in enumerate(codes[:100]):
    try:
        df = dl.taiwan_stock_margin_purchase_short_sale(stock_id=code, start_date="2019-01-01", end_date="2025-12-31")
        if not df.empty: margin_raw[code] = df
        time.sleep(0.3)
    except: pass
    if (i+1) % 25 == 0: print(f"  {i+1}/100... ({len(margin_raw)} OK)")
print(f"  Downloaded: {len(margin_raw)}")

# 3. Revenue
print("\n=== 3. Monthly Revenue ===")
rev_raw = {}
for i, code in enumerate(codes[:100]):
    try:
        df = dl.taiwan_stock_month_revenue(stock_id=code, start_date="2019-01-01", end_date="2025-12-31")
        if not df.empty: rev_raw[code] = df
        time.sleep(0.3)
    except: pass
    if (i+1) % 25 == 0: print(f"  {i+1}/100... ({len(rev_raw)} OK)")
print(f"  Downloaded: {len(rev_raw)}")

# Save raw data
with open(".cache/institutional_data.pkl", "wb") as f:
    pickle.dump({"inst": inst_raw, "margin": margin_raw, "revenue": rev_raw}, f)
print("\nSaved to .cache/institutional_data.pkl")

# Build panels
print("\n=== Building Factor Panels ===")
all_close = pd.DataFrame({s: data[s]["close"] for s in data})
all_close = all_close.dropna(axis=1, thresh=int(len(all_close)*0.5))
date_idx = all_close.index

def build_inst_factor(inst_raw, investor_name, all_close, date_idx):
    panel = pd.DataFrame(index=date_idx, columns=all_close.columns, dtype=float)
    for code, df in inst_raw.items():
        sym = f"{code}.TW"
        if sym not in all_close.columns: continue
        sub = df[df["name"] == investor_name].copy()
        if sub.empty: continue
        sub["date"] = pd.to_datetime(sub["date"])
        sub = sub.set_index("date").sort_index()
        sub["net"] = pd.to_numeric(sub["buy"], errors="coerce") - pd.to_numeric(sub["sell"], errors="coerce")
        net5 = sub["net"].rolling(5, min_periods=1).sum()
        common = net5.index.intersection(panel.index)
        panel.loc[common, sym] = net5.loc[common].values
    return panel

foreign_net = build_inst_factor(inst_raw, "Foreign_Investor", all_close, date_idx)
trust_net = build_inst_factor(inst_raw, "Investment_Trust", all_close, date_idx)
dealer_net = build_inst_factor(inst_raw, "Dealer_self", all_close, date_idx)

# Margin balance change
margin_chg = pd.DataFrame(index=date_idx, columns=all_close.columns, dtype=float)
for code, df in margin_raw.items():
    sym = f"{code}.TW"
    if sym not in all_close.columns: continue
    if "MarginPurchaseTodayBalance" not in df.columns: continue
    df2 = df.copy()
    df2["date"] = pd.to_datetime(df2["date"])
    df2 = df2.set_index("date").sort_index()
    bal = pd.to_numeric(df2["MarginPurchaseTodayBalance"], errors="coerce")
    chg = bal.pct_change(5)
    common = chg.index.intersection(margin_chg.index)
    margin_chg.loc[common, sym] = chg.loc[common].values

# Short sale change
short_chg = pd.DataFrame(index=date_idx, columns=all_close.columns, dtype=float)
for code, df in margin_raw.items():
    sym = f"{code}.TW"
    if sym not in all_close.columns: continue
    if "ShortSaleTodayBalance" not in df.columns: continue
    df2 = df.copy()
    df2["date"] = pd.to_datetime(df2["date"])
    df2 = df2.set_index("date").sort_index()
    bal = pd.to_numeric(df2["ShortSaleTodayBalance"], errors="coerce")
    chg = bal.pct_change(5)
    common = chg.index.intersection(short_chg.index)
    short_chg.loc[common, sym] = chg.loc[common].values

# Revenue MoM
rev_mom = pd.DataFrame(index=date_idx, columns=all_close.columns, dtype=float)
for code, df in rev_raw.items():
    sym = f"{code}.TW"
    if sym not in all_close.columns or "revenue" not in df.columns: continue
    df2 = df.copy()
    df2["date"] = pd.to_datetime(df2["date"])
    df2 = df2.sort_values("date")
    rev = pd.to_numeric(df2.set_index("date")["revenue"], errors="coerce")
    mom = rev.pct_change()
    for dt, val in mom.items():
        if pd.isna(val): continue
        mask = (rev_mom.index >= dt) & (rev_mom.index < dt + pd.Timedelta(days=35))
        rev_mom.loc[mask, sym] = float(val)

# Revenue YoY
rev_yoy = pd.DataFrame(index=date_idx, columns=all_close.columns, dtype=float)
for code, df in rev_raw.items():
    sym = f"{code}.TW"
    if sym not in all_close.columns or "revenue" not in df.columns: continue
    df2 = df.copy()
    df2["date"] = pd.to_datetime(df2["date"])
    df2 = df2.sort_values("date")
    rev = pd.to_numeric(df2.set_index("date")["revenue"], errors="coerce")
    yoy = rev.pct_change(12)
    for dt, val in yoy.items():
        if pd.isna(val): continue
        mask = (rev_yoy.index >= dt) & (rev_yoy.index < dt + pd.Timedelta(days=35))
        rev_yoy.loc[mask, sym] = float(val)

# Report coverage
factors = {
    "foreign_net_5d": foreign_net, "trust_net_5d": trust_net, "dealer_net_5d": dealer_net,
    "margin_chg_5d": margin_chg, "short_chg_5d": short_chg,
    "revenue_mom": rev_mom, "revenue_yoy": rev_yoy,
}

for name, panel in factors.items():
    valid = panel.dropna(axis=1, thresh=int(len(panel)*0.05)).shape[1]
    print(f"  {name}: {valid} symbols")

# Add price factors for comparison
fn_rsi = VECTORIZED_FACTORS["rsi"]
fn_mom6 = VECTORIZED_FACTORS["momentum_6m"]
fn_mom = VECTORIZED_FACTORS["momentum"]
factors["rsi"] = pd.DataFrame({s: fn_rsi(data[s]) for s in all_close.columns if s in data})
factors["momentum_6m"] = pd.DataFrame({s: fn_mom6(data[s]) for s in all_close.columns if s in data})
factors["momentum"] = pd.DataFrame({s: fn_mom(data[s]) for s in all_close.columns if s in data})

# IC analysis
print(f"\n=== IC Analysis (20-day fwd, {all_close.shape[1]} stocks) ===")
fwd20 = all_close.pct_change(20).shift(-20)
fwd20 = fwd20[fwd20.index >= pd.Timestamp("2020-06-01")]

all_mcap = pd.DataFrame({s: data[s]["close"] * data[s]["volume"] for s in all_close.columns})
size_rank = all_mcap.rank(axis=1, pct=True)
large_fwd = fwd20.where(size_rank >= 0.67)

def panel_icir(fp, fwd):
    cidx = fp.index.intersection(fwd.index)
    ccol = fp.columns.intersection(fwd.columns)
    sampled = cidx[::5]
    if len(sampled) < 20 or len(ccol) < 8: return np.nan
    ics = []
    for dt in sampled:
        fr = fp.loc[dt, ccol].dropna()
        rr = fwd.loc[dt, ccol].dropna()
        sh = fr.index.intersection(rr.index)
        if len(sh) >= 8:
            rho, _ = spearmanr(fr[sh].values, rr[sh].values)
            if not np.isnan(rho): ics.append(rho)
    if len(ics) < 15: return np.nan
    return np.mean(ics) / np.std(ics) if np.std(ics) > 0 else 0

print(f"\n{'Factor':<25} {'ALL ICIR':>10} {'LARGE ICIR':>12}")
print("-" * 50)
for name, fp in sorted(factors.items()):
    fp_clean = fp.dropna(axis=1, thresh=int(len(fp)*0.03))
    icir_all = panel_icir(fp_clean, fwd20)
    icir_lg = panel_icir(fp_clean, large_fwd)
    def fmt(v):
        if np.isnan(v): return "      N/A"
        flag = " ***" if abs(v) >= 0.5 else (" **" if abs(v) >= 0.3 else (" *" if abs(v) >= 0.2 else ""))
        return f"{v:>+6.2f}{flag}"
    print(f"{name:<25} {fmt(icir_all):>10} {fmt(icir_lg):>12}")
