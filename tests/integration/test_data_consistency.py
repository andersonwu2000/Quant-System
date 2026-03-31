"""AK-2 Layer 1: Data dict consistency across all compute_factor call sites.

Regression tests for 2026-03-31 bugs:
- evaluate.py _FactorStrategy missing per_history/margin/institutional
- strategy_builder missing per_history/margin/institutional
- deployed_executor data dict only had bars
- vectorized.py _build_factor_data missing per_history/margin
- Context.get_revenue bypassing DataCatalog (no FinLab merge)
- Weight formula inconsistency (1/n vs 0.95/n)
"""

from __future__ import annotations

import ast
import inspect
import re
import textwrap
from pathlib import Path

import pytest

# ── Test 1.1: Data dict key consistency ─────────────────────────────


# The canonical set of keys that _mask_data provides to compute_factor
CANONICAL_KEYS = {
    "bars", "revenue", "institutional", "per_history", "margin",
    "pe", "pb", "roe",
}


def _extract_data_dict_keys_from_source(source: str) -> list[set[str]]:
    """Extract all dict literal keys that look like data dicts from source code.

    Finds patterns like: data = {"bars": ..., "revenue": ..., ...}
    Returns list of key sets found.
    """
    results = []
    # Match dict literals with string keys that include "bars"
    # Simple approach: find lines with '"bars"' and collect surrounding dict keys
    lines = source.splitlines()
    in_dict = False
    current_keys: set[str] = set()
    brace_depth = 0

    for line in lines:
        stripped = line.strip()
        # Detect start of a data dict (contains "bars" key)
        if '"bars"' in stripped and ("{" in stripped or ":" in stripped):
            in_dict = True
            current_keys = set()
            brace_depth = 0

        if in_dict:
            brace_depth += stripped.count("{") - stripped.count("}")
            # Extract string keys
            for match in re.finditer(r'"(\w+)"\s*:', stripped):
                current_keys.add(match.group(1))

            if brace_depth <= 0 and current_keys:
                # Filter: must contain "bars" to be a data dict
                if "bars" in current_keys:
                    results.append(current_keys)
                in_dict = False
                current_keys = set()

    return results


class TestDataDictKeyConsistency:
    """Verify all call sites provide the canonical data dict keys."""

    def _check_keys_in_file(self, path: Path, label: str):
        """Assert file contains all canonical keys as dict keys ('"key":' pattern)."""
        source = path.read_text(encoding="utf-8")
        for key in CANONICAL_KEYS:
            pattern = f'"{key}"'
            assert pattern in source, f"{label}: missing data dict key {key}"

    def test_evaluate_factor_strategy(self):
        self._check_keys_in_file(
            Path("scripts/autoresearch/evaluate.py"),
            "evaluate.py",
        )

    def test_strategy_builder(self):
        self._check_keys_in_file(
            Path("src/alpha/auto/strategy_builder.py"),
            "strategy_builder.py",
        )

    def test_deployed_executor(self):
        self._check_keys_in_file(
            Path("src/alpha/auto/deployed_executor.py"),
            "deployed_executor.py",
        )

    def test_vectorized_build_factor_data(self):
        self._check_keys_in_file(
            Path("src/backtest/vectorized.py"),
            "vectorized.py",
        )


# ── Test 1.2: Context vs DataCatalog consistency ────────────────────


class TestContextDataCatalogConsistency:
    """Verify Context methods use DataCatalog (not direct parquet reads)."""

    def test_get_revenue_uses_data_catalog(self):
        """Context.get_revenue must import and call DataCatalog, not parquet_path."""
        source = inspect.getsource(
            __import__("src.strategy.base", fromlist=["Context"]).Context.get_revenue
        )
        assert "get_catalog" in source, "get_revenue should use DataCatalog.get_catalog()"
        assert "parquet_path" not in source, "get_revenue should NOT use parquet_path directly"

    def test_get_per_history_exists_and_uses_catalog(self):
        """Context.get_per_history must exist and use DataCatalog."""
        Context = __import__("src.strategy.base", fromlist=["Context"]).Context
        assert hasattr(Context, "get_per_history"), "Context missing get_per_history method"
        source = inspect.getsource(Context.get_per_history)
        assert "get_catalog" in source

    def test_get_institutional_exists_and_uses_catalog(self):
        Context = __import__("src.strategy.base", fromlist=["Context"]).Context
        assert hasattr(Context, "get_institutional"), "Context missing get_institutional method"
        source = inspect.getsource(Context.get_institutional)
        assert "get_catalog" in source

    def test_get_margin_exists_and_uses_catalog(self):
        Context = __import__("src.strategy.base", fromlist=["Context"]).Context
        assert hasattr(Context, "get_margin"), "Context missing get_margin method"
        source = inspect.getsource(Context.get_margin)
        assert "get_catalog" in source


# ── Test 1.4: Weight formula consistency ────────────────────────────


class TestWeightFormulaConsistency:
    """All strategy wrappers must use 0.95/n with 0.10 cap."""

    def _check_weight_formula(self, path: Path, label: str):
        source = path.read_text(encoding="utf-8")
        # Must contain 0.95 (investment ratio) and 0.10 (per-stock cap)
        has_095 = "0.95" in source
        has_010 = "0.10" in source or "0.1)" in source
        assert has_095, f"{label}: missing 0.95 investment ratio"
        assert has_010, f"{label}: missing 0.10 per-stock cap"

    def test_evaluate_factor_strategy_weights(self):
        self._check_weight_formula(
            Path("scripts/autoresearch/evaluate.py"),
            "evaluate.py _FactorStrategy",
        )

    def test_strategy_builder_weights(self):
        self._check_weight_formula(
            Path("src/alpha/auto/strategy_builder.py"),
            "strategy_builder.py",
        )

    def test_deployed_executor_weights(self):
        self._check_weight_formula(
            Path("src/alpha/auto/deployed_executor.py"),
            "deployed_executor.py",
        )

    def test_volume_filter_consistency(self):
        """All 3 wrappers must filter at 300,000 shares (300 lots).

        strategy_builder uses `min_volume_lots * 1000` (default 300),
        others use literal 300_000. Both are equivalent.
        """
        for path, label in [
            (Path("scripts/autoresearch/evaluate.py"), "evaluate.py"),
            (Path("src/alpha/auto/deployed_executor.py"), "deployed_executor.py"),
        ]:
            source = path.read_text(encoding="utf-8")
            assert "300_000" in source or "300000" in source, (
                f"{label}: missing 300,000 volume filter"
            )
        # strategy_builder uses parameter: min_volume_lots=300, multiplied by 1000
        sb_source = Path("src/alpha/auto/strategy_builder.py").read_text(encoding="utf-8")
        assert "min_volume_lots" in sb_source and "* 1000" in sb_source, (
            "strategy_builder: missing volume filter (min_volume_lots * 1000)"
        )
