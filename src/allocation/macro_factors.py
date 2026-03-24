"""
宏觀因子模型 — 從 FRED 數據計算四大宏觀信號。

四因子：
- 成長 (growth): GDP proxy (製造業就業 + 失業率反向)
- 通膨 (inflation): CPI 同比變化率
- 利率 (rates): 10-2 年利差 + 聯邦基金利率水位
- 信用 (credit): BAA 信用利差（反向，利差收窄 = 正向信號）

輸出為標準化 z-score，正值 = 有利環境。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.data.sources.fred import FredDataSource

logger = logging.getLogger(__name__)

# 各因子使用的 FRED series keys
_GROWTH_KEYS = ["unemployment", "pmi"]
_INFLATION_KEYS = ["cpi"]
_RATES_KEYS = ["yield_spread_10y2y", "fed_funds"]
_CREDIT_KEYS = ["credit_spread"]

# 前向填補上限（交易日）
_DEFAULT_FFILL_LIMIT = 66


@dataclass
class MacroSignals:
    """宏觀因子信號快照。"""

    growth: float = 0.0
    inflation: float = 0.0
    rates: float = 0.0
    credit: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "growth": self.growth,
            "inflation": self.inflation,
            "rates": self.rates,
            "credit": self.credit,
        }

    def __repr__(self) -> str:
        return (
            f"MacroSignals(growth={self.growth:+.2f}, inflation={self.inflation:+.2f}, "
            f"rates={self.rates:+.2f}, credit={self.credit:+.2f})"
        )


@dataclass
class MacroFactorConfig:
    """宏觀因子配置。"""

    ffill_limit: int = _DEFAULT_FFILL_LIMIT
    zscore_lookback: int = 252  # z-score 回望期（交易日）
    start: str | None = None
    end: str | None = None


class MacroFactorModel:
    """宏觀因子計算引擎。

    使用 FRED 數據計算四大宏觀信號的 z-score 時序。
    """

    def __init__(
        self,
        fred: FredDataSource | None = None,
        config: MacroFactorConfig | None = None,
    ):
        self._fred = fred or FredDataSource()
        self._config = config or MacroFactorConfig()
        self._panel: pd.DataFrame | None = None

    def load_data(
        self,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        """下載 FRED 宏觀面板資料。"""
        s = start or self._config.start
        e = end or self._config.end
        all_keys = list({
            *_GROWTH_KEYS, *_INFLATION_KEYS, *_RATES_KEYS, *_CREDIT_KEYS,
        })
        panel = self._fred.get_macro_panel(s, e, series_keys=all_keys)
        if panel.empty:
            logger.warning("FRED macro panel is empty")
            return panel
        # 前向填補上限
        panel = panel.ffill(limit=self._config.ffill_limit)
        self._panel = panel
        logger.info("Loaded macro panel: %d rows × %d cols", len(panel), len(panel.columns))
        return panel

    def compute_signals(
        self,
        as_of: pd.Timestamp | str | None = None,
    ) -> MacroSignals:
        """計算截至指定日期的宏觀信號。

        Args:
            as_of: 計算日期。None = 最新可用日期。

        Returns:
            MacroSignals（各因子的 z-score）
        """
        if self._panel is None or self._panel.empty:
            self.load_data()
        if self._panel is None or self._panel.empty:
            return MacroSignals()

        panel = self._panel
        if as_of is not None:
            ts = pd.Timestamp(as_of)
            panel = panel.loc[:ts]

        if len(panel) < 20:
            return MacroSignals()

        growth = self._compute_growth(panel)
        inflation = self._compute_inflation(panel)
        rates = self._compute_rates(panel)
        credit = self._compute_credit(panel)

        return MacroSignals(
            growth=growth,
            inflation=inflation,
            rates=rates,
            credit=credit,
        )

    def compute_signal_series(self) -> pd.DataFrame:
        """計算整條時序的宏觀信號（用於回測）。

        Returns:
            DataFrame, index=date, columns=["growth", "inflation", "rates", "credit"]
        """
        if self._panel is None or self._panel.empty:
            self.load_data()
        if self._panel is None or self._panel.empty:
            return pd.DataFrame(columns=["growth", "inflation", "rates", "credit"])

        panel = self._panel
        lookback = self._config.zscore_lookback
        result: dict[str, list[float]] = {
            "growth": [], "inflation": [], "rates": [], "credit": [],
        }
        dates: list[pd.Timestamp] = []

        for i in range(lookback, len(panel)):
            window = panel.iloc[:i + 1]
            signals = MacroSignals(
                growth=self._compute_growth(window),
                inflation=self._compute_inflation(window),
                rates=self._compute_rates(window),
                credit=self._compute_credit(window),
            )
            for k, v in signals.to_dict().items():
                result[k].append(v)
            dates.append(panel.index[i])

        return pd.DataFrame(result, index=dates)

    # ── 個別因子計算 ─────────────────────────────────────

    def _compute_growth(self, panel: pd.DataFrame) -> float:
        """成長因子：失業率下降 + 製造業就業上升 = 正向。"""
        signals: list[float] = []

        if "unemployment" in panel.columns:
            unemp = panel["unemployment"].dropna()
            if len(unemp) >= 3:
                # 失業率下降 = 正向（取反）
                signals.append(-self._zscore_latest(unemp))

        if "pmi" in panel.columns:
            pmi = panel["pmi"].dropna()
            if len(pmi) >= 3:
                # 製造業就業上升 = 正向
                signals.append(self._zscore_change(pmi))

        return float(np.mean(signals)) if signals else 0.0

    def _compute_inflation(self, panel: pd.DataFrame) -> float:
        """通膨因子：CPI 同比變化率的 z-score。"""
        if "cpi" not in panel.columns:
            return 0.0
        cpi = panel["cpi"].dropna()
        if len(cpi) < 13:
            return 0.0
        # 12 個月同比變化率
        yoy = cpi.pct_change(12).dropna()
        if len(yoy) < 2:
            return 0.0
        return self._zscore_latest(yoy)

    def _compute_rates(self, panel: pd.DataFrame) -> float:
        """利率因子：利差擴大 = 正向（經濟擴張信號）。"""
        signals: list[float] = []

        if "yield_spread_10y2y" in panel.columns:
            spread = panel["yield_spread_10y2y"].dropna()
            if len(spread) >= 20:
                signals.append(self._zscore_latest(spread))

        if "fed_funds" in panel.columns:
            ff = panel["fed_funds"].dropna()
            if len(ff) >= 20:
                # 利率下降 = 正向（取反向變化）
                signals.append(-self._zscore_change(ff))

        return float(np.mean(signals)) if signals else 0.0

    def _compute_credit(self, panel: pd.DataFrame) -> float:
        """信用因子：信用利差收窄 = 正向（取反）。"""
        if "credit_spread" not in panel.columns:
            return 0.0
        cs = panel["credit_spread"].dropna()
        if len(cs) < 20:
            return 0.0
        return -self._zscore_latest(cs)

    # ── z-score 工具 ─────────────────────────────────────

    def _zscore_latest(self, series: pd.Series) -> float:
        """取最新值的 rolling z-score。"""
        lookback = min(self._config.zscore_lookback, len(series))
        window = series.iloc[-lookback:]
        std = window.std()
        if std == 0 or np.isnan(std):
            return 0.0
        z = (window.iloc[-1] - window.mean()) / std
        return float(np.clip(z, -3.0, 3.0))

    def _zscore_change(self, series: pd.Series) -> float:
        """取近期變化量的 z-score。"""
        lookback = min(self._config.zscore_lookback, len(series))
        window = series.iloc[-lookback:]
        diff = window.diff().dropna()
        if len(diff) < 2:
            return 0.0
        std = diff.std()
        if std == 0 or np.isnan(std):
            return 0.0
        z = diff.iloc[-1] / std
        return float(np.clip(z, -3.0, 3.0))
