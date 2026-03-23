"""
數據品質引擎 — 在數據進入系統前攔截問題。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

import pandas as pd

logger = logging.getLogger(__name__)


class QualityStatus(Enum):
    PASS = "PASS"
    SUSPECT = "SUSPECT"
    REJECT = "REJECT"


@dataclass
class QualityResult:
    status: QualityStatus
    issues: list[str]
    suspect_dates: set[str] | None = None  # ISO 日期字串，標記為不可交易日

    @property
    def ok(self) -> bool:
        return self.status == QualityStatus.PASS


def check_bars(df: pd.DataFrame, symbol: str = "") -> QualityResult:
    """
    檢查 K 線 DataFrame 的數據品質。

    檢查項目：
    1. 必要欄位是否存在
    2. 是否有 NaN
    3. 價格是否為正
    4. high >= low
    5. 成交量是否為非負
    6. 時間戳是否單調遞增
    7. 價格跳變是否異常 (> 5σ)
    """
    issues: list[str] = []
    prefix = f"[{symbol}] " if symbol else ""

    # 1. 欄位檢查
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        return QualityResult(QualityStatus.REJECT, [f"{prefix}缺少欄位: {missing}"])

    if df.empty:
        return QualityResult(QualityStatus.REJECT, [f"{prefix}數據為空"])

    # 2. NaN 檢查
    nan_counts = df[list(required)].isna().sum()
    nan_cols = nan_counts[nan_counts > 0]
    if not nan_cols.empty:
        issues.append(f"{prefix}含 NaN: {dict(nan_cols)}")

    # 3. 價格為正
    for col in ["open", "high", "low", "close"]:
        if (df[col] <= 0).any():
            issues.append(f"{prefix}{col} 含非正數值")

    # 4. high >= low
    invalid_hl = (df["high"] < df["low"]).sum()
    if invalid_hl > 0:
        issues.append(f"{prefix}{invalid_hl} 根 bar 的 high < low")

    # 5. 成交量非負
    if (df["volume"] < 0).any():
        issues.append(f"{prefix}volume 含負值")

    # 6. 時間戳單調遞增
    if isinstance(df.index, pd.DatetimeIndex):
        if not df.index.is_monotonic_increasing:
            issues.append(f"{prefix}時間戳非單調遞增")

    # 7. 價格跳變
    suspect_dates: set[str] = set()
    if len(df) > 20:
        returns = df["close"].pct_change().dropna()
        if len(returns) > 0:
            mean_ret = returns.mean()
            std_ret = returns.std()
            if std_ret > 0:
                z_scores = ((returns - mean_ret) / std_ret).abs()
                jump_mask = z_scores > 5
                jumps = int(jump_mask.sum())
                if jumps > 0:
                    issues.append(f"{prefix}{jumps} 個價格跳變 > 5σ (可疑)")
                    suspect_dates = {str(d.date()) for d in z_scores[jump_mask].index}

    if not issues:
        return QualityResult(QualityStatus.PASS, [])

    # 有問題但不至於 reject
    has_critical = any("缺少欄位" in i or "數據為空" in i for i in issues)
    status = QualityStatus.REJECT if has_critical else QualityStatus.SUSPECT

    for issue in issues:
        logger.warning("DataQuality: %s", issue)

    return QualityResult(status, issues, suspect_dates=suspect_dates or None)
