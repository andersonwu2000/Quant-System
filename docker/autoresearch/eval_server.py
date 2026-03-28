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

    stdout = result.stdout
    level = _extract(stdout, "level:")
    passed = _extract(stdout, "passed:") == "True"
    composite = 0.0
    best_icir = 0.0
    try:
        composite = float(_extract(stdout, "composite_score:"))
    except (ValueError, TypeError):
        pass
    try:
        best_icir = float(_extract(stdout, "best_icir:"))
    except (ValueError, TypeError):
        pass

    return jsonify({
        "passed": passed,
        "level": level,
        "composite_score": round(composite, 4),
        "best_icir": round(best_icir, 4),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
