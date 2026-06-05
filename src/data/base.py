"""Data layer interface: ``DataProvider``.

Concrete providers (yfinance, Alpaca, later Kite) implement a single dumb fetch method,
``_fetch_raw``. Everything that matters for correctness — caching, timezone normalization, RTH
filtering, and dropping the forming bar — is centralized here, so every provider behaves
identically and look-ahead cannot sneak in per-provider.

OHLCV contract returned by every public method:
- pandas DataFrame, tz-aware DatetimeIndex in America/New_York
- columns: open, high, low, close, volume
- sorted ascending, de-duplicated, RTH-filtered
- the last (possibly forming) bar is dropped unless ``include_forming=True``
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from src.core.config import REPO_ROOT, load_settings
from src.core.types import TimeFrame
from src.data.cache import BarCache
from src.data.normalize import normalize_bars

NY_TZ = "America/New_York"


class DataProvider(ABC):
    """Abstract source of historical and (later) live OHLCV bars.

    Subclasses set ``key`` (used in cache paths) and implement ``_fetch_raw``. They never touch
    caching, timezones, or look-ahead — that is all handled by ``get_bars`` here.
    """

    #: Short identifier used as the cache namespace, e.g. "yfinance" / "alpaca".
    key: str = "base"
    #: Whether intraday bars are NYSE-RTH-filtered. False for 24/7 markets (crypto, futures).
    rth: bool = True

    def __init__(self, cache_dir: Optional[str | Path] = None) -> None:
        if cache_dir is None:
            cache_dir = REPO_ROOT / load_settings().get("data", {}).get("cache_dir", "data/cache")
        self.cache = BarCache(cache_dir)

    # --- the public, look-ahead-safe API -----------------------------------

    def get_bars(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start: datetime,
        end: datetime,
        include_forming: bool = False,
    ) -> pd.DataFrame:
        """Cached, normalized historical OHLCV for ``symbol`` over ``[start, end]``.

        Fetches only the date ranges not already cached (gap-only refetch), normalizes them, and
        stores completed bars. By default the final, possibly-incomplete bar is dropped to prevent
        look-ahead at the data boundary.
        """
        start_ny, end_ny = self._to_ny(start), self._to_ny(end)

        for gap_start, gap_end in self.cache.covered_gaps(
            self.key, symbol, timeframe, start_ny, end_ny
        ):
            raw = self._fetch_raw(symbol, timeframe, gap_start, gap_end)
            # Cache completed bars only (now=None ⇒ drop the forming bar before storing).
            bars = normalize_bars(raw, timeframe, include_forming=False, now=None, rth=self.rth)
            self.cache.write(self.key, symbol, timeframe, bars, gap_start, gap_end)

        cached = self.cache.read(self.key, symbol, timeframe, start_ny, end_ny)
        if include_forming:
            # Caller explicitly wants the live edge: re-fetch the tail uncached.
            raw = self._fetch_raw(symbol, timeframe, end_ny - self._lookback(timeframe, 5), end_ny)
            tail = normalize_bars(raw, timeframe, include_forming=True, now=None, rth=self.rth)
            cached = pd.concat([cached, tail])
            cached = cached[~cached.index.duplicated(keep="last")].sort_index()
            cached = cached[(cached.index >= start_ny) & (cached.index <= end_ny)]
        return cached

    def get_latest_bars(
        self,
        symbol: str,
        timeframe: TimeFrame,
        n: int,
        include_forming: bool = False,
    ) -> pd.DataFrame:
        """The most recent ``n`` bars (for the live paper loop, REST poll). Fetches fresh — the
        live tail is never served from cache — and returns the last ``n`` rows after normalization.
        """
        now = pd.Timestamp.now(tz=NY_TZ)
        start = now - self._lookback(timeframe, n)
        raw = self._fetch_raw(symbol, timeframe, start, now)
        bars = normalize_bars(raw, timeframe, include_forming=include_forming, now=now, rth=self.rth)
        return bars.tail(n)

    def subscribe(
        self,
        symbols: list[str],
        timeframe: TimeFrame,
        callback: Callable[[str, object], None],
    ) -> None:
        """Stream live bars to ``callback``. Stubbed until WebSocket support (LATER).

        REST bar-polling via ``get_latest_bars`` covers bar-close strategies for now.
        """
        raise NotImplementedError("streaming not implemented yet; use get_latest_bars (REST)")

    # --- the one thing providers implement ---------------------------------

    @abstractmethod
    def _fetch_raw(
        self, symbol: str, timeframe: TimeFrame, start: datetime, end: datetime
    ) -> pd.DataFrame:
        """Fetch raw provider bars for ``[start, end]``. Any tz, any column casing — the base
        class normalizes. Should contain at least open/high/low/close/volume columns.
        """

    # --- helpers -----------------------------------------------------------

    @staticmethod
    def _to_ny(ts: datetime) -> pd.Timestamp:
        t = pd.Timestamp(ts)
        return t.tz_localize(NY_TZ) if t.tz is None else t.tz_convert(NY_TZ)

    @staticmethod
    def _lookback(timeframe: TimeFrame, n: int) -> timedelta:
        """Generous wall-clock span needed to cover ``n`` trading bars (accounts for nights,
        weekends, holidays by padding to whole sessions)."""
        if timeframe is TimeFrame.D1:
            return timedelta(days=math.ceil(n * 1.6) + 5)
        sessions = math.ceil(n * timeframe.minutes / 390)
        return timedelta(days=math.ceil(sessions * 1.6) + 5)
