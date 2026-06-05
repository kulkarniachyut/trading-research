"""``BacktestContext`` — the concrete ``MarketContext`` the engine hands to a strategy each bar.

It is a thin view over the ``MultiTFClock`` plus the engine's current state (now, position,
account). Because every bar lookup goes through the clock's ``completed`` view, the strategy can
only ever see bars that have already closed as of ``now`` — look-ahead is impossible here, exactly
as in the live paper loop.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.backtest.clock import MultiTFClock
from src.core.types import Account, MarketContext, Position, TimeFrame


class BacktestContext(MarketContext):
    def __init__(self, clock: MultiTFClock, symbol: str,
                 ref_clock: MultiTFClock | None = None,
                 regime_series=None, news_calendar=None) -> None:
        self._clock = clock
        self._symbol = symbol
        self._ref_clock = ref_clock
        self._regime_series = regime_series      # pd.Series of tags, session-dated (Phase D)
        self._news_calendar = news_calendar      # events.NewsCalendar (Phase D)
        self._now: datetime | None = None
        self._price: float = float("nan")
        self._position = Position(symbol, qty=0.0, avg_px=0.0)
        self._account = Account(cash=0.0, equity=0.0, buying_power=0.0)

    # the engine updates these each bar before calling on_bar
    def _update(self, now: datetime, price: float, position: Position, account: Account) -> None:
        self._now, self._price, self._position, self._account = now, price, position, account

    @property
    def now(self) -> datetime:
        return self._now

    def bars(self, timeframe: TimeFrame) -> pd.DataFrame:
        return self._clock.completed(timeframe, self._now)

    def last(self, timeframe: TimeFrame):
        return self._clock.last(timeframe, self._now)

    def window(self, timeframe: TimeFrame, n: int) -> pd.DataFrame:
        return self._clock.window(timeframe, self._now, n)

    def ref(self, timeframe: TimeFrame) -> pd.DataFrame:
        """Completed bars of the correlated reference symbol as of ``now`` (SMT). Empty if none."""
        if self._ref_clock is None:
            return pd.DataFrame()
        return self._ref_clock.completed(timeframe, self._now)

    def regime(self):
        """Macro risk regime tag as of ``now`` (session-dated, causal asof). None if not wired."""
        if self._regime_series is None or len(self._regime_series) == 0:
            return None
        val = self._regime_series.asof(self._now)
        return None if val is None or (isinstance(val, float) and pd.isna(val)) else val

    def is_news_day(self) -> bool:
        if self._news_calendar is None:
            return False
        return self._news_calendar.is_news_day(self._now)

    @property
    def price(self) -> float:
        return self._price

    @property
    def position(self) -> Position:
        return self._position

    @property
    def account(self) -> Account:
        return self._account
