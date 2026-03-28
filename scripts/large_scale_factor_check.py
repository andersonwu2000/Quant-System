"""大規模因子 IC 檢驗 — 874 支台股全 universe 驗證。

用法:
    python -m scripts.large_scale_factor_check
"""
from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MARKET_DIR = Path("data/market")
FUND_DIR = Path("data/fundamental")


def load_data():
    data = {}
    for p in sorted(MARKET_DIR.glob("*_1d.parquet")):
        sym = p.stem.replace("_1d", "")
        if sym.startswith("finmind_"):
            sym = sym[len("finmind_"):]
        if sym.startswith("00") or ".TW" not in sym:
            continue
        try:
            df = pd.read_parquet(p)
            if len(df) < 500:
                continue
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            df.index = pd.to_datetime(df.index.date)
            df = df[~df.index.duplicated(keep="first")]
            data[sym] = df
        except Exception:
            continue
    return data


def load_revenue():
    cache = {}
    for p in sorted(FUND_DIR.glob("*_revenue.parquet")):
        sym = p.stem.replace("_revenue", "")
        try:
            df = pd.read_parquet(p)
            if df.empty or "revenue" not in df.columns:
                continue
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
            df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")
            cache[sym] = df
        except Exception:
            continue
    return cache


# ── Factor definitions ──────────────────────────────────────────


def make_rev_seasonal_deviation(rev_cache):
    def compute(symbols, as_of):
        results = {}
        for sym in symbols:
            df = rev_cache.get(sym)
            if df is None:
                continue
            usable = df[df["date"] <= as_of - pd.DateOffset(days=40)]
            if len(usable) < 36:
                continue
            revenues = usable["revenue"].astype(float).values
            current = revenues[-1]
            idx = len(revenues) - 1
            same = [revenues[idx - 12 * k] for k in range(1, 4) if idx - 12 * k >= 0]
            if not same or np.mean(same) <= 0:
                continue
            results[sym] = float(current / np.mean(same) - 1)
        return results
    return compute


def make_rev_accel_2nd_deriv(rev_cache):
    def compute(symbols, as_of):
        results = {}
        for sym in symbols:
            df = rev_cache.get(sym)
            if df is None:
                continue
            usable = df[df["date"] <= as_of - pd.DateOffset(days=40)]
            if len(usable) < 24:
                continue
            rev = usable["revenue"].astype(float).values
            if len(rev) < 24:
                continue
            prev = rev[-13:-1]
            prev2 = rev[-25:-13]
            if len(prev) < 12 or len(prev2) < 12:
                continue
            if prev[-1] <= 0 or prev2[-1] <= 0:
                continue
            yoy1 = rev[-1] / prev[-1] - 1
            yoy0 = prev[-1] / prev2[-1] - 1
            results[sym] = yoy1 - yoy0
        return results
    return compute


def make_rev_acceleration(rev_cache):
    def compute(symbols, as_of):
        results = {}
        for sym in symbols:
            df = rev_cache.get(sym)
            if df is None:
                continue
            usable = df[df["date"] <= as_of - pd.DateOffset(days=40)]
            if len(usable) < 12:
                continue
            rev = usable["revenue"].astype(float).values
            r3 = np.mean(rev[-3:])
            r12 = np.mean(rev[-12:])
            if r12 <= 0:
                continue
            results[sym] = r3 / r12
        return results
    return compute


def make_rev_new_high(rev_cache):
    def compute(symbols, as_of):
        results = {}
        for sym in symbols:
            df = rev_cache.get(sym)
            if df is None:
                continue
            usable = df[df["date"] <= as_of - pd.DateOffset(days=40)]
            if len(usable) < 12:
                continue
            rev = usable["revenue"].astype(float).values
            if len(rev) < 12:
                continue
            current = rev[-1]
            past_max = np.max(rev[-12:-1]) if len(rev) > 12 else np.max(rev[:-1])
            if past_max <= 0:
                continue
            results[sym] = float(current / past_max)
        return results
    return compute


def make_rev_yoy(rev_cache):
    def compute(symbols, as_of):
        results = {}
        for sym in symbols:
            df = rev_cache.get(sym)
            if df is None:
                continue
            usable = df[df["date"] <= as_of - pd.DateOffset(days=40)]
            if len(usable) < 13:
                continue
            rev = usable["revenue"].astype(float).values
            if rev[-13] <= 0:
                continue
            results[sym] = rev[-1] / rev[-13] - 1
        return results
    return compute


