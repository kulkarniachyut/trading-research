"""Databento data provider — CME futures historical bars (``GLBX.MDP3``).

The instruments the ICT 2022 model was actually built for: two-sided, drift-neutral, 23h index
and FX/metal futures (ES/NQ/YM/RTY, 6E/6B/6J/6A, GC), where — unlike drifting single-name equities —
the *short* side is not structurally doomed (see exp-012/exp-014). Sealed behind the same
``DataProvider`` contract as Alpaca/yfinance: implements only ``_fetch_raw``; the base class caches,
normalizes (tz → NY), and drops the forming bar.

Symbology: **continuous front-month** (``ES.c.0``, ``NQ.c.0`` …) via ``stype_in="continuous"`` —
calendar-rolled so a multi-year request is one clean series. Databento OHLCV schemas are 1m/1h/1d,
so sub-hourly timeframes (5m/15m) are fetched at 1m and resampled here. Futures trade ~23h → no RTH
filter (``rth = False``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from src.core.config import databento_api_key
from src.core.types import TimeFrame
from src.data.base import DataProvider
from src.data.normalize import OHLCV_COLS
from src.data.resample import resample_ohlcv

_MISSING_KEY_MSG = (
    "Databento API key not found. Set DATABENTO_API_KEY in your environment or .env, or add a "
    "`databento: {api_key}` block to config/secrets.yaml (both are git-ignored). Free signup "
    "credits at databento.com cover the CME GLBX.MDP3 historical feed."
)

_DATASET = "GLBX.MDP3"

# Native Databento OHLCV schema per timeframe; sub-hourly TFs fetch 1m and resample locally.
_NATIVE_SCHEMA = {
    TimeFrame.M1: "ohlcv-1m",
    TimeFrame.H1: "ohlcv-1h",
    TimeFrame.D1: "ohlcv-1d",
}


class DatabentoProvider(DataProvider):
    key = "databento"
    rth = False  # CME futures run ~23h — no RTH filtering

    def __init__(self, cache_dir=None, api_key: Optional[str] = None,
                 dataset: str = _DATASET) -> None:
        key = api_key or databento_api_key()
        if not key:
            raise RuntimeError(_MISSING_KEY_MSG)
        self._api_key = key
        self._dataset = dataset
        self._client = None  # lazily constructed so import stays cheap / offline-safe
        super().__init__(cache_dir=cache_dir)

    def _get_client(self):
        if self._client is None:
            import databento as db

            self._client = db.Historical(self._api_key)
        return self._client

    def _fetch_raw(
        self, symbol: str, timeframe: TimeFrame, start: datetime, end: datetime
    ) -> pd.DataFrame:
        # 5m/15m have no native OHLCV schema → pull 1m and roll up locally.
        schema = _NATIVE_SCHEMA.get(timeframe, "ohlcv-1m")
        data = self._get_client().timeseries.get_range(
            dataset=self._dataset,
            symbols=symbol,
            schema=schema,
            stype_in="continuous",
            start=pd.Timestamp(start).tz_convert("UTC"),
            end=pd.Timestamp(end).tz_convert("UTC"),
        )
        df = self._to_ohlcv(data)
        if df.empty:
            return df
        # Roll 1m → the requested timeframe when there is no native schema for it.
        if timeframe not in _NATIVE_SCHEMA:
            df = resample_ohlcv(df, timeframe)
        return df

    @staticmethod
    def _to_ohlcv(data) -> pd.DataFrame:
        """Databento ``DBNStore`` → a tz-aware OHLCV frame (UTC index, float prices). The base class
        converts UTC → NY. ``to_df()`` already lower-cases columns and renders prices as floats."""
        df = data.to_df()
        if df is None or len(df) == 0:
            return pd.DataFrame(columns=OHLCV_COLS, index=pd.DatetimeIndex([], tz="UTC"))
        # A multi-symbol request would carry a `symbol` column; single-symbol requests don't need it.
        cols = {c.lower(): c for c in df.columns}
        keep = {std: cols[std] for std in OHLCV_COLS if std in cols}
        out = df[list(keep.values())].rename(columns={v: k for k, v in keep.items()})
        if out.index.tz is None:
            out.index = out.index.tz_localize("UTC")
        return out[OHLCV_COLS]
