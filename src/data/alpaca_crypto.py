"""Alpaca crypto data provider — historical 24/7 bars via ``alpaca-py``.

Same ``DataProvider`` contract as the stock provider, but ``rth=False`` so the central normalizer
keeps overnight/weekend bars (crypto trades 24/7). This is what lets us test the ICT
session/killzone thesis (London/Asia) that RTH equities structurally cannot show.

Public symbols are slash-free (e.g. ``BTCUSD``) so cache paths stay clean; the Alpaca request needs
the ``BASE/QUOTE`` form (``BTC/USD``), inserted here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from src.core.config import AlpacaCredentials, alpaca_credentials
from src.core.types import TimeFrame
from src.data.alpaca import AlpacaProvider
from src.data.base import DataProvider

_QUOTES = ("USDT", "USDC", "USD", "BTC", "ETH")


def _to_pair(symbol: str) -> str:
    """``BTCUSD`` -> ``BTC/USD`` (Alpaca crypto request format). Pass-through if already slashed."""
    if "/" in symbol:
        return symbol
    s = symbol.upper()
    for q in _QUOTES:
        if s.endswith(q) and len(s) > len(q):
            return f"{s[:-len(q)]}/{q}"
    return s


class AlpacaCryptoProvider(DataProvider):
    key = "alpaca_crypto"
    rth = False  # 24/7 market — no NYSE RTH filter

    def __init__(self, cache_dir=None, credentials: Optional[AlpacaCredentials] = None) -> None:
        # crypto market data is free; keys are optional but used if present.
        self._creds = credentials or alpaca_credentials()
        self._client = None
        super().__init__(cache_dir=cache_dir)

    def _get_client(self):
        if self._client is None:
            from alpaca.data.historical import CryptoHistoricalDataClient

            if self._creds is not None:
                self._client = CryptoHistoricalDataClient(
                    api_key=self._creds.api_key_id, secret_key=self._creds.api_secret_key
                )
            else:
                self._client = CryptoHistoricalDataClient()  # keyless works for crypto history
        return self._client

    def _fetch_raw(
        self, symbol: str, timeframe: TimeFrame, start: datetime, end: datetime
    ) -> pd.DataFrame:
        from alpaca.data.requests import CryptoBarsRequest

        pair = _to_pair(symbol)
        req = CryptoBarsRequest(
            symbol_or_symbols=pair,
            timeframe=AlpacaProvider._alpaca_timeframe(timeframe),
            start=pd.Timestamp(start).tz_convert("UTC").to_pydatetime()
            if pd.Timestamp(start).tz
            else pd.Timestamp(start).to_pydatetime(),
            end=pd.Timestamp(end).tz_convert("UTC").to_pydatetime()
            if pd.Timestamp(end).tz
            else pd.Timestamp(end).to_pydatetime(),
        )
        bars = self._get_client().get_crypto_bars(req)
        df = bars.df
        if df is None or df.empty:
            return pd.DataFrame()
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(pair, level="symbol")
        return df
