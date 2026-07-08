"""Tests for the deterministic US trading-calendar holiday logic."""

from datetime import date

from src.ingestion.reference_loader import (
    _easter,
    _nth_weekday,
    us_market_holidays,
)


def test_july_4_is_a_holiday_and_not_a_trading_day():
    holidays = us_market_holidays(2025)
    # 2025-07-04 is a Friday — a full-day market holiday.
    assert date(2025, 7, 4) in holidays
    assert holidays[date(2025, 7, 4)] == "Independence Day"


def test_known_trading_day_is_not_a_holiday():
    holidays = us_market_holidays(2025)
    # 2025-07-07 (the Monday after July 4) is a normal trading day.
    assert date(2025, 7, 7) not in holidays


def test_fixed_and_floating_holidays_2025():
    holidays = us_market_holidays(2025)
    assert date(2025, 1, 1) in holidays                 # New Year's Day
    assert date(2025, 1, 20) in holidays                # MLK — 3rd Mon of Jan
    assert date(2025, 2, 17) in holidays                # Washington's Birthday — 3rd Mon Feb
    assert date(2025, 4, 18) in holidays                # Good Friday (Easter 2025-04-20)
    assert date(2025, 5, 26) in holidays                # Memorial Day — last Mon May
    assert date(2025, 6, 19) in holidays                # Juneteenth
    assert date(2025, 9, 1) in holidays                 # Labor Day — 1st Mon Sep
    assert date(2025, 11, 27) in holidays               # Thanksgiving — 4th Thu Nov
    assert date(2025, 12, 25) in holidays               # Christmas


def test_weekend_observation_rule():
    # 2021-07-04 fell on a Sunday, observed Monday 2021-07-05.
    holidays = us_market_holidays(2021)
    assert date(2021, 7, 5) in holidays
    assert date(2021, 7, 4) not in holidays
    # 2021-12-25 fell on a Saturday, observed Friday 2021-12-24.
    assert date(2021, 12, 24) in holidays


def test_juneteenth_only_from_2022():
    assert date(2021, 6, 18) not in us_market_holidays(2021)  # not observed pre-2022
    assert date(2022, 6, 20) in us_market_holidays(2022)      # 6/19/2022 Sun -> Mon 6/20


def test_easter_computus():
    assert _easter(2025) == date(2025, 4, 20)
    assert _easter(2024) == date(2024, 3, 31)


def test_nth_weekday_helper():
    # 3rd Monday of January 2025 is the 20th.
    assert _nth_weekday(2025, 1, 0, 3) == date(2025, 1, 20)