def make_rev_momentum(rev_cache):
    def compute(symbols, as_of):
        results = {}
        for sym in symbols:
            df = rev_cache.get(sym)
            if df is None:
                continue
            usable = df[df["date"] <= as_of - pd.DateOffset(days=40)]
            if len(usable) < 6:
                continue
            rev = usable["revenue"].astype(float).values
            r3 = np.mean(rev[-3:])
            r6 = np.mean(rev[-6:])
            if r6 <= 0:
                continue
            results[sym] = r3 / r6
        return results
    return compute


def main():
    print("=== Large-Scale Factor IC Validation ===")
    print()

    data = load_data()
    print(f"Price data: {len(data)} stocks")

    rev_cache = load_revenue()
    print(f"Revenue data: {len(rev_cache)} stocks")
    print()

    factors = {
        "rev_seasonal_deviation": make_rev_seasonal_deviation(rev_cache),
        "rev_accel_2nd_derivative": make_rev_accel_2nd_deriv(rev_cache),
        "revenue_acceleration": make_rev_acceleration(rev_cache),
        "revenue_new_high": make_rev_new_high(rev_cache),
        "revenue_yoy": make_rev_yoy(rev_cache),
        "revenue_momentum": make_rev_momentum(rev_cache),
    }

    all_symbols = sorted(data.keys())
    all_dates = sorted(set().union(*[set(data[s].index) for s in all_symbols]))
    trading_day_index = pd.DatetimeIndex(all_dates)
    monthly_periods = trading_day_index.to_period("M").unique()

    horizons = [5, 20, 60]
    ic_store = {name: {h: [] for h in horizons} for name in factors}

    t0 = time.time()
    n_months = 0

    for period in monthly_periods:
        month_end = period.to_timestamp() + pd.DateOffset(months=1) - pd.DateOffset(days=1)
        if month_end < pd.Timestamp("2017-01-01") or month_end > pd.Timestamp("2025-12-31"):
            continue
        candidates = trading_day_index[trading_day_index <= month_end]
        if len(candidates) == 0:
            continue
        as_of = candidates[-1]

        active = [s for s in all_symbols if s in data and as_of in data[s].index]
        if len(active) < 50:
            continue

        for fname, ffunc in factors.items():
            fvals = ffunc(active, as_of)
            if len(fvals) < 20:
                continue

            for horizon in horizons:
                xs, ys = [], []
                for sym, fv in fvals.items():
                    if sym not in data:
                        continue
                    df = data[sym]
                    if as_of not in df.index:
                        continue
                    after = df.index[df.index > as_of]
                    if len(after) < horizon:
                        continue
                    ret = float(df.loc[after[horizon - 1], "close"] / df.loc[as_of, "close"] - 1)
                    xs.append(fv)
                    ys.append(ret)

                if len(xs) < 20:
                    continue
                ic, _ = spearmanr(xs, ys)
                if not np.isnan(ic):
                    ic_store[fname][horizon].append(ic)

        n_months += 1
        if n_months % 20 == 0:
            print(f"  {n_months} months done...")

    elapsed = time.time() - t0
    print(f"Completed: {n_months} months, {elapsed:.0f}s")
    print()

    # ── Print table ──
    print("| Factor | Type | ICIR(5d) | ICIR(20d) | ICIR(60d) | N | Hit%(20d) |")
    print("|--------|------|:--------:|:---------:|:---------:|:-:|:---------:|")

    for fname in factors:
        ftype = "NEW" if fname.startswith("rev_s") or fname.startswith("rev_a") else "existing"
        row = []
        for h in horizons:
            ics = ic_store[fname][h]
            if len(ics) > 5:
                icir = np.mean(ics) / np.std(ics, ddof=1) if np.std(ics, ddof=1) > 0 else 0
                row.append(f"{icir:+.3f}")
            else:
                row.append("N/A")
        ics_20 = ic_store[fname][20]
        hit = sum(1 for x in ics_20 if x > 0) / len(ics_20) * 100 if ics_20 else 0
        n = len(ics_20)
        print(f"| **{fname}** | {ftype} | {row[0]} | {row[1]} | {row[2]} | {n} | {hit:.1f}% |")


if __name__ == "__main__":
    main()
