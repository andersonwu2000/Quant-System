"""Tests for TWTradingCalendar — 台灣證券交易所交易日曆。"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from src.core.calendar import TWTradingCalendar, get_tw_calendar


@pytest.fixture
def cal() -> TWTradingCalendar:
    return TWTradingCalendar()


class TestIsTraingDay:
    """is_trading_day() 測試。"""

    def test_weekday_not_holiday_is_trading_day(self, cal: TWTradingCalendar) -> None:
        """一般工作日（非假日）應為交易日。"""
        # 2024-03-04 是週一且不是假日
        assert cal.is_trading_day(date(2024, 3, 4)) is True

    def test_saturday_is_not_trading_day(self, cal: TWTradingCalendar) -> None:
        assert cal.is_trading_day(date(2024, 3, 2)) is False

    def test_sunday_is_not_trading_day(self, cal: TWTradingCalendar) -> None:
        assert cal.is_trading_day(date(2024, 3, 3)) is False

    def test_chinese_new_year_2024_not_trading_day(self, cal: TWTradingCalendar) -> None:
        """2024 春節（2/8 除夕 ~ 2/14）不是交易日。"""
        assert cal.is_trading_day(date(2024, 2, 8)) is False
        assert cal.is_trading_day(date(2024, 2, 9)) is False
        assert cal.is_trading_day(date(2024, 2, 12)) is False
        assert cal.is_trading_day(date(2024, 2, 14)) is False

    def test_national_day_2025_not_trading_day(self, cal: TWTradingCalendar) -> None:
        """2025 國慶日 (10/10) 不是交易日。"""
        assert cal.is_trading_day(date(2025, 10, 10)) is False

    def test_new_year_2024_not_trading_day(self, cal: TWTradingCalendar) -> None:
        """元旦不是交易日。"""
        assert cal.is_trading_day(date(2024, 1, 1)) is False

    def test_labor_day_2025_not_trading_day(self, cal: TWTradingCalendar) -> None:
        """勞動節不是交易日。"""
        assert cal.is_trading_day(date(2025, 5, 1)) is False

    def test_peace_memorial_day_2024(self, cal: TWTradingCalendar) -> None:
        """2024 和平紀念日 (2/28) 不是交易日。"""
        assert cal.is_trading_day(date(2024, 2, 28)) is False

    def test_dragon_boat_2025(self, cal: TWTradingCalendar) -> None:
        """2025 端午節補假 (5/30) 不是交易日。"""
        assert cal.is_trading_day(date(2025, 5, 30)) is False

    def test_mid_autumn_2025(self, cal: TWTradingCalendar) -> None:
        """2025 中秋節 (10/6) 不是交易日。"""
        assert cal.is_trading_day(date(2025, 10, 6)) is False


class TestNextTradingDay:
    """next_trading_day() 測試。"""

    def test_next_from_weekday(self, cal: TWTradingCalendar) -> None:
        """週一→週二（無假日）。"""
        assert cal.next_trading_day(date(2024, 3, 4)) == date(2024, 3, 5)

    def test_next_skips_weekend(self, cal: TWTradingCalendar) -> None:
        """週五→下週一。"""
        assert cal.next_trading_day(date(2024, 3, 1)) == date(2024, 3, 4)

    def test_next_skips_holiday(self, cal: TWTradingCalendar) -> None:
        """2025-01-24 (週五) → 2025-02-03 (跳過除夕~春節)。"""
        result = cal.next_trading_day(date(2025, 1, 24))
        assert result == date(2025, 2, 3)

    def test_next_skips_weekend_and_holiday(self, cal: TWTradingCalendar) -> None:
        """跨週末 + 假日。"""
        # 2024-02-07 (三) 是假日，next_trading_day 應跳過所有春節假期
        result = cal.next_trading_day(date(2024, 2, 7))
        assert result == date(2024, 2, 15)


class TestPrevTradingDay:
    """prev_trading_day() 測試。"""

    def test_prev_from_weekday(self, cal: TWTradingCalendar) -> None:
        """週二→週一。"""
        assert cal.prev_trading_day(date(2024, 3, 5)) == date(2024, 3, 4)

    def test_prev_skips_weekend(self, cal: TWTradingCalendar) -> None:
        """週一→上週五。"""
        assert cal.prev_trading_day(date(2024, 3, 4)) == date(2024, 3, 1)

    def test_prev_skips_holiday(self, cal: TWTradingCalendar) -> None:
        """2024-02-15 (春節後首日) → 2024-02-02 (春節前最後交易日)。"""
        result = cal.prev_trading_day(date(2024, 2, 15))
        assert result == date(2024, 2, 2)


class TestTradingDaysBetween:
    """trading_days_between() / trading_days_count() 測試。"""

    def test_one_week(self, cal: TWTradingCalendar) -> None:
        """一般一週有 5 個交易日。"""
        days = cal.trading_days_between(date(2024, 3, 4), date(2024, 3, 8))
        assert len(days) == 5
        assert days[0] == date(2024, 3, 4)
        assert days[-1] == date(2024, 3, 8)

    def test_week_with_weekend(self, cal: TWTradingCalendar) -> None:
        """包含週末的區間。"""
        days = cal.trading_days_between(date(2024, 3, 1), date(2024, 3, 8))
        # 3/1(Fri), 3/4(Mon)~3/8(Fri) = 6 trading days
        assert len(days) == 6

    def test_trading_days_count_2024_full_year(self, cal: TWTradingCalendar) -> None:
        """2024 全年交易日約 247-250 天。"""
        count = cal.trading_days_count(date(2024, 1, 1), date(2024, 12, 31))
        assert 245 <= count <= 252

    def test_trading_days_count_matches_between(self, cal: TWTradingCalendar) -> None:
        start = date(2024, 6, 1)
        end = date(2024, 6, 30)
        assert cal.trading_days_count(start, end) == len(
            cal.trading_days_between(start, end)
        )

    def test_empty_range(self, cal: TWTradingCalendar) -> None:
        """start > end 應回傳空 list。"""
        days = cal.trading_days_between(date(2024, 3, 8), date(2024, 3, 4))
        assert days == []


class TestUpdateHolidays:
    """update_holidays() 測試。"""

    def test_update_replaces_year(self, cal: TWTradingCalendar) -> None:
        """更新後舊年度假日被替換。"""
        new_holidays = {date(2024, 12, 25)}
        cal.update_holidays(2024, new_holidays)
        # 原本 2024-01-01 是假日，更新後只剩 12/25
        assert cal.is_trading_day(date(2024, 1, 1)) is True  # 不再是假日
        assert cal.is_trading_day(date(2024, 12, 25)) is False  # 新假日


class TestSingleton:
    """get_tw_calendar() singleton 測試。"""

    def test_singleton_returns_same_instance(self) -> None:
        import src.core.calendar as cal_mod

        # Reset singleton
        cal_mod._calendar = None
        c1 = get_tw_calendar()
        c2 = get_tw_calendar()
        assert c1 is c2
        # Clean up
        cal_mod._calendar = None


class TestIsTradableWithCalendar:
    """is_tradable() 整合 calendar 測試。"""

    def test_is_tradable_returns_false_on_holiday(self) -> None:
        """國定假日 + 交易時段內 → 不可交易。"""
        from src.execution.market_hours import TW_TZ, is_tradable

        # 2024-02-08 (除夕) 10:00 — 在盤中時段但是假日
        holiday_during_session = datetime(2024, 2, 8, 10, 0, 0, tzinfo=TW_TZ)
        assert is_tradable(holiday_during_session) is False

    def test_is_tradable_returns_true_on_normal_day(self) -> None:
        """一般交易日盤中 → 可交易。"""
        from src.execution.market_hours import TW_TZ, is_tradable

        # 2024-03-04 (週一) 10:00
        normal_day = datetime(2024, 3, 4, 10, 0, 0, tzinfo=TW_TZ)
        assert is_tradable(normal_day) is True

    def test_is_tradable_returns_false_on_weekend(self) -> None:
        """週末 → 不可交易。"""
        from src.execution.market_hours import TW_TZ, is_tradable

        weekend = datetime(2024, 3, 2, 10, 0, 0, tzinfo=TW_TZ)
        assert is_tradable(weekend) is False
