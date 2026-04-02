import math

from fastapi import HTTPException


def validate_weights(weights: dict[str, float]) -> dict[str, float]:
    """Reject NaN, Infinity, and negative weights from API input."""
    clean = {}
    for sym, w in weights.items():
        if not isinstance(w, (int, float)) or math.isnan(w) or math.isinf(w):
            raise HTTPException(400, f"Invalid weight for {sym}: {w}")
        if w < 0:
            raise HTTPException(400, f"Negative weight for {sym}: {w}")
        clean[sym] = float(w)
    return clean
