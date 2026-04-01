"""Evaluation-as-a-Service — HTTP wrapper for evaluate.py.

Agent submits evaluation request, gets back only: passed, level, composite_score, best_icir.
No IC values, no OOS data, no Validator details.
"""
import os
import subprocess
import json
from flask import Flask, jsonify

app = Flask(__name__)

# 單線程是刻意的 — 評估必須序列化，防止併發 evaluate 耗盡資源
# evaluate.py 需要 5-60 秒，不需要 gunicorn

# Bucket boundaries (AF-M3: centralized)
ICIR_THRESHOLDS = (0.50, 0.40, 0.30, 0.20, 0.10)  # exceptional/strong/moderate/near/weak/noise
SCORE_THRESHOLDS = (15, 5, 0)                # high / medium / low / none
SATURATION_HIGH = 10
SATURATION_MEDIUM = 5
MAX_REPLACEMENTS_PER_CYCLE = 10


def _extract(text: str, prefix: str) -> str:
    """Extract value after prefix from evaluate.py stdout."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped.split(prefix, 1)[1].strip()
    return ""


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/learnings", methods=["GET"])
def learnings():
    """Return filtered experience summary — direction descriptions only, no precise ICIR."""
    learnings_path = "/app/watchdog_data/learnings.jsonl"
    try:
        with open(learnings_path, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    entries = []
    for line in lines:
        try:
            entries.append(json.loads(line.strip()))
        except Exception:
            continue

    # Recent 100 entries only (TTL)
    recent = entries[-100:]

    # Aggregate by direction
    direction_stats: dict[str, dict] = {}
    for e in recent:
        d = e.get("direction", "unknown")
        if d not in direction_stats:
            direction_stats[d] = {"tried": 0, "passed": 0, "l3_corr_fail": 0}
        direction_stats[d]["tried"] += 1
        if e.get("passed"):
            direction_stats[d]["passed"] += 1
        if "corr" in e.get("failure", "").lower() or e.get("level") == "L3":
            direction_stats[d]["l3_corr_fail"] += 1

    successful = [{"direction": d, "variants_tried": s["tried"],
                    "saturation": "HIGH" if s["tried"] >= SATURATION_HIGH else "MEDIUM" if s["tried"] >= SATURATION_MEDIUM else "LOW"}
                   for d, s in direction_stats.items() if s["passed"] > 0]
    failed = [d for d, s in direction_stats.items() if s["passed"] == 0 and s["tried"] >= 2]
    forbidden = [d for d, s in direction_stats.items() if s["l3_corr_fail"] >= 3]

    # Library health (written by evaluate.py after replacements)
    library_health = {}
    try:
        health_path = "/app/watchdog_data/library_health.json"
        with open(health_path, encoding="utf-8") as f:
            health_data = json.loads(f.read())
        library_health = {
            "avg_corr": health_data.get("avg_pairwise_corr", 0),
            "effective_n": health_data.get("effective_n", 0),
            "diversity": health_data.get("diversity_ratio", 1.0),
            "n_factors": health_data.get("n_factors", 0),
        }
    except Exception:
        pass

    # Replacement budget remaining
    replacement_budget = MAX_REPLACEMENTS_PER_CYCLE
    try:
        counter_path = "/app/watchdog_data/l5_query_count.json"
        with open(counter_path, encoding="utf-8") as f:
            counter_data = json.loads(f.read())
        used = counter_data.get("replacement_count", 0)
        replacement_budget = max(0, MAX_REPLACEMENTS_PER_CYCLE - used)
    except Exception:
        pass

    # ICIR bucket distribution (6-level: noise/weak/near/moderate/strong/exceptional)
    # Only aggregate counts — no direction names (prevents overfitting to specific approaches)
    icir_dist: dict[str, int] = {}
    source_dist: dict[str, int] = {}
    trend_dist: dict[str, int] = {}
    for e in recent:
        bucket = e.get("icir", "unknown")
        icir_dist[bucket] = icir_dist.get(bucket, 0) + 1
        src = e.get("source", "")
        if src:
            source_dist[src] = source_dist.get(src, 0) + 1
        trend = e.get("trend", "")
        if trend:
            trend_dist[trend] = trend_dist.get(trend, 0) + 1

    return jsonify({
        "successful_patterns": successful,
        "failed_patterns": failed,
        "forbidden": forbidden,
        "icir_distribution": icir_dist,
        "source_distribution": source_dist,   # stock_alpha vs industry_beta vs mixed
        "trend_distribution": trend_dist,      # stable vs improving vs declining
        "stats": {
            "total_experiments": len(entries),
            "directions_explored": len(direction_stats),
            "l5_pass_count": sum(1 for e in entries if e.get("passed")),
        },
        "library_health": library_health,
        "replacement_budget_remaining": replacement_budget,
    })


@app.route("/evaluate", methods=["POST"])
def evaluate():
    """Run evaluate.py and return only safe fields."""
    # Enforce commit before evaluate — agent must follow program.md protocol
    # Compare factor.py hash with last known hash stored after each successful evaluate
    try:
        import hashlib
        factor_path = "/app/work/factor.py"
        hash_path = "/app/watchdog_data/last_evaluated_hash.txt"
        current_hash = hashlib.sha256(open(factor_path, "rb").read()).hexdigest()
        last_hash = ""
        if os.path.exists(hash_path):
            last_hash = open(hash_path).read().strip()
        if current_hash == last_hash:
            return jsonify({
                "passed": False, "level": "UNCHANGED",
                "score": "none", "icir": "none",
                "error": "factor.py unchanged since last evaluate. Edit factor.py first."
            })
    except Exception:
        pass  # hash check failure should not block evaluation

    env = {**os.environ, "PYTHONPATH": "/app/work:/app", "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        result = subprocess.run(
            ["python", "/app/evaluate.py"],
            capture_output=True, text=True, timeout=300,
            cwd="/app", env=env,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"passed": False, "level": "TIMEOUT", "composite_score": 0, "best_icir": 0})

    if result.returncode != 0 and not result.stdout.strip():
        # evaluate.py crashed before producing output
        return jsonify({"passed": False, "level": "CRASH", "composite_score": 0, "best_icir": 0})

    stdout = result.stdout
    level = _extract(stdout, "level:") or "UNKNOWN"
    passed = _extract(stdout, "passed:") == "True"

    # Bucket median |ICIR| across horizons (Method D — consistent with L2 gate).
    import statistics
    horizon_icirs = []
    for h in ["5d", "10d", "20d", "60d"]:
        try:
            v = abs(float(_extract(stdout, f"icir_{h}:")))
            if v > 0:
                horizon_icirs.append(v)
        except (ValueError, TypeError):
            pass
    median_icir = statistics.median(horizon_icirs) if horizon_icirs else 0.0
    if median_icir >= ICIR_THRESHOLDS[0]:
        icir_bucket = "exceptional"
    elif median_icir >= ICIR_THRESHOLDS[1]:
        icir_bucket = "strong"
    elif median_icir >= ICIR_THRESHOLDS[2]:
        icir_bucket = "moderate"
    elif median_icir >= ICIR_THRESHOLDS[3]:
        icir_bucket = "near"
    elif median_icir >= ICIR_THRESHOLDS[4]:
        icir_bucket = "weak"
    else:
        icir_bucket = "noise"

    # Bucket composite similarly
    composite = 0.0
    try:
        composite = float(_extract(stdout, "composite_score:"))
    except (ValueError, TypeError):
        pass
    if composite >= SCORE_THRESHOLDS[0]:
        score_bucket = "high"
    elif composite >= SCORE_THRESHOLDS[1]:
        score_bucket = "medium"
    elif composite > SCORE_THRESHOLDS[2]:
        score_bucket = "low"
    else:
        score_bucket = "none"

    # Record hash to prevent re-evaluating unchanged factor.py
    try:
        import hashlib
        current_hash = hashlib.sha256(open("/app/work/factor.py", "rb").read()).hexdigest()
        with open("/app/watchdog_data/last_evaluated_hash.txt", "w") as f:
            f.write(current_hash)
    except Exception:
        pass

    # Auto-save "near" and above factors to library for ensemble testing
    if median_icir >= ICIR_THRESHOLDS[3]:  # >= 0.20 ("near" or better)
        try:
            import time as _t
            lib_dir = "/app/watchdog_data/factor_library"
            os.makedirs(lib_dir, exist_ok=True)
            factor_code = open("/app/work/factor.py", encoding="utf-8").read()
            # Use direction as filename (sanitized)
            import re
            safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', ic_source or "unknown")[:40]
            ts = _t.strftime("%Y%m%d_%H%M%S")
            lib_path = f"{lib_dir}/{ts}_{safe_name}_{icir_bucket}.py"
            with open(lib_path, "w", encoding="utf-8") as f:
                f.write(factor_code)
            # Save metadata
            meta_path = f"{lib_dir}/index.json"
            meta = {}
            if os.path.exists(meta_path):
                try:
                    meta = json.loads(open(meta_path, encoding="utf-8").read())
                except Exception:
                    meta = {}
            meta[os.path.basename(lib_path)] = {
                "icir": icir_bucket,
                "source": ic_source,
                "trend": ic_trend,
                "best_horizon": best_horizon,
                "level": level,
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except Exception:
            pass  # library save failure must not block evaluation

    # Extract factor decomposition info (already printed by evaluate.py)
    ic_source = _extract(stdout, "ic_source:") or "unknown"   # stock_alpha | mixed | industry_beta
    ic_trend = _extract(stdout, "ic_trend:") or "unknown"     # stable | improving | declining
    novelty = _extract(stdout, "novelty:") or "unknown"       # high | not_high

    # Find best horizon (agent can learn which timeframe works)
    best_horizon = _extract(stdout, "best_horizon:") or ""

    return jsonify({
        "passed": passed,
        "level": level,
        "score": score_bucket,
        "icir": icir_bucket,
        "source": ic_source,     # stock_alpha = good, industry_beta = needs neutralization
        "trend": ic_trend,        # declining = signal decaying, improving = getting stronger
        "novelty": novelty,       # high = unique signal, not_high = correlated with existing
        "best_horizon": best_horizon,  # which timeframe the signal is strongest
    })


@app.route("/factor-library", methods=["GET"])
def factor_library():
    """List saved factors available for ensemble testing."""
    lib_dir = "/app/watchdog_data/factor_library"
    meta_path = f"{lib_dir}/index.json"
    if not os.path.exists(meta_path):
        return jsonify({"factors": [], "count": 0})
    try:
        meta = json.loads(open(meta_path, encoding="utf-8").read())
        factors = [
            {"name": name, **info}
            for name, info in meta.items()
        ]
        return jsonify({"factors": factors, "count": len(factors)})
    except Exception:
        return jsonify({"factors": [], "count": 0})


@app.route("/evaluate-ensemble", methods=["POST"])
def evaluate_ensemble():
    """Test rank composite of 2-3 library factors.

    Agent sends: curl -X POST http://evaluator:5000/evaluate-ensemble \
      -H 'Content-Type: application/json' \
      -d '{"factors": ["20260401_xxx_near.py", "20260401_yyy_near.py"]}'

    Returns: composite IC/ICIR across horizons.
    """
    from flask import request
    data = request.get_json(silent=True) or {}
    factor_names = data.get("factors", [])

    if len(factor_names) < 2:
        return jsonify({"error": "Need at least 2 factors", "passed": False})
    if len(factor_names) > 5:
        return jsonify({"error": "Max 5 factors", "passed": False})

    lib_dir = "/app/watchdog_data/factor_library"

    # Load factor functions
    factor_fns = []
    for name in factor_names:
        path = os.path.join(lib_dir, name)
        if not os.path.exists(path):
            return jsonify({"error": f"Factor not found: {name}", "passed": False})
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            fn = getattr(mod, "compute_factor", None)
            if fn is None:
                return jsonify({"error": f"No compute_factor in {name}", "passed": False})
            factor_fns.append((name, fn))
        except Exception as e:
            return jsonify({"error": f"Load error for {name}: {e}", "passed": False})

    # Run ensemble evaluation via evaluate.py's infrastructure
    try:
        import sys
        sys.path.insert(0, "/app")
        from evaluate import _load_universe, _load_all_data, _mask_data, _compute_ic, _compute_forward_returns
        import numpy as np
        import pandas as pd
        from scipy.stats import rankdata

        universe = _load_universe()
        data_dict = _load_all_data(universe)
        bars = data_dict["bars"]

        # Sample dates (every 20 trading days, IS only)
        all_dates = set()
        for df in bars.values():
            all_dates |= set(df.index)
        from evaluate import EVAL_START, IS_END, SAMPLE_FREQ_DAYS, MIN_SYMBOLS, FORWARD_HORIZONS
        eval_dates = sorted(d for d in all_dates if pd.Timestamp(EVAL_START) <= d <= pd.Timestamp(IS_END))
        sample_dates = eval_dates[::SAMPLE_FREQ_DAYS]

        ic_by_horizon = {h: [] for h in FORWARD_HORIZONS}

        for as_of in sample_dates:
            masked = _mask_data(data_dict, as_of)
            active = [s for s in universe if s in bars and as_of in bars[s].index]
            if len(active) < MIN_SYMBOLS:
                continue

            # Compute each factor
            all_vals = []
            for name, fn in factor_fns:
                try:
                    vals = fn(active, as_of, masked)
                    vals = {k: v for k, v in (vals or {}).items()
                            if isinstance(v, (int, float)) and np.isfinite(v)}
                    if len(vals) >= MIN_SYMBOLS:
                        all_vals.append(vals)
                except Exception:
                    pass

            if len(all_vals) < 2:
                continue

            # Rank composite: equal-weight rank average
            common = set(active)
            for vals in all_vals:
                common &= set(vals.keys())
            common = sorted(common)
            if len(common) < MIN_SYMBOLS:
                continue

            composite = {}
            for sym in common:
                ranks = []
                for vals in all_vals:
                    # Rank within common symbols
                    scores = [vals[s] for s in common]
                    r = rankdata(scores)
                    idx = common.index(sym)
                    ranks.append(r[idx])
                composite[sym] = sum(ranks) / len(ranks)

            # IC for each horizon
            for h in FORWARD_HORIZONS:
                fwd = _compute_forward_returns(bars, as_of, h)
                ic = _compute_ic(composite, fwd)
                if ic is not None:
                    ic_by_horizon[h].append(ic)

        # Compute ICIR
        result_horizons = {}
        best_icir = 0.0
        best_h = ""
        for h in FORWARD_HORIZONS:
            ics = ic_by_horizon[h]
            if len(ics) >= 10:
                ic_mean = float(np.mean(ics))
                ic_std = float(np.std(ics, ddof=1))
                icir = ic_mean / ic_std if ic_std > 0 else 0
                result_horizons[f"{h}d"] = round(icir, 4)
                if abs(icir) > abs(best_icir):
                    best_icir = icir
                    best_h = f"{h}d"
            else:
                result_horizons[f"{h}d"] = 0.0

        median_icir = float(np.median([abs(v) for v in result_horizons.values()])) if result_horizons else 0.0

        # Bucket
        if median_icir >= 0.30:
            passed_l2 = True
        else:
            passed_l2 = False

        return jsonify({
            "passed": passed_l2,
            "n_factors": len(factor_fns),
            "median_icir": round(median_icir, 4),
            "best_icir": round(best_icir, 4),
            "best_horizon": best_h,
            "icir_by_horizon": result_horizons,
            "n_dates": len(sample_dates),
        })

    except Exception as e:
        return jsonify({"error": str(e), "passed": False})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
