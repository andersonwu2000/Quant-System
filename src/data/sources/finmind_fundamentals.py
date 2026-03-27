"""
FinMind 台股基本面數據。

支援財務報表、本益比/淨值比、產業分類、月營收、股利、法人買賣超。
快取 TTL 7 天（基本面數據更新頻率低）。
FinMind import 使用 lazy loading。
優先讀取 data/fundamental/ 本地 parquet，沒有才呼叫 API。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import pandas as pd

from src.data.fundamentals import FundamentalsProvider
from src.data.sources.finmind_common import get_dataloader, strip_tw_suffix, ensure_tw_suffix

logger = logging.getLogger(__name__)

# 基本面快取 TTL: 7 天
_FUNDAMENTALS_CACHE_TTL = 7 * 24 * 3600


class FinMindFundamentals(FundamentalsProvider):
    """FinMind 台股基本面數據。"""

    def __init__(self, token: str = ""):
        self._token = token
        self._cache: dict[str, tuple[float, object]] = {}  # key -> (timestamp, data)

    def _get_dataloader(self) -> Any:
        """Get cached FinMind DataLoader instance."""
        return get_dataloader(self._token)

    def _get_cached(self, key: str) -> object | None:
        """Get cached value if not expired."""
        if key in self._cache:
            ts, data = self._cache[key]
            if time.time() - ts < _FUNDAMENTALS_CACHE_TTL:
                return data
        return None

    def _set_cached(self, key: str, data: object) -> None:
        """Set cached value with current timestamp."""
        self._cache[key] = (time.time(), data)

    @staticmethod
    def _read_local_parquet(symbol: str, suffix: str) -> pd.DataFrame | None:
        """Try to read from data/fundamental/{symbol}_{suffix}.parquet."""
        tw_sym = ensure_tw_suffix(symbol)
        path = Path("data/fundamental") / f"{tw_sym}_{suffix}.parquet"
        if path.exists():
            try:
                df = pd.read_parquet(path)
                if not df.empty:
                    return df
            except Exception:
                pass
        return None

    def get_financials(self, symbol: str, date: str | None = None) -> dict[str, float]:
        """Get financial metrics from FinMind.

        Uses TaiwanStockFinancialStatement for EPS/ROE,
        TaiwanStockPER for PE ratio/PB ratio.
        """
        bare_id = strip_tw_suffix(symbol)
        cache_key = f"financials_{bare_id}_{date or 'latest'}"

        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        result: dict[str, float] = {}

        try:
            dl = self._get_dataloader()

            # PE ratio and PB ratio from TaiwanStockPER (daily data)
            per_kwargs: dict[str, str] = {"stock_id": bare_id}
            if date:
                # Get data up to the specified date
                per_kwargs["start_date"] = (
                    pd.Timestamp(date) - pd.DateOffset(days=30)
                ).strftime("%Y-%m-%d")
                per_kwargs["end_date"] = date
            else:
                # Get recent data
                per_kwargs["start_date"] = (
                    pd.Timestamp.now() - pd.DateOffset(days=30)
                ).strftime("%Y-%m-%d")

            per_df = dl.taiwan_stock_per_pbr(
                **per_kwargs,
            )

            if per_df is not None and not per_df.empty:
                latest_per = per_df.iloc[-1]
                if "PER" in per_df.columns:
                    val = latest_per["PER"]
                    if pd.notna(val) and val != 0:
                        result["pe_ratio"] = float(val)
                if "PBR" in per_df.columns:
                    val = latest_per["PBR"]
                    if pd.notna(val) and val != 0:
                        result["pb_ratio"] = float(val)

            # EPS and ROE from TaiwanStockFinancialStatement
            fin_kwargs: dict[str, str] = {"stock_id": bare_id}
            if date:
                fin_kwargs["start_date"] = (
                    pd.Timestamp(date) - pd.DateOffset(years=1)
                ).strftime("%Y-%m-%d")
                fin_kwargs["end_date"] = date
            else:
                fin_kwargs["start_date"] = (
                    pd.Timestamp.now() - pd.DateOffset(years=1)
                ).strftime("%Y-%m-%d")

            fin_df = dl.taiwan_stock_financial_statement(
                **fin_kwargs,
            )

            if fin_df is not None and not fin_df.empty:
                # Extract EPS (filter by type)
                eps_rows = fin_df[fin_df["type"] == "EPS"] if "type" in fin_df.columns else pd.DataFrame()
                if not eps_rows.empty:
                    val = eps_rows.iloc[-1].get("value")
                    if pd.notna(val):
                        result["eps"] = float(val)

                # Extract ROE
                roe_rows = fin_df[fin_df["type"] == "ROE"] if "type" in fin_df.columns else pd.DataFrame()
                if not roe_rows.empty:
                    val = roe_rows.iloc[-1].get("value")
                    if pd.notna(val):
                        result["roe"] = float(val)

        except Exception as e:
            logger.warning("Failed to get financials for %s: %s", symbol, e)

        self._set_cached(cache_key, result)
        return result

    def get_sector(self, symbol: str) -> str:
        """Get sector/industry classification from TaiwanStockInfo."""
        bare_id = strip_tw_suffix(symbol)
        cache_key = f"sector_{bare_id}"

        cached = self._get_cached(cache_key)
        if cached is not None:
            return str(cached)

        # Download full stock info table once and cache all sectors
        try:
            self._populate_sector_cache()
        except Exception as e:
            logger.warning("Failed to get sector for %s: %s", symbol, e)

        # Check cache again after population
        cached = self._get_cached(cache_key)
        if cached is not None:
            return str(cached)

        self._set_cached(cache_key, "")
        return ""

    def _populate_sector_cache(self) -> None:
        """Download full TaiwanStockInfo table and cache all sectors at once."""
        if self._get_cached("_sector_table_loaded") is not None:
            return

        dl = self._get_dataloader()
        info_df = dl.taiwan_stock_info()

        if info_df is not None and not info_df.empty and "industry_category" in info_df.columns:
            for _, row in info_df.iterrows():
                stock_id = row.get("stock_id", "")
                sector = str(row.get("industry_category", ""))
                if stock_id:
                    self._set_cached(f"sector_{stock_id}", sector)

        self._set_cached("_sector_table_loaded", True)

    def get_revenue(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Get monthly revenue from local parquet or TaiwanStockMonthRevenue API."""
        bare_id = strip_tw_suffix(symbol)
        full_cache_key = f"revenue_full_{bare_id}"

        empty = pd.DataFrame(columns=["date", "revenue", "yoy_growth"])

        cached_full = self._get_cached(full_cache_key)
        if cached_full is not None:
            full_result: pd.DataFrame = cached_full  # type: ignore[assignment]
            # Filter and return
            if full_result.empty:
                return empty
            filtered: pd.DataFrame = full_result[
                (full_result["date"] >= pd.Timestamp(start))
                & (full_result["date"] <= pd.Timestamp(end))
            ].reset_index(drop=True)
            return filtered

        # Local parquet only — no API calls during backtest
        local_df = self._read_local_parquet(bare_id, "revenue")
        if local_df is None:
            self._set_cached(full_cache_key, empty)
            return empty
        rev_df = local_df

        # Build result
        rev_df = rev_df.sort_values("date").reset_index(drop=True)

        result_rows = []
        for _, row in rev_df.iterrows():
            revenue = row.get("revenue", 0)
            date_val = row["date"]

            # Calculate YoY growth
            yoy_growth = 0.0
            if "revenue_year_ago" in rev_df.columns:
                year_ago = row.get("revenue_year_ago", 0)
                if pd.notna(year_ago) and year_ago > 0:
                    yoy_growth = (revenue / year_ago - 1) * 100
            elif "revenue" in rev_df.columns:
                # Manual YoY: find same month previous year
                current_date = pd.Timestamp(date_val)
                prev_year_date = current_date - pd.DateOffset(years=1)
                prev_rows = rev_df[
                    pd.to_datetime(rev_df["date"]).dt.to_period("M")
                    == prev_year_date.to_period("M")
                ]
                if not prev_rows.empty:
                    prev_rev = prev_rows.iloc[0].get("revenue", 0)
                    if pd.notna(prev_rev) and prev_rev > 0:
                        yoy_growth = (revenue / prev_rev - 1) * 100

            result_rows.append(
                {"date": date_val, "revenue": revenue, "yoy_growth": yoy_growth}
            )

        full_result = pd.DataFrame(result_rows)
        if not full_result.empty:
            full_result["date"] = pd.to_datetime(full_result["date"])

        self._set_cached(full_cache_key, full_result)

        # Filter to requested range
        if full_result.empty:
            return empty
        filtered = full_result[
            (full_result["date"] >= pd.Timestamp(start))
            & (full_result["date"] <= pd.Timestamp(end))
        ].reset_index(drop=True)
        return filtered

    def get_dividends(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Get dividend history from TaiwanStockDividend."""
        bare_id = strip_tw_suffix(symbol)
        cache_key = f"dividends_{bare_id}_{start}_{end}"

        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        empty = pd.DataFrame(columns=["date", "amount"])

        try:
            dl = self._get_dataloader()
            div_df = dl.taiwan_stock_dividend(
                stock_id=bare_id,
                start_date=start,
                end_date=end,
            )

            if div_df is None or div_df.empty:
                self._set_cached(cache_key, empty)
                return empty

            # Build result with date and total dividend amount
            result_rows = []
            for _, row in div_df.iterrows():
                date_val = row.get("date", row.get("CashExDividendTradingDate", ""))
                # Sum cash and stock dividends
                cash_div = float(row.get("CashEarningsDistribution", 0) or 0)
                stock_div = float(row.get("StockEarningsDistribution", 0) or 0)
                total = cash_div + stock_div
                if total > 0 and date_val:
                    result_rows.append({"date": date_val, "amount": total})

            result = pd.DataFrame(result_rows) if result_rows else empty

            if not result.empty:
                result["date"] = pd.to_datetime(result["date"])
                result = result.sort_values("date").reset_index(drop=True)

            self._set_cached(cache_key, result)
            return result

        except Exception as e:
            logger.warning("Failed to get dividends for %s: %s", symbol, e)
            self._set_cached(cache_key, empty)
            return empty

    def get_institutional(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Get institutional investor data from local parquet or API."""
        bare_id = strip_tw_suffix(symbol)

        # Use symbol-only cache key for local parquet (avoid re-parsing per date range)
        full_cache_key = f"institutional_full_{bare_id}"
        cached_full = self._get_cached(full_cache_key)

        empty = pd.DataFrame(columns=["date", "trust_net", "foreign_net", "dealer_net"])

        if cached_full is not None:
            full_result: pd.DataFrame = cached_full  # type: ignore[assignment]
        else:
            # Local parquet only — no API calls during backtest
            local_df = self._read_local_parquet(bare_id, "institutional")
            if local_df is None:
                self._set_cached(full_cache_key, empty)
                return empty
            df = local_df

            # Calculate net = buy - sell for each row
            df["net"] = df["buy"].astype(float) - df["sell"].astype(float)

            # Institution name mappings
            trust_names = ["Investment_Trust"]
            foreign_names = ["Foreign_Investor", "Foreign_Dealer_Self"]
            dealer_names = ["Dealer_self", "Dealer_Hedging"]

            result_rows = []
            for date_val, group in df.groupby("date"):
                trust_net = group[group["name"].isin(trust_names)]["net"].sum()
                foreign_net = group[group["name"].isin(foreign_names)]["net"].sum()
                dealer_net = group[group["name"].isin(dealer_names)]["net"].sum()
                result_rows.append({
                    "date": date_val,
                    "trust_net": float(trust_net),
                    "foreign_net": float(foreign_net),
                    "dealer_net": float(dealer_net),
                })

            full_result = pd.DataFrame(result_rows)
            if not full_result.empty:
                full_result["date"] = pd.to_datetime(full_result["date"])
                full_result = full_result.sort_values("date").reset_index(drop=True)

            self._set_cached(full_cache_key, full_result)

        # Filter to requested range
        if full_result.empty:
            return empty
        filtered: pd.DataFrame = full_result[
            (full_result["date"] >= pd.Timestamp(start))
            & (full_result["date"] <= pd.Timestamp(end))
        ].reset_index(drop=True)
        return filtered
