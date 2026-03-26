"""
數據品質引擎 — 在數據進入系統前攔截問題。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# ── 基本面合理範圍 ─────────────────────────────────────────────────
FUNDAMENTAL_BOUNDS: dict[str, tuple[float, float]] = {
    "pe_ratio": (0, 200),
    "pb_ratio": (0, 50),
    "roe": (-100, 100),
    "eps": (-50, 500),
    "revenue_growth": (-100, 1000),
    "yoy_growth": (-100, 1000),
    "market_cap": (0, 1e15),
}


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

    # 7. 價格跳變（排除疑似除權息日）
    suspect_dates: set[str] = set()
    if len(df) > 20:
        returns = df["close"].pct_change().dropna()
        if len(returns) > 0:
            mean_ret = returns.mean()
            std_ret = returns.std()
            if std_ret > 0:
                z_scores = ((returns - mean_ret) / std_ret).abs()
                jump_mask = z_scores > 5
                if jump_mask.any():
                    volume_median = float(df["volume"].median()) if len(df["volume"]) > 0 else 0
                    for idx in z_scores[jump_mask].index:
                        ret_val = float(returns.loc[idx])
                        vol_val = float(df["volume"].get(idx, 0))
                        # 除權息特徵：下跌 1~10% + 成交量正常（> 中位數 50%）
                        is_likely_ex_dividend = (
                            -0.10 < ret_val < -0.01
                            and volume_median > 0
                            and vol_val > volume_median * 0.5
                        )
                        if not is_likely_ex_dividend:
                            suspect_dates.add(
                                str(idx.date()) if hasattr(idx, "date") else str(idx)
                            )
                    if suspect_dates:
                        issues.append(
                            f"{prefix}{len(suspect_dates)} 個價格跳變 > 5σ "
                            f"(已排除疑似除權息日)"
                        )

    if not issues:
        return QualityResult(QualityStatus.PASS, [])

    # 有問題但不至於 reject
    has_critical = any("缺少欄位" in i or "數據為空" in i for i in issues)
    status = QualityStatus.REJECT if has_critical else QualityStatus.SUSPECT

    for issue in issues:
        logger.warning("DataQuality: %s", issue)

    return QualityResult(status, issues, suspect_dates=suspect_dates or None)


# ── 除權息精確比對 ─────────────────────────────────────────────────


def load_dividend_dates(symbol: str, data_dir: str = "data/market") -> set[str]:
    """從本地 Parquet 讀取已下載的除權息日期。

    嘗試兩種來源：
    1. YahooFeed 存的 {symbol}_dividends.parquet
    2. FinMind 存的 finmind_{symbol}_dividends.parquet
    """
    candidates = [
        Path(data_dir) / f"{symbol}_dividends.parquet",
        Path(data_dir) / f"finmind_{symbol}_dividends.parquet",
    ]
    for p in candidates:
        if not p.exists():
            continue
        try:
            df = pd.read_parquet(p)
            if df.empty:
                continue
            # 從 index 或 date column 取日期
            if isinstance(df.index, pd.DatetimeIndex):
                dates = df.index
            elif "date" in df.columns:
                dates = pd.to_datetime(df["date"])
            else:
                continue
            return {str(d.date()) if hasattr(d, "date") else str(d) for d in dates}
        except Exception:
            continue
    return set()


def check_bars_with_dividends(
    df: pd.DataFrame,
    symbol: str = "",
    dividend_dates: set[str] | None = None,
) -> QualityResult:
    """check_bars 增強版：使用真實除權息日期做精確比對。

    如果 dividend_dates 為 None，自動嘗試從本地讀取。
    """
    if dividend_dates is None and symbol:
        dividend_dates = load_dividend_dates(symbol)

    # 先跑基礎檢查（不含 5σ 跳變）
    issues: list[str] = []
    prefix = f"[{symbol}] " if symbol else ""

    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        return QualityResult(QualityStatus.REJECT, [f"{prefix}缺少欄位: {missing}"])
    if df.empty:
        return QualityResult(QualityStatus.REJECT, [f"{prefix}數據為空"])

    nan_counts = df[list(required)].isna().sum()
    nan_cols = nan_counts[nan_counts > 0]
    if not nan_cols.empty:
        issues.append(f"{prefix}含 NaN: {dict(nan_cols)}")

    for col in ["open", "high", "low", "close"]:
        if (df[col] <= 0).any():
            issues.append(f"{prefix}{col} 含非正數值")

    invalid_hl = (df["high"] < df["low"]).sum()
    if invalid_hl > 0:
        issues.append(f"{prefix}{invalid_hl} 根 bar 的 high < low")

    if (df["volume"] < 0).any():
        issues.append(f"{prefix}volume 含負值")

    if isinstance(df.index, pd.DatetimeIndex):
        if not df.index.is_monotonic_increasing:
            issues.append(f"{prefix}時間戳非單調遞增")

    # 5σ 跳變 — 使用真實除權息日期
    suspect_dates: set[str] = set()
    known_div_dates = dividend_dates or set()

    if len(df) > 20:
        returns = df["close"].pct_change().dropna()
        if len(returns) > 0:
            mean_ret = returns.mean()
            std_ret = returns.std()
            if std_ret > 0:
                z_scores = ((returns - mean_ret) / std_ret).abs()
                jump_mask = z_scores > 5
                if jump_mask.any():
                    volume_median = float(df["volume"].median())
                    for idx in z_scores[jump_mask].index:
                        date_str = str(idx.date()) if hasattr(idx, "date") else str(idx)
                        # 精確比對：如果在除權息日期表中，跳過
                        if date_str in known_div_dates:
                            continue
                        # 啟發式備用（沒有除權息表時）
                        if not known_div_dates:
                            ret_val = float(returns.loc[idx])
                            vol_val = float(df["volume"].get(idx, 0))
                            is_likely_ex_dividend = (
                                -0.10 < ret_val < -0.01
                                and volume_median > 0
                                and vol_val > volume_median * 0.5
                            )
                            if is_likely_ex_dividend:
                                continue
                        suspect_dates.add(date_str)
                    if suspect_dates:
                        issues.append(
                            f"{prefix}{len(suspect_dates)} 個價格跳變 > 5σ"
                        )

    if not issues:
        return QualityResult(QualityStatus.PASS, [])

    has_critical = any("缺少欄位" in i or "數據為空" in i for i in issues)
    status = QualityStatus.REJECT if has_critical else QualityStatus.SUSPECT
    for issue in issues:
        logger.warning("DataQuality: %s", issue)
    return QualityResult(status, issues, suspect_dates=suspect_dates or None)


# ── 基本面異常值過濾 ───────────────────────────────────────────────


def check_fundamentals(data: dict[str, float]) -> dict[str, float]:
    """過濾基本面異常值。超出合理範圍的值 clip 到邊界。

    Returns:
        清理後的 dict（原始 dict 不被修改）。
    """
    result = dict(data)
    for key, (lo, hi) in FUNDAMENTAL_BOUNDS.items():
        if key in result:
            val = result[key]
            if pd.isna(val):
                del result[key]
            else:
                result[key] = max(lo, min(val, hi))
    return result


# ── 停牌日偵測 ─────────────────────────────────────────────────────


def detect_halted_dates(
    df: pd.DataFrame,
    max_unchanged_days: int = 3,
) -> set[str]:
    """偵測停牌日：volume=0 或連續 N 天收盤價完全相同。

    Returns:
        ISO 日期字串 set。
    """
    halted: set[str] = set()
    if df.empty or "close" not in df.columns or "volume" not in df.columns:
        return halted

    # 1. volume = 0
    zero_vol = df[df["volume"] == 0]
    for idx in zero_vol.index:
        halted.add(str(idx.date()) if hasattr(idx, "date") else str(idx))

    # 2. 連續 N 天收盤價完全相同
    if len(df) >= max_unchanged_days:
        close = df["close"]
        unchanged = close == close.shift(1)
        streak = 0
        streak_start_indices: list[int] = []
        for i in range(len(unchanged)):
            if unchanged.iloc[i]:
                streak += 1
                if streak >= max_unchanged_days:
                    # 標記整段
                    for j in range(i - streak + 1, i + 1):
                        idx = df.index[j]
                        halted.add(str(idx.date()) if hasattr(idx, "date") else str(idx))
            else:
                streak = 0

    return halted
