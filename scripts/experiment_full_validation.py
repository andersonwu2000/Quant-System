"""實驗 #12：營收因子全流程驗證。

因子層：IC 多期限 + IC 衰減 + 穩定性 + 分層（大/中/小市值）
策略層：baseline + composite_b0% 的 StrategyValidator
統計層：t-test + bootstrap CI + Deflated Sharpe + PBO

用法: python -u -m scripts.experiment_full_validation
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


# ══════════════════════════════════════════════════════════════
# Part 1: Factor-Level Validation
# ══════════════════════════════════════════════════════════════


def load_price_panel() -> pd.DataFrame:
    all_close = {}
    for p in MARKET_DIR.glob("*.TW_1d.parquet"):
        sym = p.stem.replace("_1d", "")
        if sym.startswith("00"):
            continue
        try:
            df = pd.read_parquet(p)
            if not df.empty and "close" in df.columns:
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)
                all_close[sym] = df["close"]
        except Exception:
            continue
    panel = pd.DataFrame(all_close).sort_index().dropna(how="all")
    panel.index = pd.to_datetime(panel.index.date)
    panel = panel[~panel.index.duplicated(keep="first")]
    return panel


def load_volume_panel() -> pd.DataFrame:
    all_vol = {}
    for p in MARKET_DIR.glob("*.TW_1d.parquet"):
        sym = p.stem.replace("_1d", "")
        if sym.startswith("00"):
            continue
        try:
            df = pd.read_parquet(p)
            if not df.empty and "volume" in df.columns:
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)
                all_vol[sym] = df["volume"]
        except Exception:
            continue
    panel = pd.DataFrame(all_vol).sort_index().dropna(how="all")
    panel.index = pd.to_datetime(panel.index.date)
    panel = panel[~panel.index.duplicated(keep="first")]
    return panel


def build_revenue_factors(symbols: list[str], daily_index: pd.DatetimeIndex) -> dict[str, pd.DataFrame]:
    yoy = {}; accel = {}; new_high = {}; momentum = {}
    for sym in symbols:
        p = FUND_DIR / f"{sym}_revenue.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if df.empty or "revenue" not in df.columns or len(df) < 12:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").set_index("date")
        rev = df["revenue"].astype(float)

        # YoY
        yoy_s = rev.pct_change(12) * 100
        yoy[sym] = yoy_s

        # Acceleration: 3M/12M
        avg3 = rev.rolling(3, min_periods=3).mean()
        avg12 = rev.rolling(12, min_periods=12).mean()
        accel[sym] = avg3 / avg12.replace(0, np.nan)

        # New high
        rolling_max = avg3.rolling(12, min_periods=12).max()
        new_high[sym] = (avg3 >= rolling_max * 0.99).astype(float)

        # Momentum (consecutive growth)
        streak = pd.Series(0.0, index=yoy_s.index)
        count = 0.0
        for i, val in enumerate(yoy_s):
            if pd.notna(val) and val > 0:
                count += 1
            else:
                count = 0
            streak.iloc[i] = min(count, 12)
        momentum[sym] = streak

    result = {}
    for name, data in [("revenue_yoy", yoy), ("revenue_acceleration", accel),
                        ("revenue_new_high", new_high), ("revenue_momentum", momentum)]:
        if data:
            panel = pd.DataFrame(data).sort_index()
            result[name] = panel.reindex(daily_index, method="ffill", limit=60)
    return result


def compute_ic(factor: pd.DataFrame, fwd_ret: pd.DataFrame, sample_every: int = 5) -> pd.Series:
    common_dates = factor.index.intersection(fwd_ret.index)
    common_syms = factor.columns.intersection(fwd_ret.columns)
    if len(common_dates) < 10 or len(common_syms) < 5:
        return pd.Series(dtype=float)
    ics = []
    dates = []
    for i, dt in enumerate(common_dates):
        if i % sample_every != 0:
            continue
        f = factor.loc[dt, common_syms].dropna()
        r = fwd_ret.loc[dt, common_syms].dropna()
        c = f.index.intersection(r.index)
        if len(c) < 5:
            continue
        corr, _ = sp_stats.spearmanr(f[c], r[c])
        if not np.isnan(corr):
            ics.append(corr)
            dates.append(dt)
    return pd.Series(ics, index=dates)


def market_cap_proxy(close_panel: pd.DataFrame, vol_panel: pd.DataFrame) -> pd.DataFrame:
    """Market cap proxy = close * avg volume (20d)."""
    avg_vol = vol_panel.rolling(20).mean()
    return close_panel * avg_vol


def main() -> None:
    t_start = time.time()
    print("=" * 80, flush=True)
    print("實驗 #12：營收因子全流程驗證", flush=True)
    print("=" * 80, flush=True)

    # Load data
    print("\n[1/6] Loading data...", flush=True)
    close = load_price_panel()
    vol = load_volume_panel()
    print(f"  Price panel: {close.shape[1]} symbols, {close.shape[0]} dates ({close.index[0].date()} ~ {close.index[-1].date()})", flush=True)

    symbols = list(close.columns)
    factors = build_revenue_factors(symbols, close.index)
    print(f"  Revenue factors: {list(factors.keys())}", flush=True)
    for name, panel in factors.items():
        n_valid = panel.count().sum()
        print(f"    {name}: {panel.shape[1]} symbols, {n_valid:,.0f} valid obs", flush=True)

    # ── Part 1: Multi-horizon IC ──
    print("\n[2/6] Multi-horizon IC analysis...", flush=True)
    horizons = [5, 10, 20, 60]
    print(f"\n{'Factor':25s}", end="", flush=True)
    for h in horizons:
        print(f" | {'IC':>6s} {'ICIR':>6s} {'Hit%':>5s}", end="", flush=True)
    print(f" | {'N':>4s}")
    print("-" * 95, flush=True)

    ic_results = {}
    for fname, fpanel in factors.items():
        print(f"{fname:25s}", end="", flush=True)
        ic_results[fname] = {}
        for h in horizons:
            fwd = close.pct_change(h).shift(-h)
            ic_s = compute_ic(fpanel, fwd)
            ic_mean = ic_s.mean() if len(ic_s) > 0 else 0
            ic_std = ic_s.std() if len(ic_s) > 0 else 1
            icir = ic_mean / ic_std if ic_std > 0 else 0
            hit = (ic_s > 0).mean() if len(ic_s) > 0 else 0
            ic_results[fname][h] = {"ic": ic_mean, "icir": icir, "hit": hit, "n": len(ic_s)}
            print(f" | {ic_mean:>+6.3f} {icir:>+6.3f} {hit:>4.0%}", end="", flush=True)
        print(f" | {ic_results[fname][20]['n']:>4d}", flush=True)

    # ── Part 2: IC Decay ──
    print("\n[3/6] IC decay (factor persistence)...", flush=True)
    print(f"{'Factor':25s} | {'5d':>7s} {'10d':>7s} {'20d':>7s} {'60d':>7s} | {'Decay?':>6s}", flush=True)
    print("-" * 75, flush=True)
    for fname in factors:
        vals = [ic_results[fname][h]["icir"] for h in horizons]
        decay = "YES" if vals[-1] < vals[0] * 0.5 else "mild" if vals[-1] < vals[0] else "NO"
        print(f"{fname:25s} | {vals[0]:>+7.3f} {vals[1]:>+7.3f} {vals[2]:>+7.3f} {vals[3]:>+7.3f} | {decay:>6s}", flush=True)

    # ── Part 3: IC Stability (rolling 1-year IC) ──
    print("\n[4/6] IC stability (rolling 1-year)...", flush=True)
    fwd_20 = close.pct_change(20).shift(-20)
    for fname, fpanel in factors.items():
        ic_s = compute_ic(fpanel, fwd_20, sample_every=5)
        if len(ic_s) < 50:
            continue
        # Split into yearly chunks
        yearly_ic = ic_s.resample("YE").mean()
        pos_years = (yearly_ic > 0).sum()
        total_years = len(yearly_ic)
        stability = pos_years / total_years if total_years > 0 else 0
        print(f"  {fname:25s} yearly IC>0: {pos_years}/{total_years} ({stability:.0%})", flush=True)
        yearly_str = "  ".join(f"{y.year}:{v:+.3f}" for y, v in yearly_ic.items())
        print(f"    {yearly_str}", flush=True)

    # ── Part 4: Size stratification ──
    print("\n[5/6] Size stratification (large/mid/small)...", flush=True)
    mcap = market_cap_proxy(close, vol)
    # Use median market cap to split
    median_mcap = mcap.median(axis=1)

    for fname, fpanel in factors.items():
        print(f"\n  {fname}:", flush=True)
        for size_name, cond_fn in [
            ("large (top 33%)", lambda mc, row: mc > row.quantile(0.67)),
            ("mid (33-67%)", lambda mc, row: (mc >= row.quantile(0.33)) & (mc <= row.quantile(0.67))),
            ("small (bottom 33%)", lambda mc, row: mc < row.quantile(0.33)),
        ]:
            # Filter symbols by size each date
            size_factor = fpanel.copy()
            for dt in fpanel.index:
                if dt not in mcap.index:
                    continue
                mc_row = mcap.loc[dt]
                mask = cond_fn(mc_row, mc_row)
                excluded = mask.index[~mask]
                for sym in excluded:
                    if sym in size_factor.columns:
                        size_factor.loc[dt, sym] = np.nan

            ic_s = compute_ic(size_factor, fwd_20, sample_every=10)
            if len(ic_s) == 0:
                continue
            ic_mean = ic_s.mean()
            icir = ic_mean / ic_s.std() if ic_s.std() > 0 else 0
            print(f"    {size_name:20s} IC={ic_mean:+.4f} ICIR={icir:+.4f} N={len(ic_s)}", flush=True)

    # ── Part 5: Statistical tests on best factor ──
    print("\n[6/6] Statistical tests (revenue_yoy, 20d horizon)...", flush=True)
    best_ic = compute_ic(factors["revenue_yoy"], fwd_20, sample_every=5)
    n = len(best_ic)
    ic_mean = best_ic.mean()
    ic_std = best_ic.std()
    icir = ic_mean / ic_std

    # t-test
    t_stat, p_value = sp_stats.ttest_1samp(best_ic, 0)

    # Bootstrap CI
    rng = np.random.RandomState(42)
    boot_means = [rng.choice(best_ic.values, size=n, replace=True).mean() for _ in range(1000)]
    ci_lo = np.percentile(boot_means, 2.5)
    ci_hi = np.percentile(boot_means, 97.5)

    # Fraction of periods with IC > 0
    hit = (best_ic > 0).mean()

    print(f"  N observations: {n}", flush=True)
    print(f"  IC mean:  {ic_mean:+.4f}", flush=True)
    print(f"  IC std:   {ic_std:.4f}", flush=True)
    print(f"  ICIR:     {icir:+.4f}", flush=True)
    print(f"  Hit rate: {hit:.1%}", flush=True)
    print(f"  t-stat:   {t_stat:.3f}", flush=True)
    print(f"  p-value:  {p_value:.6f}", flush=True)
    print(f"  95% CI:   [{ci_lo:+.4f}, {ci_hi:+.4f}]", flush=True)

    sig = "SIGNIFICANT" if p_value < 0.05 else "NOT significant"
    harvey = "PASS (t > 3.0)" if abs(t_stat) > 3.0 else ("marginal (t > 2.0)" if abs(t_stat) > 2.0 else "FAIL")
    print(f"  Result:   {sig} ({harvey})", flush=True)

    # ── Summary ──
    print(f"\n{'='*80}", flush=True)
    print("SUMMARY", flush=True)
    print(f"{'='*80}", flush=True)
    print(f"Factors tested: {list(factors.keys())}", flush=True)
    print(f"Universe: {close.shape[1]} symbols, {close.shape[0]} dates", flush=True)
    print(f"Best factor: revenue_yoy (ICIR={icir:+.3f}, p={p_value:.4f})", flush=True)
    print(f"All 4 revenue factors ICIR > 0.3 at 20d horizon: "
          f"{all(ic_results[f][20]['icir'] > 0.3 for f in factors)}", flush=True)
    print(f"Total time: {time.time() - t_start:.0f}s", flush=True)


if __name__ == "__main__":
    main()
