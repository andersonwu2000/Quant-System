"""
跨資產信號 — 計算各資產類別的動量/carry/value/volatility 得分。

所有信號以 z-score 輸出（正值 = 看多）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.domain.models import AssetClass

logger = logging.getLogger(__name__)


@dataclass
class CrossAssetConfig:
    """跨資產信號配置。"""

    momentum_lookback: int = 252  # 動量回望期（交易日）
    momentum_skip: int = 21      # 跳過最近 N 日（反轉效應）
    vol_lookback: int = 60       # 波動率回望期
    value_lookback: int = 756    # 均值回歸回望期（~3 年）
    zscore_lookback: int = 252   # z-score 標準化回望期


class CrossAssetSignals:
    """跨資產信號計算器。

    輸入：各資產類別的代表性價格序列
    輸出：dict[AssetClass, float] — 各類別的合成得分
    """

    def __init__(self, config: CrossAssetConfig | None = None):
        self._config = config or CrossAssetConfig()

    def compute(
        self,
        price_by_class: dict[AssetClass, pd.Series],
    ) -> dict[AssetClass, float]:
        """計算各資產類別的跨資產合成信號。

        Args:
            price_by_class: 每個 AssetClass 的代表性價格序列
                            e.g. {EQUITY: SPY_close, ETF: TLT_close, FUTURE: GC_close}

        Returns:
            dict[AssetClass, float] — 合成 z-score 信號
        """
        result: dict[AssetClass, float] = {}

        for ac, prices in price_by_class.items():
            if prices.empty or len(prices) < 60:
                result[ac] = 0.0
                continue

            signals: list[float] = []

            mom = self._momentum(prices)
            if mom is not None:
                signals.append(mom)

            vol = self._volatility(prices)
            if vol is not None:
                signals.append(vol)

            val = self._value(prices)
            if val is not None:
                signals.append(val)

            result[ac] = float(np.mean(signals)) if signals else 0.0

        return result

    def compute_detail(
        self,
        price_by_class: dict[AssetClass, pd.Series],
    ) -> dict[AssetClass, dict[str, float]]:
        """計算各資產類別的個別信號（用於研究/歸因）。"""
        result: dict[AssetClass, dict[str, float]] = {}

        for ac, prices in price_by_class.items():
            detail: dict[str, float] = {}
            if prices.empty or len(prices) < 60:
                detail = {"momentum": 0.0, "volatility": 0.0, "value": 0.0}
            else:
                detail["momentum"] = self._momentum(prices) or 0.0
                detail["volatility"] = self._volatility(prices) or 0.0
                detail["value"] = self._value(prices) or 0.0
            result[ac] = detail

        return result

    # ── 個別信號 ─────────────────────────────────────────

    def _momentum(self, prices: pd.Series) -> float | None:
        """時間序列動量：過去 lookback 天報酬（跳過近期）。"""
        c = self._config
        need = c.momentum_lookback + c.momentum_skip
        if len(prices) < need:
            return None

        past = prices.iloc[-(c.momentum_lookback + c.momentum_skip)]
        recent = prices.iloc[-c.momentum_skip] if c.momentum_skip > 0 else prices.iloc[-1]

        if past <= 0:
            return None

        raw_ret = float(recent / past - 1)
        return self._zscore_scalar(raw_ret, prices, self._momentum_series)

    def _volatility(self, prices: pd.Series) -> float | None:
        """波動率信號：低波動 = 正向（防禦性因子）。"""
        c = self._config
        if len(prices) < c.vol_lookback + 1:
            return None

        ret = prices.pct_change().dropna()
        if len(ret) < c.vol_lookback:
            return None

        recent_vol = float(ret.iloc[-c.vol_lookback:].std() * np.sqrt(252))
        if recent_vol == 0:
            return None

        # 低波動 = 正向（取反）
        lookback = min(c.zscore_lookback, len(ret) - c.vol_lookback)
        if lookback < 20:
            return None

        vol_series = ret.rolling(c.vol_lookback).std() * np.sqrt(252)
        vol_series = vol_series.dropna()
        if len(vol_series) < 20:
            return None

        std = vol_series.iloc[-c.zscore_lookback:].std()
        if std == 0 or np.isnan(std):
            return None

        mean = vol_series.iloc[-c.zscore_lookback:].mean()
        z = -(recent_vol - mean) / std  # 負號：低波動 = 正
        return float(np.clip(z, -3.0, 3.0))

    def _value(self, prices: pd.Series) -> float | None:
        """均值回歸信號：偏離長期均線 → 反向信號。"""
        c = self._config
        if len(prices) < c.value_lookback:
            return None

        current = float(prices.iloc[-1])
        long_ma = float(prices.iloc[-c.value_lookback:].mean())

        if long_ma <= 0:
            return None

        deviation = current / long_ma - 1

        # 偏高 = 預期回歸（做空信號），偏低 = 做多
        lookback = min(c.zscore_lookback, len(prices) - c.value_lookback)
        if lookback < 20:
            return None

        # 用 rolling deviation 做 z-score
        rolling_ma = prices.rolling(c.value_lookback).mean()
        dev_series = (prices / rolling_ma - 1).dropna()
        if len(dev_series) < 20:
            return None

        std = dev_series.iloc[-c.zscore_lookback:].std()
        if std == 0 or np.isnan(std):
            return None

        mean = dev_series.iloc[-c.zscore_lookback:].mean()
        z = -(deviation - mean) / std  # 負號：偏高 = 做空
        return float(np.clip(z, -3.0, 3.0))

    # ── 工具 ─────────────────────────────────────────────

    @staticmethod
    def _momentum_series(prices: pd.Series, lookback: int, skip: int) -> pd.Series:
        """計算完整的動量時序。"""
        shifted_past = prices.shift(lookback + skip)
        shifted_recent = prices.shift(skip)
        return (shifted_recent / shifted_past - 1).dropna()

    def _zscore_scalar(
        self,
        value: float,
        prices: pd.Series,
        series_fn: object,
    ) -> float:
        """用歷史分布對單一值做 z-score。"""
        c = self._config
        mom_ts = self._momentum_series(prices, c.momentum_lookback, c.momentum_skip)
        if len(mom_ts) < 20:
            # fallback: 直接回傳 clipped 原始值
            return float(np.clip(value * 5, -3.0, 3.0))

        window = mom_ts.iloc[-c.zscore_lookback:]
        std = window.std()
        if std == 0 or np.isnan(std):
            return 0.0
        z = (value - window.mean()) / std
        return float(np.clip(z, -3.0, 3.0))
