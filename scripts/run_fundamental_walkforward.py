"""K5: 基本面因子 Walk-Forward 驗證。

測試 revenue_yoy + momentum_6m + pe_ratio 組合策略。
"""

from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FUND_DIR = Path("data/fundamental")
MARKET_DIR = Path("data/market")

HOLDING_PERIOD = 20
TRAIN_WINDOW = 120
COST_BPS = 50  # 單邊 50 bps
DD_CONTROL = 0.10  # 10% drawdown control
N_QUANTILES = 5


def load_price_panel() -> pd.DataFrame:
    all_close = {}
    for p in MARKET_DIR.glob("*.TW_1d.parquet"):
        sym = p.stem.replace("_1d", "")
        if sym.startswith("finmind_") or sym in ("0050.TW", "0056.TW"):
            continue
        try:
            df = pd.read_parquet(p)
            if not df.empty and "close" in df.columns:
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)
                df.index = pd.to_datetime(df.index.date)
                df = df[~df.index.duplicated(keep="first")]
                all_close[sym] = df["close"]
        except Exception:
            continue
    panel = pd.DataFrame(all_close).sort_index().dropna(how="all")
    return panel


def build_factor_panels(symbols: list[str], close_panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build all factor panels needed for walkforward."""
    panels = {}

    # 1. revenue_yoy (monthly → forward-fill to daily)
    yoy_data = {}
    for sym in symbols:
        p = FUND_DIR / f"{sym}_revenue.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if df.empty or "revenue" not in df.columns:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        rev = df.set_index("date")["revenue"].astype(float)
        yoy = rev.pct_change(12) * 100
        yoy_data[sym] = yoy
    if yoy_data:
        raw = pd.DataFrame(yoy_data).sort_index()
        panels["revenue_yoy"] = raw.reindex(close_panel.index, method="ffill", limit=60)

    # 2. momentum_6m (from prices)
    panels["momentum_6m"] = close_panel.pct_change(120)

    # 3. pe_ratio (inverse: 1/PE = value factor)
    pe_data = {}
    for sym in symbols:
        p = FUND_DIR / f"{sym}_per.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if df.empty or "PER" not in df.columns:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        pe = pd.to_numeric(df["PER"], errors="coerce")
        # Inverse: low PE = high score (value)
        inv_pe = 1.0 / pe.clip(lower=1)
        pe_data[sym] = inv_pe
    if pe_data:
        panels["value_pe"] = pd.DataFrame(pe_data).sort_index()

    return panels


def compute_composite_signal(
    factor_panels: dict[str, pd.DataFrame],
    date: pd.Timestamp,
    symbols: list[str],
    weights: dict[str, float] | None = None,
) -> pd.Series:
    """等權 z-score 合成信號。"""
    if weights is None:
        weights = {k: 1.0 for k in factor_panels}

    z_scores = []
    for name, panel in factor_panels.items():
        if date not in panel.index:
            continue
        vals = panel.loc[date, symbols].dropna()
        if len(vals) < 5:
            continue
        # Cross-sectional z-score
        z = (vals - vals.mean()) / vals.std()
        z_scores.append(z * weights.get(name, 1.0))

    if not z_scores:
        return pd.Series(dtype=float)

    combined = pd.concat(z_scores, axis=1).mean(axis=1)
    return combined.dropna()


def run_walkforward(
    close_panel: pd.DataFrame,
    factor_panels: dict[str, pd.DataFrame],
    strategy_name: str,
) -> dict:
    """Run walk-forward backtest with DD control."""
    dates = close_panel.index
    symbols_all = list(close_panel.columns)

    # Find symbols with factor coverage
    factor_symbols = set(symbols_all)
    for panel in factor_panels.values():
        factor_symbols &= set(panel.columns)
    factor_symbols = sorted(factor_symbols)

    if len(factor_symbols) < 10:
        return {"name": strategy_name, "error": f"Only {len(factor_symbols)} symbols with data"}

    # Walk-forward periods
    start_idx = TRAIN_WINDOW + HOLDING_PERIOD
    periods = []
    i = start_idx
    while i + HOLDING_PERIOD <= len(dates):
        periods.append((dates[i], dates[min(i + HOLDING_PERIOD - 1, len(dates) - 1)]))
        i += HOLDING_PERIOD

    if not periods:
        return {"name": strategy_name, "error": "No periods"}

    # Run each period
    period_returns = []
    benchmark_returns = []
    cumulative = 1.0
    peak = 1.0
    dd_active = False

    for period_start, period_end in periods:
        # Compute signal at period start
        signal = compute_composite_signal(factor_panels, period_start, factor_symbols)
        if signal.empty:
            period_returns.append(0.0)
            benchmark_returns.append(0.0)
            continue

        # Top quintile (Q5)
        q_threshold = signal.quantile(1 - 1.0 / N_QUANTILES)
        long_stocks = signal[signal >= q_threshold].index.tolist()

        if not long_stocks:
            period_returns.append(0.0)
            benchmark_returns.append(0.0)
            continue

        # Period returns
        start_prices = close_panel.loc[period_start]
        end_prices = close_panel.loc[period_end]

        strat_ret = 0.0
        n_valid = 0
        for s in long_stocks:
            if s in start_prices and s in end_prices:
                p0, p1 = start_prices[s], end_prices[s]
                if pd.notna(p0) and pd.notna(p1) and p0 > 0:
                    strat_ret += (p1 / p0 - 1)
                    n_valid += 1
        if n_valid > 0:
            strat_ret /= n_valid

        # Benchmark: equal-weight all factor_symbols
        bench_ret = 0.0
        n_bench = 0
        for s in factor_symbols:
            if s in start_prices and s in end_prices:
                p0, p1 = start_prices[s], end_prices[s]
                if pd.notna(p0) and pd.notna(p1) and p0 > 0:
                    bench_ret += (p1 / p0 - 1)
                    n_bench += 1
        if n_bench > 0:
            bench_ret /= n_bench

        # Cost deduction
        strat_ret -= COST_BPS / 10000 * 2  # round-trip cost per period

        # DD control
        cumulative *= (1 + strat_ret)
        peak = max(peak, cumulative)
        dd = (cumulative / peak) - 1
        if dd < -DD_CONTROL:
            dd_active = True
        if dd_active:
            strat_ret *= 0.5  # 50% position
            if dd > -DD_CONTROL * 0.5:
                dd_active = False

        period_returns.append(strat_ret)
        benchmark_returns.append(bench_ret)

    # Compute stats
    n_periods = len(period_returns)
    strat_cum = np.cumprod([1 + r for r in period_returns])
    bench_cum = np.cumprod([1 + r for r in benchmark_returns])

    total_ret = strat_cum[-1] - 1
    bench_total = bench_cum[-1] - 1
    n_years = n_periods * HOLDING_PERIOD / 252

    ann_ret = (1 + total_ret) ** (1 / n_years) - 1 if n_years > 0 else 0
    ann_vol = np.std(period_returns) * np.sqrt(252 / HOLDING_PERIOD)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0

    bench_ann = (1 + bench_total) ** (1 / n_years) - 1 if n_years > 0 else 0

    excess_ret = ann_ret - bench_ann
    excess_series = [s - b for s, b in zip(period_returns, benchmark_returns)]
    excess_vol = np.std(excess_series) * np.sqrt(252 / HOLDING_PERIOD)
    excess_sharpe = excess_ret / excess_vol if excess_vol > 0 else 0

    # MaxDD
    running_max = np.maximum.accumulate(strat_cum)
    drawdowns = strat_cum / running_max - 1
    max_dd = drawdowns.min()

    # Win rate
    win_rate = np.mean([r > 0 for r in period_returns])

    # Year-by-year
    year_results = {}
    period_dates = [p[0] for p in periods]
    for i, (pr, br) in enumerate(zip(period_returns, benchmark_returns)):
        yr = period_dates[i].year
        if yr not in year_results:
            year_results[yr] = {"strat": [], "bench": []}
        year_results[yr]["strat"].append(pr)
        year_results[yr]["bench"].append(br)

    return {
        "name": strategy_name,
        "n_periods": n_periods,
        "n_symbols": len(factor_symbols),
        "ann_return": ann_ret,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "win_rate": win_rate,
        "bench_ann": bench_ann,
        "excess_return": excess_ret,
        "excess_sharpe": excess_sharpe,
        "year_results": year_results,
    }


def print_year_breakdown(result: dict) -> None:
    yr_data = result.get("year_results", {})
    if not yr_data:
        return
    print(f"\n  {'Year':<6} {'Strategy':>10} {'Benchmark':>10} {'Excess':>10}")
    for yr in sorted(yr_data.keys()):
        s = np.prod([1 + r for r in yr_data[yr]["strat"]]) - 1
        b = np.prod([1 + r for r in yr_data[yr]["bench"]]) - 1
        e = s - b
        marker = "  **" if e > 0 else ""
        print(f"  {yr:<6} {s:>+9.1%} {b:>+9.1%} {e:>+9.1%}{marker}")


def main() -> None:
    t0 = time.perf_counter()

    print("Loading data...", flush=True)
    close_panel = load_price_panel()
    symbols = list(close_panel.columns)
    print(f"Price panel: {close_panel.shape[1]} symbols, {close_panel.shape[0]} dates")

    print("Building factor panels...", flush=True)
    all_panels = build_factor_panels(symbols, close_panel)
    for name, panel in all_panels.items():
        print(f"  {name}: {panel.shape}")

    # Define strategies
    strategies = {
        "revenue_yoy only": {"revenue_yoy": 1.0},
        "mom6m only": {"momentum_6m": 1.0},
        "rev_yoy + mom6m": {"revenue_yoy": 1.0, "momentum_6m": 1.0},
        "rev_yoy + value_pe": {"revenue_yoy": 1.0, "value_pe": 1.0},
        "rev + mom + value": {"revenue_yoy": 1.0, "momentum_6m": 1.0, "value_pe": 1.0},
    }

    print(f"\nRunning {len(strategies)} strategies...\n", flush=True)

    results = []
    for name, weights in strategies.items():
        panels_subset = {k: all_panels[k] for k in weights if k in all_panels}
        result = run_walkforward(close_panel, panels_subset, name)
        results.append(result)

    # Print results
    hdr = f"{'Strategy':<25} {'Ann%':>7} {'SR':>6} {'MDD':>7} {'Win%':>6} {'Bench%':>8} {'Excess%':>8} {'ExSR':>6}"
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        if "error" in r:
            print(f"{r['name']:<25} ERROR: {r['error']}")
            continue
        print(
            f"{r['name']:<25} {r['ann_return']:>+6.1%} {r['sharpe']:>+5.2f} "
            f"{r['max_dd']:>+6.1%} {r['win_rate']:>5.0%} "
            f"{r['bench_ann']:>+7.1%} {r['excess_return']:>+7.1%} {r['excess_sharpe']:>+5.2f}"
        )

    # Year breakdown for best strategy
    best = max((r for r in results if "error" not in r), key=lambda x: x["excess_sharpe"])
    print(f"\nBest strategy: {best['name']} (Excess SR = {best['excess_sharpe']:+.2f})")
    print_year_breakdown(best)

    # Bootstrap confidence
    print(f"\nTotal time: {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
