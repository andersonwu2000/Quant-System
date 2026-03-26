"""
Experiment Final: Comprehensive validation of best strategy (mom6m + turnover_vol, large cap).

Addresses 5 gaps:
  1. Statistical testing (bootstrap CI, t-test for excess return)
  2. Realistic size-dependent cost model (TW commission + tax)
  3. Turnover analysis (actual turnover tracking, cost drag)
  4. True OOS validation (train on 2020-01~2025-06, test 2025-07~2025-12)
  5. Loss period deep dive (worst 5 periods analysis)

Usage:
  cd D:/Finance && PYTHONPATH=. python scripts/experiment_final.py
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, pickle, time, sys, os
from scipy import stats as scipy_stats
from src.strategy.research import VECTORIZED_FACTORS

# ── Config ──────────────────────────────────────────────────────────────
HOLD_DAYS = 20
TOP_N = 20          # number of stocks to hold
BOOTSTRAP_N = 5000  # bootstrap iterations
OOS_START = "2025-07-01"
OOS_END = "2025-12-31"
IS_START = "2020-01-01"
IS_END = "2025-06-30"
TW_COMMISSION_RATE = 0.001425  # each way
TW_SELL_TAX = 0.003            # sell only
COST_BPS_LARGE = 30   # top 1/3 by mcap
COST_BPS_MID = 50     # middle 1/3
COST_BPS_SMALL = 80   # bottom 1/3
REPORT_PATH = "docs/dev/test/20260326_6.md"

np.random.seed(42)

# ── Load data ───────────────────────────────────────────────────────────
print("Loading data...")
with open("data/market/experiment_data.pkl", "rb") as f:
    all_data = pickle.load(f)
data = {s: df for s, df in all_data.items() if s.endswith(".TW") and len(df) >= 500}
for sym in data:
    data[sym].index = data[sym].index.normalize()

all_close = pd.DataFrame({s: data[s]["close"] for s in data})
all_close = all_close.dropna(axis=1, thresh=int(len(all_close) * 0.5))
all_volume = pd.DataFrame({s: data[s]["volume"] for s in all_close.columns if s in data})
syms = all_close.columns.tolist()
N_syms = len(syms)
print(f"  {N_syms} stocks loaded")

# Market cap proxy (20d avg price × 20d avg volume)
mcap = pd.DataFrame({
    s: data[s]["close"].rolling(20).mean() * data[s]["volume"].rolling(20).mean()
    for s in syms
})
size_pct = mcap.rank(axis=1, pct=True)  # percentile rank

# Size tercile masks
large_mask = (size_pct >= 2/3)
mid_mask = (size_pct >= 1/3) & (size_pct < 2/3)
small_mask = (size_pct < 1/3)

# ── Compute factors ────────────────────────────────────────────────────
print("Computing factors...")
fn_mom6m = VECTORIZED_FACTORS["momentum_6m"]
fn_tvol = VECTORIZED_FACTORS["turnover_vol"]

mom6m_panel = pd.DataFrame({s: fn_mom6m(data[s]) for s in syms if s in data})
tvol_panel = pd.DataFrame({s: fn_tvol(data[s]) for s in syms if s in data})

# Forward returns
fwd = all_close.pct_change(HOLD_DAYS).shift(-HOLD_DAYS)

# ── Strategy function ──────────────────────────────────────────────────
def run_strategy(start_date, end_date, label=""):
    """Run mom6m + turnover_vol large-cap strategy over a date range.

    Returns dict with period-level details for all 5 analyses.
    """
    start_ts = pd.Timestamp(start_date).normalize()
    end_ts = pd.Timestamp(end_date).normalize()

    # Rebalance dates: every HOLD_DAYS trading days within range
    valid_dates = all_close.index[
        (all_close.index >= start_ts) & (all_close.index <= end_ts)
    ]
    rebal_dates = valid_dates[::HOLD_DAYS]

    periods = []
    prev_weights = {}

    for i, dt in enumerate(rebal_dates):
        if dt not in mom6m_panel.index or dt not in tvol_panel.index:
            continue

        # Large cap filter on this date
        lg = large_mask.loc[dt] if dt in large_mask.index else pd.Series(dtype=bool)
        large_syms = lg[lg].index.tolist()
        if len(large_syms) < TOP_N:
            continue

        # Composite score: z(momentum_6m) - z(turnover_vol)  [lower tvol = better]
        m = mom6m_panel.loc[dt, large_syms].dropna()
        t = tvol_panel.loc[dt, large_syms].dropna()
        common = m.index.intersection(t.index)
        if len(common) < TOP_N:
            continue

        m = m[common]
        t = t[common]
        z_m = (m - m.mean()) / m.std() if m.std() > 0 else m * 0
        z_t = (t - t.mean()) / t.std() if t.std() > 0 else t * 0
        score = z_m - z_t  # high mom, low turnover_vol
        top = score.nlargest(TOP_N).index.tolist()

        # Equal weight
        new_weights = {s: 1.0 / len(top) for s in top}

        # Turnover = sum of |weight_change|
        all_keys = set(list(prev_weights.keys()) + list(new_weights.keys()))
        turnover = sum(abs(new_weights.get(s, 0) - prev_weights.get(s, 0)) for s in all_keys)

        # Size-dependent cost for each traded stock
        total_cost_bps = 0.0
        trade_count = 0
        for s in all_keys:
            w_old = prev_weights.get(s, 0)
            w_new = new_weights.get(s, 0)
            trade_size = abs(w_new - w_old)
            if trade_size < 1e-8:
                continue
            trade_count += 1
            # Determine size bucket
            if dt in size_pct.index and s in size_pct.columns:
                pct = size_pct.loc[dt, s]
                if pd.notna(pct):
                    if pct >= 2/3:
                        bps = COST_BPS_LARGE
                    elif pct >= 1/3:
                        bps = COST_BPS_MID
                    else:
                        bps = COST_BPS_SMALL
                else:
                    bps = COST_BPS_MID
            else:
                bps = COST_BPS_MID

            # TW explicit costs: commission both ways + sell tax
            tw_explicit_bps = (TW_COMMISSION_RATE * 2 + TW_SELL_TAX) * 10000  # ~58.5 bps
            effective_bps = bps + tw_explicit_bps  # market impact + explicit
            total_cost_bps += trade_size * effective_bps

        # Forward return for this period
        if dt not in fwd.index:
            prev_weights = new_weights
            continue
        port_ret = fwd.loc[dt, top].mean()  # equal-weight return
        if pd.isna(port_ret):
            prev_weights = new_weights
            continue

        # Benchmark: equal-weight all large-cap
        bench_ret = fwd.loc[dt, large_syms].mean()
        if pd.isna(bench_ret):
            bench_ret = 0.0

        # Cost drag this period
        cost_drag = total_cost_bps / 10000  # as a fraction

        # Realized volatility of portfolio holdings (for regime detection)
        lookback = 60
        loc_idx = all_close.index.get_loc(dt)
        if loc_idx >= lookback:
            hist_slice = all_close.iloc[loc_idx-lookback:loc_idx]
            port_vol = hist_slice[top].pct_change().mean(axis=1).std() * np.sqrt(252)
            bench_vol = hist_slice[large_syms].pct_change().mean(axis=1).std() * np.sqrt(252)
        else:
            port_vol = np.nan
            bench_vol = np.nan

        periods.append({
            "date": dt,
            "port_ret": port_ret,
            "bench_ret": bench_ret,
            "excess_ret": port_ret - bench_ret,
            "cost_drag": cost_drag,
            "net_ret": port_ret - cost_drag,
            "net_excess": port_ret - bench_ret - cost_drag,
            "turnover": turnover,
            "holdings": top,
            "port_vol": port_vol,
            "bench_vol": bench_vol,
            "trade_count": trade_count,
        })
        prev_weights = new_weights

    return pd.DataFrame(periods)


# ══════════════════════════════════════════════════════════════════════
# Run IS and OOS
# ══════════════════════════════════════════════════════════════════════
print(f"\nRunning IS strategy ({IS_START} to {IS_END})...")
is_df = run_strategy(IS_START, IS_END, "IS")
print(f"  {len(is_df)} rebalance periods")

print(f"Running OOS strategy ({OOS_START} to {OOS_END})...")
oos_df = run_strategy(OOS_START, OOS_END, "OOS")
print(f"  {len(oos_df)} rebalance periods")

full_df = run_strategy(IS_START, OOS_END, "FULL")

# ══════════════════════════════════════════════════════════════════════
# Analysis 1: Statistical Testing
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("1. STATISTICAL TESTING")
print("=" * 70)

excess = is_df["net_excess"].values
n = len(excess)
mean_excess = np.mean(excess)
std_excess = np.std(excess, ddof=1)
t_stat = mean_excess / (std_excess / np.sqrt(n)) if std_excess > 0 else 0
p_value = 2 * (1 - scipy_stats.t.cdf(abs(t_stat), df=n-1))

print(f"  IS periods: {n}")
print(f"  Mean net excess per period: {mean_excess*100:.3f}%")
print(f"  Std of excess: {std_excess*100:.3f}%")
print(f"  t-statistic: {t_stat:.3f}")
print(f"  p-value (two-tailed): {p_value:.4f}")
print(f"  Significant at 5%: {'YES' if p_value < 0.05 else 'NO'}")
print(f"  Significant at 10%: {'YES' if p_value < 0.10 else 'NO'}")

# Bootstrap CI
boot_means = []
for _ in range(BOOTSTRAP_N):
    sample = np.random.choice(excess, size=n, replace=True)
    boot_means.append(np.mean(sample))
boot_means = np.array(boot_means)
ci_lo = np.percentile(boot_means, 2.5) * (252 / HOLD_DAYS)  # annualized
ci_hi = np.percentile(boot_means, 97.5) * (252 / HOLD_DAYS)
ann_mean = mean_excess * (252 / HOLD_DAYS)

print(f"\n  Annualized net excess: {ann_mean*100:.2f}%")
print(f"  95% Bootstrap CI (annualized): [{ci_lo*100:.2f}%, {ci_hi*100:.2f}%]")
print(f"  CI contains zero: {'YES' if ci_lo <= 0 <= ci_hi else 'NO'}")


# ══════════════════════════════════════════════════════════════════════
# Analysis 2: Realistic Cost Model
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("2. REALISTIC COST MODEL")
print("=" * 70)

tw_roundtrip = (TW_COMMISSION_RATE * 2 + TW_SELL_TAX) * 100
print(f"  TW explicit costs: commission {TW_COMMISSION_RATE*100:.4f}% × 2 + tax {TW_SELL_TAX*100:.1f}% = {tw_roundtrip:.3f}% round trip")
print(f"  Market impact (large/mid/small): {COST_BPS_LARGE}/{COST_BPS_MID}/{COST_BPS_SMALL} bps")
print(f"  Total effective cost per full turnover:")
print(f"    Large cap: {COST_BPS_LARGE + tw_roundtrip*100:.0f} bps ({(COST_BPS_LARGE + tw_roundtrip*100)/100:.2f}%)")
print(f"    Mid cap:   {COST_BPS_MID + tw_roundtrip*100:.0f} bps ({(COST_BPS_MID + tw_roundtrip*100)/100:.2f}%)")
print(f"    Small cap: {COST_BPS_SMALL + tw_roundtrip*100:.0f} bps ({(COST_BPS_SMALL + tw_roundtrip*100)/100:.2f}%)")

avg_cost = is_df["cost_drag"].mean()
total_cost_ann = avg_cost * (252 / HOLD_DAYS)
print(f"\n  Avg cost per rebalance: {avg_cost*10000:.1f} bps")
print(f"  Annualized cost drag: {total_cost_ann*100:.2f}%")

# Compare gross vs net
gross_ann = is_df["excess_ret"].mean() * (252 / HOLD_DAYS)
net_ann = is_df["net_excess"].mean() * (252 / HOLD_DAYS)
print(f"\n  Gross excess (annualized): {gross_ann*100:.2f}%")
print(f"  Net excess (annualized):   {net_ann*100:.2f}%")
print(f"  Cost erosion:              {(gross_ann - net_ann)*100:.2f}%")


# ══════════════════════════════════════════════════════════════════════
# Analysis 3: Turnover Analysis
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("3. TURNOVER ANALYSIS")
print("=" * 70)

avg_turnover = is_df["turnover"].mean()
ann_turnover = avg_turnover * (252 / HOLD_DAYS)
print(f"  Avg turnover per rebalance: {avg_turnover*100:.1f}%")
print(f"  Annualized turnover: {ann_turnover*100:.0f}%")
print(f"  Avg trades per rebalance: {is_df['trade_count'].mean():.1f}")

# Turnover over time
print(f"\n  Turnover by year:")
is_df_copy = is_df.copy()
is_df_copy["year"] = is_df_copy["date"].dt.year
for yr, grp in is_df_copy.groupby("year"):
    yr_turn = grp["turnover"].mean() * (252 / HOLD_DAYS)
    yr_cost = grp["cost_drag"].mean() * (252 / HOLD_DAYS)
    print(f"    {yr}: turnover {yr_turn*100:.0f}%, cost drag {yr_cost*100:.2f}%")


# ══════════════════════════════════════════════════════════════════════
# Analysis 4: True OOS Validation
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("4. TRUE OUT-OF-SAMPLE VALIDATION")
print("=" * 70)

def summarize(df, label):
    if len(df) == 0:
        print(f"  {label}: No data")
        return {}
    periods_per_year = 252 / HOLD_DAYS
    mean_ret = df["net_ret"].mean()
    mean_bench = df["bench_ret"].mean()
    mean_excess = df["net_excess"].mean()
    ann_ret = mean_ret * periods_per_year
    ann_bench = mean_bench * periods_per_year
    ann_excess = mean_excess * periods_per_year

    # Sharpe (annualized)
    if df["net_ret"].std() > 0:
        sharpe = (mean_ret / df["net_ret"].std()) * np.sqrt(periods_per_year)
    else:
        sharpe = 0

    # Excess Sharpe
    if df["net_excess"].std() > 0:
        excess_sharpe = (mean_excess / df["net_excess"].std()) * np.sqrt(periods_per_year)
    else:
        excess_sharpe = 0

    # Max drawdown (cumulative)
    cum = (1 + df["net_ret"]).cumprod()
    mdd = (cum / cum.cummax() - 1).min()

    # Win rate
    win_rate = (df["net_excess"] > 0).mean()

    print(f"  {label}:")
    print(f"    Periods: {len(df)}")
    print(f"    Ann. return:    {ann_ret*100:+.2f}%")
    print(f"    Ann. benchmark: {ann_bench*100:+.2f}%")
    print(f"    Ann. excess:    {ann_excess*100:+.2f}%")
    print(f"    Sharpe:         {sharpe:.2f}")
    print(f"    Excess Sharpe:  {excess_sharpe:.2f}")
    print(f"    MDD:            {mdd*100:.1f}%")
    print(f"    Win rate:       {win_rate*100:.0f}%")

    return {
        "label": label, "n": len(df),
        "ann_ret": ann_ret, "ann_bench": ann_bench, "ann_excess": ann_excess,
        "sharpe": sharpe, "excess_sharpe": excess_sharpe, "mdd": mdd,
        "win_rate": win_rate,
    }

is_stats = summarize(is_df, "In-Sample (2020-01 to 2025-06)")
print()
oos_stats = summarize(oos_df, "Out-of-Sample (2025-07 to 2025-12)")

if oos_stats:
    print(f"\n  OOS Degradation:")
    print(f"    Excess return: {is_stats.get('ann_excess',0)*100:+.2f}% → {oos_stats.get('ann_excess',0)*100:+.2f}%")
    print(f"    Sharpe:        {is_stats.get('sharpe',0):.2f} → {oos_stats.get('sharpe',0):.2f}")
    print(f"    Excess Sharpe: {is_stats.get('excess_sharpe',0):.2f} → {oos_stats.get('excess_sharpe',0):.2f}")


# ══════════════════════════════════════════════════════════════════════
# Analysis 5: Loss Period Deep Dive
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("5. LOSS PERIOD DEEP DIVE")
print("=" * 70)

# Use full sample for deep dive
analysis_df = full_df.copy()
worst5 = analysis_df.nsmallest(5, "net_excess")

# Market returns for regime detection
market_ret_20d = all_close.mean(axis=1).pct_change(HOLD_DAYS)

# Realized vol for regime
market_vol = all_close.mean(axis=1).pct_change().rolling(60).std() * np.sqrt(252)

# Factor momentum reversal check: did momentum factor flip?
mom6m_avg = mom6m_panel.mean(axis=1)  # average momentum across stocks
mom6m_chg = mom6m_avg.diff(HOLD_DAYS)  # change in factor level

print(f"\n  Worst 5 periods (by net excess return):\n")
for rank, (idx, row) in enumerate(worst5.iterrows(), 1):
    dt = row["date"]
    print(f"  --- #{rank}: {dt.strftime('%Y-%m-%d')} ---")
    print(f"    Portfolio return: {row['port_ret']*100:+.2f}%")
    print(f"    Benchmark return: {row['bench_ret']*100:+.2f}%")
    print(f"    Net excess:       {row['net_excess']*100:+.2f}%")
    print(f"    Turnover:         {row['turnover']*100:.0f}%")
    print(f"    Cost drag:        {row['cost_drag']*10000:.0f} bps")

    # Holdings
    holdings = row["holdings"][:10]  # show top 10
    print(f"    Holdings (top 10): {', '.join(holdings)}")

    # Market regime
    if dt in market_ret_20d.index:
        mkt_r = market_ret_20d.loc[dt]
        print(f"    Market 20d return: {mkt_r*100:+.2f}%" if pd.notna(mkt_r) else "    Market 20d return: N/A")

    if dt in market_vol.index:
        vol = market_vol.loc[dt]
        vol_med = market_vol.loc[:dt].median()
        regime = "HIGH VOL" if pd.notna(vol) and pd.notna(vol_med) and vol > vol_med * 1.5 else "NORMAL"
        print(f"    Market vol (60d ann.): {vol*100:.1f}% (median: {vol_med*100:.1f}%) → {regime}" if pd.notna(vol) else "    Market vol: N/A")

    # Factor reversal
    if dt in mom6m_chg.index:
        fc = mom6m_chg.loc[dt]
        print(f"    Momentum factor shift: {fc:+.4f}" + (" ← REVERSAL" if pd.notna(fc) and fc < -0.05 else ""))

    # Was this during a known market stress?
    yr = dt.year
    mo = dt.month
    if yr == 2022:
        print(f"    Context: 2022 global rate hike cycle / TW bear market")
    elif yr == 2020 and mo <= 4:
        print(f"    Context: COVID crash")
    elif yr == 2025 and mo >= 7:
        print(f"    Context: 2025 H2 (OOS period)")

    print()

# Correlation analysis of losses
print("  Loss correlation analysis:")
analysis_df_copy = analysis_df.copy()
if len(analysis_df_copy) > 10:
    # Add market data
    analysis_df_copy["mkt_ret"] = analysis_df_copy["date"].map(
        lambda d: market_ret_20d.loc[d] if d in market_ret_20d.index else np.nan
    )
    analysis_df_copy["mkt_vol"] = analysis_df_copy["date"].map(
        lambda d: market_vol.loc[d] if d in market_vol.index else np.nan
    )
    analysis_df_copy["mom_shift"] = analysis_df_copy["date"].map(
        lambda d: mom6m_chg.loc[d] if d in mom6m_chg.index else np.nan
    )

    valid = analysis_df_copy.dropna(subset=["net_excess", "mkt_ret", "mkt_vol", "mom_shift"])
    if len(valid) > 10:
        corr_mkt = valid["net_excess"].corr(valid["mkt_ret"])
        corr_vol = valid["net_excess"].corr(valid["mkt_vol"])
        corr_mom = valid["net_excess"].corr(valid["mom_shift"])
        print(f"    Excess vs market return:  r = {corr_mkt:+.3f}")
        print(f"    Excess vs market vol:     r = {corr_vol:+.3f}")
        print(f"    Excess vs momentum shift: r = {corr_mom:+.3f}")

        # Conditional analysis: worst quartile of market
        q25 = valid["mkt_ret"].quantile(0.25)
        bad_mkt = valid[valid["mkt_ret"] <= q25]
        good_mkt = valid[valid["mkt_ret"] > q25]
        print(f"\n    Excess in worst market quartile: {bad_mkt['net_excess'].mean()*100:+.2f}%/period")
        print(f"    Excess in rest of market:        {good_mkt['net_excess'].mean()*100:+.2f}%/period")


# ══════════════════════════════════════════════════════════════════════
# Generate Report
# ══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("GENERATING REPORT...")
print("=" * 70)

# Prepare summary numbers
periods_per_year = 252 / HOLD_DAYS

report = []
report.append("# Experiment Final: 5-Gap Comprehensive Validation")
report.append("")
report.append("> **Date**: 2026-03-26")
report.append(f"> **Strategy**: momentum_6m + turnover_vol (inverse), large cap, equal-weight top {TOP_N}, {HOLD_DAYS}d hold")
report.append(f"> **Universe**: {N_syms} TW stocks")
report.append(f"> **IS Period**: {IS_START} to {IS_END} ({len(is_df)} rebalance periods)")
report.append(f"> **OOS Period**: {OOS_START} to {OOS_END} ({len(oos_df)} rebalance periods)")
report.append("")

# Section 1
report.append("## 1. Statistical Testing (統計檢定)")
report.append("")
report.append(f"| Metric | Value |")
report.append(f"|--------|-------|")
report.append(f"| IS periods | {n} |")
report.append(f"| Mean net excess / period | {mean_excess*100:+.3f}% |")
report.append(f"| Std of excess | {std_excess*100:.3f}% |")
report.append(f"| **t-statistic** | **{t_stat:.3f}** |")
report.append(f"| **p-value (two-tailed)** | **{p_value:.4f}** |")
report.append(f"| Significant at 5% | {'YES' if p_value < 0.05 else 'NO'} |")
report.append(f"| Significant at 10% | {'YES' if p_value < 0.10 else 'NO'} |")
report.append(f"| Ann. net excess | {ann_mean*100:+.2f}% |")
report.append(f"| **95% Bootstrap CI (ann.)** | **[{ci_lo*100:+.2f}%, {ci_hi*100:+.2f}%]** |")
report.append(f"| CI contains zero | {'YES' if ci_lo <= 0 <= ci_hi else 'NO'} |")
report.append("")
ci_interp = "alpha is statistically distinguishable from zero" if not (ci_lo <= 0 <= ci_hi) else "we cannot reject the null of zero alpha"
report.append(f"**Interpretation**: With t={t_stat:.2f} and p={p_value:.4f}, {ci_interp}. The bootstrap CI {'excludes' if not (ci_lo <= 0 <= ci_hi) else 'includes'} zero.")
report.append("")

# Section 2
report.append("## 2. Realistic Cost Model (交易成本模型)")
report.append("")
report.append("### Cost Structure")
report.append("")
report.append("| Component | Rate |")
report.append("|-----------|------|")
report.append(f"| TW Commission (each way) | {TW_COMMISSION_RATE*100:.4f}% |")
report.append(f"| TW Sell Tax | {TW_SELL_TAX*100:.1f}% |")
report.append(f"| **TW Round-trip explicit** | **{tw_roundtrip:.3f}%** |")
report.append(f"| Market impact — Large cap | {COST_BPS_LARGE} bps |")
report.append(f"| Market impact — Mid cap | {COST_BPS_MID} bps |")
report.append(f"| Market impact — Small cap | {COST_BPS_SMALL} bps |")
report.append("")
report.append("### Cost Impact")
report.append("")
report.append(f"| Metric | Value |")
report.append(f"|--------|-------|")
report.append(f"| Avg cost per rebalance | {avg_cost*10000:.1f} bps |")
report.append(f"| Annualized cost drag | {total_cost_ann*100:.2f}% |")
report.append(f"| Gross excess (ann.) | {gross_ann*100:+.2f}% |")
report.append(f"| **Net excess (ann.)** | **{net_ann*100:+.2f}%** |")
report.append(f"| Cost erosion | {(gross_ann - net_ann)*100:.2f}% |")
report.append("")

# Section 3
report.append("## 3. Turnover Analysis (換手率分析)")
report.append("")
report.append(f"| Metric | Value |")
report.append(f"|--------|-------|")
report.append(f"| Avg turnover / rebalance | {avg_turnover*100:.1f}% |")
report.append(f"| Annualized turnover | {ann_turnover*100:.0f}% |")
report.append(f"| Avg trades / rebalance | {is_df['trade_count'].mean():.1f} |")
report.append("")
report.append("### Turnover by Year")
report.append("")
report.append("| Year | Ann. Turnover | Ann. Cost Drag |")
report.append("|------|--------------|---------------|")
for yr, grp in is_df_copy.groupby("year"):
    yr_turn = grp["turnover"].mean() * periods_per_year
    yr_cost = grp["cost_drag"].mean() * periods_per_year
    report.append(f"| {yr} | {yr_turn*100:.0f}% | {yr_cost*100:.2f}% |")
report.append("")

# Section 4
report.append("## 4. True Out-of-Sample Validation (OOS 驗證)")
report.append("")
report.append("| Metric | IS (2020-01~2025-06) | OOS (2025-07~2025-12) | Delta |")
report.append("|--------|---------------------|----------------------|-------|")
for metric, fmt in [
    ("ann_ret", "{:+.2f}%"), ("ann_bench", "{:+.2f}%"), ("ann_excess", "{:+.2f}%"),
    ("sharpe", "{:.2f}"), ("excess_sharpe", "{:.2f}"), ("mdd", "{:.1f}%"),
    ("win_rate", "{:.0f}%"),
]:
    is_v = is_stats.get(metric, 0)
    oos_v = oos_stats.get(metric, 0) if oos_stats else 0
    mult = 100 if "%" in fmt else 1
    is_s = fmt.format(is_v * mult)
    oos_s = fmt.format(oos_v * mult) if oos_stats else "N/A"
    delta = (oos_v - is_v) * mult if oos_stats else 0
    delta_s = f"{delta:+.2f}" if oos_stats else "N/A"
    report.append(f"| {metric} | {is_s} | {oos_s} | {delta_s} |")
report.append("")

if oos_stats:
    if oos_stats.get("ann_excess", 0) > 0 and is_stats.get("ann_excess", 0) > 0:
        oos_verdict = "OOS shows positive excess — encouraging but limited sample"
    elif oos_stats.get("ann_excess", 0) < 0:
        oos_verdict = "OOS excess is negative — possible IS overfitting or regime change"
    else:
        oos_verdict = "OOS shows zero excess"
else:
    oos_verdict = "Insufficient OOS data for conclusion"
report.append(f"**Verdict**: {oos_verdict}")
report.append("")

# Section 5
report.append("## 5. Loss Period Deep Dive (虧損分析)")
report.append("")
report.append("### Worst 5 Periods")
report.append("")
report.append("| # | Date | Port Ret | Bench Ret | Net Excess | Turnover | Regime |")
report.append("|---|------|----------|-----------|------------|----------|--------|")
for rank, (idx, row) in enumerate(worst5.iterrows(), 1):
    dt = row["date"]
    vol_val = row.get("port_vol", np.nan)
    if pd.notna(vol_val) and dt in market_vol.index:
        vol_med = market_vol.loc[:dt].median()
        regime = "HIGH VOL" if pd.notna(vol_med) and vol_val > vol_med * 1.5 else "Normal"
    else:
        regime = "N/A"
    yr = dt.year
    if yr == 2022:
        regime += " (rate hike)"
    elif yr == 2020 and dt.month <= 4:
        regime += " (COVID)"
    report.append(f"| {rank} | {dt.strftime('%Y-%m-%d')} | {row['port_ret']*100:+.1f}% | {row['bench_ret']*100:+.1f}% | {row['net_excess']*100:+.1f}% | {row['turnover']*100:.0f}% | {regime} |")
report.append("")

# Holdings detail for worst period
worst_row = worst5.iloc[0]
report.append(f"**Worst period ({worst_row['date'].strftime('%Y-%m-%d')}) holdings**: {', '.join(worst_row['holdings'][:10])}")
report.append("")

# Correlation analysis
report.append("### Loss Correlation Analysis")
report.append("")
if len(analysis_df_copy) > 10:
    valid = analysis_df_copy.dropna(subset=["net_excess", "mkt_ret", "mkt_vol", "mom_shift"])
    if len(valid) > 10:
        corr_mkt = valid["net_excess"].corr(valid["mkt_ret"])
        corr_vol = valid["net_excess"].corr(valid["mkt_vol"])
        corr_mom = valid["net_excess"].corr(valid["mom_shift"])
        report.append(f"| Factor | Correlation with Excess |")
        report.append(f"|--------|------------------------|")
        report.append(f"| Market return (20d) | r = {corr_mkt:+.3f} |")
        report.append(f"| Market volatility | r = {corr_vol:+.3f} |")
        report.append(f"| Momentum factor shift | r = {corr_mom:+.3f} |")
        report.append("")
        q25 = valid["mkt_ret"].quantile(0.25)
        bad_mkt = valid[valid["mkt_ret"] <= q25]
        good_mkt = valid[valid["mkt_ret"] > q25]
        report.append(f"- Excess in worst market quartile: **{bad_mkt['net_excess'].mean()*100:+.2f}%/period**")
        report.append(f"- Excess in remaining market: **{good_mkt['net_excess'].mean()*100:+.2f}%/period**")
        report.append("")
        if corr_mkt > 0.3:
            report.append("Strategy **underperforms more when market drops** — momentum is pro-cyclical.")
        elif corr_vol < -0.3:
            report.append("Strategy **suffers in high volatility** — momentum reversals hurt.")
        else:
            report.append("Loss drivers are diversified across market, volatility, and factor regimes.")
report.append("")

# Final conclusion
report.append("## Overall Conclusion")
report.append("")
report.append("| Gap | Finding |")
report.append("|-----|---------|")
sig_str = f"t={t_stat:.2f}, p={p_value:.3f}" + (", significant" if p_value < 0.05 else ", NOT significant")
report.append(f"| 1. Statistical testing | {sig_str}; CI [{ci_lo*100:+.1f}%, {ci_hi*100:+.1f}%] |")
report.append(f"| 2. Realistic costs | {total_cost_ann*100:.1f}% ann. drag; net excess {net_ann*100:+.1f}% |")
report.append(f"| 3. Turnover | {ann_turnover*100:.0f}% ann.; cost drag proportional |")
oos_str = f"{oos_stats['ann_excess']*100:+.1f}% excess" if oos_stats else "insufficient data"
report.append(f"| 4. OOS validation | {oos_str} |")
report.append(f"| 5. Loss deep dive | See worst periods table; losses correlate with market regime |")
report.append("")

# Write report
os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
with open(REPORT_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(report))
print(f"\nReport saved to {REPORT_PATH}")
print("Done.")
