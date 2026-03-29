"""
投資組合優化器 — 將原始信號轉化為滿足約束的目標權重。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class OptConstraints:
    """投資組合約束。"""
    max_weight: float = 0.05            # 單一標的上限
    max_total_weight: float = 0.95      # 總投資比例上限 (留 5% 現金)
    min_weight: float = 0.001           # 低於此權重直接歸零
    long_only: bool = True              # 是否只做多


def equal_weight(
    signals: dict[str, float],
    constraints: OptConstraints | None = None,
) -> dict[str, float]:
    """
    等權重配置：所有正信號的標的等權分配。
    最簡單的配置方法，適合起步。
    """
    c = constraints or OptConstraints()

    # 篩選正信號
    if c.long_only:
        selected = {k: v for k, v in signals.items() if v > 0}
    else:
        selected = {k: v for k, v in signals.items() if abs(v) > 0}

    if not selected:
        return {}

    n = len(selected)
    w = min(c.max_weight, c.max_total_weight / n)

    return {symbol: w for symbol in selected}


def signal_weight(
    signals: dict[str, float],
    constraints: OptConstraints | None = None,
) -> dict[str, float]:
    """
    信號加權配置：按信號強度分配權重。
    """
    c = constraints or OptConstraints()

    if c.long_only:
        filtered = {k: v for k, v in signals.items() if v > 0}
    else:
        filtered = {k: v for k, v in signals.items() if abs(v) > 0}

    if not filtered:
        return {}

    # 正規化
    total_signal = sum(abs(v) for v in filtered.values())
    if total_signal == 0:
        return {}

    weights = {}
    for symbol, sig in filtered.items():
        raw_w = (sig / total_signal) * c.max_total_weight
        # 截斷到 max_weight
        w = max(-c.max_weight, min(c.max_weight, raw_w))
        if abs(w) >= c.min_weight:
            weights[symbol] = w

    # 空頭總曝險約束：short 不超過 max_total_weight
    if not c.long_only:
        total_short = sum(w for w in weights.values() if w < 0)
        if total_short < -c.max_total_weight:
            scale = -c.max_total_weight / total_short
            weights = {k: (v * scale if v < 0 else v) for k, v in weights.items()}

    return weights


def risk_parity(
    signals: dict[str, float],
    volatilities: dict[str, float],
    constraints: OptConstraints | None = None,
) -> dict[str, float]:
    """
    風險平價配置：按波動率的倒數分配權重。
    每個標的貢獻相等的風險。

    Args:
        signals: 信號（用於篩選方向）
        volatilities: 各標的年化波動率
    """
    c = constraints or OptConstraints()

    # 只選有正信號且有波動率的標的
    zero_vol_assets = [
        k for k in signals
        if signals[k] > 0 and k in volatilities and volatilities[k] == 0
    ]
    if zero_vol_assets:
        logger.warning(
            "risk_parity: assets with zero volatility excluded: %s", zero_vol_assets
        )

    selected = {
        k: volatilities[k]
        for k in signals
        if signals[k] > 0 and k in volatilities and volatilities[k] > 0
    }

    if not selected:
        return {}

    # 波動率倒數
    inv_vols = {k: 1.0 / v for k, v in selected.items()}
    total_inv = sum(inv_vols.values())

    weights = {}
    for symbol, inv_v in inv_vols.items():
        raw_w = (inv_v / total_inv) * c.max_total_weight
        w = min(c.max_weight, raw_w)
        if w >= c.min_weight:
            weights[symbol] = w

    return weights
