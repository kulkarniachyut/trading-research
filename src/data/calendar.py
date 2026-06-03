"""NYSE session calendar (wraps ``pandas-market-calendars``).

Centralizes "when is the regular session open?" so RTH filtering is correct on holidays and
**early-close half-days** (the schedule carries each day's true close), instead of assuming a
fixed 09:30-16:00. Intraday bars get RTH-filtered against this; daily bars are session-dated and
are left alone.
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache

import pandas as pd
import pandas_market_calendars as mcal

NY_TZ = "America/New_York"
_CALENDAR_NAME = "XNYS"


@lru_cache(maxsize=1)
def _calendar():
    return mcal.get_calendar(_CALENDAR_NAME)


def _naive_dates(index) -> pd.DatetimeIndex:
    """Normalize an index of dates to tz-naive midnight (for date-keyed lookups)."""
    idx = pd.DatetimeIndex(index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    return idx.normalize()


def schedule(start: datetime, end: datetime) -> pd.DataFrame:
    """Per-session ``market_open`` / ``market_close`` timestamps (tz-aware NY) over the date
    span of ``[start, end]``. Honors holidays and early closes; empty if no sessions.
    """
    sched = _calendar().schedule(
        start_date=pd.Timestamp(start).date(),
        end_date=pd.Timestamp(end).date(),
    )
    if sched.empty:
        return sched
    # ``market_open`` / ``market_close`` are tz-aware UTC columns; present them in NY.
    for col in ("market_open", "market_close"):
        if sched[col].dt.tz is not None:
            sched[col] = sched[col].dt.tz_convert(NY_TZ)
    return sched


def rth_mask(index: pd.DatetimeIndex) -> pd.Series:
    """Boolean mask of which timestamps in ``index`` fall inside that day's regular session
    ``[market_open, market_close)``. ``index`` must be tz-aware NY. Half-open so the 16:00
    close-stamped bar (which belongs to the next interval) is excluded.
    """
    if len(index) == 0:
        return pd.Series([], dtype=bool, index=index)

    sched = schedule(index.min(), index.max())
    if sched.empty:
        return pd.Series(False, index=index)

    # Map each timestamp to its calendar date, then look up that session's open/close.
    dates = index.normalize().tz_localize(None)
    opens = sched["market_open"].copy()
    closes = sched["market_close"].copy()
    opens.index = _naive_dates(opens.index)
    closes.index = _naive_dates(closes.index)

    day_open = pd.Series(dates, index=index).map(opens)
    day_close = pd.Series(dates, index=index).map(closes)

    ts = pd.Series(index, index=index)
    return (ts >= day_open) & (ts < day_close) & day_open.notna()


def is_session_open(ts: datetime) -> bool:
    """True if ``ts`` (tz-aware) is within the regular trading session that day."""
    idx = pd.DatetimeIndex([pd.Timestamp(ts)])
    return bool(rth_mask(idx).iloc[0])


def sessions(start: datetime, end: datetime) -> pd.DatetimeIndex:
    """Trading-session dates (tz-naive, normalized) in ``[start, end]``."""
    sched = schedule(start, end)
    if sched.empty:
        return pd.DatetimeIndex([])
    return pd.DatetimeIndex(sched.index).tz_localize(None).normalize()
