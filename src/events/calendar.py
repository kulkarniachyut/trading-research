"""High-impact US scheduled-news calendar (Phase D, toggle).

Day-level filter: our entry window (10–11 ET) doesn't overlap the release *times* (CPI/NFP 08:30,
FOMC 14:00), so the useful signal is *"is today a high-impact news day?"* — days when the whole
session behaves differently (anticipation/digestion chop).

Forward-safe: the schedule is published well in advance, so knowing a future release date is not
look-ahead (the *result* would be, but we only use the date).

Coverage here is **NFP** (first Friday, formulaic → exact) + **FOMC** announcement dates (curated,
2021–2025). This is the sealed seam to later swap for a live economic-calendar provider (Finnhub /
Trading Economics) and add CPI/PCE — same ``NewsCalendar`` contract.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

# FOMC rate-decision announcement dates (2:00pm ET). Public, stable schedule.
FOMC_DATES: set[dt.date] = {
    dt.date(*x) for x in [
        (2021, 1, 27), (2021, 3, 17), (2021, 4, 28), (2021, 6, 16), (2021, 7, 28), (2021, 9, 22), (2021, 11, 3), (2021, 12, 15),
        (2022, 1, 26), (2022, 3, 16), (2022, 5, 4), (2022, 6, 15), (2022, 7, 27), (2022, 9, 21), (2022, 11, 2), (2022, 12, 14),
        (2023, 2, 1), (2023, 3, 22), (2023, 5, 3), (2023, 6, 14), (2023, 7, 26), (2023, 9, 20), (2023, 11, 1), (2023, 12, 13),
        (2024, 1, 31), (2024, 3, 20), (2024, 5, 1), (2024, 6, 12), (2024, 7, 31), (2024, 9, 18), (2024, 11, 7), (2024, 12, 18),
        (2025, 1, 29), (2025, 3, 19), (2025, 5, 7), (2025, 6, 18), (2025, 7, 30), (2025, 9, 17), (2025, 10, 29), (2025, 12, 10),
    ]
}


def nfp_days(year: int) -> set[dt.date]:
    """US Non-Farm Payrolls: the first Friday of each month (08:30 ET). Formulaic → exact."""
    out: set[dt.date] = set()
    for month in range(1, 13):
        d = dt.date(year, month, 1)
        d += dt.timedelta(days=(4 - d.weekday()) % 7)  # advance to the first Friday
        out.add(d)
    return out


def HIGH_IMPACT_US(start_year: int = 2021, end_year: int = 2025) -> set[dt.date]:
    """Union of high-impact US news days (FOMC + NFP) over the year range."""
    days = set(FOMC_DATES)
    for y in range(start_year, end_year + 1):
        days |= nfp_days(y)
    return days


class NewsCalendar:
    """A set of high-impact news *dates*; ``is_news_day(ts)`` is a same-day membership test."""

    def __init__(self, dates: set[dt.date] | None = None) -> None:
        self.dates = dates if dates is not None else HIGH_IMPACT_US()

    def is_news_day(self, ts) -> bool:
        return pd.Timestamp(ts).date() in self.dates
