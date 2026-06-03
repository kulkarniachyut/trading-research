"""Alpaca data provider — historical IEX bars (free tier), via ``alpaca-py``.

Implements only ``_fetch_raw``; the base class handles caching, tz/RTH normalization, and the
forming-bar drop. Requires Alpaca API keys (paper keys work for historical IEX data); if they are
absent, construction raises a clear, actionable error rather than failing obscurely at fetch time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from src.core.config import AlpacaCredentials, alpaca_credentials
from src.core.types import TimeFrame
from src.data.base import DataProvider

_MISSING_KEYS_MSG = (
    "Alpaca API keys not found. Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY in your "
    "environment or .env, or add an `alpaca: {api_key_id, api_secret_key}` block to "
    "config/secrets.yaml (both are git-ignored). Paper keys from alpaca.markets work for "
    "historical IEX data."
)


class AlpacaProvider(DataProvider):
    key = "alpaca"

    def __init__(self, cache_dir=None, credentials: Optional[AlpacaCredentials] = None) -> None:
        creds = credentials or alpaca_credentials()
        if creds is None:
            raise RuntimeError(_MISSING_KEYS_MSG)
        self._creds = creds
        self._client = None  # lazily constructed so import stays cheap / offline-safe
        super().__init__(cache_dir=cache_dir)

    def _get_client(self):
        if self._client is None:
            from alpaca.data.historical import StockHistoricalDataClient

            self._client = StockHistoricalDataClient(
                api_key=self._creds.api_key_id,
                secret_key=self._creds.api_secret_key,
            )
        return self._client

    @staticmethod
    def _alpaca_timeframe(timeframe: TimeFrame):
        from alpaca.data.timeframe import TimeFrame as AlpacaTF
        from alpaca.data.timeframe import TimeFrameUnit

        return {
            TimeFrame.M1: AlpacaTF(1, TimeFrameUnit.Minute),
            TimeFrame.M5: AlpacaTF(5, TimeFrameUnit.Minute),
            TimeFrame.M15: AlpacaTF(15, TimeFrameUnit.Minute),
            TimeFrame.H1: AlpacaTF(1, TimeFrameUnit.Hour),
            TimeFrame.D1: AlpacaTF(1, TimeFrameUnit.Day),
        }[timeframe]

    def _fetch_raw(
        self, symbol: str, timeframe: TimeFrame, start: datetime, end: datetime
    ) -> pd.DataFrame:
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockBarsRequest

        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=self._alpaca_timeframe(timeframe),
            start=pd.Timestamp(start).tz_convert("UTC").to_pydatetime()
            if pd.Timestamp(start).tz
            else pd.Timestamp(start).to_pydatetime(),
            end=pd.Timestamp(end).tz_convert("UTC").to_pydatetime()
            if pd.Timestamp(end).tz
            else pd.Timestamp(end).to_pydatetime(),
            feed=DataFeed.IEX,
        )
        bars = self._get_client().get_stock_bars(req)
        df = bars.df
        if df is None or df.empty:
            return pd.DataFrame()

        # Multi-symbol requests yield a (symbol, timestamp) MultiIndex; drop the symbol level.
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(symbol, level="symbol")
        # alpaca timestamps are tz-aware UTC; columns are already open/high/low/close/volume.
        return df
