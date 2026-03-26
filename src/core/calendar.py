"""台灣證券交易所交易日曆。

提供交易日判斷、前後交易日查詢、交易日區間計算等功能。
休市日來源：TWSE 每年 12 月公告之次年休市日。

用法：
    from src.core.calendar import get_tw_calendar

    cal = get_tw_calendar()
    cal.is_trading_day(date(2025, 1, 29))  # False (春節)
    cal.next_trading_day(date(2025, 1, 28))  # 2025-02-03
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)


class TWTradingCalendar:
    """台灣證券交易所交易日曆。"""

    def __init__(self) -> None:
        self._holidays: set[date] = self._load_holidays()

    def is_trading_day(self, dt: date) -> bool:
        """是否為交易日（排除週末 + 國定假日 + 補假）。"""
        if dt.weekday() >= 5:
            return False
        return dt not in self._holidays

    def next_trading_day(self, dt: date) -> date:
        """下一個交易日。"""
        candidate = dt + timedelta(days=1)
        while not self.is_trading_day(candidate):
            candidate += timedelta(days=1)
        return candidate

    def prev_trading_day(self, dt: date) -> date:
        """前一個交易日。"""
        candidate = dt - timedelta(days=1)
        while not self.is_trading_day(candidate):
            candidate -= timedelta(days=1)
        return candidate

    def trading_days_between(self, start: date, end: date) -> list[date]:
        """兩個日期之間的所有交易日（含頭尾）。"""
        result: list[date] = []
        current = start
        while current <= end:
            if self.is_trading_day(current):
                result.append(current)
            current += timedelta(days=1)
        return result

    def trading_days_count(self, start: date, end: date) -> int:
        """兩個日期之間的交易日數量（含頭尾）。"""
        return len(self.trading_days_between(start, end))

    def update_holidays(self, year: int, dates: set[date]) -> None:
        """手動更新指定年份的休市日。

        Args:
            year: 年份。
            dates: 該年的休市日集合。
        """
        # 移除該年度舊的假日
        self._holidays = {d for d in self._holidays if d.year != year}
        # 加入新的
        self._holidays |= dates
        logger.info("Updated %d holidays for year %d", len(dates), year)

    def _load_holidays(self) -> set[date]:
        """硬編碼 TWSE 休市日 2024-2026。

        資料來源：台灣證券交易所年度休市日公告。
        """
        holidays: set[date] = set()

        # 2024 年休市日
        holidays |= {
            date(2024, 1, 1),   # 元旦
            date(2024, 2, 5),   # 農曆除夕前
            date(2024, 2, 6),   # 農曆除夕前
            date(2024, 2, 7),   # 農曆除夕前
            date(2024, 2, 8),   # 除夕
            date(2024, 2, 9),   # 春節
            date(2024, 2, 12),  # 春節
            date(2024, 2, 13),  # 春節
            date(2024, 2, 14),  # 春節
            date(2024, 2, 28),  # 和平紀念日
            date(2024, 4, 4),   # 兒童節/清明節
            date(2024, 4, 5),   # 清明節
            date(2024, 5, 1),   # 勞動節
            date(2024, 6, 10),  # 端午節
            date(2024, 9, 17),  # 中秋節
            date(2024, 10, 10), # 國慶日
        }

        # 2025 年休市日
        holidays |= {
            date(2025, 1, 1),   # 元旦
            date(2025, 1, 27),  # 農曆除夕前
            date(2025, 1, 28),  # 除夕
            date(2025, 1, 29),  # 春節
            date(2025, 1, 30),  # 春節
            date(2025, 1, 31),  # 春節
            date(2025, 2, 28),  # 和平紀念日
            date(2025, 4, 3),   # 兒童節
            date(2025, 4, 4),   # 清明節
            date(2025, 5, 1),   # 勞動節
            date(2025, 5, 30),  # 端午節(補假)
            date(2025, 5, 31),  # 端午節 (週六，不影響交易)
            date(2025, 10, 6),  # 中秋節
            date(2025, 10, 10), # 國慶日
        }

        # 2026 年休市日 (估計，實際以 TWSE 公告為準)
        holidays |= {
            date(2026, 1, 1),   # 元旦
            date(2026, 2, 16),  # 除夕前
            date(2026, 2, 17),  # 除夕
            date(2026, 2, 18),  # 春節
            date(2026, 2, 19),  # 春節
            date(2026, 2, 20),  # 春節
            date(2026, 2, 28),  # 和平紀念日(週六，不影響交易)
            date(2026, 4, 3),   # 兒童節
            date(2026, 4, 5),   # 清明節(週日，不影響交易)
            date(2026, 4, 6),   # 清明節補假
            date(2026, 5, 1),   # 勞動節
            date(2026, 6, 19),  # 端午節
            date(2026, 9, 25),  # 中秋節(估計)
            date(2026, 10, 10), # 國慶日(週六，不影響交易)
        }

        return holidays


# ── Module-level singleton ──

_calendar: TWTradingCalendar | None = None


def get_tw_calendar() -> TWTradingCalendar:
    """取得 TWTradingCalendar 單例。"""
    global _calendar  # noqa: PLW0603
    if _calendar is None:
        _calendar = TWTradingCalendar()
    return _calendar
