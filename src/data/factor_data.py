"""Unified factor data bundle — single source of truth for factor runtime data.

AP-1: Replaces scattered data assembly in evaluate.py, strategy_builder.py,
deployed_executor.py, and Context. All PIT delays come from registry.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FactorDataBundle:
    """Factor runtime data with point-in-time enforcement."""
    bars: dict[str, pd.DataFrame] = field(default_factory=dict)
    revenue: dict[str, pd.DataFrame] = field(default_factory=dict)
    per_history: dict[str, pd.DataFrame] = field(default_factory=dict)
    institutional: dict[str, pd.DataFrame] = field(default_factory=dict)
    margin: dict[str, pd.DataFrame] = field(default_factory=dict)
    shareholding: dict[str, pd.DataFrame] = field(default_factory=dict)
    as_of: pd.Timestamp | None = None

    def get(self, dataset: str, symbol: str) -> pd.DataFrame:
        """Get data for a specific dataset and symbol."""
        store = getattr(self, dataset, None)
        if store is None:
            return pd.DataFrame()
        return store.get(symbol, pd.DataFrame())


# Map public dataset names -> bundle attribute names and registry keys
_DATASET_MAP: dict[str, tuple[str, str]] = {
    # (bundle_attr, registry_key)
    "price": ("bars", "price"),
    "revenue": ("revenue", "revenue"),
    "per": ("per_history", "per"),
    "institutional": ("institutional", "institutional"),
    "margin": ("margin", "margin"),
    "shareholding": ("shareholding", "shareholding"),
}

_DEFAULT_DATASETS = list(_DATASET_MAP.keys())


def build_factor_data(
    symbols: list[str],
    as_of: pd.Timestamp | None = None,
    datasets: list[str] | None = None,
) -> FactorDataBundle:
    """Build factor data bundle with PIT enforcement from registry.

    Single source of truth — all callers (evaluate.py, strategy_builder,
    deployed_executor, validator) should use this instead of assembling
    data themselves.

    PIT delays are read from src.data.registry.REGISTRY (not hardcoded).
    """
    from src.data.data_catalog import get_catalog
    from src.data.registry import REGISTRY

    catalog = get_catalog()
    if datasets is None:
        datasets = _DEFAULT_DATASETS

    bundle = FactorDataBundle(as_of=as_of)

    for ds_name in datasets:
        mapping = _DATASET_MAP.get(ds_name)
        if mapping is None:
            logger.warning("Unknown dataset %r, skipping", ds_name)
            continue

        attr_name, registry_key = mapping
        store: dict[str, pd.DataFrame] = {}

        # Get PIT delay from registry (single source of truth)
        pit_delay = 0
        if registry_key in REGISTRY:
            pit_delay = REGISTRY[registry_key].pit_delay_days

        for sym in symbols:
            try:
                df = catalog.get(registry_key, sym)
                if df.empty:
                    continue

                # Ensure DatetimeIndex
                if not isinstance(df.index, pd.DatetimeIndex):
                    if "date" in df.columns:
                        df["date"] = pd.to_datetime(df["date"])
                        df = df.set_index("date")
                    df.index = pd.to_datetime(df.index)
                df = df.sort_index()

                # Apply PIT masking
                if as_of is not None and pit_delay > 0:
                    cutoff = as_of - pd.Timedelta(days=pit_delay)
                    df = df[df.index <= cutoff]
                elif as_of is not None:
                    df = df[df.index <= as_of]

                if not df.empty:
                    store[sym] = df
            except Exception:
                logger.debug("Failed to load %s for %s", ds_name, sym)

        setattr(bundle, attr_name, store)

    return bundle
