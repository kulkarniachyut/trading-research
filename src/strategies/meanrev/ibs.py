"""IBS mean reversion — short-term daily reversion on equity index futures (Step 4, family 3).

Internal Bar Strength: ``(close - low) / (high - low)`` of the daily bar — where today closed
inside its own range. Closes near the low (IBS < buy threshold) revert upward over the next days
on equity indices; documented since the 1990s and one of the few daily MR effects that survived
post-2010. Long-only by default: the short side of index MR is structurally poor (drift), and our
own diagnostics agree (diag_session_anatomy §3-4 — downside follow-through is weak, small gaps
fade *upward*).

Mechanics (same engine fit as Tsmom — H1 base, decisions on completed D1 bars):
- Enter long when IBS <= ``buy_below`` AND close is above the ``trend_ma``-day MA (regime gate:
  buy dips in an uptrend, never falling knives in a downtrend).
- Exit when IBS >= ``exit_above`` (strength returned) or after ``max_hold_days`` (time stop —
  reversion that hasn't happened in a week isn't coming).
- Disaster stop at ``atr_stop`` daily ATRs (the engine needs a stop to size; wide on purpose so
  the *time* exit, not the stop, does the work).
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from src.core.types import MarketContext, Signal, TimeFrame
from src.indicators import classic
from src.strategies.base import BaseStrategy, register_strategy


def ibs(bar: pd.Series) -> float:
    """Internal bar strength of one OHLC bar — 0 = closed at low, 1 = closed at high."""
    rng = float(bar["high"]) - float(bar["low"])
    return 0.5 if rng <= 0 else (float(bar["close"]) - float(bar["low"])) / rng


@register_strategy("ibs_rev")
class IbsRev(BaseStrategy):
    """Long-only daily IBS dip-buying with a trend gate, IBS/time exits, ATR disaster stop."""

    required_timeframes = [TimeFrame.D1]

    @classmethod
    def default_params(cls) -> dict[str, Any]:
        return {
            "buy_below": 0.2,
            "exit_above": 0.8,
            "trend_ma": 200,      # only buy dips above the long MA
            "max_hold_days": 5,
            "atr_period": 20,
            "atr_stop": 3.0,
            # Passive entry: rest a buy limit at the signal day's close instead of paying the
            # taker spread at the next open. IBS buys weakness — the natural passive fill.
            # Unfilled (price never pulled back) = signal expires; that selection effect is
            # part of the measurement, not an inconvenience.
            "limit_entry": False,
            "limit_ttl_bars": 24,  # ~one session of H1 base bars
        }

    @classmethod
    def param_space(cls) -> dict[str, list[Any]]:
        return {"buy_below": [0.15, 0.2, 0.3], "exit_above": [0.7, 0.8, 0.9]}

    def on_start(self, ctx: MarketContext) -> None:
        self._last_d1: Optional[pd.Timestamp] = None
        self._days_held: int = 0

    def on_bar(self, ctx: MarketContext) -> Optional[Signal]:
        p = self.params
        need = max(int(p["trend_ma"]), int(p["atr_period"])) + 1
        d1 = ctx.window(TimeFrame.D1, need)
        if d1.empty:
            return None
        label = d1.index[-1]
        if label == self._last_d1:
            return None  # no new completed day
        self._last_d1 = label

        today = d1.iloc[-1]
        cur_ibs = ibs(today)

        if ctx.position.qty != 0:
            self._days_held += 1
            if cur_ibs >= p["exit_above"] or self._days_held >= int(p["max_hold_days"]):
                return Signal(timestamp=ctx.now, symbol=ctx.position.symbol, side="flat",
                              reason=f"ibs_exit_{cur_ibs:.2f}_d{self._days_held}")
            return None

        self._days_held = 0
        if len(d1) < need:
            return None  # warm-up
        close = float(today["close"])
        if cur_ibs > p["buy_below"]:
            return None
        trend_ma = int(p["trend_ma"])
        if trend_ma > 1:  # <=1 disables the gate (ablation)
            ma = float(d1["close"].rolling(trend_ma).mean().iloc[-1])
            if close <= ma:
                return None
        atr_d = float(classic.atr(d1, int(p["atr_period"])).iloc[-1])
        if not atr_d > 0:
            return None
        return Signal(timestamp=ctx.now, symbol=ctx.position.symbol, side="long",
                      stop=close - p["atr_stop"] * atr_d,
                      reason=f"ibs_buy_{cur_ibs:.2f}",
                      limit=close if p["limit_entry"] else None,
                      ttl_bars=int(p["limit_ttl_bars"]))
