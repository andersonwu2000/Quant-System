"""Basic portfolio optimization methods: equal weight, inverse vol, risk parity, constraints."""

from __future__ import annotations

import numpy as np
import pandas as pd


class BasicMethods:
    """Mixin providing basic allocation methods."""

    @staticmethod
    def _equal_weight(symbols: list[str]) -> dict[str, float]:
        n = len(symbols)
        return {s: 1.0 / n for s in symbols} if n > 0 else {}

    def _inverse_vol(
        self, returns: pd.DataFrame, symbols: list[str],
    ) -> dict[str, float]:
        vol = self.risk_model.compute_volatilities(returns)
        inv = {}
        for s in symbols:
            v = vol.get(s, 0.0)
            inv[s] = 1.0 / v if v > 0 else 0.0
        total = sum(inv.values())
        if total <= 0:
            return self._equal_weight(symbols)
        return {s: inv[s] / total for s in symbols}

    def _risk_parity(
        self, cov: pd.DataFrame, symbols: list[str],
    ) -> dict[str, float]:
        """等風險貢獻 (Risk Parity) — 迭代法。"""
        n = len(symbols)
        w = np.ones(n) / n
        sigma = cov.loc[symbols, symbols].values

        for _ in range(100):
            port_var = w @ sigma @ w
            if port_var <= 0:
                break
            marginal = sigma @ w
            target_rc = port_var / n

            # 調整權重使風險貢獻趨於相等
            for i in range(n):
                if marginal[i] > 0:
                    w[i] = target_rc / marginal[i]

            # 正規化
            total = w.sum()
            if total > 0:
                w = w / total

        return {symbols[i]: float(w[i]) for i in range(n)}

    def _apply_constraints(
        self,
        raw: dict[str, float],
        symbols: list[str],
    ) -> dict[str, float]:
        """套用權重上下限約束。

        Supports both long-only and long-short portfolios.
        For long-short: negative weights are capped symmetrically at -max_weight.
        """
        cfg = self.config
        w = dict(raw)

        for s in symbols:
            v = w.get(s, 0.0)
            if cfg.long_only:
                v = max(v, 0.0)
            else:
                # #9: Symmetric cap for short positions
                v = max(-cfg.max_weight, v)
            v = min(v, cfg.max_weight)
            if abs(v) < cfg.min_weight:
                v = 0.0
            w[s] = v

        # 正規化
        if cfg.long_only:
            total = sum(w.values())
            if total > 0:
                w = {s: v / total for s, v in w.items() if v > 0}
        else:
            # Long-short: keep both sides, remove zero-weight entries
            w = {s: v for s, v in w.items() if v != 0.0}

        return w
