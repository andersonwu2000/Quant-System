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


@app.route("/evaluate", methods=["POST"])
def evaluate():
    """Run evaluate.py and return only safe fields."""
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

    # Bucket ICIR to prevent agent from building IS→OOS regression model.
    # Precise ICIR + L5 pass/fail = partial Thresholdout bypass over many experiments.
    best_icir = 0.0
    try:
        best_icir = float(_extract(stdout, "best_icir:"))
    except (ValueError, TypeError):
        pass
    if best_icir >= 0.40:
        icir_bucket = "strong"
    elif best_icir >= 0.20:
        icir_bucket = "moderate"
    elif best_icir >= 0.10:
        icir_bucket = "weak"
    else:
        icir_bucket = "none"

    # Bucket composite similarly
    composite = 0.0
    try:
        composite = float(_extract(stdout, "composite_score:"))
    except (ValueError, TypeError):
        pass
    if composite >= 15:
        score_bucket = "high"
    elif composite >= 5:
        score_bucket = "medium"
    elif composite > 0:
        score_bucket = "low"
    else:
        score_bucket = "none"

    return jsonify({
        "passed": passed,
        "level": level,
        "score": score_bucket,
        "icir": icir_bucket,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
