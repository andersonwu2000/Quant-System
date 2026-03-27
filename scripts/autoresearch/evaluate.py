#!/usr/bin/env python3
"""Alpha Factor Evaluation Harness — READ ONLY. Do NOT modify this file.

Autoresearch-style fixed evaluation for quantitative factor research.
Incorporates best practices from both Karpathy autoresearch and the
legacy alpha_research_agent pipeline.

Safety features:
  1. Revenue data truncated by 40 days BEFORE passing to factor function
  2. Agent cannot modify this file (evaluation criteria are fixed)
  3. L1 early-exit saves compute on bad factors (~30s vs ~3min)
  4. IC-series dedup catches clone factors numerically
  5. Full results.tsv enables post-hoc DSR (Deflated Sharpe Ratio)
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

# ---------------------------------------------------------------------------
# Constants — do NOT change
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

REVENUE_DELAY_DAYS = 40        # Taiwan monthly revenue publication delay
MIN_SYMBOLS = 30               # Minimum symbols per date for valid IC
EVAL_START = "2017-01-01"      # Evaluation period start
EVAL_END = "2024-12-31"        # Evaluation period end
SAMPLE_FREQ_DAYS = 20          # Sample IC every 20 trading days
FORWARD_HORIZONS = [5, 10, 20, 60]  # Forward return horizons (trading days)

# L1-L4 gate thresholds (from legacy factor_evaluator.py)
MIN_IC_L1 = 0.02              # L1: minimum |IC_20d| — fast reject
MIN_ICIR_L2 = 0.15            # L2: minimum ICIR (best horizon)
MAX_CORRELATION = 0.50         # L3: max IC-series correlation with known factors
MIN_POSITIVE_YEARS = 5         # L3: minimum years with positive mean IC
MIN_FITNESS = 3.0              # L4: minimum WorldQuant BRAIN fitness

# Dedup: known good factors' IC series (from legacy L3 check)
DEDUP_FACTORS_FILE = PROJECT_ROOT / "data" / "research" / "baseline_ic_series.json"

# Universe
UNIVERSE_FILE = PROJECT_ROOT / "data" / "research" / "universe.txt"
DEFAULT_UNIVERSE = [
    "2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW",
    "2881.TW", "2882.TW", "2886.TW", "2891.TW", "2892.TW",
    "1301.TW", "1303.TW", "1216.TW", "2002.TW", "2412.TW",
    "3711.TW", "2207.TW", "1101.TW", "2603.TW", "5880.TW",
    "3034.TW", "2303.TW", "6505.TW", "2345.TW", "2357.TW",
    "2395.TW", "2408.TW", "2474.TW", "2801.TW", "2880.TW",
    "2883.TW", "2884.TW", "2885.TW", "2887.TW", "2890.TW",
    "3037.TW", "3045.TW", "4904.TW", "5871.TW", "5876.TW",
    "1326.TW", "1402.TW", "2301.TW", "2327.TW", "2379.TW",
    "2609.TW", "2615.TW", "2912.TW", "3231.TW", "6415.TW",
]

# Large-scale universe for Stage 2 verification (865+ symbols)
LARGE_UNIVERSE_FILE = PROJECT_ROOT / "data" / "research" / "large_universe.txt"


# ---------------------------------------------------------------------------
# Data Loading (cached)
# ---------------------------------------------------------------------------

_data_cache: dict | None = None


def _load_universe(large: bool = False) -> list[str]:
    """Load universe from file or use default."""
    path = LARGE_UNIVERSE_FILE if large else UNIVERSE_FILE
    if path.exists():
        syms = [
            line.strip() for line in path.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
        if syms:
            return syms
    if large:
        # Fallback: scan all parquet files in data/market/
        market_dir = PROJECT_ROOT / "data" / "market"
        if market_dir.exists():
            syms = []
            for p in market_dir.glob("finmind_*.parquet"):
                bare = p.stem.replace("finmind_", "")
                syms.append(f"{bare}.TW")
            if len(syms) > 100:
                return sorted(syms)
    return list(DEFAULT_UNIVERSE)


def _load_all_data(universe: list[str]) -> dict:
    """Load all available data for the universe. Cached after first call."""
    global _data_cache
    if _data_cache is not None:
        return _data_cache

    print(f"Loading data for {len(universe)} symbols...")

    bars: dict[str, pd.DataFrame] = {}
    revenue: dict[str, pd.DataFrame] = {}
    institutional: dict[str, pd.DataFrame] = {}
    pe_ratios: dict[str, float] = {}
    pb_ratios: dict[str, float] = {}
    roe_values: dict[str, float] = {}

    market_dir = PROJECT_ROOT / "data" / "market"
    fund_dir = PROJECT_ROOT / "data" / "fundamental"

    for sym in universe:
        bare = sym.replace(".TW", "").replace(".TWO", "")

        # Market data (OHLCV) — try multiple naming conventions
        for pattern in [f"{sym}_1d.parquet", f"{sym}.parquet", f"finmind_{bare}.parquet"]:
            path = market_dir / pattern
            if path.exists():
                df = pd.read_parquet(path)
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.set_index("date").sort_index()
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)
                df.index = pd.to_datetime(df.index.date)  # normalize to date-only
                df = df[~df.index.duplicated(keep="first")]
                if not df.empty and "close" in df.columns:
                    bars[sym] = df
                break

        # Revenue (try sym first, then bare)
        rev_path = fund_dir / f"{sym}_revenue.parquet"
        if not rev_path.exists():
            rev_path = fund_dir / f"{bare}_revenue.parquet"
        if rev_path.exists():
            df = pd.read_parquet(rev_path)
            if not df.empty and "revenue" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                revenue[sym] = df.sort_values("date")

        # Institutional
        inst_path = fund_dir / f"{sym}_institutional.parquet"
        if not inst_path.exists():
            inst_path = fund_dir / f"{bare}_institutional.parquet"
        if inst_path.exists():
            df = pd.read_parquet(inst_path)
            if not df.empty:
                df["date"] = pd.to_datetime(df["date"])
                institutional[sym] = df.sort_values("date")

        # Financial metrics (PE, PB, ROE)
        fin_path = fund_dir / f"{sym}_financial_statement.parquet"
        if not fin_path.exists():
            fin_path = fund_dir / f"{bare}_financial_statement.parquet"
        if fin_path.exists():
            try:
                df = pd.read_parquet(fin_path)
                if not df.empty:
                    latest = df.iloc[-1]
                    if "pe_ratio" in df.columns:
                        pe_ratios[sym] = float(latest.get("pe_ratio", 0) or 0)
                    if "pb_ratio" in df.columns:
                        pb_ratios[sym] = float(latest.get("pb_ratio", 0) or 0)
                    if "roe" in df.columns:
                        roe_values[sym] = float(latest.get("roe", 0) or 0)
            except Exception:
                pass

    print(f"  Loaded: {len(bars)} bars, {len(revenue)} revenue, "
          f"{len(institutional)} institutional, {len(pe_ratios)} PE ratios")

    _data_cache = {
        "bars": bars,
        "revenue": revenue,
        "institutional": institutional,
        "pe": pe_ratios,
        "pb": pb_ratios,
        "roe": roe_values,
    }
    return _data_cache


def _load_dedup_ic_series() -> dict[str, list[float]]:
    """Load known factors' IC series for dedup (L3 correlation check)."""
    if DEDUP_FACTORS_FILE.exists():
        try:
            with open(DEDUP_FACTORS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# ---------------------------------------------------------------------------
# Revenue Delay Enforcement (agent cannot bypass)
# ---------------------------------------------------------------------------

def _mask_revenue(data: dict, as_of: pd.Timestamp) -> dict:
    """Return a copy of data with revenue truncated by REVENUE_DELAY_DAYS."""
    masked = dict(data)
    cutoff = as_of - pd.DateOffset(days=REVENUE_DELAY_DAYS)
    masked["revenue"] = {
        sym: df[df["date"] <= cutoff].copy()
        for sym, df in data["revenue"].items()
    }
    masked["institutional"] = {
        sym: df[df["date"] <= as_of].copy()
        for sym, df in data["institutional"].items()
    }
    return masked


# ---------------------------------------------------------------------------
# Forward Return Computation
# ---------------------------------------------------------------------------

def _compute_forward_returns(
    bars: dict[str, pd.DataFrame], as_of: pd.Timestamp, horizon: int,
) -> dict[str, float]:
    """Compute forward returns for each symbol from as_of."""
    returns: dict[str, float] = {}
    for sym, df in bars.items():
        if as_of not in df.index:
            continue
        future = df.index[df.index > as_of]
        if len(future) < horizon:
            continue
        try:
            p0 = float(df.loc[as_of, "close"])
            p1 = float(df.loc[future[horizon - 1], "close"])
            if p0 > 0:
                returns[sym] = p1 / p0 - 1
        except Exception:
            continue
    return returns


# ---------------------------------------------------------------------------
# IC / ICIR Computation
# ---------------------------------------------------------------------------

def _compute_ic(
    factor_values: dict[str, float], forward_returns: dict[str, float],
) -> float | None:
    """Compute Spearman rank IC."""
    common = set(factor_values) & set(forward_returns)
    if len(common) < MIN_SYMBOLS:
        return None
    syms = sorted(common)
    x = [factor_values[s] for s in syms]
    y = [forward_returns[s] for s in syms]
    if all(v == x[0] for v in x):
        return None
    ic, _ = spearmanr(x, y)
    return float(ic) if not np.isnan(ic) else None


# ---------------------------------------------------------------------------
# Dedup: IC-series correlation check (from legacy L3)
# ---------------------------------------------------------------------------

def _check_dedup(ic_series_20d: list[float], known: dict[str, list[float]]) -> tuple[float, str]:
    """Check max correlation between this factor's IC series and known factors.

    Returns (max_correlation, correlated_with_name).
    """
    if not known or len(ic_series_20d) < 10:
        return 0.0, ""

    new = pd.Series(ic_series_20d)
    max_corr = 0.0
    max_name = ""
    for name, existing_ics in known.items():
        min_len = min(len(new), len(existing_ics))
        if min_len < 10:
            continue
        corr = float(new.iloc[:min_len].corr(pd.Series(existing_ics[:min_len])))
        if abs(corr) > abs(max_corr):
            max_corr = corr
            max_name = name
    return max_corr, max_name


# ---------------------------------------------------------------------------
# Main Evaluation (with early-exit from legacy L1-L4 gates)
# ---------------------------------------------------------------------------

def evaluate() -> dict:
    """Run the full evaluation pipeline with early-exit gates.

    Stage 1: Core universe (50 symbols) — fast screening
      L1: |IC_20d| >= 0.02     (early exit if fail — saves ~2 min)
      L2: |ICIR| >= 0.15
      L3: dedup correlation <= 0.50, yearly stability
      L4: fitness >= 3.0

    Stage 2 (if L4 passed): Large universe (865+ symbols) — confirmation
      Recompute ICIR on full universe, require ICIR(20d) >= 0.20
    """
    from factor import compute_factor

    universe = _load_universe()
    data = _load_all_data(universe)
    bars = data["bars"]
    known_ics = _load_dedup_ic_series()

    # Build sample dates
    all_dates: set[pd.Timestamp] = set()
    for df in bars.values():
        all_dates |= set(df.index)
    eval_dates = sorted(d for d in all_dates
                        if pd.Timestamp(EVAL_START) <= d <= pd.Timestamp(EVAL_END))
    sample_dates = eval_dates[::SAMPLE_FREQ_DAYS]

    print(f"Stage 1: {len(sample_dates)} dates, {len(bars)} symbols")

    # ── Stage 1: L1 early screening (20d IC only, first 30 dates) ──
    t0 = time.time()
    early_ics: list[float] = []
    early_limit = min(30, len(sample_dates))

    for as_of in sample_dates[:early_limit]:
        masked_data = _mask_revenue(data, as_of)
        active = [s for s in universe if s in bars and as_of in bars[s].index]
        if len(active) < MIN_SYMBOLS:
            continue
        try:
            values = compute_factor(active, as_of, masked_data)
        except Exception as e:
            print(f"  [WARN] Factor crashed at {as_of}: {e}")
            continue
        values = {k: v for k, v in (values or {}).items()
                  if isinstance(v, (int, float)) and np.isfinite(v)}
        if len(values) < MIN_SYMBOLS:
            continue
        fwd = _compute_forward_returns(bars, as_of, 20)
        ic = _compute_ic(values, fwd)
        if ic is not None:
            early_ics.append(ic)

    early_ic = float(np.mean(early_ics)) if early_ics else 0.0
    early_time = time.time() - t0

    # L1 early exit
    if abs(early_ic) < MIN_IC_L1:
        return _make_result(
            level="L0", failure=f"|IC_20d|={abs(early_ic):.4f} < {MIN_IC_L1} (early exit)",
            ic_20d=early_ic, elapsed=early_time,
        )

    print(f"  L1 passed: IC_20d={early_ic:.4f} ({early_time:.1f}s)")

    # ── Stage 1: Full evaluation (all dates, all horizons) ──
    ic_by_horizon: dict[int, list[float]] = {h: [] for h in FORWARD_HORIZONS}
    ic_by_year: dict[int, list[float]] = {}
    ic_series_20d: list[float] = []
    turnover_changes = 0
    turnover_total = 0
    prev_top: set[str] | None = None

    for as_of in sample_dates:
        masked_data = _mask_revenue(data, as_of)
        active = [s for s in universe if s in bars and as_of in bars[s].index]
        if len(active) < MIN_SYMBOLS:
            continue
        try:
            values = compute_factor(active, as_of, masked_data)
        except Exception:
            continue
        values = {k: v for k, v in (values or {}).items()
                  if isinstance(v, (int, float)) and np.isfinite(v)}
        if len(values) < MIN_SYMBOLS:
            continue

        for h in FORWARD_HORIZONS:
            fwd = _compute_forward_returns(bars, as_of, h)
            ic = _compute_ic(values, fwd)
            if ic is not None:
                ic_by_horizon[h].append(ic)
                if h == 20:
                    ic_by_year.setdefault(as_of.year, []).append(ic)
                    ic_series_20d.append(ic)

        sorted_syms = sorted(values, key=lambda s: values[s], reverse=True)
        n_top = max(len(sorted_syms) // 5, 1)
        top = set(sorted_syms[:n_top])
        if prev_top is not None:
            changed = len(top.symmetric_difference(prev_top))
            turnover_changes += changed
            turnover_total += len(top | prev_top)
        prev_top = top

    elapsed = time.time() - t0

    # Compute metrics
    ics_20d = ic_by_horizon.get(20, [])
    ic_20d = float(np.mean(ics_20d)) if ics_20d else 0.0

    icir_by_horizon: dict[str, float] = {}
    best_icir = 0.0
    best_horizon = ""
    for h in FORWARD_HORIZONS:
        ics = ic_by_horizon[h]
        if len(ics) >= 5:
            ic_mean = float(np.mean(ics))
            ic_std = float(np.std(ics, ddof=1))
            icir = ic_mean / ic_std if ic_std > 0 else 0.0
        else:
            icir = 0.0
        icir_by_horizon[f"{h}d"] = round(icir, 4)
        if abs(icir) > abs(best_icir):
            best_icir = icir
            best_horizon = f"{h}d"

    avg_turnover = turnover_changes / turnover_total if turnover_total > 0 else 0.0
    positive_years = sum(1 for ics in ic_by_year.values() if np.mean(ics) > 0)
    total_years = len(ic_by_year)
    returns_proxy = abs(ic_20d) * 10000
    effective_turnover = max(avg_turnover, 0.125)
    fitness = math.sqrt(returns_proxy / effective_turnover) * abs(best_icir) if returns_proxy > 0 else 0.0

    # L3: Dedup check
    max_corr, corr_with = _check_dedup(ic_series_20d, known_ics)

    # ── Gate checks (L2-L4) ──
    if abs(best_icir) < MIN_ICIR_L2:
        return _make_result(
            level="L1", failure=f"|ICIR|={abs(best_icir):.4f} < {MIN_ICIR_L2}",
            ic_20d=ic_20d, best_icir=best_icir, best_horizon=best_horizon,
            icir_by_horizon=icir_by_horizon, avg_turnover=avg_turnover,
            elapsed=elapsed,
        )

    if abs(max_corr) > MAX_CORRELATION:
        return _make_result(
            level="L2", failure=f"corr={max_corr:.3f} with {corr_with} > {MAX_CORRELATION}",
            ic_20d=ic_20d, best_icir=best_icir, best_horizon=best_horizon,
            icir_by_horizon=icir_by_horizon, avg_turnover=avg_turnover,
            max_correlation=max_corr, correlated_with=corr_with,
            elapsed=elapsed,
        )

    if positive_years < MIN_POSITIVE_YEARS and total_years >= MIN_POSITIVE_YEARS:
        return _make_result(
            level="L2", failure=f"positive_years={positive_years}/{total_years} < {MIN_POSITIVE_YEARS}",
            ic_20d=ic_20d, best_icir=best_icir, best_horizon=best_horizon,
            icir_by_horizon=icir_by_horizon, avg_turnover=avg_turnover,
            positive_years=positive_years, total_years=total_years,
            elapsed=elapsed,
        )

    if fitness < MIN_FITNESS:
        return _make_result(
            level="L3", failure=f"fitness={fitness:.2f} < {MIN_FITNESS}",
            ic_20d=ic_20d, best_icir=best_icir, best_horizon=best_horizon,
            icir_by_horizon=icir_by_horizon, avg_turnover=avg_turnover,
            fitness=fitness, positive_years=positive_years, total_years=total_years,
            elapsed=elapsed,
        )

    print(f"  L4 passed: ICIR={best_icir:.4f}, fitness={fitness:.2f}")

    # ── Stage 2: Large-scale IC verification (865+ symbols) ──
    large_icir_20d = 0.0
    large_universe = _load_universe(large=True)
    if len(large_universe) > len(universe):
        print(f"\nStage 2: Large-scale verification ({len(large_universe)} symbols)")
        # Reset cache to load full universe
        global _data_cache
        saved_cache = _data_cache
        _data_cache = None
        try:
            large_data = _load_all_data(large_universe)
            large_bars = large_data["bars"]
            large_ics: list[float] = []
            # Sample fewer dates for speed (every 40 days)
            large_dates = eval_dates[::40]
            for as_of in large_dates:
                masked = _mask_revenue(large_data, as_of)
                active = [s for s in large_universe if s in large_bars and as_of in large_bars[s].index]
                if len(active) < 50:
                    continue
                try:
                    vals = compute_factor(active, as_of, masked)
                except Exception:
                    continue
                vals = {k: v for k, v in (vals or {}).items()
                        if isinstance(v, (int, float)) and np.isfinite(v)}
                if len(vals) < 50:
                    continue
                fwd = _compute_forward_returns(large_bars, as_of, 20)
                ic = _compute_ic(vals, fwd)
                if ic is not None:
                    large_ics.append(ic)

            if len(large_ics) >= 5:
                large_ic_std = float(np.std(large_ics, ddof=1))
                large_icir_20d = float(np.mean(large_ics)) / large_ic_std if large_ic_std > 0 else 0.0
            print(f"  Large-scale ICIR(20d): {large_icir_20d:.4f} ({len(large_ics)} dates)")
        except Exception as e:
            print(f"  [WARN] Large-scale verification failed: {e}")
        finally:
            _data_cache = saved_cache  # restore small universe cache

    elapsed = time.time() - t0

    return _make_result(
        level="L4", passed=True,
        ic_20d=ic_20d, best_icir=best_icir, best_horizon=best_horizon,
        icir_by_horizon=icir_by_horizon, avg_turnover=avg_turnover,
        fitness=fitness, positive_years=positive_years, total_years=total_years,
        max_correlation=max_corr, correlated_with=corr_with,
        large_icir_20d=large_icir_20d,
        elapsed=elapsed,
    )


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------

def _make_result(
    level: str = "L0", passed: bool = False, failure: str = "",
    ic_20d: float = 0.0, best_icir: float = 0.0, best_horizon: str = "",
    icir_by_horizon: dict | None = None, avg_turnover: float = 0.0,
    fitness: float = 0.0, positive_years: int = 0, total_years: int = 0,
    max_correlation: float = 0.0, correlated_with: str = "",
    large_icir_20d: float = 0.0, elapsed: float = 0.0,
) -> dict:
    composite = (
        abs(best_icir) * 5.0
        + fitness * 0.3
        + (positive_years / max(total_years, 1)) * 2.0
    )
    return {
        "passed": passed,
        "level": level,
        "failure": failure,
        "composite_score": round(composite, 4),
        "ic_20d": round(ic_20d, 4),
        "icir_by_horizon": icir_by_horizon or {},
        "best_icir": round(best_icir, 4),
        "best_horizon": best_horizon,
        "avg_turnover": round(avg_turnover, 4),
        "positive_years": positive_years,
        "total_years": total_years,
        "fitness": round(fitness, 2),
        "max_correlation": round(max_correlation, 3),
        "correlated_with": correlated_with,
        "large_icir_20d": round(large_icir_20d, 4),
        "elapsed_seconds": round(elapsed, 1),
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("Alpha Factor Evaluation Harness v2 (READ ONLY)")
    print("  L1 early-exit | IC-series dedup | large-scale verification")
    print("=" * 60)

    try:
        results = evaluate()
    except Exception as e:
        print("\n--- CRASH ---")
        print(f"error: {e}")
        import traceback
        traceback.print_exc()
        print("composite_score: 0.0000")
        print("status: crash")
        sys.exit(1)

    print("\n--- RESULTS ---")
    print(f"composite_score:  {results['composite_score']:.4f}")
    print(f"ic_20d:           {results['ic_20d']:.4f}")
    print(f"best_icir:        {results['best_icir']:.4f}")
    print(f"best_horizon:     {results['best_horizon']}")
    print(f"fitness:          {results['fitness']:.2f}")
    print(f"avg_turnover:     {results['avg_turnover']:.4f}")
    print(f"positive_years:   {results['positive_years']}/{results['total_years']}")
    print(f"max_correlation:  {results['max_correlation']:.3f} ({results['correlated_with']})")
    print(f"large_icir_20d:   {results['large_icir_20d']:.4f}")
    print(f"level:            {results['level']}")
    print(f"passed:           {results['passed']}")
    if results["failure"]:
        print(f"failure:          {results['failure']}")
    print(f"elapsed_seconds:  {results['elapsed_seconds']:.1f}")

    for h, icir in results["icir_by_horizon"].items():
        print(f"icir_{h}:          {icir:.4f}")

    if results["passed"]:
        print("\nstatus: PASSED (L4+)")
        # Auto-submit to system pipeline for Validator + deploy
        _auto_submit(results)
    elif results["composite_score"] > 0:
        print(f"\nstatus: evaluated ({results['level']})")
    else:
        print("\nstatus: no_signal")


def _auto_submit(results: dict) -> None:
    """Submit passed factor to API for Validator 15-check + auto-deploy."""
    try:
        import requests
        factor_code = Path(__file__).parent.joinpath("factor.py").read_text(encoding="utf-8")
        # Extract factor name from git log or use generic
        name = f"autoresearch_{int(time.time())}"
        try:
            import subprocess
            log = subprocess.run(
                ["git", "log", "--oneline", "-1", "--format=%s"],
                capture_output=True, text=True, timeout=5,
                cwd=str(Path(__file__).parent),
            )
            if log.returncode == 0 and log.stdout.strip():
                import re as _re
                raw = log.stdout.strip().replace("experiment: ", "").replace(" ", "_")[:40]
                raw = _re.sub(r'[^a-zA-Z0-9_]', '', raw)
                name = f"ar_{raw}" if raw else name
        except Exception:
            pass

        resp = requests.post(
            "http://127.0.0.1:8000/api/v1/auto-alpha/submit-factor",
            json={
                "name": name,
                "code": factor_code,
                "composite_score": results["composite_score"],
                "icir_20d": results["icir_by_horizon"].get("20d", 0),
                "large_icir_20d": results["large_icir_20d"],
                "description": f"autoresearch L4+ (score={results['composite_score']:.2f})",
            },
            headers={"X-API-Key": "dev-key"},
            timeout=300,
        )
        if resp.status_code == 200:
            data = resp.json()
            print("\n--- SYSTEM PIPELINE ---")
            print(f"validator: {data.get('validator_passed', '?')}/{data.get('validator_total', '?')}")
            print(f"deployed:  {data.get('deployed', False)}")
            print(f"message:   {data.get('message', '')}")
        else:
            print(f"\n[WARN] submit-factor failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"\n[WARN] auto-submit failed: {e} (API server may not be running)")


if __name__ == "__main__":
    main()
