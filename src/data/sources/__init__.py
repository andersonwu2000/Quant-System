"""
數據源工廠 — 統一建立 DataFeed 與 FundamentalsProvider。

Market-agnostic: 未來可擴充 EODHD, Polygon, Tiingo 等。
"""

from __future__ import annotations

from src.data.feed import DataFeed
from src.data.fundamentals import FundamentalsProvider


def create_feed(source: str, universe: list[str], **kwargs: object) -> DataFeed:
    """Factory for creating data feeds.

    Args:
        source: Data source name ("yahoo", "finmind", etc.)
        universe: List of stock symbols
        **kwargs: Source-specific options (e.g., token for FinMind)

    Returns:
        DataFeed instance

    Raises:
        ValueError: If source is unknown
    """
    if source == "yahoo":
        from src.data.sources.yahoo import YahooFeed

        return YahooFeed(universe)
    elif source == "finmind":
        from src.data.sources.finmind import FinMindFeed

        token = str(kwargs.get("token", ""))
        return FinMindFeed(universe, token=token)
    elif source == "catalog":
        from src.data.sources.catalog_feed import CatalogFeed

        return CatalogFeed(universe)
    elif source == "shioaji":
        from src.data.sources.shioaji_feed import ShioajiFeed

        api = kwargs.get("api", None)
        return ShioajiFeed(api=api, universe=universe)
    else:
        raise ValueError(
            f"Unknown data source: {source}. Available: yahoo, finmind, catalog, shioaji"
        )


def create_fundamentals(source: str, **kwargs: object) -> FundamentalsProvider | None:
    """Factory for creating fundamentals providers.

    Returns None if the source has no fundamentals support.

    Args:
        source: Data source name
        **kwargs: Source-specific options (e.g., token for FinMind)

    Returns:
        FundamentalsProvider instance, or None
    """
    if source == "finmind":
        from src.data.sources.finmind_fundamentals import FinMindFundamentals

        token = str(kwargs.get("token", ""))
        return FinMindFundamentals(token=token)

    # Yahoo mode: try FinMind fundamentals if token is available
    if source == "yahoo":
        from src.core.config import get_config

        cfg = get_config()
        if cfg.finmind_token:
            from src.data.sources.finmind_fundamentals import FinMindFundamentals

            return FinMindFundamentals(token=cfg.finmind_token)

    return None
