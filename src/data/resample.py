"""Resample OHLCV bars up to a higher timeframe — the multi-timeframe rollup.

A higher-TF bar aggregates the base bars inside its window:
``open=first, high=max, low=min, close=last, volume=sum``.

Bars are grouped by their natural boundary, and **labeled by the boundary start** (so the bar's
close time is exactly ``label + duration`` — what ``MultiTFClock`` needs):
- intraday → floor to the target's clock boundary (e.g. 1h buckets at :00),
- daily    → NY session date (midnight),
- weekly   → Monday of that week.

Because we group by the timestamps that actually exist (not a full date range), overnight/weekend
gaps never create empty or straddling bars. Each base bar rolls up into exactly one higher bar.
"""

from __future__ import annotations

import pandas as pd

from src.core.types import TimeFrame
from src.data.normalize import OHLCV_COLS

_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def _bucket_key(index: pd.DatetimeIndex, target: TimeFrame) -> pd.DatetimeIndex:
    """The boundary-start label each bar in ``index`` belongs to, for ``target`` (tz preserved).

    Daily/weekly bucket on the NY *session date* (00:00 is unambiguous). Intraday floors in **UTC**
    then converts back: a 24/7 instrument has bars inside the DST fall-back hour (e.g. 01:00 ET on
    2024-11-03, which occurs twice), and flooring those in wall-clock NY raises "cannot infer dst".
    UTC has no such ambiguity, and since ET is a whole-hour offset the :00 boundaries are identical.
    """
    if target is TimeFrame.W1:
        # Monday 00:00 of each timestamp's week (tz-safe: stay in the index's tz).
        return index.normalize() - pd.to_timedelta(index.weekday, unit="D")
    if target is TimeFrame.D1:
        return index.normalize()
    return index.tz_convert("UTC").floor(target.pandas_freq).tz_convert(index.tz)


def resample_ohlcv(df: pd.DataFrame, target: TimeFrame) -> pd.DataFrame:
    """Aggregate base OHLCV ``df`` up to ``target``. Returns a canonical OHLCV frame (tz-aware NY,
    open-labeled by boundary start, sorted). Empty in → empty out."""
    if len(df) == 0:
        return df.iloc[0:0][OHLCV_COLS] if set(OHLCV_COLS).issubset(df.columns) else df.iloc[0:0]

    key = _bucket_key(df.index, target)
    out = df.groupby(key).agg(_AGG)[OHLCV_COLS]
    out.index.name = df.index.name
    return out.sort_index()
