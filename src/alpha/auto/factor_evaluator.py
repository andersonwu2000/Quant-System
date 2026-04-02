"""[DEPRECATED] Legacy factor evaluator — use scripts/autoresearch/evaluate.py.

This module has zero callers (verified by AP audit). Retained in archive/ for reference.
Actual implementation: src/alpha/auto/archive/factor_evaluator.py
"""
import warnings
warnings.warn(
    "factor_evaluator.py is deprecated. Use scripts/autoresearch/evaluate.py as the single evaluation standard.",
    DeprecationWarning,
    stacklevel=2,
)
