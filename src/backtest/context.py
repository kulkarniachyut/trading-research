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
    def __init__(self, clock: MultiTFClock, symbol: str) -> None:
        self._clock = clock
        self._symbol = symbol
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

    @property
    def price(self) -> float:
        return self._price

    @property
    def position(self) -> Position:
        return self._position

    @property
    def account(self) -> Account:
        return self._account
