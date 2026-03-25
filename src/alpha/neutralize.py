"""
因子中性化 — 從原始因子值中移除系統性暴露，隔離純 Alpha。

處理流程：原始因子 → winsorize (去極端值) → standardize (Z-score) → neutralize (去暴露)

所有變換在每個日期的橫截面上獨立執行，保證時間因果性。
"""

from __future__ import annotations

import logging
from enum import Enum

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class NeutralizeMethod(Enum):
    MARKET = "market"  # 去市場均值
    INDUSTRY = "industry"  # 行業內去均值
    SIZE = "size"  # 回歸去規模暴露
    INDUSTRY_SIZE = "ind_size"  # 行業 + 規模雙重中性化


def winsorize(
    factor_values: pd.DataFrame,
    lower: float = 0.01,
    upper: float = 0.99,
) -> pd.DataFrame:
    """
    極端值處理：每個日期的橫截面上，截尾到指定百分位。

    Args:
        factor_values: index=date, columns=symbols, values=factor values
        lower: 下界百分位 (0~1)
        upper: 上界百分位 (0~1)
    """
    result = factor_values.copy()
    for dt in result.index:
        row = result.loc[dt].dropna()
        if len(row) < 3:
            continue
        lo = float(row.quantile(lower))
        hi = float(row.quantile(upper))
        result.loc[dt] = result.loc[dt].clip(lower=lo, upper=hi)
    return result


def standardize(
    factor_values: pd.DataFrame,
    method: str = "zscore",
) -> pd.DataFrame:
    """
    橫截面標準化。

    Args:
        method: "zscore" (Z-score), "rank" (百分位排名), "rank_zscore" (排名後再 Z-score)
    """
    if method == "rank":
        return factor_values.rank(axis=1, pct=True)

    if method == "rank_zscore":
        ranked = factor_values.rank(axis=1, pct=True)
        return _zscore_cross_section(ranked)

    # zscore (default)
    return _zscore_cross_section(factor_values)


