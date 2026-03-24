"""
股票池篩選框架 — 定義可投資標的，排除不可交易或不適合量化策略的股票。

篩選條件：流動性、上市天數、數據完整性、產業、市值。
每個篩選在每個日期的橫截面上獨立執行，保證時間因果性。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.data.fundamentals import FundamentalsProvider


@dataclass
class UniverseConfig:
    """股票池篩選配置。"""

    min_avg_volume: float | None = None  # 最低日均成交量（股）
    min_avg_turnover: float | None = None  # 最低日均成交額（元）
    min_market_cap: float | None = None  # 最低市值（元）
    min_listing_days: int = 252  # 最少上市天數
    exclude_sectors: list[str] = field(default_factory=list)  # 排除的產業
    volume_lookback: int = 60  # 流動性計算回望天數
    max_missing_pct: float = 0.1  # 最大允許缺值比例


class UniverseFilter:
    """股票池篩選器。"""

    def __init__(self, config: UniverseConfig | None = None):
        self.config = config or UniverseConfig()

    def filter(
        self,
        data: dict[str, pd.DataFrame],
        date: pd.Timestamp,
        fundamentals: FundamentalsProvider | None = None,
    ) -> list[str]:
        """回傳在指定日期通過所有篩選條件的標的列表。"""
        passed: list[str] = []
        c = self.config

        for symbol, df in data.items():
            if not self._check_symbol(symbol, df, date, c, fundamentals):
                continue
            passed.append(symbol)

        return sorted(passed)

    def filter_timeseries(
        self,
        data: dict[str, pd.DataFrame],
        dates: list[pd.Timestamp],
        fundamentals: FundamentalsProvider | None = None,
    ) -> dict[pd.Timestamp, list[str]]:
        """回傳每個日期的可投資標的，用於回測。"""
        result: dict[pd.Timestamp, list[str]] = {}
        for dt in dates:
            result[dt] = self.filter(data, dt, fundamentals)
        return result

    def _check_symbol(
        self,
        symbol: str,
        df: pd.DataFrame,
        date: pd.Timestamp,
        c: UniverseConfig,
        fundamentals: FundamentalsProvider | None,
    ) -> bool:
        """檢查單一標的是否通過所有篩選。"""
        # 截斷到當前日期（時間因果性）
        visible = df.loc[df.index <= date]
        if visible.empty:
            return False

        # 上市天數篩選
        if len(visible) < c.min_listing_days:
            return False

        # 取回望窗口
        window = visible.iloc[-c.volume_lookback :]

        # 數據完整性篩選
        if len(window) > 0:
            missing_pct = window["close"].isna().sum() / len(window)
            if missing_pct > c.max_missing_pct:
                return False

        # 流動性篩選：日均成交量
        if c.min_avg_volume is not None and len(window) > 0:
            avg_vol = float(window["volume"].mean())
            if np.isnan(avg_vol) or avg_vol < c.min_avg_volume:
                return False

        # 流動性篩選：日均成交額
        if c.min_avg_turnover is not None and len(window) > 0:
            turnover = (window["close"] * window["volume"]).mean()
            if np.isnan(turnover) or turnover < c.min_avg_turnover:
                return False

        # 產業篩選
        if c.exclude_sectors and fundamentals is not None:
            sector = fundamentals.get_sector(symbol)
            if sector in c.exclude_sectors:
                return False

        # 市值篩選
        if c.min_market_cap is not None and fundamentals is not None:
            date_str = date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date)
            financials = fundamentals.get_financials(symbol, date_str)
            market_cap = financials.get("market_cap", 0.0)
            if market_cap < c.min_market_cap:
                return False

        return True
