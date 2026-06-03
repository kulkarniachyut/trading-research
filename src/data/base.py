"""Data layer interface: ``DataProvider``.

Concrete providers (yfinance, Alpaca, later Kite) implement this. The rest of the system
depends only on this contract, so providers are interchangeable. All caching, timezone
normalization, and RTH filtering are centralized in the data layer (Step 1) so every provider
behaves identically and look-ahead cannot sneak in per-provider.

OHLCV contract returned by every method:
- pandas DataFrame, tz-aware DatetimeIndex in America/New_York
- columns: open, high, low, close, volume
- sorted ascending, de-duplicated, RTH-filtered
- the last (possibly forming) bar is dropped unless ``include_forming=True``
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Callable

from src.core.types import TimeFrame


class DataProvider(ABC):
    """Abstract source of historical and (later) live OHLCV bars."""

    @abstractmethod
    def get_bars(
        self,
        symbol: str,
        timeframe: TimeFrame,
        start: datetime,
        end: datetime,
        include_forming: bool = False,
    ):
        """Return cached, normalized historical OHLCV for ``symbol`` over [start, end].

        Must satisfy the OHLCV contract documented in this module. By default the final,
        possibly-incomplete bar is dropped to prevent look-ahead at the data boundary.
        """

    @abstractmethod
    def get_latest_bars(
        self,
        symbol: str,
        timeframe: TimeFrame,
        n: int,
        include_forming: bool = False,
    ):
        """Return the most recent ``n`` completed bars (for the live paper loop, REST poll)."""

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
