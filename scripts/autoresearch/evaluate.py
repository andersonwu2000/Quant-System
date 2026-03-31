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
MIN_ICIR_L2 = 0.30            # L2: minimum median |ICIR| across horizons (no horizon bias)
MAX_ICIR_L2 = 1.00            # L2: maximum median |ICIR| — above this is suspicious
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
# Read: prefer watchdog_data (rw, updated by replacements), fallback to data/research (ro, seed)
# Write: always to watchdog_data (evaluator rw, agent cannot access)
DEDUP_FACTORS_RO = PROJECT_ROOT / "data" / "research" / "baseline_ic_series.json"


def _dedup_read_path() -> Path:
    """Writable copy in watchdog_data takes precedence over ro seed."""
    wd = Path("/app/watchdog_data/baseline_ic_series.json")
    if not wd.parent.exists():
        wd = PROJECT_ROOT / "docker" / "autoresearch" / "watchdog_data" / "baseline_ic_series.json"
    return wd if wd.exists() else DEDUP_FACTORS_RO


def _dedup_write_path() -> Path:
    """Always write to watchdog_data (rw)."""
    wd = Path("/app/watchdog_data/baseline_ic_series.json")
    if not wd.parent.exists():
        wd = PROJECT_ROOT / "docker" / "autoresearch" / "watchdog_data" / "baseline_ic_series.json"
    wd.parent.mkdir(parents=True, exist_ok=True)
    return wd

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
    # Fallback: scan all price parquet files via DataCatalog
    from src.data.data_catalog import DataCatalog
    catalog = DataCatalog(str(PROJECT_ROOT / "data"))
    syms = catalog.available_symbols("price")
    if syms:
        if large and len(syms) > 100:
            return sorted(syms)
        if not large and len(syms) > 50:
            return sorted(syms)[:200]
    raise FileNotFoundError(f"Universe file not found: {path}. Run universe builder first.")


def _load_all_data(universe: list[str]) -> dict:
    """Load all available data for the universe via DataCatalog.

    Uses DataCatalog for path resolution and reading, but preserves the exact
    same output dict format (data["bars"][sym], data["revenue"][sym], etc.)
    so all downstream code is unaffected.

    Cached after first call.
    """
    global _data_cache
    if _data_cache is not None:
        return _data_cache

    from src.data.data_catalog import DataCatalog
    catalog = DataCatalog(str(PROJECT_ROOT / "data"))

    print(f"Loading data for {len(universe)} symbols...")

    bars: dict[str, pd.DataFrame] = {}
    revenue: dict[str, pd.DataFrame] = {}
    institutional: dict[str, pd.DataFrame] = {}
    pe_ratios: dict[str, float] = {}
    pb_ratios: dict[str, float] = {}
    roe_values: dict[str, float] = {}
    per_history: dict[str, pd.DataFrame] = {}
    market_cap: dict[str, float] = {}
    margin_data: dict[str, pd.DataFrame] = {}

    for sym in universe:
        # Market data (OHLCV)
        df = catalog.get("price", sym)
        if not df.empty and "close" in df.columns:
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            df.index = pd.to_datetime(df.index.date)  # normalize to date-only
            df = df[~df.index.duplicated(keep="first")]
            df["close"] = df["close"].where(df["close"] > 0)
            if df["close"].isna().sum() / len(df) <= 0.10:
                bars[sym] = df

        # Revenue
        df = catalog.get("revenue", sym)
        if not df.empty and "revenue" in df.columns:
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                revenue[sym] = df.sort_values("date")

        # Institutional
        df = catalog.get("institutional", sym)
        if not df.empty and "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            institutional[sym] = df.sort_values("date")

        # PER history (daily PER/PBR/dividend_yield)
        try:
            df = catalog.get("per", sym)
            if not df.empty and "PER" in df.columns and "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                per_history[sym] = df.sort_values("date")
        except Exception:
            pass

        # Margin data
        try:
            df = catalog.get("margin", sym)
            if not df.empty and "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                margin_data[sym] = df.sort_values("date")
        except Exception:
            pass

        # D3: Market cap (close × shares_issued)
        if sym in bars:
            try:
                sh_df = catalog.get("shareholding", sym)
                if not sh_df.empty and "NumberOfSharesIssued" in sh_df.columns:
                    if "date" in sh_df.columns:
                        sh_df = sh_df.sort_values("date")
                    shares = float(sh_df.iloc[-1]["NumberOfSharesIssued"])
                    last_close = float(bars[sym]["close"].iloc[-1])
                    if shares > 0 and last_close > 0:
                        market_cap[sym] = last_close * shares
            except Exception:
                pass

        # Financial metrics (PE, PB, ROE)
        try:
            df = catalog.get("financial_statement", sym)
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
          f"{len(institutional)} institutional, {len(per_history)} PER history, "
          f"{len(margin_data)} margin, {len(pe_ratios)} PE ratios")

    _data_cache = {
        "bars": bars,
        "revenue": revenue,
        "institutional": institutional,
        "per_history": per_history,  # data["per_history"][sym] → DataFrame[date, PER, PBR, dividend_yield]
        "margin": margin_data,       # data["margin"][sym] → DataFrame[date, ...]
        "pe": pe_ratios,
        "pb": pb_ratios,
        "roe": roe_values,
        "market_cap": market_cap,  # D3: {sym: float} latest market cap
    }

    # Build close matrix for vectorized forward returns (date × symbol)
    global _close_matrix
    close_series = {sym: df["close"] for sym, df in bars.items() if "close" in df.columns}
    if close_series:
        _close_matrix = pd.DataFrame(close_series).sort_index()
        print(f"  Close matrix: {_close_matrix.shape[0]} dates × {_close_matrix.shape[1]} symbols")
    else:
        _close_matrix = None

    return _data_cache


