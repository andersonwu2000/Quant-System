"""
基本面數據統一介面 — Market-agnostic ABC.

任何市場的基本面數據源（FinMind for 台股, EODHD for US, etc.）都實作此介面。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class FundamentalsProvider(ABC):
    """基本面數據的統一介面。Market-agnostic."""

    @abstractmethod
    def get_financials(self, symbol: str, date: str | None = None) -> dict[str, float]:
        """Get financial metrics.

        Returns:
            Dict with keys like: pe_ratio, pb_ratio, roe, eps, revenue_growth, ...
            If date is provided, return point-in-time data as of that date.
            Returns empty dict if data unavailable.
        """

    @abstractmethod
    def get_sector(self, symbol: str) -> str:
        """Get sector/industry classification.

        Returns:
            Sector string, or empty string if unavailable.
        """

    @abstractmethod
    def get_revenue(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Get revenue history.

        Returns:
            DataFrame with columns: [date, revenue, yoy_growth]
            Empty DataFrame if unavailable.
        """

    @abstractmethod
    def get_dividends(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Get dividend history.

        Returns:
            DataFrame with columns: [date, amount]
            Empty DataFrame if unavailable.
        """
