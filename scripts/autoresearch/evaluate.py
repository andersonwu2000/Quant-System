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

import os as _os
# Support both local (scripts/autoresearch/evaluate.py) and Docker (/app/evaluate.py)
PROJECT_ROOT = Path(_os.environ["PROJECT_ROOT"]) if "PROJECT_ROOT" in _os.environ \
    else Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

REVENUE_DELAY_DAYS = 40        # Taiwan monthly revenue publication delay
MIN_SYMBOLS = 50               # Minimum symbols per date for valid IC (200-stock universe)
EVAL_START = "2017-01-01"      # Evaluation period start

# Rolling OOS: computed at runtime (not import time) via _compute_dates()
# OOS = most recent 1.5 years (before forward-return buffer)
# Forward returns need ~60 trading days ≈ 3 months after EVAL_END
from datetime import datetime as _dt, timedelta as _td

def _compute_dates() -> tuple[str, str, str]:
    """Compute rolling dates at call time, not import time."""
    today = _dt.now()
    eval_end = (today - _td(days=90)).strftime("%Y-%m-%d")
    oos_start = (today - _td(days=90 + 548)).strftime("%Y-%m-%d")
    is_end = (today - _td(days=91 + 548)).strftime("%Y-%m-%d")
    return eval_end, oos_start, is_end

EVAL_END, OOS_START, IS_END = _compute_dates()
SAMPLE_FREQ_DAYS = 20          # Sample IC every 20 trading days
FORWARD_HORIZONS = [5, 10, 20, 60]  # Forward return horizons (trading days)

# L1-L4 gate thresholds (from legacy factor_evaluator.py)
MIN_IC_L1 = 0.02              # L1: minimum |IC_20d| — fast reject
MIN_ICIR_L2 = 0.15            # L2: minimum ICIR (best horizon)
MAX_CORRELATION = 0.50         # L3: max IC-series correlation with known factors
MIN_POSITIVE_YEARS = 4         # L3: minimum years with positive mean IC (IS=6.5yr)
MIN_FITNESS = 3.0              # L4: minimum WorldQuant BRAIN fitness

# L5: OOS validation thresholds (Phase X anti-overfitting)
OOS_ICIR_DECAY_MAX = 0.60     # OOS |ICIR| must be >= IS |ICIR| * (1 - decay)

# Thresholdout (Dwork et al. 2015): add noise to L5 pass/fail to preserve holdout validity
# Safe budget ≈ τ² × n_oos_days. With τ=0.10, n=375 → B ≈ 3.75 (pure adaptive).
# Thresholdout raises effective budget to O(n) by adding Laplace noise to comparisons.
THRESHOLDOUT_NOISE_SCALE = 0.05   # Laplace scale for noisy L5 comparisons
L5_QUERY_BUDGET = 200             # warn after this many L5 queries
OOS_MIN_POSITIVE_RATIO = 0.50 # OOS months with positive IC >= 50%

# Phase AF: Factor replacement & library health (FactorMiner Wang et al. 2026)
REPLACEMENT_ICIR_MULTIPLIER = 1.3   # New must have >= 1.3x ICIR of replaced (Eq.11)
REPLACEMENT_MIN_ICIR = 0.20          # Minimum absolute ICIR for replacement candidate
MAX_REPLACEMENTS_PER_CYCLE = 10      # Max replacements per research cycle
SATURATION_MATCH_LIMIT = 10          # Direction saturated after 10 correlated variants
DIVERSITY_WARN_THRESHOLD = 0.30      # diversity_ratio < this → warning
DIVERSITY_BLOCK_THRESHOLD = 0.15     # diversity_ratio < this → block replacement

# Dedup: known good factors' IC series (from legacy L3 check)
DEDUP_FACTORS_FILE = PROJECT_ROOT / "data" / "research" / "baseline_ic_series.json"

# Universe — core universe (200 large/mid-cap by ADV) from file
# Replaces old hardcoded 50-stock list for better statistical robustness
UNIVERSE_FILE = PROJECT_ROOT / "data" / "research" / "universe.txt"

# Large-scale universe for Stage 2 verification (865+ symbols)
LARGE_UNIVERSE_FILE = PROJECT_ROOT / "data" / "research" / "large_universe.txt"


# ---------------------------------------------------------------------------
# L5 Query Counter (Thresholdout budget tracking)
# ---------------------------------------------------------------------------

def _get_l5_query_count() -> int:
    """Read L5 query count from watchdog_data (agent cannot access)."""
    counter_path = Path("/app/watchdog_data/l5_query_count.json")
    if not counter_path.exists():
        counter_path = PROJECT_ROOT / "docker" / "autoresearch" / "watchdog_data" / "l5_query_count.json"
    if counter_path.exists():
        try:
            return json.loads(counter_path.read_text(encoding="utf-8")).get("count", 0)
        except Exception:
            return 0
    return 0


def _increment_l5_query_count() -> int:
    """Increment and return new L5 query count."""
    counter_path = Path("/app/watchdog_data/l5_query_count.json")
    if not counter_path.parent.exists():
        counter_path = PROJECT_ROOT / "docker" / "autoresearch" / "watchdog_data" / "l5_query_count.json"
    counter_path.parent.mkdir(parents=True, exist_ok=True)
    count = _get_l5_query_count() + 1
    data = {"count": count, "updated": time.strftime("%Y-%m-%d %H:%M:%S")}
    # Preserve replacement_count if it exists
    if counter_path.exists():
        try:
            existing = json.loads(counter_path.read_text(encoding="utf-8"))
            if "replacement_count" in existing:
                data["replacement_count"] = existing["replacement_count"]
        except Exception:
            pass
    counter_path.write_text(json.dumps(data), encoding="utf-8")
    return count


