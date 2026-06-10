"""Turn-of-month — calendar-flow long on equity indices (Step 4, family 5).

McConnell & Xu (2008, FAJ): since 1926, effectively *all* of the US equity premium accrues in
the turn-of-month window — the last few and first few trading days — attributed to recurring
month-end flows (pension contributions, fund rebalancing, payroll sweeps). One of the oldest
documented calendar effects that survived publication.

Theory-fixed spec (predeclared, no knobs): long from the close of the 5th-to-last trading day
of the month (fills next open = 4th-to-last) through the close of the 3rd trading day of the
next month (flat signal then, fills the 4th day's open). ~12 round-trips/yr/symbol, ~7-session
holds. Wide ATR disaster stop only because the engine sizes off a stop.

Causality: the NYSE session calendar is **published ahead of time** — using "this is the Nth
trading day from month-end" is forward-safe, exactly like news *schedules* (CLAUDE.md). The
calendar is precomputed once in ``on_start`` via pandas-market-calendars; no bar data informs it.
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from src.core.types import MarketContext, Signal, TimeFrame
from src.indicators import classic
from src.strategies.base import BaseStrategy, register_strategy


def month_position(sessions: pd.DatetimeIndex) -> dict[pd.Timestamp, tuple[int, int]]:
    """Map each session date -> (trading day # within month [1-based], # remaining incl. self)."""
    out: dict[pd.Timestamp, tuple[int, int]] = {}
    s = pd.Series(sessions, index=sessions)
    for _, days in s.groupby([sessions.year, sessions.month]):
        n = len(days)
        for i, d in enumerate(days):
            out[pd.Timestamp(d).normalize()] = (i + 1, n - i)
    return out


@register_strategy("turn_of_month")
class TurnOfMonth(BaseStrategy):
    """Long the turn-of-month window on equity indices; flat the rest of the month."""

    required_timeframes = [TimeFrame.D1]

    @classmethod
    def default_params(cls) -> dict[str, Any]:
        return {
            "enter_days_left": 5,   # signal on the 5th-to-last session close -> hold last 4
            "exit_day_of_month": 3,  # signal flat on the 3rd session close of the new month
            "atr_period": 20,
            "atr_stop": 3.0,         # disaster stop only — the calendar is the exit
            "calendar": "NYSE",
        }

    @classmethod
    def param_space(cls) -> dict[str, list[Any]]:
        return {"enter_days_left": [4, 5, 6], "exit_day_of_month": [2, 3, 4]}

    def on_start(self, ctx: MarketContext) -> None:
        import pandas_market_calendars as mcal

        cal = mcal.get_calendar(str(self.params["calendar"]))
        # Generous fixed range: the calendar is public/deterministic; no look-ahead in using it.
        sched = cal.schedule(start_date="1995-01-01", end_date="2030-12-31")
        self._pos = month_position(pd.DatetimeIndex(sched.index))
        self._last_d1: Optional[pd.Timestamp] = None

    def on_bar(self, ctx: MarketContext) -> Optional[Signal]:
        p = self.params
        d1 = ctx.window(TimeFrame.D1, int(p["atr_period"]) + 1)
        if d1.empty:
            return None
        label = d1.index[-1]
        if label == self._last_d1:
            return None
        self._last_d1 = label
        day_no, days_left = self._pos.get(pd.Timestamp(label).tz_localize(None).normalize(),
                                          (0, 0))
        if ctx.position.qty != 0:
            # flat at the close of the exit day (fills next open); disaster stop is engine-side
            if day_no >= int(p["exit_day_of_month"]) and days_left > int(p["enter_days_left"]):
                return Signal(timestamp=ctx.now, symbol=ctx.position.symbol, side="flat",
                              reason=f"tom_exit_d{day_no}")
            return None

        if days_left == int(p["enter_days_left"]) and len(d1) > int(p["atr_period"]):
            close = float(d1["close"].iloc[-1])
            atr_d = float(classic.atr(d1, int(p["atr_period"])).iloc[-1])
            if atr_d > 0:
                return Signal(timestamp=ctx.now, symbol=ctx.position.symbol, side="long",
                              stop=close - p["atr_stop"] * atr_d,
                              reason=f"tom_enter_left{days_left}")
        return None
