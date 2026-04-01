"""Compare top-15 equal-weight vs AlphaPipeline construct_portfolio().

Tests whether score-weighted, turnover-penalized, cost-aware portfolio
construction can improve composite_growth_value from CAGR 6% / Sharpe 0.5
toward the 8% / 0.7 target.

Usage: python -m scripts.run_alpha_pipeline_test
"""
from __future__ import annotations

import sys
sys.path.insert(0, ".")
import os
os.environ.setdefault("QUANT_ENV", "dev")

import importlib.util
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.data.data_catalog import get_catalog
from src.alpha.construction import ConstructionConfig, construct_portfolio


# ── Config ────────────────────────────────────────────────────
START = "2018-01-01"
END = "2025-12-31"
INITIAL_CASH = 10_000_000
TOP_N = 15
COMMISSION_RATE = 0.001425
TAX_RATE = 0.003
MAX_WEIGHT = 0.10
INVESTED_FRAC = 0.95


def _load_factor_fn():
    path = "src/strategy/factors/research/composite_growth_value.py"
    spec = importlib.util.spec_from_file_location("cgv", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.compute_factor


def _build_universe(catalog, n=200):
    all_syms = sorted(
        s for s in catalog.available_symbols("price")
        if ".TW" in s and not s.replace(".TW", "").startswith("00")
    )
    good = []
    for sym in all_syms[:n]:
        df = catalog.get("price", sym)
        if len(df) >= 500:
            good.append(sym)
    return good


def _load_all_data(catalog, universe):
    """Load bars, revenue, per_history for the universe."""
    bars = {}
    revenue = {}
    per_history = {}

    print(f"Loading data for {len(universe)} symbols...")
    for sym in universe:
        df = catalog.get("price", sym)
        if not df.empty and "close" in df.columns:
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            bars[sym] = df

        rev = catalog.get("revenue", sym)
        if not rev.empty:
            if "date" in rev.columns:
                rev["date"] = pd.to_datetime(rev["date"])
            revenue[sym] = rev

        per = catalog.get("per", sym)
        if not per.empty:
            if "date" in per.columns:
                per["date"] = pd.to_datetime(per["date"])
            per_history[sym] = per

    print(f"  Loaded: {len(bars)} bars, {len(revenue)} revenue, {len(per_history)} per")
    return {
        "bars": bars,
        "revenue": revenue,
        "institutional": {},
        "per_history": per_history,
        "margin": {},
        "pe": {}, "pb": {}, "roe": {},
    }


def _get_monthly_rebalance_dates(bars: dict[str, pd.DataFrame], start: str, end: str):
    """Get the first trading day of each month within [start, end]."""
    all_dates = set()
    for df in bars.values():
        all_dates |= set(df.index)
    all_dates = sorted(d for d in all_dates
                       if pd.Timestamp(start) <= d <= pd.Timestamp(end))
    if not all_dates:
        return []

    monthly = []
    last_month = ""
    for d in all_dates:
        m = d.strftime("%Y-%m")
        if m != last_month:
            monthly.append(d)
            last_month = m
    return monthly


def _volume_filter(bars: dict[str, pd.DataFrame], as_of: pd.Timestamp,
                   min_vol=300_000, lookback=60, min_bars=20):
    """Filter symbols by volume (match strategy_builder)."""
    eligible = []
    for sym, df in bars.items():
        b = df.loc[:as_of]
        if len(b) < min_bars:
            continue
        avg_vol = float(b["volume"].iloc[-lookback:].mean()) if len(b) >= lookback else float(b["volume"].mean())
        if avg_vol >= min_vol:
            eligible.append(sym)
    return eligible


def _compute_daily_returns(bars: dict[str, pd.DataFrame], start: str, end: str):
    """Build daily return panel: index=date, columns=symbols."""
    close_dict = {}
    for sym, df in bars.items():
        subset = df.loc[pd.Timestamp(start):pd.Timestamp(end)]
        if "close" in subset.columns and len(subset) > 1:
            close_dict[sym] = subset["close"]
    close = pd.DataFrame(close_dict).sort_index()
    returns = close.pct_change().iloc[1:]
    return returns


def _simulate_portfolio(weights_by_date: dict[pd.Timestamp, dict[str, float]],
                        daily_returns: pd.DataFrame,
                        label: str,
                        cost_model: bool = True):
    """Simulate daily NAV from monthly rebalanced weights.

    Simple model: on rebalance day, move to target weights and pay
    round-trip cost on the delta. Between rebalances, weights drift
    with returns.
    """
    dates = sorted(daily_returns.index)
    rebalance_dates = sorted(weights_by_date.keys())

    nav = INITIAL_CASH
    nav_series = {dates[0]: nav}
    current_weights = pd.Series(dtype=float)  # symbol -> weight
    total_cost = 0.0

    reb_idx = 0

    for i, date in enumerate(dates):
        # Check if we need to rebalance
        while reb_idx < len(rebalance_dates) and rebalance_dates[reb_idx] <= date:
            target = weights_by_date[rebalance_dates[reb_idx]]
            target_s = pd.Series(target)

            if cost_model and not current_weights.empty:
                # Compute turnover cost
                all_syms = sorted(set(target_s.index) | set(current_weights.index))
                t = target_s.reindex(all_syms, fill_value=0.0)
                c = current_weights.reindex(all_syms, fill_value=0.0)
                turnover = float((t - c).abs().sum()) / 2
                # Cost: commission both sides + tax on sell side
                buy_cost = turnover * nav * COMMISSION_RATE
                sell_cost = turnover * nav * (COMMISSION_RATE + TAX_RATE)
                cost = buy_cost + sell_cost
                total_cost += cost
                nav -= cost

            current_weights = target_s.copy()
            reb_idx += 1

        # Apply daily returns
        if not current_weights.empty:
            day_ret = daily_returns.loc[date] if date in daily_returns.index else pd.Series(dtype=float)
            port_ret = 0.0
            new_weights = {}
            total_w = 0.0

            for sym, w in current_weights.items():
                r = day_ret.get(sym, 0.0)
                if pd.isna(r):
                    r = 0.0
                port_ret += w * r
                new_w = w * (1 + r)
                new_weights[sym] = new_w
                total_w += new_w

            nav *= (1 + port_ret)

            # Renormalize drifted weights
            if total_w > 0:
                current_weights = pd.Series({s: w / total_w * INVESTED_FRAC
                                             for s, w in new_weights.items() if w > 0.001})
            else:
                current_weights = pd.Series(dtype=float)

        nav_series[date] = nav

    nav_s = pd.Series(nav_series).sort_index()
    daily_ret = nav_s.pct_change().dropna()

    # Metrics
    n_years = len(daily_ret) / 252
    total_return = nav_s.iloc[-1] / nav_s.iloc[0] - 1
    cagr = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else 0
    vol = float(daily_ret.std() * np.sqrt(252))
    sharpe = float(daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() > 0 else 0

    # Max drawdown
    cummax = nav_s.cummax()
    dd = (nav_s - cummax) / cummax
    mdd = float(-dd.min())

    # Sortino
    down = daily_ret[daily_ret < 0]
    down_vol = float(down.std() * np.sqrt(252)) if len(down) > 0 else 0
    sortino = float(daily_ret.mean() / down.std() * np.sqrt(252)) if len(down) > 0 and down.std() > 0 else 0

    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  Period:       {nav_s.index[0].date()} ~ {nav_s.index[-1].date()}")
    print(f"  Final NAV:    ${nav_s.iloc[-1]:,.0f}")
    print(f"  Total Return: {total_return:+.2%}")
    print(f"  CAGR:         {cagr:+.2%}")
    print(f"  Sharpe:       {sharpe:.3f}")
    print(f"  Sortino:      {sortino:.3f}")
    print(f"  Max DD:       {mdd:.2%}")
    print(f"  Volatility:   {vol:.2%}")
    print(f"  Total Cost:   ${total_cost:,.0f}")

    return {
        "cagr": cagr, "sharpe": sharpe, "sortino": sortino,
        "mdd": mdd, "vol": vol, "total_return": total_return,
        "total_cost": total_cost, "nav_series": nav_s,
    }


def main():
    t0 = time.time()
    catalog = get_catalog()

    # 1. Build universe
    universe = _build_universe(catalog, n=200)
    print(f"Universe: {len(universe)} symbols")

    # 2. Load data
    data = _load_all_data(catalog, universe)
    bars = data["bars"]
    print(f"Data loaded in {time.time()-t0:.1f}s")

    # 3. Get monthly rebalance dates
    rebalance_dates = _get_monthly_rebalance_dates(bars, START, END)
    print(f"Rebalance dates: {len(rebalance_dates)} months")

    # 4. Build daily returns panel
    daily_returns = _compute_daily_returns(bars, START, END)
    print(f"Daily returns: {daily_returns.shape}")

    # 5. Load factor function
    compute_factor = _load_factor_fn()

    # 6. Compute factor values + weights for each rebalance date
    ew_weights = {}   # equal-weight top-15
    cp_weights = {}   # construct_portfolio (score-weighted, turnover-penalized)
    cp_weights_v2 = {}  # variant: wider portfolio, lower max_weight

    prev_cp_weights = None
    prev_cp_v2_weights = None

    config_cp = ConstructionConfig(
        max_weight=0.10,
        max_total_weight=0.95,
        min_weight=0.005,
        long_only=True,
        turnover_penalty=0.0005,
        cost_bps=30.0,
    )

    config_cp_v2 = ConstructionConfig(
        max_weight=0.06,         # wider spread
        max_total_weight=0.95,
        min_weight=0.005,
        long_only=True,
        turnover_penalty=0.001,  # stronger turnover penalty
        cost_bps=30.0,
        half_life=None,
    )

    print(f"\nComputing factor values for {len(rebalance_dates)} rebalance dates...")
    for idx, date in enumerate(rebalance_dates):
        as_of = pd.Timestamp(date)

        # Volume filter
        eligible = _volume_filter(bars, as_of)
        if not eligible:
            continue

        # Compute factor
        values = compute_factor(eligible, as_of, data)
        if not values or len(values) < 10:
            continue

        # ── Approach 1: Top-15 Equal Weight ──
        sorted_syms = sorted(values, key=lambda s: values[s], reverse=True)
        selected = sorted_syms[:TOP_N]
        n = len(selected)
        w = min(INVESTED_FRAC / n, MAX_WEIGHT)
        ew_weights[date] = {s: w for s in selected}

        # ── Approach 2: construct_portfolio (score-weighted) ──
        alpha_signal = pd.Series(values)
        # Standardize to z-scores for construct_portfolio
        mu, std = alpha_signal.mean(), alpha_signal.std()
        if std > 0:
            alpha_z = (alpha_signal - mu) / std
        else:
            alpha_z = alpha_signal

        cp_w = construct_portfolio(
            alpha_signal=alpha_z,
            current_weights=prev_cp_weights,
            config=config_cp,
        )
        if cp_w:
            cp_weights[date] = cp_w
            prev_cp_weights = pd.Series(cp_w)

        # ── Approach 3: wider portfolio, stronger turnover penalty ──
        cp_w2 = construct_portfolio(
            alpha_signal=alpha_z,
            current_weights=prev_cp_v2_weights,
            config=config_cp_v2,
        )
        if cp_w2:
            cp_weights_v2[date] = cp_w2
            prev_cp_v2_weights = pd.Series(cp_w2)

        if (idx + 1) % 12 == 0:
            print(f"  {idx+1}/{len(rebalance_dates)} done "
                  f"(factor coverage: {len(values)} symbols, "
                  f"EW: {len(selected)}, CP: {len(cp_w)}, CP-v2: {len(cp_w2)})")

    print(f"\nFactor computation done. EW: {len(ew_weights)} months, "
          f"CP: {len(cp_weights)} months, CP-v2: {len(cp_weights_v2)} months")

    # 7. Simulate
    r_ew = _simulate_portfolio(ew_weights, daily_returns, "Baseline: Top-15 Equal-Weight")
    r_cp = _simulate_portfolio(cp_weights, daily_returns, "AlphaPipeline: Score-Weighted + Turnover Penalty (0.0005)")
    r_cp2 = _simulate_portfolio(cp_weights_v2, daily_returns, "AlphaPipeline V2: Wider (max 6%) + Stronger Penalty (0.001)")

    # 8. Summary comparison
    print(f"\n{'='*70}")
    print(f"  COMPARISON SUMMARY")
    print(f"{'='*70}")
    print(f"{'Metric':<20} {'EW Top-15':>14} {'CP (score)':>14} {'CP-v2 (wide)':>14}")
    print(f"{'-'*20} {'-'*14} {'-'*14} {'-'*14}")
    print(f"{'CAGR':<20} {r_ew['cagr']:>+13.2%} {r_cp['cagr']:>+13.2%} {r_cp2['cagr']:>+13.2%}")
    print(f"{'Sharpe':<20} {r_ew['sharpe']:>14.3f} {r_cp['sharpe']:>14.3f} {r_cp2['sharpe']:>14.3f}")
    print(f"{'Sortino':<20} {r_ew['sortino']:>14.3f} {r_cp['sortino']:>14.3f} {r_cp2['sortino']:>14.3f}")
    print(f"{'Max DD':<20} {r_ew['mdd']:>13.2%} {r_cp['mdd']:>13.2%} {r_cp2['mdd']:>13.2%}")
    print(f"{'Volatility':<20} {r_ew['vol']:>13.2%} {r_cp['vol']:>13.2%} {r_cp2['vol']:>13.2%}")
    print(f"{'Total Cost':<20} ${r_ew['total_cost']:>12,.0f} ${r_cp['total_cost']:>12,.0f} ${r_cp2['total_cost']:>12,.0f}")
    print(f"{'Total Return':<20} {r_ew['total_return']:>+13.2%} {r_cp['total_return']:>+13.2%} {r_cp2['total_return']:>+13.2%}")

    # Target check
    print(f"\n{'='*70}")
    print(f"  TARGET: CAGR >= 8%, Sharpe >= 0.7")
    print(f"{'='*70}")
    for name, r in [("EW Top-15", r_ew), ("CP Score-Weighted", r_cp), ("CP-v2 Wide", r_cp2)]:
        cagr_ok = "PASS" if r["cagr"] >= 0.08 else "FAIL"
        sharpe_ok = "PASS" if r["sharpe"] >= 0.7 else "FAIL"
        print(f"  {name:<25} CAGR={r['cagr']:+.2%} [{cagr_ok}]  Sharpe={r['sharpe']:.3f} [{sharpe_ok}]")

    print(f"\nTotal time: {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