def _counter_path() -> Path:
    """Get path to l5_query_count.json (shared with replacement counter)."""
    p = Path("/app/watchdog_data/l5_query_count.json")
    if not p.parent.exists():
        p = PROJECT_ROOT / "docker" / "autoresearch" / "watchdog_data" / "l5_query_count.json"
    return p


def _get_replacement_count() -> int:
    """Read replacement count from l5_query_count.json."""
    p = _counter_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("replacement_count", 0)
        except Exception:
            pass
    return 0


def _increment_replacement_count() -> None:
    """Increment replacement count in l5_query_count.json."""
    p = _counter_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    data["replacement_count"] = data.get("replacement_count", 0) + 1
    data["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    p.write_text(json.dumps(data), encoding="utf-8")


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
    # Fallback: scan all parquet files in data/market/
    market_dir = PROJECT_ROOT / "data" / "market"
    if market_dir.exists():
        syms = []
        for p in market_dir.glob("finmind_*.parquet"):
            bare = p.stem.replace("finmind_", "")
            syms.append(f"{bare}.TW")
        if large and len(syms) > 100:
            return sorted(syms)
        if not large and len(syms) > 50:
            # Use top 200 by filename as rough proxy if universe.txt missing
            return sorted(syms)[:200]
    raise FileNotFoundError(f"Universe file not found: {path}. Run universe builder first.")


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
                    # Replace zero/negative close with NaN, skip if >10% bad
                    df["close"] = df["close"].where(df["close"] > 0)
                    if df["close"].isna().sum() / len(df) <= 0.10:
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
    """Load known factors' IC series for dedup (L3 correlation check).

    Supports v1 (name → list) and v2 (name → {series, icir}) formats.
    """
    if DEDUP_FACTORS_FILE.exists():
        try:
            with open(DEDUP_FACTORS_FILE, encoding="utf-8") as f:
                raw = json.load(f)
            result = {}
            for name, val in raw.items():
                if isinstance(val, list):
                    result[name] = val
                elif isinstance(val, dict) and "series" in val:
                    result[name] = val["series"]
            return result
        except Exception:
            pass
    return {}


def _load_factor_icirs() -> dict[str, float]:
    """Load known factors' ICIR from baseline_ic_series.json (v2 format)."""
    if DEDUP_FACTORS_FILE.exists():
        try:
            with open(DEDUP_FACTORS_FILE, encoding="utf-8") as f:
                raw = json.load(f)
            return {name: val.get("icir", 0.0) for name, val in raw.items()
                    if isinstance(val, dict)}
        except Exception:
            pass
    return {}


# ---------------------------------------------------------------------------
# Revenue Delay Enforcement (agent cannot bypass)
# ---------------------------------------------------------------------------

def _mask_data(data: dict, as_of: pd.Timestamp) -> dict:
    """Return a copy of data with ALL time-series truncated to as_of.

    Safety: agent cannot see future data regardless of what factor.py does.
    - bars: truncated to as_of (no future prices)
    - revenue: truncated to as_of - 40 days (publication delay)
    - institutional: truncated to as_of
    - pe/pb/roe: passed as-is (point-in-time snapshots)
    """
    cutoff = as_of - pd.DateOffset(days=REVENUE_DELAY_DAYS)
    # Use slicing without .copy() for bars (largest data) — safe because
    # factor.py receives a slice view and any mutation raises SettingWithCopyWarning.
    # Revenue/institutional keep .copy() as they use boolean indexing (always copies).
    masked = {
        "bars": {
            sym: df.loc[:as_of]
            for sym, df in data["bars"].items()
        },
        "revenue": {
            sym: df[df["date"] <= cutoff]
            for sym, df in data["revenue"].items()
        },
        "institutional": {
            sym: df[df["date"] <= as_of]
            for sym, df in data["institutional"].items()
        },
        "pe": data["pe"],
        "pb": data["pb"],
        "roe": data["roe"],
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
            if p0 > 0 and p1 > 0:
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

def _check_dedup(ic_series_20d: list[float], known: dict[str, list[float]]) -> tuple[float, str, int]:
    """Check max correlation between this factor's IC series and known factors.

    Returns (max_correlation, correlated_with_name, n_high_corr).
    n_high_corr = number of known factors with |corr| > MAX_CORRELATION (for one-to-one check).
    """
    if not known or len(ic_series_20d) < 10:
        return 0.0, "", 0

    new = pd.Series(ic_series_20d)
    max_corr = 0.0
    max_name = ""
    n_high = 0
    for name, existing_ics in known.items():
        min_len = min(len(new), len(existing_ics))
        if min_len < 10:
            continue
        corr = float(new.iloc[:min_len].corr(pd.Series(existing_ics[:min_len])))
        if abs(corr) > MAX_CORRELATION:
            n_high += 1
        if abs(corr) > abs(max_corr):
            max_corr = corr
            max_name = name
    return max_corr, max_name, n_high


def _get_match_count(factor_name: str) -> int:
    """Count experiments that correlated with factor_name (from learnings.jsonl)."""
    learnings_path = Path("/app/watchdog_data/learnings.jsonl")
    if not learnings_path.exists():
        learnings_path = PROJECT_ROOT / "docker" / "autoresearch" / "watchdog_data" / "learnings.jsonl"
    if not learnings_path.exists():
        return 0
    count = 0
    try:
        for line in learnings_path.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line.strip())
                if entry.get("correlated_with") == factor_name:
                    count += 1
            except Exception:
                continue
    except Exception:
        pass
    return count


def _library_health_metrics(known_ics: dict[str, list[float]]) -> dict:
    """Compute factor library health: avg_pairwise_corr, effective_n, diversity_ratio."""
    names = list(known_ics.keys())
    n = len(names)
    if n < 2:
        return {"avg_pairwise_corr": 0.0, "effective_n": float(n),
                "diversity_ratio": 1.0, "n_factors": n}

    min_len = min(len(v) for v in known_ics.values())
    if min_len < 10:
        return {"avg_pairwise_corr": 0.0, "effective_n": float(n),
                "diversity_ratio": 1.0, "n_factors": n}

    mat = np.array([known_ics[name][:min_len] for name in names])
    corr_matrix = np.corrcoef(mat)

    # avg pairwise |corr| (upper triangle)
    triu_idx = np.triu_indices(n, k=1)
    avg_corr = float(np.mean(np.abs(corr_matrix[triu_idx])))

    # effective_n via eigenvalue decomposition
    eigenvalues = np.maximum(np.linalg.eigvalsh(corr_matrix), 0)
    sum_eig = float(np.sum(eigenvalues))
    sum_eig2 = float(np.sum(eigenvalues ** 2))
    effective_n = sum_eig ** 2 / sum_eig2 if sum_eig2 > 0 else float(n)

    return {
        "avg_pairwise_corr": round(avg_corr, 4),
        "effective_n": round(effective_n, 2),
        "diversity_ratio": round(effective_n / n, 4) if n > 0 else 1.0,
        "n_factors": n,
    }


def _replace_factor(old_name: str, new_ic_series: list[float], new_icir: float) -> str:
    """Replace old factor with new one in baseline_ic_series.json. Returns new name."""
    new_name = f"factor_{time.strftime('%Y%m%d_%H%M%S')}"

    raw = {}
    if DEDUP_FACTORS_FILE.exists():
        try:
            raw = json.loads(DEDUP_FACTORS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    raw.pop(old_name, None)
    raw[new_name] = {
        "series": [round(v, 6) for v in new_ic_series],
        "icir": round(new_icir, 4),
        "added": time.strftime("%Y-%m-%d"),
        "replaced": old_name,
    }

    DEDUP_FACTORS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEDUP_FACTORS_FILE.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    # Save library health snapshot for /learnings API
    try:
        updated_ics = _load_dedup_ic_series()
        health = _library_health_metrics(updated_ics)
        health_path = Path("/app/watchdog_data/library_health.json")
        if not health_path.parent.exists():
            health_path = PROJECT_ROOT / "docker" / "autoresearch" / "watchdog_data" / "library_health.json"
        health_path.parent.mkdir(parents=True, exist_ok=True)
        health_path.write_text(json.dumps(health, indent=2), encoding="utf-8")
    except Exception:
        pass

    return new_name


# ---------------------------------------------------------------------------
# Main Evaluation (with early-exit from legacy L1-L4 gates)
# ---------------------------------------------------------------------------

def evaluate() -> dict:
    """Run the full evaluation pipeline with early-exit gates.

    Stage 1: Core universe (200 symbols), IN-SAMPLE period — fast screening
      L1: |IC_20d| >= 0.02     (early exit if fail — saves ~2 min)
      L2: |ICIR| >= 0.15
      L3: dedup correlation <= 0.50, yearly stability
      L4: fitness >= 3.0
      L5: OOS holdout validation (IC sign, ICIR decay, monthly stability)

    Stage 2 (if L5 passed): Large universe (865+ symbols) — confirmation
      Recompute ICIR on full universe, require ICIR(20d) >= 0.20
    """
    from factor import compute_factor

    # Complexity gate: reject overly complex factors (8.3 prevention)
    # Check both local path and Docker /app/work/ path
    factor_path = Path(__file__).parent / "factor.py"
    if not factor_path.exists():
        factor_path = Path(__file__).parent / "work" / "factor.py"
    if factor_path.exists():
        n_lines = len(factor_path.read_text(encoding="utf-8").strip().splitlines())
        if n_lines > 80:
            return _make_result(
                level="L0",
                failure=f"factor.py too complex: {n_lines} lines > 80 max",
                elapsed=0.0,
            )

    universe = _load_universe()
    data = _load_all_data(universe)
    bars = data["bars"]
    known_ics = _load_dedup_ic_series()

    # Build sample dates — split into IS and OOS
    all_dates: set[pd.Timestamp] = set()
    for df in bars.values():
        all_dates |= set(df.index)
    eval_dates = sorted(d for d in all_dates
                        if pd.Timestamp(EVAL_START) <= d <= pd.Timestamp(EVAL_END))

    is_dates = [d for d in eval_dates if d <= pd.Timestamp(IS_END)]
    oos_dates = [d for d in eval_dates if pd.Timestamp(OOS_START) <= d <= pd.Timestamp(EVAL_END)]
    is_sample = is_dates[::SAMPLE_FREQ_DAYS]
    oos_sample = oos_dates[::SAMPLE_FREQ_DAYS]

    # L1-L4 use IS only; L5 uses OOS
    sample_dates = is_sample

    print(f"Stage 1: {len(is_sample)} IS dates, {len(bars)} symbols")

    # ── Stage 1: L1 early screening (20d IC only, first 30 dates) ──
    t0 = time.time()
    early_ics: list[float] = []
    early_limit = min(30, len(sample_dates))

    for as_of in sample_dates[:early_limit]:
        masked_data = _mask_data(data, as_of)
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
            level="L1", failure=f"|IC_20d|={abs(early_ic):.4f} < {MIN_IC_L1} (early exit)",
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
        masked_data = _mask_data(data, as_of)
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
    max_corr, corr_with, n_high_corr = _check_dedup(ic_series_20d, known_ics)

    # Phase AF: replacement candidate tracking
    is_replacement_candidate = False
    replacement_target = ""

    # ── Gate checks (L2-L4) ──
    if abs(best_icir) < MIN_ICIR_L2:
        return _make_result(
            level="L2", failure=f"|ICIR|={abs(best_icir):.4f} < {MIN_ICIR_L2}",
            ic_20d=ic_20d, best_icir=best_icir, best_horizon=best_horizon,
            icir_by_horizon=icir_by_horizon, avg_turnover=avg_turnover,
            elapsed=elapsed,
        )

    if abs(max_corr) > MAX_CORRELATION:
        # Phase AF: check replacement eligibility before rejecting
        match_count = _get_match_count(corr_with)
        factor_icirs = _load_factor_icirs()
        correlated_icir = abs(factor_icirs.get(corr_with, 0.0))
        replacement_count = _get_replacement_count()

        can_replace = (
            n_high_corr == 1  # one-to-one only
            and correlated_icir > 0  # can't replace unknown-ICIR factors
            and abs(best_icir) >= REPLACEMENT_ICIR_MULTIPLIER * correlated_icir
            and abs(best_icir) >= REPLACEMENT_MIN_ICIR
            and replacement_count < MAX_REPLACEMENTS_PER_CYCLE
        )

        if can_replace:
            is_replacement_candidate = True
            replacement_target = corr_with
            print(f"  L3: replacement candidate (ICIR {abs(best_icir):.4f} >= {REPLACEMENT_ICIR_MULTIPLIER}x {correlated_icir:.4f})")
        elif match_count >= SATURATION_MATCH_LIMIT:
            return _make_result(
                level="L3", failure=f"direction saturated: {match_count} variants for {corr_with}",
                ic_20d=ic_20d, best_icir=best_icir, best_horizon=best_horizon,
                icir_by_horizon=icir_by_horizon, avg_turnover=avg_turnover,
                max_correlation=max_corr, correlated_with=corr_with,
                elapsed=elapsed,
            )
        else:
            return _make_result(
                level="L3", failure=f"corr={max_corr:.3f} with {corr_with} > {MAX_CORRELATION}",
                ic_20d=ic_20d, best_icir=best_icir, best_horizon=best_horizon,
                icir_by_horizon=icir_by_horizon, avg_turnover=avg_turnover,
                max_correlation=max_corr, correlated_with=corr_with,
                elapsed=elapsed,
            )

    if positive_years < MIN_POSITIVE_YEARS and total_years >= MIN_POSITIVE_YEARS:
        return _make_result(
            level="L3", failure=f"positive_years={positive_years}/{total_years} < {MIN_POSITIVE_YEARS}",
            ic_20d=ic_20d, best_icir=best_icir, best_horizon=best_horizon,
            icir_by_horizon=icir_by_horizon, avg_turnover=avg_turnover,
            positive_years=positive_years, total_years=total_years,
            elapsed=elapsed,
        )

    if fitness < MIN_FITNESS:
        return _make_result(
            level="L4", failure=f"fitness={fitness:.2f} < {MIN_FITNESS}",
            ic_20d=ic_20d, best_icir=best_icir, best_horizon=best_horizon,
            icir_by_horizon=icir_by_horizon, avg_turnover=avg_turnover,
            fitness=fitness, positive_years=positive_years, total_years=total_years,
            elapsed=elapsed,
        )

    print(f"  L4 passed: ICIR={best_icir:.4f}, fitness={fitness:.2f}")

    # ── L5: Out-of-Sample Validation (Phase X anti-overfitting) ──
    oos_ics_20d: list[float] = []
    oos_ic_by_month: dict[str, list[float]] = {}

    if oos_sample:
        print(f"\n  L5 OOS validation: {len(oos_sample)} dates")
        for as_of in oos_sample:
            masked_data = _mask_data(data, as_of)
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
            fwd = _compute_forward_returns(bars, as_of, 20)
            ic = _compute_ic(values, fwd)
            if ic is not None:
                oos_ics_20d.append(ic)
                month_key = as_of.strftime("%Y-%m")
                oos_ic_by_month.setdefault(month_key, []).append(ic)

    oos_ic_mean = float(np.mean(oos_ics_20d)) if oos_ics_20d else 0.0
    oos_ic_std = float(np.std(oos_ics_20d, ddof=1)) if len(oos_ics_20d) > 1 else 1.0
    oos_icir = oos_ic_mean / oos_ic_std if oos_ic_std > 0 else 0.0
    oos_positive_months = sum(
        1 for ics in oos_ic_by_month.values() if np.mean(ics) > 0
    )
    oos_total_months = len(oos_ic_by_month)
    oos_positive_ratio = oos_positive_months / oos_total_months if oos_total_months > 0 else 0.0

    is_ic_sign = 1 if ic_20d >= 0 else -1
    oos_ic_sign = 1 if oos_ic_mean >= 0 else -1

    # L5 gate checks with Thresholdout (Dwork et al. 2015)
    # Add Laplace noise to comparisons to preserve holdout validity.
    # Deterministic checks become noisy: agent gets ~0.7 bits per query instead of 1.0.
    l5_query_n = _increment_l5_query_count()
    rng_l5 = np.random.default_rng(hash((ic_20d, best_icir, l5_query_n)) % (2**31))
    noise = lambda: float(rng_l5.laplace(0, THRESHOLDOUT_NOISE_SCALE))

    l5_failure = False
    is_icir_20d = float(icir_by_horizon.get("20d", 0))
    # Sub-check 1: IC sign consistency (add noise to sign comparison margin)
    if is_ic_sign != oos_ic_sign and abs(oos_ic_mean) > noise():
        l5_failure = True
    # Sub-check 2: ICIR decay (noisy threshold)
    elif abs(is_icir_20d) > 0 and abs(oos_icir) < abs(is_icir_20d) * (1 - OOS_ICIR_DECAY_MAX) + noise():
        l5_failure = True
    # Sub-check 3: monthly consistency (noisy threshold)
    elif oos_positive_ratio < OOS_MIN_POSITIVE_RATIO + noise() and oos_total_months >= 6:
        l5_failure = True

    # Budget warning (printed to stderr, not visible to agent via tail -30)
    if l5_query_n > L5_QUERY_BUDGET:
        import sys
        print(f"[WARN] L5 query budget exceeded: {l5_query_n}/{L5_QUERY_BUDGET}", file=sys.stderr)

    # P-01: only show pass/fail — no reason, no direction, no magnitude
    print(f"  OOS validation: {'PASS' if not l5_failure else 'FAIL'}")

    if l5_failure:
        return _make_result(
            level="L5", failure="L5 OOS validation failed",
            ic_20d=ic_20d, best_icir=best_icir, best_horizon=best_horizon,
            icir_by_horizon=icir_by_horizon, avg_turnover=avg_turnover,
            fitness=fitness, positive_years=positive_years, total_years=total_years,
            max_correlation=max_corr, correlated_with=corr_with,
            oos_icir=oos_icir, oos_positive_months=oos_positive_months,
            oos_total_months=oos_total_months,
            elapsed=time.time() - t0,
        )

    print(f"  L5 passed: OOS validated")

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
            # Use IS dates only (not OOS) to avoid data leakage in Stage 2
            large_dates = is_dates[::40]
            for as_of in large_dates:
                masked = _mask_data(large_data, as_of)
                active = [s for s in large_universe if s in large_bars and as_of in large_bars[s].index]
                if len(active) < MIN_SYMBOLS:
                    continue
                try:
                    vals = compute_factor(active, as_of, masked)
                except Exception:
                    continue
                vals = {k: v for k, v in (vals or {}).items()
                        if isinstance(v, (int, float)) and np.isfinite(v)}
                if len(vals) < MIN_SYMBOLS:
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

    # Phase AF: execute replacement if candidate passed all gates
    replaced_name = ""
    if is_replacement_candidate and replacement_target:
        test_ics = dict(known_ics)
        test_ics.pop(replacement_target, None)
        test_ics["__candidate__"] = ic_series_20d
        health = _library_health_metrics(test_ics)

        if health["diversity_ratio"] < DIVERSITY_BLOCK_THRESHOLD:
            print(f"  Replacement BLOCKED: diversity_ratio={health['diversity_ratio']:.4f} < {DIVERSITY_BLOCK_THRESHOLD}")
        else:
            if health["diversity_ratio"] < DIVERSITY_WARN_THRESHOLD:
                print(f"  [WARN] Low diversity after replacement: {health['diversity_ratio']:.4f}")
            replaced_name = _replace_factor(replacement_target, ic_series_20d, best_icir)
            _increment_replacement_count()
            print(f"  REPLACED: {replacement_target} -> {replaced_name} "
                  f"(health: corr={health['avg_pairwise_corr']:.3f}, "
                  f"eff_n={health['effective_n']:.1f}, div={health['diversity_ratio']:.3f})")

    result = _make_result(
        level="L5", passed=True,
        ic_20d=ic_20d, best_icir=best_icir, best_horizon=best_horizon,
        icir_by_horizon=icir_by_horizon, avg_turnover=avg_turnover,
        fitness=fitness, positive_years=positive_years, total_years=total_years,
        max_correlation=max_corr, correlated_with=corr_with,
        large_icir_20d=large_icir_20d,
        oos_icir=oos_icir, oos_positive_months=oos_positive_months,
        oos_total_months=oos_total_months,
        elapsed=elapsed,
    )
    if replaced_name:
        result["replaced"] = replacement_target
        result["replaced_by"] = replaced_name
    return result


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
    oos_icir: float = 0.0, oos_positive_months: int = 0, oos_total_months: int = 0,
) -> dict:
    # fitness already includes ICIR — don't double-count
    composite = (
        fitness * 1.5
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
        "oos_icir": round(oos_icir, 4),
        "oos_positive_months": oos_positive_months,
        "oos_total_months": oos_total_months,
        "elapsed_seconds": round(elapsed, 1),
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("Alpha Factor Evaluation Harness v3 (READ ONLY)")
    print("  L1-L4 in-sample | L5 OOS holdout | large-scale verification")
    print(f"  IS: {EVAL_START} to {IS_END} | OOS: [hidden]")
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

    # Canary metric: random factor IC should be ≈ 0. If not, evaluation pipeline is biased.
    try:
        _canary_rng = np.random.default_rng(int(time.time()))
        _canary_vals = {s: float(_canary_rng.standard_normal()) for s in _load_universe(large=False)[:50]}
        _canary_bars = _load_all_data(_load_universe(large=False))["bars"]
        _canary_dates = sorted(d for d in list(_canary_bars.values())[0].index if d <= pd.Timestamp(IS_END))[-5:]
        _canary_ics = []
        for _cd in _canary_dates:
            _cfwd = _compute_forward_returns(_canary_bars, _cd, 20)
            _cic = _compute_ic(_canary_vals, _cfwd)
            if _cic is not None:
                _canary_ics.append(_cic)
        if _canary_ics and abs(np.mean(_canary_ics)) > 0.10:
            print(f"[CANARY ALERT] Random factor IC = {np.mean(_canary_ics):.4f} (expected ~0). Pipeline may be biased!", file=sys.stderr)
    except Exception:
        pass  # canary failure should not block evaluation

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
    # P-01: hide exact OOS values from agent (only show pass/fail)
    print(f"oos_validated:    {results['level'] == 'L5'}")
    print(f"level:            {results['level']}")
    print(f"passed:           {results['passed']}")
    if results["failure"]:
        print(f"failure:          {results['failure']}")
    print(f"elapsed_seconds:  {results['elapsed_seconds']:.1f}")

    for h, icir in results["icir_by_horizon"].items():
        print(f"icir_{h}:          {icir:.4f}")

    # Phase AB: store daily returns for Factor-Level PBO (all factors, not just L5 pass)
    if results.get("level") not in ("L0",):  # L0 = complexity fail, no factor values
        _store_factor_returns(results)

    # Phase AF: append to learnings.jsonl
    _write_learning(results)

    if results["passed"]:
        print("\nstatus: PASSED (L5+ OOS validated)")
        # Write pending marker for background Validator (watchdog picks it up)
        _write_pending_marker(results)
        # Also try auto-submit to API (for paper deploy, if running)
        _auto_submit(results)
    elif results["composite_score"] > 0:
        print(f"\nstatus: evaluated ({results['level']})")
    else:
        print("\nstatus: no_signal")


def _store_factor_returns(results: dict) -> None:
    """Store equal-weight top-15 daily returns for Factor-Level PBO (Phase AB).

    Stores for ALL factors (including failures) — Bailey requires N to include
    failed trials. Uses VectorizedPBOBacktest for fast computation (~5-10s).
    """
    try:
        from src.backtest.vectorized import VectorizedPBOBacktest
        from factor import compute_factor

        # Store factor_returns OUTSIDE work/ so agent cannot read them
        # Docker: /app/watchdog_data/factor_returns (separate volume)
        # Host: docker/autoresearch/watchdog_data/factor_returns
        returns_dir = Path("/app/watchdog_data/factor_returns")
        if not returns_dir.parent.exists():
            returns_dir = Path(__file__).resolve().parent.parent.parent / "docker" / "autoresearch" / "watchdog_data" / "factor_returns"
        returns_dir.mkdir(parents=True, exist_ok=True)

        # Use same universe and dates as evaluation
        universe = _load_universe(large=False)

        vbt = VectorizedPBOBacktest(
            universe=universe, start=EVAL_START, end=EVAL_END,
            data_dir=str(PROJECT_ROOT / "data" / "market"),
            fund_dir=str(PROJECT_ROOT / "data" / "fundamental"),
        )

        daily_rets = vbt.run_variant(compute_factor, top_n=15, weight_mode="equal")

        if daily_rets is not None and len(daily_rets) > 20:
            # Clean inf/nan before storing
            daily_rets = daily_rets.replace([np.inf, -np.inf], 0.0).fillna(0.0)
            ts = time.strftime("%Y%m%d_%H%M%S")
            path = returns_dir / f"{ts}.parquet"
            daily_rets.to_frame("returns").to_parquet(path)

            # Update metadata
            meta_path = returns_dir / "metadata.json"
            meta = {}
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            meta[ts] = {
                "composite_score": results.get("composite_score", 0),
                "level": results.get("level", "?"),
                "best_icir": results.get("best_icir", 0),
            }
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            print(f"factor_returns: {path.name} ({len(daily_rets)} days)")
    except Exception as e:
        print(f"[WARN] factor_returns store failed: {e}")


def _write_learning(results: dict) -> None:
    """Append structured experience to learnings.jsonl (Phase AF)."""
    try:
        learnings_dir = Path("/app/watchdog_data")
        if not learnings_dir.exists():
            learnings_dir = PROJECT_ROOT / "docker" / "autoresearch" / "watchdog_data"
        learnings_dir.mkdir(parents=True, exist_ok=True)
        learnings_path = learnings_dir / "learnings.jsonl"

        # Extract direction from factor.py docstring
        direction = "unknown"
        try:
            factor_path = Path(__file__).parent / "factor.py"
            if not factor_path.exists():
                factor_path = Path(__file__).parent / "work" / "factor.py"
            if factor_path.exists():
                for line in factor_path.read_text(encoding="utf-8").splitlines():
                    stripped = line.strip().strip('"').strip("'")
                    if stripped and not stripped.startswith(("from ", "import ", "def ", "#", '"""', "'''")):
                        direction = stripped[:80]
                        break
        except Exception:
            pass

        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "direction": direction,
            "level": results.get("level", ""),
            "passed": results.get("passed", False),
            "best_icir": round(results.get("best_icir", 0), 4),
            "failure": results.get("failure", ""),
            "max_correlation": round(results.get("max_correlation", 0), 3),
            "correlated_with": results.get("correlated_with", ""),
        }
        if results.get("replaced"):
            entry["replaced"] = results["replaced"]
            entry["replaced_by"] = results.get("replaced_by", "")
        with open(learnings_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[WARN] learnings write failed: {e}")


def _write_pending_marker(results: dict) -> None:
    """Write a pending validation marker for background Validator (watchdog)."""
    try:
        # Read factor code
        factor_path = Path(__file__).parent / "factor.py"
        if not factor_path.exists():
            factor_path = Path(__file__).parent / "work" / "factor.py"
        factor_code = factor_path.read_text(encoding="utf-8") if factor_path.exists() else ""

        # Store pending markers OUTSIDE work/ so agent cannot read OOS data
        pending_dir = Path("/app/watchdog_data/pending")
        if not pending_dir.parent.exists():
            pending_dir = Path(__file__).resolve().parent.parent.parent / "docker" / "autoresearch" / "watchdog_data" / "pending"
        pending_dir.mkdir(parents=True, exist_ok=True)

        # Strip OOS-related fields to prevent agent reading them from pending/*.json
        safe_results = {k: v for k, v in results.items()
                        if k not in ("oos_icir", "oos_positive_months", "oos_total_months")}
        marker = {
            "results": safe_results,
            "factor_code": factor_code,
            "timestamp": time.strftime("%Y%m%d_%H%M%S"),
        }
        marker_path = pending_dir / f"{marker['timestamp']}.json"
        marker_path.write_text(json.dumps(marker, indent=2, default=str), encoding="utf-8")
        print(f"pending_validation: {marker_path.name}")
    except Exception as e:
        print(f"[WARN] pending marker write failed: {e}")


def _run_validator(results: dict) -> dict | None:
    """Run StrategyValidator 15-check locally. No API dependency."""
    try:
        from src.backtest.validator import StrategyValidator, ValidationConfig
        from src.strategy.base import Context, Strategy as StrategyBase
        from factor import compute_factor
        import inspect

        print("\n--- VALIDATOR (15 checks) ---")

        # Read n_independent from watchdog's Factor-Level PBO (dynamic, not hardcoded)
        _n_trials = 15  # default fallback
        try:
            _pbo_path = Path("/app/watchdog_data/factor_pbo.json")
            if not _pbo_path.exists():
                _pbo_path = PROJECT_ROOT / "docker" / "autoresearch" / "watchdog_data" / "factor_pbo.json"
            if _pbo_path.exists():
                _pbo_data = json.loads(_pbo_path.read_text(encoding="utf-8"))
                _n_ind = _pbo_data.get("n_independent", 15)
                if isinstance(_n_ind, (int, float)) and _n_ind >= 2:
                    _n_trials = int(_n_ind)
        except Exception:
            pass

        config = ValidationConfig(
            n_trials=_n_trials,
            initial_cash=10_000_000, min_universe_size=50,
            wf_train_years=2,
        )

        # Build a minimal Strategy wrapper around compute_factor
        _sig = inspect.signature(compute_factor)
        _is_3arg = len([p for p in _sig.parameters.values()
                        if p.default is inspect.Parameter.empty]) >= 3

        class _FactorStrategy(StrategyBase):
            def name(self) -> str:
                return "autoresearch_candidate"
            def on_bar(self, ctx: Context) -> dict[str, float]:
                symbols = ctx.universe()
                as_of = pd.Timestamp(ctx.now())
                if _is_3arg:
                    # Build data dict using Context's public API
                    revenue = {}
                    for s in symbols:
                        rev = ctx.get_revenue(s, lookback_months=36)
                        if rev is not None and not rev.empty:
                            revenue[s] = rev
                    data = {
                        "bars": {s: ctx.bars(s, lookback=500) for s in symbols},
                        "revenue": revenue,
                        "institutional": {},
                        "pe": {}, "pb": {}, "roe": {},
                    }
                    values = compute_factor(symbols, as_of, data)
                else:
                    values = compute_factor(symbols, as_of)
                if not values:
                    return {}
                sorted_syms = sorted(values, key=lambda s: values[s], reverse=True)
                selected = sorted_syms[:15]
                w = 1.0 / len(selected)
                return {s: w for s in selected}

        strategy = _FactorStrategy()
        universe = _load_universe(large=False)

        validator = StrategyValidator(config)
        report = validator.validate(strategy, universe, EVAL_START, EVAL_END,
                                    compute_fn=compute_factor)

        if report.error:
            print(f"  [ERROR] {report.error}")

        n_passed = report.n_passed
        n_total = report.n_total
        checks = report.checks

        # Print results — hide OOS-related values to prevent information leakage
        # Agent should not see exact OOS Sharpe, recent Sharpe, or regime values
        OOS_CHECKS = {"oos_sharpe", "recent_period_sharpe", "worst_regime"}
        for c in checks:
            mark = "PASS" if c.passed else "FAIL"
            if c.name in OOS_CHECKS:
                print(f"  [{mark}] {c.name}: [hidden] (threshold: {c.threshold})")
            else:
                print(f"  [{mark}] {c.name}: {c.value} (threshold: {c.threshold})")
        print(f"\nvalidator: {n_passed}/{n_total}")

        # Hard/soft deployment threshold (Phase AC §7)
        HARD_CHECKS = {
            "cagr", "sharpe", "annual_cost_ratio", "temporal_consistency",
            "deflated_sharpe", "bootstrap_p_sharpe_positive", "vs_ew_universe",
            "construction_sensitivity", "market_correlation", "permutation_p",
        }
        deployed = all(c.passed for c in checks if c.name in HARD_CHECKS)

        print(f"deploy_eligible: {deployed}")

        return {
            "n_passed": n_passed,
            "n_total": n_total,
            "deployed": deployed,
            "checks": [(c.name, c.passed, str(c.value), str(c.threshold)) for c in checks],
        }
    except Exception as e:
        print(f"\n[WARN] Validator failed: {e}")
        return None


def _write_report(results: dict, validator_report: dict) -> None:
    """Write a factor report only when Validator passes deployment threshold."""
    try:
        # Docker: /app/reports is bind-mounted to docs/research/autoresearch/
        # Local: PROJECT_ROOT/docs/research/autoresearch/
        report_dir = Path("/app/reports") if Path("/app/reports").exists() \
            else PROJECT_ROOT / "docs" / "research" / "autoresearch"
        report_dir.mkdir(parents=True, exist_ok=True)

        # Read factor code
        factor_path = Path(__file__).parent / "factor.py"
        if not factor_path.exists():
            factor_path = Path(__file__).parent / "work" / "factor.py"
        factor_code = factor_path.read_text(encoding="utf-8") if factor_path.exists() else "(not found)"

        # Extract name from factor.py docstring (works in Docker without git)
        import re as _re
        name = "unknown"
        name_safe = "unknown"
        try:
            factor_lines = factor_code.splitlines()
            for line in factor_lines:
                stripped = line.strip().strip('"').strip("'")
                if stripped and not stripped.startswith(("from ", "import ", "def ", "#", "\"\"\"", "'''")) \
                        and len(stripped) > 5:
                    # First meaningful docstring line
                    name = stripped[:80]
                    name_safe = _re.sub(r'[^a-zA-Z0-9_-]', '_', name)[:60]
                    break
            # Fallback: try git (works on host, not in Docker)
            if name == "unknown":
                import subprocess
                for cwd in [str(Path(__file__).parent / "work"), str(Path(__file__).parent)]:
                    log = subprocess.run(
                        ["git", "log", "--oneline", "-1", "--format=%s"],
                        capture_output=True, text=True, timeout=5, cwd=cwd,
                    )
                    if log.returncode == 0 and log.stdout.strip():
                        name = log.stdout.strip().replace("experiment: ", "")[:60]
                        name_safe = _re.sub(r'[^a-zA-Z0-9_-]', '_', name)
                        break
        except Exception:
            pass

        ts = time.strftime("%Y%m%d_%H%M%S")
        report_path = report_dir / f"{ts}_{name_safe}.md"

        vr = validator_report
        n_p, n_t = vr["n_passed"], vr["n_total"]

        content = (
            f"# Factor Report: {name}\n\n"
            f"> Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"> Status: **DEPLOYED** | Validator: {n_p}/{n_t}\n\n"
            f"## Metrics\n\n"
            f"| Metric | Value |\n"
            f"|--------|-------|\n"
            f"| Composite Score | {results['composite_score']} |\n"
            f"| IC (20d) | {results['ic_20d']} |\n"
            f"| Best ICIR | {results['best_icir']} ({results['best_horizon']}) |\n"
            f"| Fitness | {results['fitness']} |\n"
            f"| Positive Years | {results['positive_years']}/{results['total_years']} |\n"
            f"| Turnover | {results['avg_turnover']} |\n"
            f"| Large-scale ICIR | {results['large_icir_20d']} |\n"
            f"| Max Correlation | {results['max_correlation']} ({results['correlated_with']}) |\n\n"
            f"## Validator Results ({n_p}/{n_t})\n\n"
            f"| Check | Result | Value | Threshold |\n"
            f"|-------|--------|-------|----------|\n"
        )
        for cname, cpassed, cval, cthresh in vr["checks"]:
            mark = "PASS" if cpassed else "FAIL"
            content += f"| {cname} | {mark} | {cval} | {cthresh} |\n"

        content += (
            f"\n## ICIR by Horizon\n\n"
            f"| Horizon | ICIR |\n"
            f"|---------|------|\n"
        )
        for h, icir in results["icir_by_horizon"].items():
            content += f"| {h} | {icir} |\n"

        content += (
            f"\n## Factor Code\n\n"
            f"```python\n{factor_code}```\n"
        )

        report_path.write_text(content, encoding="utf-8")
        print(f"\nreport: {report_path}")
    except Exception as e:
        print(f"\n[WARN] report write failed: {e}")


def _auto_submit(results: dict) -> None:
    """Submit passed factor to API for Validator 15-check + auto-deploy."""
    try:
        import requests
        factor_path = Path(__file__).parent / "factor.py"
        if not factor_path.exists():
            factor_path = Path(__file__).parent / "work" / "factor.py"
        factor_code = factor_path.read_text(encoding="utf-8")
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

        api_url = _os.environ.get("API_URL", "http://127.0.0.1:8000")
        resp = requests.post(
            f"{api_url}/api/v1/auto-alpha/submit-factor",
            json={
                "name": name,
                "code": factor_code,
                "composite_score": results["composite_score"],
                "icir_20d": results["icir_by_horizon"].get("20d", 0),
                "large_icir_20d": results["large_icir_20d"],
                "description": f"autoresearch L4+ (score={results['composite_score']:.2f})",
            },
            headers={"X-API-Key": _os.environ.get("QUANT_API_KEY", "dev-key")},
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
