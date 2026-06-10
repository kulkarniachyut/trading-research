"""ORB — opening-range breakout on index futures (Step 4, family 1).

Spec follows Zarattini & Aziz (2023, "Can Day Trading Really Be Profitable?"), adapted to our
event-driven engine and validated against OUR data's anatomy (scripts/diag_session_anatomy.py,
2017-2022): first-5m-direction -> close carries ~+0.13-0.15 R/day gross with positive skew, so the
construction (tight structural stop, EOD flat, far target) is where any net edge must come from.

Mechanics (one trade per day, day-trade only):
- The opening range = the first ``or_bars`` completed 5m RTH bars (default 1 = the 09:30-09:35 bar).
- ``mode="first_bar_dir"`` (default, the paper's spec): when the OR completes, enter in the
  direction of the first OR bar's body at the next bar's open (the engine's fill discipline).
  A doji first bar ⇒ stand down for the day.
- ``mode="range_break"``: after the OR completes, enter on the first bar that *closes* beyond the
  OR high/low (long/short), until ``entry_cutoff``.
- Stop at the opposite OR extreme; target at ``rr_target`` R (far by default — most exits are the
  stop or the EOD flat, which is what gives the documented positive skew).
- Flat by the cash close: emit a "flat" Signal at/after ``eod_exit`` (fills next bar open).
  Futures trade ~23h; everything outside RTH is ignored.

Anatomy notes encoded here rather than hard-coded filters: downside OR breaks follow through less
than upside ones (diag §3) ⇒ ``long_only`` is a first-class ablation, not an afterthought. OR-width
and day-of-week conditioning flip sign between ES and NQ ⇒ deliberately NOT parameters.
"""

from __future__ import annotations

from datetime import date, time
from typing import Any, Optional

import pandas as pd

from src.core.types import MarketContext, Signal, TimeFrame
from src.strategies.base import BaseStrategy, register_strategy
from src.strategies.common import NY_TZ, _parse_hhmm, r_multiple_target

_RTH_OPEN = time(9, 30)


@register_strategy("orb")
class Orb(BaseStrategy):
    """Opening-range breakout, one day-trade per session, EOD flat."""

    required_timeframes = [TimeFrame.M5]

    @classmethod
    def default_params(cls) -> dict[str, Any]:
        return {
            "or_bars": 1,               # opening range = first N completed 5m bars
            "mode": "first_bar_dir",    # "first_bar_dir" (paper) | "range_break"
            "rr_target": 10.0,          # take-profit in R; 0/None => no target (EOD exit only)
            "long_only": False,         # diag §3: downside breaks are weaker — first ablation
            "entry_cutoff": "11:30",    # range_break only: no entries after this NY time
            "eod_exit": "15:55",        # emit flat at/after this bar-close time
        }

    @classmethod
    def param_space(cls) -> dict[str, list[Any]]:
        return {
            "or_bars": [1, 3, 6],               # 5m / 15m / 30m opening range
            "mode": ["first_bar_dir", "range_break"],
            "rr_target": [2.0, 5.0, 10.0, 0.0],
            "long_only": [True, False],
        }

    def on_start(self, ctx: MarketContext) -> None:
        self._session: Optional[date] = None
        self._or_high: Optional[float] = None
        self._or_low: Optional[float] = None
        self._first_dir: int = 0
        self._or_count: int = 0
        self._done_today: bool = False     # entered (or stood down) — one decision per day

    # --- helpers -------------------------------------------------------------

    def _ny(self, ctx: MarketContext) -> pd.Timestamp:
        return pd.Timestamp(ctx.now).tz_convert(NY_TZ)

    def _signal(self, ctx: MarketContext, side: str, stop: float) -> Signal:
        rr = self.params["rr_target"]
        entry_proxy = ctx.price  # actual fill is next bar's open; proxy is this close
        target = r_multiple_target(entry_proxy, stop, side, rr) if rr else None
        self._done_today = True
        return Signal(timestamp=ctx.now, symbol=ctx.position.symbol, side=side,
                      stop=stop, target=target,
                      reason=f"orb_{self.params['mode']}_{self.params['or_bars']}x5m")

    # --- event handler -------------------------------------------------------

    def on_bar(self, ctx: MarketContext) -> Optional[Signal]:
        now = self._ny(ctx)
        t = now.time()

        # EOD discipline first: never hold past the cash close (or into the next session).
        if ctx.position.qty != 0:
            if t >= _parse_hhmm(self.params["eod_exit"]) or t <= _RTH_OPEN:
                return Signal(timestamp=ctx.now, symbol=ctx.position.symbol, side="flat",
                              reason="eod_flat")
            return None  # stop/target are managed by the engine

        # New session reset (first bar whose close lands inside RTH).
        if now.date() != self._session:
            if not (_RTH_OPEN < t <= time(16, 0)):
                return None  # overnight bar — RTH hasn't opened yet
            self._session = now.date()
            self._or_high = self._or_low = None
            self._first_dir = 0
            self._or_count = 0
            self._done_today = False
        if self._done_today or not (_RTH_OPEN < t <= time(16, 0)):
            return None

        bar = ctx.window(TimeFrame.M5, 1)
        if bar.empty:
            return None
        b = bar.iloc[-1]

        # Build the opening range from the first `or_bars` RTH bars.
        if self._or_count < int(self.params["or_bars"]):
            hi, lo = float(b["high"]), float(b["low"])
            self._or_high = hi if self._or_high is None else max(self._or_high, hi)
            self._or_low = lo if self._or_low is None else min(self._or_low, lo)
            if self._or_count == 0:
                self._first_dir = (
                    1 if b["close"] > b["open"] else -1 if b["close"] < b["open"] else 0
                )
            self._or_count += 1
            if self._or_count < int(self.params["or_bars"]):
                return None
            # OR just completed — first_bar_dir mode acts immediately.
            if self.params["mode"] == "first_bar_dir":
                if self._first_dir == 0 or self._or_high == self._or_low:
                    self._done_today = True  # doji / dead open — stand down
                    return None
                if self._first_dir > 0:
                    return self._signal(ctx, "long", stop=self._or_low)
                if self.params["long_only"]:
                    self._done_today = True
                    return None
                return self._signal(ctx, "short", stop=self._or_high)
            return None

        # range_break mode: first close beyond the OR, until the cutoff.
        if self.params["mode"] == "range_break":
            if t > _parse_hhmm(self.params["entry_cutoff"]):
                self._done_today = True
                return None
            close = float(b["close"])
            if self._or_high is not None and close > self._or_high:
                return self._signal(ctx, "long", stop=self._or_low)
            if close < (self._or_low or float("-inf")) and not self.params["long_only"]:
                return self._signal(ctx, "short", stop=self._or_high)
        return None
