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
    for e in recent:
        bucket = e.get("icir", "unknown")
        icir_dist[bucket] = icir_dist.get(bucket, 0) + 1

    return jsonify({
        "successful_patterns": successful,
        "failed_patterns": failed,
        "forbidden": forbidden,
        "icir_distribution": icir_dist,
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

    return jsonify({
        "passed": passed,
        "level": level,
        "score": score_bucket,
        "icir": icir_bucket,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
