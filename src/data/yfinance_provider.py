"""yfinance data provider — free history, no API keys.

Implements only ``_fetch_raw``; the base class handles caching, tz/RTH normalization, and the
forming-bar drop. yfinance enforces intraday lookback limits (see ``_MAX_INTRADAY_LOOKBACK``);
requests beyond them simply return what yfinance has.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from src.core.types import TimeFrame
from src.data.base import DataProvider

# yfinance ``interval`` strings keyed by our TimeFrame.
_INTERVAL = {
    TimeFrame.M1: "1m",
    TimeFrame.M5: "5m",
    TimeFrame.M15: "15m",
    TimeFrame.H1: "1h",
    TimeFrame.D1: "1d",
}

# Approximate yfinance history limits per intraday interval (no limit for daily).
_MAX_INTRADAY_LOOKBACK = {
    TimeFrame.M1: timedelta(days=30),
    TimeFrame.M5: timedelta(days=60),
    TimeFrame.M15: timedelta(days=60),
    TimeFrame.H1: timedelta(days=730),
}


class YFinanceProvider(DataProvider):
    key = "yfinance"

    def _fetch_raw(
        self, symbol: str, timeframe: TimeFrame, start: datetime, end: datetime
    ) -> pd.DataFrame:
        import yfinance as yf

        start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)

        # Clamp intraday requests to yfinance's lookback window so the call doesn't error out.
        limit = _MAX_INTRADAY_LOOKBACK.get(timeframe)
        if limit is not None:
            earliest = pd.Timestamp.now(tz="UTC") - limit
            earliest = earliest.tz_convert(start_ts.tz) if start_ts.tz else earliest.tz_localize(None)
            if start_ts < earliest:
                start_ts = earliest

        df = yf.download(
            tickers=symbol,
            start=start_ts.tz_localize(None) if start_ts.tz else start_ts,
            end=end_ts.tz_localize(None) if end_ts.tz else end_ts,
            interval=_INTERVAL[timeframe],
            auto_adjust=False,
            prepost=False,
            progress=False,
            threads=False,
        )
        if df is None or df.empty:
            return pd.DataFrame()

        # yfinance returns a MultiIndex column frame for a single ticker in newer versions.
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=str.lower)
        return df