def _load_dedup_ic_series() -> dict[str, list[float]]:
    """Load known factors' IC series for dedup (L3 correlation check).

    Supports v1 (name → list) and v2 (name → {series, icir}) formats.
    """
    path = _dedup_read_path()
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
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
    path = _dedup_read_path()
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
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
    - per_history: truncated to as_of (daily PER/PBR)
    - margin: truncated to as_of (daily margin balances)
    - pe/pb/roe: passed as-is (point-in-time snapshots, backward compat)

    Optimized: uses .loc[:as_of] for DatetimeIndex (O(log N) bisect),
    and searchsorted for date-column DataFrames (avoids boolean mask).
    """
    cutoff = as_of - pd.DateOffset(days=REVENUE_DELAY_DAYS)

    # Fast path for date-column truncation: searchsorted on sorted dates
    def _trunc_date_col(df: pd.DataFrame, limit: pd.Timestamp) -> pd.DataFrame:
        dates = df["date"].values
        idx = np.searchsorted(dates, np.datetime64(limit), side="right")
        return df.iloc[:idx]

    masked = {
        "bars": {
            sym: df.loc[:as_of]
            for sym, df in data["bars"].items()
        },
        "revenue": {
            sym: _trunc_date_col(df, cutoff)
            for sym, df in data["revenue"].items()
        },
        "institutional": {
            sym: _trunc_date_col(df, as_of)
            for sym, df in data["institutional"].items()
        },
        "per_history": {
            sym: _trunc_date_col(df, as_of)
            for sym, df in data.get("per_history", {}).items()
        },
        "margin": {
            sym: _trunc_date_col(df, as_of)
            for sym, df in data.get("margin", {}).items()
        },
        # pe/pb/roe are latest-only snapshots → look-ahead bias in historical IC calculation
        # Use per_history (daily PER/PBR with date truncation) instead
        "pe": {},
        "pb": {},
        "roe": {},
        # market_cap is a latest-only snapshot (close × shares_issued) → look-ahead bias.
        # Disabled same as pe/pb/roe. Agent should use bars close × volume as size proxy.
        "market_cap": {},
    }
    return masked


# ---------------------------------------------------------------------------
# Forward Return Computation
# ---------------------------------------------------------------------------

_fwd_return_cache: dict[tuple[int, str], dict[str, float]] = {}


def _compute_forward_returns(
    bars: dict[str, pd.DataFrame], as_of: pd.Timestamp, horizon: int,
) -> dict[str, float]:
    """Compute forward returns for each symbol from as_of.

    Uses a per-(horizon, as_of) cache to avoid recomputing the same
    forward returns across L1/IS/L5/Stage2 calls.

    Vectorized: uses pre-built close matrix when available (3-5x faster).
    """
    cache_key = (horizon, str(as_of))
    if cache_key in _fwd_return_cache:
        return _fwd_return_cache[cache_key]

    # Fast path: use close matrix if built
    if _close_matrix is not None and as_of in _close_matrix.index:
        idx = _close_matrix.index.get_loc(as_of)
        if idx + horizon < len(_close_matrix):
            p0 = _close_matrix.iloc[idx]
            p1 = _close_matrix.iloc[idx + horizon]
            valid = (p0 > 0) & (p1 > 0) & p0.notna() & p1.notna()
            ret = (p1 / p0 - 1)[valid]
            returns = {sym: float(v) for sym, v in ret.items()}
            _fwd_return_cache[cache_key] = returns
            return returns

    # Fallback: per-symbol loop
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

    _fwd_return_cache[cache_key] = returns
    return returns


# Pre-built close price matrix (date × symbol) for vectorized forward returns.
# Built once in _load_all_data, reused across all IC computations.
_close_matrix: pd.DataFrame | None = None


# ---------------------------------------------------------------------------
# Patton & Timmermann (2010) Monotonic Relation Test
# ---------------------------------------------------------------------------

def _mr_test(quintile_returns: np.ndarray, n_boot: int = 1000,
             block_size: int = 10, seed: int = 42) -> dict:
    """Monotonic Relation test (bootstrap-based).

    Tests H0: quintile returns are NOT monotonically ordered.
    Uses circular block bootstrap to preserve time-series dependence.

    Args:
        quintile_returns: (T, K) array, columns Q1 (top) to QK (bottom)
        n_boot: bootstrap iterations
        block_size: block length for block bootstrap
        seed: random seed

    Returns:
        dict: up_pval (Q1>Q2>...>QK), down_pval (Q1<Q2<...<QK)
    """
    rng = np.random.default_rng(seed)
    T, K = quintile_returns.shape

    means = quintile_returns.mean(axis=0)
    d_up = means[:-1] - means[1:]        # Q1-Q2, Q2-Q3, ...
    d_down = means[1:] - means[:-1]
    jt_up = float(d_up.min())
    jt_down = float(d_down.min())

    jt_up_boot = np.empty(n_boot)
    jt_down_boot = np.empty(n_boot)

    for b in range(n_boot):
        indices = []
        while len(indices) < T:
            start = rng.integers(0, T)
            for j in range(block_size):
                indices.append((start + j) % T)
        indices = indices[:T]

        boot_means = quintile_returns[indices, :].mean(axis=0)
        boot_d_up = boot_means[:-1] - boot_means[1:]
        boot_d_down = boot_means[1:] - boot_means[:-1]

        # Recenter under H0
        jt_up_boot[b] = float((boot_d_up - d_up).min())
        jt_down_boot[b] = float((boot_d_down - d_down).min())

    return {
        "up_pval": float((jt_up_boot >= jt_up).mean()),
        "down_pval": float((jt_down_boot >= jt_down).mean()),
    }


# ---------------------------------------------------------------------------
# IC / ICIR Computation
# ---------------------------------------------------------------------------

def _compute_ic(
    factor_values: dict[str, float], forward_returns: dict[str, float],
) -> float | None:
    """Compute Spearman rank IC using numpy (faster than scipy.spearmanr).

    numpy rankdata + Pearson on ranks = Spearman, ~3x faster for N=200.
    """
    common = set(factor_values) & set(forward_returns)
    if len(common) < MIN_SYMBOLS:
        return None
    syms = sorted(common)
    x = np.array([factor_values[s] for s in syms])
    y = np.array([forward_returns[s] for s in syms])
    if x.max() == x.min():
        return None
    # Rank-based Pearson = Spearman
    from scipy.stats import rankdata
    rx = rankdata(x)
    ry = rankdata(y)
    n = len(rx)
    mx, my = rx.mean(), ry.mean()
    dx, dy = rx - mx, ry - my
    denom = np.sqrt((dx * dx).sum() * (dy * dy).sum())
    if denom == 0:
        return None
    ic = float((dx * dy).sum() / denom)
    return ic if not np.isnan(ic) else None


# ---------------------------------------------------------------------------
# Dedup: IC-series correlation check (from legacy L3)
# ---------------------------------------------------------------------------

def _check_dedup(ic_series_20d: list[float], known: dict[str, list[float]]) -> tuple[float, str, int]:
    """Check max correlation between this factor's IC series and known factors.

    Returns (max_correlation, correlated_with_name, n_high_corr).
    n_high_corr = number of known factors with |corr| > MAX_CORRELATION (for one-to-one check).

    Note: this checks IC series correlation only. Portfolio returns dedup
    (catching same-stock-selection clones) is done in watchdog's Validator
    stage where factor_returns are available.
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
    from datetime import datetime as _dtnow
    new_name = f"factor_{_dtnow.now().strftime('%Y%m%d_%H%M%S_%f')}"

    read_path = _dedup_read_path()
    raw = {}
    if read_path.exists():
        try:
            raw = json.loads(read_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    raw.pop(old_name, None)
    raw[new_name] = {
        "series": [round(v, 6) for v in new_ic_series],
        "icir": round(new_icir, 4),
        "added": time.strftime("%Y-%m-%d"),
        "replaced": old_name,
    }

    write_path = _dedup_write_path()
    write_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

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

    # Clear forward return cache from previous run
    _fwd_return_cache.clear()

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
    q1_excess_list: list[float] = []  # L5b: top quintile excess vs universe mean
    quintile_returns_matrix: list[list[float]] = []  # L5c: each row = [Q1_ret, Q2_ret, ..., Q5_ret]

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

        # L5b/L5c: quintile profitability + monotonicity (using 20d forward returns)
        fwd_20d = _compute_forward_returns(bars, as_of, 20) if 20 in FORWARD_HORIZONS else {}
        common_q = sorted(set(values) & set(fwd_20d))
        if len(common_q) >= 50:
            n_q = len(common_q) // 5
            ranked_q = sorted(common_q, key=lambda s: values[s], reverse=True)
            q_means = []
            for qi in range(5):
                start_idx = qi * n_q
                end_idx = (qi + 1) * n_q if qi < 4 else len(ranked_q)  # Q5 takes all remaining
                members = ranked_q[start_idx:end_idx]
                q_means.append(float(np.mean([fwd_20d[s] for s in members])))
            ew_mean = float(np.mean([fwd_20d[s] for s in common_q]))
            q1_excess_list.append(q_means[0] - ew_mean)  # top quintile excess
            if len(q_means) == 5:
                quintile_returns_matrix.append(q_means)

    elapsed = time.time() - t0

    # Compute metrics
    ics_20d = ic_by_horizon.get(20, [])
    ic_20d = float(np.mean(ics_20d)) if ics_20d else 0.0

    icir_by_horizon: dict[str, float] = {}
    best_icir = 0.0
    best_horizon = ""
    for h in FORWARD_HORIZONS:
        ics = ic_by_horizon[h]
        if len(ics) >= 20:
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

    # Fix #8 → D: use median |ICIR| across horizons (no selection bias, no horizon discrimination)
    icir_20d = icir_by_horizon.get("20d", 0.0)
    # Include ALL horizons (0 = no data at that horizon, counts as weakness)
    horizon_icirs = [abs(v) for v in icir_by_horizon.values()]
    median_icir = float(np.median(horizon_icirs)) if horizon_icirs else 0.0
    returns_proxy = abs(ic_20d) * 10000
    effective_turnover = max(avg_turnover, 0.125)
    fitness = math.sqrt(returns_proxy / effective_turnover) * median_icir if returns_proxy > 0 else 0.0

    # Industry-neutral IC diagnostic (last 10 dates, not a gate)
    # Taiwan stock code prefix → rough industry: 11=cement, 12=food, 14=textile, 15=electric,
    # 16=wire, 17=chemical, 21=glass, 22=paper, 23=semiconductor, 24=auto, 25=construction,
    # 26=shipping, 27=tourism, 28=finance, 29=department, 30-39=electronics
    ic_neutral_label = "unknown"
    try:
        _last_dates = sample_dates[-10:] if len(sample_dates) >= 10 else sample_dates
        _raw_ics: list[float] = []
        _neutral_ics: list[float] = []
        for _d in _last_dates:
            _md = _mask_data(data, _d)
            _active = [s for s in universe if s in bars and _d in bars[s].index]
            if len(_active) < MIN_SYMBOLS:
                continue
            try:
                _vals = compute_factor(_active, _d, _md)
            except Exception:
                continue
            _vals = {k: v for k, v in (_vals or {}).items() if isinstance(v, (int, float)) and np.isfinite(v)}
            if len(_vals) < MIN_SYMBOLS:
                continue
            _fwd = _compute_forward_returns(bars, _d, 20)
            _ric = _compute_ic(_vals, _fwd)
            if _ric is not None:
                _raw_ics.append(_ric)
            # Neutralize: demean by industry prefix
            _ind_groups: dict[str, list[float]] = {}
            for s, v in _vals.items():
                # Taiwan stock code: first 2 digits = industry (skip ETFs "00xx")
                _bare = s.replace(".TW", "").replace(".TWO", "")
                prefix = _bare[:2] if len(_bare) >= 2 and _bare[0].isdigit() and _bare[:2] != "00" else "other"
                _ind_groups.setdefault(prefix, []).append(v)
            _ind_means = {p: np.mean(vs) for p, vs in _ind_groups.items()}
            _n_vals = {}
            for s, v in _vals.items():
                _b = s.replace(".TW", "").replace(".TWO", "")
                _pfx = _b[:2] if len(_b) >= 2 and _b[0].isdigit() and _b[:2] != "00" else "other"
                _n_vals[s] = v - _ind_means.get(_pfx, 0)
            _nic = _compute_ic(_n_vals, _fwd)
            if _nic is not None:
                _neutral_ics.append(_nic)
        if _raw_ics and _neutral_ics:
            _raw_mean = abs(float(np.mean(_raw_ics)))
            _neutral_mean = abs(float(np.mean(_neutral_ics)))
            if _raw_mean > 0.001:
                _retention = _neutral_mean / _raw_mean
                if _retention > 0.80:
                    ic_neutral_label = "stock_alpha"  # mostly stock-level signal
                elif _retention > 0.40:
                    ic_neutral_label = "mixed"  # part industry, part stock
                else:
                    ic_neutral_label = "industry_beta"  # mostly industry rotation
    except Exception:
        pass

    # IC trend regression (diagnostic, not a gate)
    ic_trend_slope = 0.0
    ic_trend_label = "stable"
    if len(ic_series_20d) >= 20:
        from scipy.stats import linregress as _linregress
        _slope, _, _, _p, _ = _linregress(range(len(ic_series_20d)), ic_series_20d)
        ic_trend_slope = float(_slope)
        if _slope < 0 and _p < 0.05:
            ic_trend_label = "declining"
        elif _slope > 0 and _p < 0.05:
            ic_trend_label = "improving"

    # L3: Dedup check
    max_corr, corr_with, n_high_corr = _check_dedup(ic_series_20d, known_ics)

    # Phase AF: replacement candidate tracking
    is_replacement_candidate = False
    replacement_target = ""

    # ── Gate checks (L2-L4) ──
    # Method D: median |ICIR| across horizons — no selection bias, no horizon discrimination
    if median_icir < MIN_ICIR_L2:
        return _make_result(
            level="L2", failure=f"median|ICIR|={median_icir:.4f} < {MIN_ICIR_L2}",
            ic_20d=ic_20d, best_icir=best_icir, best_horizon=best_horizon,
            icir_by_horizon=icir_by_horizon, avg_turnover=avg_turnover,
            elapsed=elapsed,
        )

    # ICIR upper bound: > 1.0 in 200-stock universe is suspicious
    if median_icir > MAX_ICIR_L2:
        return _make_result(
            level="L2", failure=f"median|ICIR|={median_icir:.4f} > {MAX_ICIR_L2} (suspicious)",
            ic_20d=ic_20d, best_icir=best_icir, best_horizon=best_horizon,
            icir_by_horizon=icir_by_horizon, avg_turnover=avg_turnover,
            elapsed=elapsed,
        )

    # Saturation check — uses BOTH IC series corr AND returns corr
    # IC corr > 0.20 → direct saturation check (fast path)
    # IC corr <= 0.20 → compute returns corr to catch hidden clones (slow path, +10s)
    _sat_corr_with = corr_with
    _sat_triggered = False
    if corr_with and abs(max_corr) > 0.20:
        _sat_triggered = True
    elif corr_with:
        # IC corr low but might be returns clone — compute returns corr
        try:
            from src.backtest.vectorized import VectorizedPBOBacktest
            from factor import compute_factor as _cf_sat
            _vbt_sat = VectorizedPBOBacktest(
                universe=[s for s in universe if s in bars],
                start=EVAL_START, end=IS_END,
            )
            _sat_rets = _vbt_sat.run_variant(_cf_sat, top_n=40, weight_mode="score_tilt")
            if _sat_rets is not None and len(_sat_rets) > 50:
                _sat_rets = _sat_rets.replace([np.inf, -np.inf], 0.0).fillna(0.0)
                _ret_dir = Path("/app/watchdog_data/factor_returns")
                if not _ret_dir.exists():
                    _ret_dir = PROJECT_ROOT / "docker" / "autoresearch" / "watchdog_data" / "factor_returns"
                _sat_max_ret_corr = 0.0
                for _p in sorted(_ret_dir.glob("*.parquet"))[-30:]:
                    try:
                        _e = pd.read_parquet(_p)
                        if "returns" in _e.columns and len(_e) > 50:
                            _min = min(len(_sat_rets), len(_e["returns"]))
                            _c = float(_sat_rets.iloc[:_min].corr(_e["returns"].iloc[:_min]))
                            if abs(_c) > abs(_sat_max_ret_corr):
                                _sat_max_ret_corr = _c
                    except Exception:
                        continue
                if abs(_sat_max_ret_corr) > 0.50:
                    _sat_triggered = True
                    print(f"  saturation: IC corr={max_corr:.3f} low but returns corr={_sat_max_ret_corr:.3f} high → clone detected")
        except Exception:
            pass

    if abs(max_corr) > MAX_CORRELATION:
        # Phase AF: check replacement eligibility before rejecting
        factor_icirs = _load_factor_icirs()
        correlated_icir = abs(factor_icirs.get(corr_with, 0.0))
        replacement_count = _get_replacement_count()

        # H-003: check replacement chain depth (prevent indirect drift)
        _chain_depth = 0
        _check_name = corr_with
        # Read raw JSON (not _load_dedup_ic_series which strips "replaced" field)
        _raw_json = {}
        try:
            _rp = _dedup_read_path()
            if _rp.exists():
                _raw_json = json.loads(_rp.read_text(encoding="utf-8"))
        except Exception:
            pass
        for _ in range(10):  # max 10 hops
            _entry = _raw_json.get(_check_name)
            if isinstance(_entry, dict) and "replaced" in _entry:
                _chain_depth += 1
                _check_name = _entry["replaced"]
            else:
                break

        can_replace = (
            n_high_corr == 1  # one-to-one only
            and correlated_icir > 0  # can't replace unknown-ICIR factors
            and median_icir >= REPLACEMENT_ICIR_MULTIPLIER * correlated_icir
            and median_icir >= REPLACEMENT_MIN_ICIR
            and replacement_count < MAX_REPLACEMENTS_PER_CYCLE
            and _chain_depth < 3  # H-003: max 3 hops in replacement chain
        )

        if can_replace:
            is_replacement_candidate = True
            replacement_target = corr_with
            print(f"  L3: replacement candidate (median_ICIR {median_icir:.4f} >= {REPLACEMENT_ICIR_MULTIPLIER}x {correlated_icir:.4f})")
        else:
            return _make_result(
                level="L3", failure=f"corr={max_corr:.3f} with {corr_with} > {MAX_CORRELATION}",
                ic_20d=ic_20d, best_icir=best_icir, best_horizon=best_horizon,
                icir_by_horizon=icir_by_horizon, avg_turnover=avg_turnover,
                max_correlation=max_corr, correlated_with=corr_with,
                elapsed=elapsed,
            )

    # Saturation check AFTER replacement logic — replacement candidates bypass saturation
    if _sat_triggered and _sat_corr_with and not is_replacement_candidate:
        match_count = _get_match_count(_sat_corr_with)
        if match_count >= SATURATION_MATCH_LIMIT:
            return _make_result(
                level="L3", failure=f"direction saturated: {match_count} variants for {_sat_corr_with}",
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

    oos_q1_excess_list: list[float] = []  # C-001: OOS quintile profitability
    oos_quintile_returns_matrix: list[list[float]] = []  # L5c OOS monotonicity
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
            # C-001: OOS quintile excess + monotonicity
            common_oos = sorted(set(values) & set(fwd))
            if len(common_oos) >= 50:
                n_q_oos = len(common_oos) // 5
                ranked_oos = sorted(common_oos, key=lambda s: values[s], reverse=True)
                q1_members = ranked_oos[:n_q_oos]
                ew_oos = float(np.mean([fwd[s] for s in common_oos]))
                q1_oos = float(np.mean([fwd[s] for s in q1_members]))
                oos_q1_excess_list.append(q1_oos - ew_oos)
                # OOS quintile means for L5c monotonicity
                oos_q_means = []
                for qi in range(5):
                    si = qi * n_q_oos
                    ei = (qi + 1) * n_q_oos if qi < 4 else len(ranked_oos)
                    oos_q_means.append(float(np.mean([fwd[s] for s in ranked_oos[si:ei]])))
                if len(oos_q_means) == 5:
                    oos_quintile_returns_matrix.append(oos_q_means)

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
    # Include factor code hash in seed — agent cannot predict noise without knowing seed
    import hashlib as _hl
    _factor_hash = int(_hl.sha256(open(Path(__file__).parent / "factor.py", "rb").read()).hexdigest()[:8], 16)
    rng_l5 = np.random.default_rng(hash((ic_20d, best_icir, l5_query_n, _factor_hash)) % (2**31))
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

    # ── L5b: Profitability gate — must pass BOTH IS and OOS (pass/fail only) ──
    avg_q1_excess_is = float(np.mean(q1_excess_list)) if q1_excess_list else 0.0
    avg_q1_excess_oos = float(np.mean(oos_q1_excess_list)) if oos_q1_excess_list else 0.0
    l5b_pass = avg_q1_excess_is > 0 and avg_q1_excess_oos > 0
    print(f"  L5b profitability: {'PASS' if l5b_pass else 'FAIL'}")
    if not l5b_pass:
        _which = "IS" if avg_q1_excess_is <= 0 else "OOS"
        return _make_result(
            level="L5", failure=f"L5b profitability: top quintile does not beat universe ({_which})",
            ic_20d=ic_20d, best_icir=best_icir, best_horizon=best_horizon,
            icir_by_horizon=icir_by_horizon, avg_turnover=avg_turnover,
            fitness=fitness, positive_years=positive_years, total_years=total_years,
            max_correlation=max_corr, correlated_with=corr_with,
            oos_icir=oos_icir, oos_positive_months=oos_positive_months,
            oos_total_months=oos_total_months,
            elapsed=time.time() - t0,
        )

    # ── L5c: Monotonicity gate — Patton & Timmermann (2010) MR test (pass/fail only) ──
    # Must pass in BOTH IS and OOS (consistent with L5b)
    l5c_pass = False
    if len(quintile_returns_matrix) < 20:
        print(f"  L5c monotonicity (MR test): FAIL (only {len(quintile_returns_matrix)} IS quintile dates, need 20)")
        return _make_result(
            level="L5", failure=f"L5c monotonicity: insufficient IS quintile data ({len(quintile_returns_matrix)} < 20)",
            ic_20d=ic_20d, best_icir=best_icir, best_horizon=best_horizon,
            icir_by_horizon=icir_by_horizon, avg_turnover=avg_turnover,
            fitness=fitness, positive_years=positive_years, total_years=total_years,
            max_correlation=max_corr, correlated_with=corr_with,
            oos_icir=oos_icir, oos_positive_months=oos_positive_months,
            oos_total_months=oos_total_months,
            elapsed=time.time() - t0,
        )
    else:
        qr = np.array(quintile_returns_matrix)  # (T, 5), Q1=top .. Q5=bottom
        mr = _mr_test(qr, n_boot=1000, block_size=max(int(len(qr)**0.5), 5))
        l5c_is_pass = mr["up_pval"] < 0.05 or mr["down_pval"] < 0.05
        # OOS monotonicity — require minimum data, fail if insufficient
        l5c_oos_pass = len(oos_quintile_returns_matrix) < 5  # pass only if truly no OOS data (< 5 dates)
        if len(oos_quintile_returns_matrix) >= 5:
            qr_oos = np.array(oos_quintile_returns_matrix)
            mr_oos = _mr_test(qr_oos, n_boot=1000, block_size=max(int(len(qr_oos)**0.5), 3))
            l5c_oos_pass = mr_oos["up_pval"] < 0.10 or mr_oos["down_pval"] < 0.10  # relaxed for shorter OOS
        l5c_pass = l5c_is_pass and l5c_oos_pass
    _l5c_detail = "IS+OOS" if len(oos_quintile_returns_matrix) >= 5 else "IS only (OOS data insufficient)"
    print(f"  L5c monotonicity (MR test): {'PASS' if l5c_pass else 'FAIL'} [{_l5c_detail}]")
    if not l5c_pass:
        _which = "IS" if not l5c_is_pass else "OOS"
        return _make_result(
            level="L5", failure=f"L5c monotonicity: MR test failed ({_which})",
            ic_20d=ic_20d, best_icir=best_icir, best_horizon=best_horizon,
            icir_by_horizon=icir_by_horizon, avg_turnover=avg_turnover,
            fitness=fitness, positive_years=positive_years, total_years=total_years,
            max_correlation=max_corr, correlated_with=corr_with,
            oos_icir=oos_icir, oos_positive_months=oos_positive_months,
            oos_total_months=oos_total_months,
            elapsed=time.time() - t0,
        )

    # ── Stage 2: Large-scale IC verification (865+ symbols) ──
    large_icir_20d = 0.0
    large_universe = _load_universe(large=True)
    if len(large_universe) > len(universe):
        # Clear fwd cache — Stage 2 has more symbols than IS, cached entries are incomplete
        _fwd_return_cache.clear()
        print(f"\nStage 2: Large-scale verification ({len(large_universe)} symbols)")
        try:
            # Incrementally load only NEW symbols (don't reset cache)
            global _data_cache
            existing_syms = set(_data_cache["bars"].keys()) if _data_cache else set()
            new_syms = [s for s in large_universe if s not in existing_syms]
            if new_syms:
                from src.data.data_catalog import DataCatalog
                catalog = DataCatalog(str(PROJECT_ROOT / "data"))
                print(f"  Loading {len(new_syms)} additional symbols...")
                for sym in new_syms:
                    # bars
                    df = catalog.get("price", sym)
                    if not df.empty and "close" in df.columns:
                        if not isinstance(df.index, pd.DatetimeIndex):
                            df.index = pd.to_datetime(df.index)
                        df.index = pd.to_datetime(df.index.date)
                        df = df[~df.index.duplicated(keep="first")]
                        df["close"] = df["close"].where(df["close"] > 0)
                        if df["close"].isna().sum() / len(df) <= 0.10:
                            _data_cache["bars"][sym] = df

            large_bars = _data_cache["bars"]
            large_data = _data_cache
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
            replaced_name = _replace_factor(replacement_target, ic_series_20d, median_icir)
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
    result["ic_trend"] = ic_trend_label
    result["ic_source"] = ic_neutral_label
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
        "ic_trend": "",  # set after _make_result for L5
        "ic_source": "",  # set after _make_result for L5
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
    # Novelty: compute returns correlation against existing factor_returns (portfolio-level)
    _returns_corr = 0.0
    _returns_corr_with = ""
    try:
        from src.backtest.vectorized import VectorizedPBOBacktest
        from factor import compute_factor as _cf_novelty
        _vbt = VectorizedPBOBacktest(
            universe=[s for s in bars if s in universe],
            start=EVAL_START, end=IS_END,
        )
        _my_rets = _vbt.run_variant(_cf_novelty, top_n=40, weight_mode="score_tilt")
        if _my_rets is not None and len(_my_rets) > 50:
            _my_rets = _my_rets.replace([np.inf, -np.inf], 0.0).fillna(0.0)
            _ret_dir = Path("/app/watchdog_data/factor_returns")
            if not _ret_dir.exists():
                _ret_dir = PROJECT_ROOT / "docker" / "autoresearch" / "watchdog_data" / "factor_returns"
            for _p in sorted(_ret_dir.glob("*.parquet"))[-30:]:
                try:
                    _existing = pd.read_parquet(_p)
                    if "returns" in _existing.columns and len(_existing) > 50:
                        _e = _existing["returns"].copy()
                        _min = min(len(_my_rets), len(_e))
                        _c = float(_my_rets.iloc[:_min].corr(_e.iloc[:_min]))
                        if abs(_c) > abs(_returns_corr):
                            _returns_corr = _c
                            _returns_corr_with = _p.stem
                except Exception:
                    continue
    except Exception:
        pass  # fallback to IC corr if returns corr unavailable

    if abs(_returns_corr) > 0.10:
        _novelty = "high" if abs(_returns_corr) < 0.50 else "not_high"
        print(f"novelty:          {_novelty}")
        print(f"returns_corr:     {_returns_corr:.3f} [portfolio-level stock overlap]")
    else:
        # No factor_returns to compare — fallback to IC corr
        _abs_corr = abs(results['max_correlation'])
        print(f"novelty:          {'high' if _abs_corr < 0.20 else 'not_high'}")
        print(f"ic_corr:          {results['max_correlation']:.3f} ({results['correlated_with']}) [no returns data, using signal corr]")
    print(f"ic_trend:         {results.get('ic_trend', 'unknown')}")
    print(f"ic_source:        {results.get('ic_source', 'unknown')}")
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

    # Phase AB: store daily returns for Factor-Level PBO
    # AB-4 fix: only L3+ factors (L1/L2 have no signal, their returns are noise that inflates n_independent)
    if results.get("level") in ("L3", "L4", "L5"):
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

    Only called for L3+ factors (caller filters at line ~1050).
    L1/L2 factors have IC < 0.02 — their top-15 portfolios are random noise,
    not meaningful strategies. Including them inflates n_independent (each noise
    portfolio is uncorrelated → own cluster → N↑) and makes PBO artificially low.
    Bailey (2014) "failed trials" = strategies with signal that failed OOS,
    not strategies with no signal at all.
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

        # top-40 score-tilt: higher TC (0.45 vs 0.10), lower variance drag
        daily_rets = vbt.run_variant(compute_factor, top_n=40, weight_mode="score_tilt")

        if daily_rets is not None and len(daily_rets) > 20:
            # Clean inf/nan before storing
            daily_rets = daily_rets.replace([np.inf, -np.inf], 0.0).fillna(0.0)
            ts = time.strftime("%Y%m%d_%H%M%S")
            path = returns_dir / f"{ts}.parquet"
            daily_rets.to_frame("returns").to_parquet(path)
            # Store timestamp so pending marker uses same stem (watchdog returns dedup match)
            results["_factor_returns_stem"] = ts

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

        # M-006: cap learnings at 10000 lines (truncate oldest)
        if learnings_path.exists() and learnings_path.stat().st_size > 5_000_000:  # > 5MB
            lines = learnings_path.read_text(encoding="utf-8").splitlines()
            if len(lines) > 10000:
                learnings_path.write_text("\n".join(lines[-5000:]) + "\n", encoding="utf-8")

        # AF-M1 fix: extract direction from compute_factor docstring (first triple-quoted line)
        direction = "unknown"
        try:
            factor_path = Path(__file__).parent / "factor.py"
            if not factor_path.exists():
                factor_path = Path(__file__).parent / "work" / "factor.py"
            if factor_path.exists():
                src = factor_path.read_text(encoding="utf-8")
                # Find docstring inside compute_factor
                in_func = False
                for line in src.splitlines():
                    if "def compute_factor" in line:
                        in_func = True
                        continue
                    if in_func:
                        stripped = line.strip().strip('"').strip("'")
                        if stripped and not stripped.startswith(("#",)):
                            direction = stripped[:80]
                            break
        except Exception:
            pass

        # AF-H1 fix: bucket ICIR (same as /evaluate) to prevent leaking precise values
        # Use median |ICIR| across horizons (consistent with L2 gate, method D)
        horizon_vals = [abs(v) for v in results.get("icir_by_horizon", {}).values() if v != 0]
        raw_icir = float(np.median(horizon_vals)) if horizon_vals else 0.0
        if raw_icir >= 0.40:
            icir_bucket = "strong"
        elif raw_icir >= 0.30:
            icir_bucket = "moderate"
        elif raw_icir >= 0.15:
            icir_bucket = "weak"
        else:
            icir_bucket = "none"

        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "direction": direction,
            "level": results.get("level", ""),
            "passed": results.get("passed", False),
            "icir": icir_bucket,
            "failure": results.get("failure", ""),
            "ic_corr": round(results.get("max_correlation", 0), 3),
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
        # Use same timestamp as factor_returns parquet so watchdog returns dedup can match
        fr_stem = results.get("_factor_returns_stem", time.strftime("%Y%m%d_%H%M%S"))
        marker = {
            "results": safe_results,
            "factor_code": factor_code,
            "timestamp": fr_stem,
        }
        marker_path = pending_dir / f"{fr_stem}.json"
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
            def __init__(self) -> None:
                self._last_month = ""
                self._cached: dict[str, float] = {}

            def name(self) -> str:
                return "autoresearch_candidate"

            def on_bar(self, ctx: Context) -> dict[str, float]:
                # Monthly rebalance cache (same as strategy_builder)
                current_date = ctx.now()
                month = pd.Timestamp(current_date).strftime("%Y-%m")
                if month == self._last_month:
                    return self._cached

                symbols = ctx.universe()
                as_of = pd.Timestamp(ctx.now())

                # Volume filter: match strategy_builder (300 lots = 300,000 shares)
                eligible = []
                for s in symbols:
                    try:
                        b = ctx.bars(s, lookback=60)
                        if len(b) >= 20 and float(b["volume"].iloc[-20:].mean()) >= 300_000:
                            eligible.append(s)
                    except Exception:
                        continue

                if not eligible:
                    self._last_month = month
                    self._cached = {}
                    return {}

                if _is_3arg:
                    revenue, institutional, per_history, margin_data = {}, {}, {}, {}
                    for s in eligible:
                        try:
                            rev = ctx.get_revenue(s, lookback_months=36)
                            if rev is not None and not rev.empty:
                                revenue[s] = rev
                        except Exception:
                            pass
                        try:
                            inst = ctx.get_institutional(s)
                            if inst is not None and not inst.empty:
                                institutional[s] = inst
                        except Exception:
                            pass
                        try:
                            per = ctx.get_per_history(s)
                            if per is not None and not per.empty:
                                per_history[s] = per
                        except Exception:
                            pass
                        try:
                            mrg = ctx.get_margin(s)
                            if mrg is not None and not mrg.empty:
                                margin_data[s] = mrg
                        except Exception:
                            pass
                    data = {
                        "bars": {s: ctx.bars(s, lookback=500) for s in eligible},
                        "revenue": revenue,
                        "institutional": institutional,
                        "per_history": per_history,
                        "margin": margin_data,
                        "pe": {}, "pb": {}, "roe": {},
                    }
                    values = compute_factor(eligible, as_of, data)
                else:
                    values = compute_factor(eligible, as_of)

                self._last_month = month
                if not values:
                    self._cached = {}
                    return {}

                sorted_syms = sorted(values, key=lambda s: values[s], reverse=True)
                selected = sorted_syms[:15]
                n = len(selected)
                # 95% invested, max 10% per stock (match strategy_builder)
                w = min(0.95 / n, 0.10)
                self._cached = {s: w for s in selected}
                return self._cached

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

        # Hard/soft deployment threshold (Phase AC §7) — import from validator (single source of truth)
        from src.backtest.validator import HARD_CHECKS
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
            f"| IC Series Corr | {results['max_correlation']} ({results['correlated_with']}) [signal, not portfolio] |\n\n"
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
