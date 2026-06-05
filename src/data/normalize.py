"""Pure, central OHLCV normalization — the single place raw provider output becomes the
canonical bars object, so every provider behaves identically and look-ahead cannot sneak in
per-provider.

Output contract (matches ``src/core/types.py``): tz-aware ``DatetimeIndex`` in
``America/New_York``, columns ``open, high, low, close, volume``, sorted ascending, de-duped,
RTH-filtered (intraday only), with the trailing *forming* bar dropped unless requested.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from src.core.types import TimeFrame
from src.data import calendar

NY_TZ = "America/New_York"
OHLCV_COLS = ["open", "high", "low", "close", "volume"]


def _to_ny(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """tz-aware NY index. Naive input is assumed already NY (e.g. yfinance daily session dates)."""
    if index.tz is None:
        return index.tz_localize(NY_TZ)
    return index.tz_convert(NY_TZ)


def bar_close_time(ts: pd.Timestamp, timeframe: TimeFrame) -> pd.Timestamp:
    """Wall-clock time a bar *opened* at ``ts`` finishes forming. Bars are open-labeled, so a
    bar is complete only once this time has passed. Daily bars roll to the next calendar day.
    """
    if timeframe is TimeFrame.W1:
        return ts.normalize() + pd.Timedelta(weeks=1)
    if timeframe is TimeFrame.D1:
        return ts.normalize() + pd.Timedelta(days=1)
    return ts + pd.Timedelta(minutes=timeframe.minutes)


def normalize_bars(
    raw: pd.DataFrame,
    timeframe: TimeFrame,
    *,
    include_forming: bool = False,
    now: Optional[datetime] = None,
    rth: bool = True,
) -> pd.DataFrame:
    """Turn raw provider bars into the canonical OHLCV DataFrame. See module docstring.

    ``rth=False`` keeps every bar (24/7 markets like crypto/futures); the NYSE RTH filter applies
    only to US equities. tz, sort/de-dupe, and the forming-bar drop still apply.
    """
    if raw is None or len(raw) == 0:
        return pd.DataFrame(columns=OHLCV_COLS, index=pd.DatetimeIndex([], tz=NY_TZ))

    df = raw.copy()

    # 1. columns -> canonical lowercase OHLCV.
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in OHLCV_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"raw bars missing required columns {missing}; got {list(df.columns)}")
    df = df[OHLCV_COLS].apply(pd.to_numeric, errors="coerce")

    # 2. tz -> America/New_York.
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.DatetimeIndex(df.index)
    df.index = _to_ny(df.index)

    # 3. sort + de-dupe (keep the last observation for a duplicate timestamp).
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]

    # 4. RTH filter (intraday US equities only; daily bars are session-dated, 24/7 markets opt out).
    if rth and timeframe is not TimeFrame.D1 and len(df) > 0:
        df = df[calendar.rth_mask(df.index).to_numpy()]

    # 5. drop the trailing forming bar(s).
    if not include_forming and len(df) > 0:
        now_ny = (
            pd.Timestamp(now).tz_convert(NY_TZ)
            if now is not None and pd.Timestamp(now).tz is not None
            else pd.Timestamp(now if now is not None else pd.Timestamp.now(tz=NY_TZ))
        )
        if now_ny.tz is None:
            now_ny = now_ny.tz_localize(NY_TZ)
        closes = pd.DatetimeIndex([bar_close_time(ts, timeframe) for ts in df.index])
        df = df[closes <= now_ny]

    return df
