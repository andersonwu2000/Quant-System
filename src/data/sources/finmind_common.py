"""Shared utilities for FinMind data sources."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def strip_tw_suffix(symbol: str) -> str:
    """Strip .TW or .TWO suffix for FinMind API calls."""
    for suffix in (".TWO", ".TW"):
        if symbol.upper().endswith(suffix):
            return symbol[: -len(suffix)]
    return symbol


def ensure_tw_suffix(symbol: str) -> str:
    """Ensure symbol has .TW suffix for internal use (if it's a bare number)."""
    if symbol.endswith(".TW") or symbol.endswith(".TWO"):
        return symbol
    if symbol.isdigit():
        return f"{symbol}.TW"
    return symbol


_dataloader_cache: dict[str, Any] = {}


def get_dataloader(token: str = "") -> Any:
    """Get or create a cached FinMind DataLoader instance.

    Reuses the same DataLoader for the same token to avoid
    repeated authentication and object creation overhead.
    """
    cache_key = token or "__no_token__"
    if cache_key in _dataloader_cache:
        return _dataloader_cache[cache_key]

    from FinMind.data import DataLoader

    dl = DataLoader()
    if token:
        dl.login_by_token(api_token=token)

    _dataloader_cache[cache_key] = dl
    return dl