def neutralize(
    factor_values: pd.DataFrame,
    method: NeutralizeMethod,
    industry_map: dict[str, str] | None = None,
    market_caps: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    因子中性化：移除系統性暴露。

    Args:
        factor_values: index=date, columns=symbols
        method: 中性化方法
        industry_map: symbol → 行業 (INDUSTRY/INDUSTRY_SIZE 必要)
        market_caps: index=date, columns=symbols (SIZE/INDUSTRY_SIZE 必要)
    """
    if method == NeutralizeMethod.MARKET:
        return _neutralize_market(factor_values)

    if method == NeutralizeMethod.INDUSTRY:
        if not industry_map:
            logger.info(
                "Industry map unavailable (non-stock universe?), falling back to MARKET neutralization"
            )
            return _neutralize_market(factor_values)
        return _neutralize_industry(factor_values, industry_map)

    if method == NeutralizeMethod.SIZE:
        if market_caps is None or market_caps.empty:
            logger.info(
                "Market caps unavailable (non-stock universe?), falling back to MARKET neutralization"
            )
            return _neutralize_market(factor_values)
        return _neutralize_size(factor_values, market_caps)

    if method == NeutralizeMethod.INDUSTRY_SIZE:
        if not industry_map and (market_caps is None or market_caps.empty):
            logger.info(
                "Industry map and market caps unavailable, falling back to MARKET neutralization"
            )
            return _neutralize_market(factor_values)
        if not industry_map:
            logger.info("Industry map unavailable, falling back to SIZE neutralization")
            return _neutralize_size(factor_values, market_caps)  # type: ignore[arg-type]
        if market_caps is None or market_caps.empty:
            logger.info("Market caps unavailable, falling back to INDUSTRY neutralization")
            return _neutralize_industry(factor_values, industry_map)
        return _neutralize_industry_size(factor_values, industry_map, market_caps)

    raise ValueError(f"Unknown method: {method}")


# ── 內部實作 ─────────────────────────────────────────────────


def _zscore_cross_section(df: pd.DataFrame) -> pd.DataFrame:
    """每個日期的橫截面 Z-score 標準化。"""
    result = df.copy()
    for dt in result.index:
        row = result.loc[dt]
        valid = row.dropna()
        if len(valid) < 2:
            continue
        mean = valid.mean()
        std = valid.std()
        if std > 0:
            result.loc[dt] = (row - mean) / std
    return result


def _neutralize_market(factor_values: pd.DataFrame) -> pd.DataFrame:
    """市場中性：每期去均值。"""
    result = factor_values.copy()
    for dt in result.index:
        row = result.loc[dt]
        valid = row.dropna()
        if len(valid) < 2:
            continue
        result.loc[dt] = row - valid.mean()
    return result


def _neutralize_industry(
    factor_values: pd.DataFrame,
    industry_map: dict[str, str],
) -> pd.DataFrame:
    """行業中性：行業內去均值。"""
    result = factor_values.copy()

    # 建立行業分組
    symbols = factor_values.columns.tolist()
    industry_groups: dict[str, list[str]] = {}
    for sym in symbols:
        ind = industry_map.get(sym, "__unknown__")
        industry_groups.setdefault(ind, []).append(sym)

    for dt in result.index:
        for _ind, members in industry_groups.items():
            cols = [m for m in members if m in result.columns]
            if not cols:
                continue
            vals = result.loc[dt, cols].dropna()
            if len(vals) < 2:
                continue
            ind_mean = vals.mean()
            for c in cols:
                if not np.isnan(result.loc[dt, c]):
                    result.loc[dt, c] -= ind_mean
    return result


def _neutralize_size(
    factor_values: pd.DataFrame,
    market_caps: pd.DataFrame,
) -> pd.DataFrame:
    """規模中性：回歸去除 log(market_cap) 暴露，保留殘差。"""
    result = factor_values.copy()

    for dt in result.index:
        fv = factor_values.loc[dt].dropna()
        if dt not in market_caps.index:
            continue
        mc = market_caps.loc[dt].dropna()
        common = fv.index.intersection(mc.index)
        if len(common) < 5:
            continue

        y = fv[common].values.astype(float)
        x = np.log(mc[common].values.astype(float) + 1)

        # OLS: y = a + b * x + residual
        x_design = np.column_stack([np.ones(len(x)), x])
        try:
            beta, _, _, _ = np.linalg.lstsq(x_design, y, rcond=None)
            predicted = x_design @ beta
            residuals = y - predicted
            for i, sym in enumerate(common):
                result.loc[dt, sym] = residuals[i]
        except np.linalg.LinAlgError:
            continue

    return result


def _neutralize_industry_size(
    factor_values: pd.DataFrame,
    industry_map: dict[str, str],
    market_caps: pd.DataFrame,
) -> pd.DataFrame:
    """行業 + 規模雙重中性化：行業 dummy + log(market_cap) 回歸殘差。"""
    result = factor_values.copy()

    # 取得所有行業
    all_industries = sorted(set(industry_map.values()))
    ind_to_idx = {ind: i for i, ind in enumerate(all_industries)}

    for dt in result.index:
        fv = factor_values.loc[dt].dropna()
        if dt not in market_caps.index:
            continue
        mc = market_caps.loc[dt].dropna()
        common = fv.index.intersection(mc.index)
        # 只保留有行業分類的
        common = [s for s in common if s in industry_map]
        if len(common) < max(len(all_industries) + 2, 5):
            continue

        y = np.array([fv[s] for s in common], dtype=float)
        log_cap = np.log(np.array([mc[s] for s in common], dtype=float) + 1)

        # 建立行業 dummy 矩陣（drop first 避免共線性）
        n_ind = len(all_industries)
        dummies = np.zeros((len(common), max(n_ind - 1, 0)))
        for i, sym in enumerate(common):
            idx = ind_to_idx.get(industry_map[sym], 0)
            if idx > 0 and idx - 1 < dummies.shape[1]:
                dummies[i, idx - 1] = 1.0

        # X = [intercept, log_cap, industry_dummies]
        x_design = np.column_stack([np.ones(len(common)), log_cap, dummies])

        try:
            beta, _, _, _ = np.linalg.lstsq(x_design, y, rcond=None)
            predicted = x_design @ beta
            residuals = y - predicted
            for i, sym in enumerate(common):
                result.loc[dt, sym] = residuals[i]
        except np.linalg.LinAlgError:
            continue

    return result
