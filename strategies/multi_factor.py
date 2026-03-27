"""
多因子策略 — 結合動量、均值回歸、RSI 的複合評分模型。
"""

from __future__ import annotations

import numpy as np

from src.strategy.base import Context, Strategy
from src.strategy.factors import momentum, mean_reversion, rsi, value_pe, value_pb, quality_roe
from src.strategy.optimizer import signal_weight, OptConstraints


class MultiFactorStrategy(Strategy):
    """
    多因子策略：
    - momentum_score: 正規化動量（百分位排名）
    - value_score: 負 Z-score（越超賣分數越高）
    - quality_score: 1 - RSI/100（RSI 越低分數越高）
    - composite = 加權平均
    - 只買入複合分數為正的標的
    """

    def __init__(
        self,
        momentum_weight: float = 0.4,
        value_weight: float = 0.3,
        quality_weight: float = 0.3,
    ):
        self.momentum_weight = momentum_weight
        self.value_weight = value_weight
        self.quality_weight = quality_weight

    def name(self) -> str:
        return "multi_factor"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        raw_scores: dict[str, dict[str, float | None]] = {}

        for symbol in ctx.universe():
            bars = ctx.bars(symbol, lookback=300)
            if len(bars) < 252:
                continue

            # 動量因子
            mom = momentum(bars, lookback=252, skip=21)
            if mom.empty:
                continue

            # 均值回歸因子（Z-score，已經取負號：越低估值越高）
            mr = mean_reversion(bars, lookback=20)
            if mr.empty:
                continue

            # RSI 因子
            rsi_factor = rsi(bars, period=14)
            if rsi_factor.empty:
                continue

            # Try fundamentals-based value/quality factors first
            fund = ctx.fundamentals(symbol)
            fund_value = None
            fund_quality = None

            if fund:
                pe = fund.get("pe_ratio")
                pb = fund.get("pb_ratio")
                roe = fund.get("roe")
                if pe is not None and pb is not None:
                    # Average of PE and PB value scores (both are inverted: lower = better)
                    fund_value = (value_pe(pe) + value_pb(pb)) / 2.0
                elif pe is not None:
                    fund_value = value_pe(pe)
                elif pb is not None:
                    fund_value = value_pb(pb)
                if roe is not None:
                    fund_quality = quality_roe(roe)

            scores: dict[str, float | None] = {
                "momentum": mom["momentum"],
                "z_score": mr["z_score"],
                "rsi": rsi_factor["rsi"],
                "fund_value": fund_value,
                "fund_quality": fund_quality,
            }
            raw_scores[symbol] = scores

        if not raw_scores:
            return {}

        # 正規化：對每個因子做百分位排名
        symbols = list(raw_scores.keys())
        n = len(symbols)

        # Check if any symbol has fundamentals data
        has_fundamentals = any(
            s["fund_value"] is not None or s["fund_quality"] is not None
            for s in raw_scores.values()
        )

        if n < 2:
            # 只有一個標的，無法排名，直接使用原始分數
            sym = symbols[0]
            scores_single = raw_scores[sym]

            # Use fundamentals if available, otherwise fall back to technical proxies
            fv = scores_single["fund_value"]
            fq = scores_single["fund_quality"]
            mom_val = scores_single["momentum"] or 0.0
            z_val = scores_single["z_score"] or 0.0
            rsi_val = scores_single["rsi"] if scores_single["rsi"] is not None else 50.0

            if has_fundamentals and fv is not None:
                value_score = min(fv * 10.0, 1.0)
            else:
                value_score = max(0.0, z_val / 3.0)

            if has_fundamentals and fq is not None:
                quality_score = fq
            else:
                quality_score = 1.0 - rsi_val / 100.0

            composite = (
                self.momentum_weight * (1.0 if mom_val > 0 else 0.0)
                + self.value_weight * value_score
                + self.quality_weight * quality_score
            )
            if composite > 0:
                return signal_weight(
                    {sym: composite},
                    OptConstraints(max_weight=0.08, max_total_weight=0.90),
                )
            return {}

        # 提取各因子的值
        mom_values: list[float] = [raw_scores[s]["momentum"] or 0.0 for s in symbols]

        # Value scores: use fundamentals if available, else technical Z-score
        if has_fundamentals:
            value_values: list[float] = []
            for s in symbols:
                fv = raw_scores[s]["fund_value"]
                if fv is not None:
                    value_values.append(min(fv * 10.0, 1.0))
                else:
                    z = raw_scores[s]["z_score"] or 0.0
                    value_values.append(max(0.0, z / 3.0))
        else:
            value_values = [raw_scores[s]["z_score"] or 0.0 for s in symbols]

        # Quality scores: use fundamentals ROE if available, else RSI-based
        if has_fundamentals:
            quality_values: list[float] = []
            for s in symbols:
                fq = raw_scores[s]["fund_quality"]
                if fq is not None:
                    quality_values.append(fq)
                else:
                    _rsi = raw_scores[s]["rsi"]
                    r = _rsi if _rsi is not None else 50.0
                    quality_values.append(1.0 - r / 100.0)
        else:
            quality_values = [1.0 - (_v if (_v := raw_scores[s]["rsi"]) is not None else 50.0) / 100.0 for s in symbols]

        # 排名百分位（0~1）
        def rank_percentile(values: list[float]) -> list[float]:
            arr = np.array(values)
            ranks = np.argsort(np.argsort(arr)).astype(float)
            result: list[float] = (ranks / (len(ranks) - 1)).tolist()
            return result

        mom_ranks = rank_percentile(mom_values)
        value_ranks = rank_percentile(value_values)
        quality_ranks = rank_percentile(quality_values)

        signals: dict[str, float] = {}
        for i, symbol in enumerate(symbols):
            momentum_score = mom_ranks[i]
            value_score = value_ranks[i]
            quality_score = quality_ranks[i]

            composite = (
                self.momentum_weight * momentum_score
                + self.value_weight * value_score
                + self.quality_weight * quality_score
            )

            if composite > 0:
                signals[symbol] = composite

        return signal_weight(
            signals,
            OptConstraints(max_weight=0.08, max_total_weight=0.90),
        )
