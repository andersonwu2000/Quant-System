"""
成本感知組合建構 — 在 Alpha 信號和交易成本之間取得平衡。

與 src/strategy/optimizer.py 的差異：
- optimizer.py 只看信號強度，不考慮換倉成本
- construction.py 加入換手率懲罰、持倉穩定性約束、Alpha 衰減調適

兩者產出相同格式 (dict[str, float])，對下游完全相容。
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class ConstructionConfig:
    """組合建構配置。"""

    max_weight: float = 0.05  # 單一標的上限
    max_total_weight: float = 0.95  # 總投資比例上限 (留 5% 現金)
    min_weight: float = 0.001  # 低於此歸零
    long_only: bool = True
    turnover_penalty: float = 0.0005  # 換手率懲罰係數
    max_turnover: float | None = None  # 單期最大換手率上限
    cost_bps: float = 30.0  # 單邊成本 (bps)
    half_life: int | None = None  # Alpha 衰減半衰期（天）


def construct_portfolio(
    alpha_signal: pd.Series,
    current_weights: pd.Series | None = None,
    config: ConstructionConfig | None = None,
    volatilities: dict[str, float] | None = None,
) -> dict[str, float]:
    """
    成本感知的組合建構。

    最佳化目標：max(alpha_exposure - turnover_penalty × turnover)
    約束：權重上限、投資比例、換手率上限

    Args:
        alpha_signal: 當期 Alpha 信號 (symbol → score)
        current_weights: 當前持倉權重 (None = 空倉)
        config: 建構配置
        volatilities: 各標的年化波動率 (用於風險預算，可選)

    Returns:
        目標權重 dict
    """
    c = config or ConstructionConfig()

    if alpha_signal.empty:
        return {}

    # 篩選方向
    if c.long_only:
        signal = alpha_signal[alpha_signal > 0].copy()
    else:
        signal = alpha_signal[alpha_signal.abs() > 0].copy()

    if signal.empty:
        return {}

    # 計算原始目標權重（信號加權）
    raw_weights = _signal_to_weights(signal, c, volatilities)

    # 如果有當前持倉，進行成本感知調整
    if current_weights is not None and not current_weights.empty and c.turnover_penalty > 0:
        raw_weights = _apply_turnover_penalty(raw_weights, current_weights, c)

    # 強制換手率上限
    if c.max_turnover is not None and current_weights is not None and not current_weights.empty:
        raw_weights = _enforce_max_turnover(raw_weights, current_weights, c.max_turnover)

    # 最終清理
    result = {}
    for sym, w in raw_weights.items():
        if abs(w) >= c.min_weight:
            result[sym] = w

    return result


def blend_with_decay(
    new_signal: pd.Series,
    old_signal: pd.Series,
    half_life: int,
) -> pd.Series:
    """
    以指數衰減混合新舊信號，減少不必要的換倉。

    blended = decay_weight * old + (1 - decay_weight) * new
    decay_weight = 0.5^(1/half_life)  # 半衰期
    """
    decay_weight = 0.5 ** (1.0 / max(half_life, 1))

    all_symbols = sorted(set(new_signal.index) | set(old_signal.index))
    new_aligned = new_signal.reindex(all_symbols, fill_value=0.0)
    old_aligned = old_signal.reindex(all_symbols, fill_value=0.0)

    blended: pd.Series = decay_weight * old_aligned + (1 - decay_weight) * new_aligned
    return blended


# ── 內部實作 ─────────────────────────────────────────────────


def _signal_to_weights(
    signal: pd.Series,
    config: ConstructionConfig,
    volatilities: dict[str, float] | None = None,
) -> dict[str, float]:
    """將信號轉為滿足約束的目標權重。"""
    c = config

    if volatilities:
        # 風險預算：信號 × 波動率倒數
        inv_vol = {s: 1.0 / volatilities[s] for s in signal.index if s in volatilities and volatilities[s] > 0}
        if inv_vol:
            adjusted = pd.Series({s: signal[s] * inv_vol.get(s, 1.0) for s in signal.index})
        else:
            adjusted = signal
    else:
        adjusted = signal

    # 正規化為權重
    total = adjusted.abs().sum()
    if total == 0:
        return {}

    weights = {}
    for sym in adjusted.index:
        raw_w = (adjusted[sym] / total) * c.max_total_weight
        w = max(-c.max_weight, min(c.max_weight, raw_w))
        weights[sym] = w

    return weights


def _apply_turnover_penalty(
    target_weights: dict[str, float],
    current_weights: pd.Series,
    config: ConstructionConfig,
) -> dict[str, float]:
    """
    應用換手率懲罰：將目標權重向當前持倉方向拉近。

    對每個標的：
      adjusted_w = target_w - penalty * sign(target_w - current_w)
    這模擬了交易成本對最佳化目標的影響。
    """
    c = config
    result = {}
    all_symbols = set(target_weights.keys()) | set(current_weights.index)

    for sym in all_symbols:
        target = target_weights.get(sym, 0.0)
        current = float(current_weights.get(sym, 0.0)) if sym in current_weights.index else 0.0
        diff = target - current

        # 換手率懲罰：只有當交易成本超過目標信號強度（proxy for alpha）
        # 且變動幅度較小時才保持現狀，避免無謂的微調交易。
        # cost scales with |diff|, benefit uses |target| as alpha proxy.
        cost = abs(diff) * c.cost_bps / 10000 * 2  # 雙邊成本
        # Use target weight magnitude as proxy for alpha conviction;
        # stronger targets justify higher transaction costs.
        benefit = abs(target) * c.turnover_penalty

        if benefit > 0 and cost > benefit and abs(diff) < c.max_weight * 0.5:
            # 成本大於收益，保持當前權重
            adjusted = current
        else:
            adjusted = target

        if abs(adjusted) >= c.min_weight:
            result[sym] = max(-c.max_weight, min(c.max_weight, adjusted))

    return result


def _enforce_max_turnover(
    target_weights: dict[str, float],
    current_weights: pd.Series,
    max_turnover: float,
) -> dict[str, float]:
    """
    強制限制單期換手率上限。

    如果目標權重的換手率超過上限，按比例縮減變動量。
    """
    all_symbols = sorted(set(target_weights.keys()) | set(current_weights.index))

    target_s = pd.Series(target_weights).reindex(all_symbols, fill_value=0.0)
    current_s = current_weights.reindex(all_symbols, fill_value=0.0)

    diff = target_s - current_s
    one_sided_turnover = float(diff.abs().sum()) / 2

    if one_sided_turnover <= max_turnover:
        return target_weights

    # 按比例縮減
    scale = max_turnover / one_sided_turnover
    adjusted = current_s + diff * scale

    return {sym: float(adjusted[sym]) for sym in all_symbols if abs(adjusted[sym]) >= 0.001}
