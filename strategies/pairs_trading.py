"""
配對交易策略 — 利用共整合關係的均值回歸特性。

支援兩種模式：
1. 共整合模式（預設）：Engle-Granger 兩步法，OLS hedge ratio 計算 spread
2. 相關性模式（後備）：簡單價格比率 Z-score
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import numpy.typing as npt

from src.strategy.base import Context, Strategy
from src.strategy.optimizer import equal_weight, OptConstraints

# 嘗試載入 statsmodels，不可用時 fallback 到相關性模式
try:
    from statsmodels.tsa.stattools import adfuller
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False


def _ols_hedge_ratio(
    prices_a: npt.NDArray[np.float64],
    prices_b: npt.NDArray[np.float64],
) -> float:
    """OLS 回歸計算 hedge ratio: prices_a = beta * prices_b + alpha."""
    x = prices_b
    x_mean = np.mean(x)
    y = prices_a
    y_mean = np.mean(y)
    beta = float(np.sum((x - x_mean) * (y - y_mean)) / np.sum((x - x_mean) ** 2))
    return beta


def _test_cointegration(
    series_a: npt.NDArray[np.float64],
    series_b: npt.NDArray[np.float64],
) -> tuple[bool, float]:
    """Engle-Granger 兩步法共整合檢驗。

    1. OLS 回歸: series_a = beta * series_b + alpha
    2. ADF 檢驗殘差序列

    Returns:
        (is_cointegrated, p_value)
    """
    if not HAS_STATSMODELS:
        return False, 1.0

    # Step 1: OLS regression
    beta = _ols_hedge_ratio(series_a, series_b)
    alpha = np.mean(series_a) - beta * np.mean(series_b)
    residuals = series_a - beta * series_b - alpha

    # Step 2: ADF test on residuals
    try:
        adf_result = adfuller(residuals, maxlag=None, autolag="AIC")
        p_value = float(adf_result[1])
        is_cointegrated = p_value < 0.05
        return is_cointegrated, p_value
    except Exception:
        return False, 1.0


class PairsTradingStrategy(Strategy):
    """
    配對交易策略：
    - 優先使用共整合檢驗選取配對（Engle-Granger 兩步法）
    - 共整合配對使用 OLS hedge ratio 計算 spread 的 Z-score
    - 非共整合配對退回簡單價格比率 Z-score（需相關性夠高）
    - 當 Z-score > 閾值時，買入相對弱勢的那一方
    - 因為 long_only 限制，只做買入被低估的標的
    - 使用等權重配置
    """

    def __init__(
        self,
        lookback: int = 60,
        z_threshold: float = 1.5,
        coint_pvalue: float = 0.05,
        corr_fallback_threshold: float = 0.7,
    ):
        self.lookback = lookback
        self.z_threshold = z_threshold
        self.coint_pvalue = coint_pvalue
        self.corr_fallback_threshold = corr_fallback_threshold

    def name(self) -> str:
        return "pairs_trading"

    def _test_cointegration(
        self,
        series_a: npt.NDArray[np.float64],
        series_b: npt.NDArray[np.float64],
    ) -> tuple[bool, float]:
        """共整合檢驗（實例方法，方便測試）。"""
        return _test_cointegration(series_a, series_b)

    def on_bar(self, ctx: Context) -> dict[str, float]:
        universe = ctx.universe()
        if len(universe) < 2:
            return {}

        # 收集所有標的的收盤價序列
        price_data: dict[str, npt.NDArray[np.float64]] = {}
        for symbol in universe:
            bars = ctx.bars(symbol, lookback=self.lookback + 10)
            if len(bars) < self.lookback:
                continue
            price_data[symbol] = np.asarray(bars["close"].values[-self.lookback:], dtype=np.float64)

        if len(price_data) < 2:
            return {}

        # 對每一對股票進行配對分析
        signals: dict[str, float] = {}
        symbols = list(price_data.keys())

        for sym_a, sym_b in combinations(symbols, 2):
            prices_a = price_data[sym_a]
            prices_b = price_data[sym_b]

            # 避免除以零
            if np.any(prices_b == 0) or np.any(prices_a == 0):
                continue

            # 嘗試共整合檢驗
            is_coint, p_value = self._test_cointegration(prices_a, prices_b)

            if is_coint:
                # 共整合模式：使用 OLS hedge ratio 計算 spread
                beta = _ols_hedge_ratio(prices_a, prices_b)
                spread = prices_a - beta * prices_b
                spread_mean = np.mean(spread)
                spread_std = np.std(spread)

                if spread_std == 0:
                    continue

                z = (spread[-1] - spread_mean) / spread_std

                # Z > threshold: spread 偏高 → A 相對偏貴，買入 B
                if z > self.z_threshold:
                    signals[sym_b] = signals.get(sym_b, 0.0) + abs(z)
                # Z < -threshold: spread 偏低 → B 相對偏貴，買入 A
                elif z < -self.z_threshold:
                    signals[sym_a] = signals.get(sym_a, 0.0) + abs(z)
            else:
                # 後備模式：簡單價格比率（僅當相關性夠高時）
                corr = float(np.corrcoef(prices_a, prices_b)[0, 1])
                if abs(corr) < self.corr_fallback_threshold:
                    continue

                ratio = prices_a / prices_b
                ratio_mean = np.mean(ratio)
                ratio_std = np.std(ratio)

                if ratio_std == 0:
                    continue

                z = (ratio[-1] - ratio_mean) / ratio_std

                # Z > threshold: A 相對 B 偏高，買入 B（被低估方）
                if z > self.z_threshold:
                    signals[sym_b] = signals.get(sym_b, 0.0) + abs(z)
                # Z < -threshold: B 相對 A 偏高，買入 A（被低估方）
                elif z < -self.z_threshold:
                    signals[sym_a] = signals.get(sym_a, 0.0) + abs(z)

        return equal_weight(
            signals,
            OptConstraints(max_weight=0.15, max_total_weight=0.90),
        )
