"""Primitives for the ICT 2022 model — the reusable, testable pieces the strategy state machine
composes. Each is pure and causal (uses only the bars handed to it; the engine supplies completed
bars only).

The model's logic, in these terms:
  liquidity levels  ->  sweep (Judas grab)  ->  structure shift (MSS)  ->  premium/discount + OTE.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from src.indicators.common.pivots import pivots


@dataclass(frozen=True, slots=True)
class Sweep:
    side: str        # "buyside" (took out highs -> bearish) / "sellside" (took out lows -> bullish)
    level: float     # the liquidity level that was swept
    extreme: float   # sweep bar's high (buyside) / low (sellside) — where the stop goes
    pos: int         # bar position of the sweep


def swing_levels(bars: pd.DataFrame, length: int = 5) -> tuple[pd.Series, pd.Series]:
    """Confirmed swing-high and swing-low *levels* (price), indexed at their confirmation bar.
    Confirmed ``length`` bars late (causal), so they're safe to treat as known liquidity."""
    highs = pivots(bars["high"], length, length, high=True)["value"].dropna()
    lows = pivots(bars["low"], length, length, high=False)["value"].dropna()
    return highs, lows


def detect_sweep(bars: pd.DataFrame, length: int = 5, lookback: int = 3) -> Optional[Sweep]:
    """A liquidity sweep in the last ``lookback`` bars: price pierces a prior swing level but
    **closes back inside** it (the stop-hunt). Returns the most recent such Sweep, or None."""
    highs, lows = swing_levels(bars, length)
    n = len(bars)
    for i in range(n - 1, max(n - 1 - lookback, -1), -1):
        bar = bars.iloc[i]
        ts = bars.index[i]
        prior_highs = highs[highs.index < ts]
        if len(prior_highs):
            lvl = float(prior_highs.iloc[-1])
            if bar["high"] > lvl and bar["close"] < lvl:
                return Sweep("buyside", lvl, float(bar["high"]), i)
        prior_lows = lows[lows.index < ts]
        if len(prior_lows):
            lvl = float(prior_lows.iloc[-1])
            if bar["low"] < lvl and bar["close"] > lvl:
                return Sweep("sellside", lvl, float(bar["low"]), i)
    return None


def structure_shift(bars: pd.DataFrame, direction: int, length: int = 5) -> bool:
    """Market Structure Shift: the latest close breaks the most recent confirmed swing in
    ``direction`` (+1 up over the last swing high, -1 down under the last swing low)."""
    highs, lows = swing_levels(bars, length)
    close = float(bars["close"].iloc[-1])
    if direction == 1 and len(highs):
        return close > float(highs.iloc[-1])
    if direction == -1 and len(lows):
        return close < float(lows.iloc[-1])
    return False


def premium_discount(price: float, range_high: float, range_low: float) -> tuple[str, float]:
    """Classify ``price`` within a dealing range. Returns (zone, fraction) where fraction is
    0 at the low … 1 at the high; >0.5 = premium (sell), <0.5 = discount (buy)."""
    if range_high == range_low:
        return "equilibrium", 0.5
    frac = (price - range_low) / (range_high - range_low)
    zone = "premium" if frac > 0.5 else "discount" if frac < 0.5 else "equilibrium"
    return zone, frac


def ote_zone(leg_start: float, leg_end: float, lo: float = 0.62, hi: float = 0.79) -> tuple[float, float]:
    """Optimal Trade Entry band: the ``lo``–``hi`` retracement of the displacement leg
    (``leg_start`` = sweep extreme, ``leg_end`` = displacement peak). Returns (low, high) prices."""
    span = leg_end - leg_start
    a = leg_end - span * lo
    b = leg_end - span * hi
    return (a, b) if a <= b else (b, a)
