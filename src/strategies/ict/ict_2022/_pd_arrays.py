"""Additional ICT PD arrays: Inverse FVG and (a pragmatic) Breaker — extra entry zones the 2022
model treats as valid points of interest. Causal: they only look at bars at or before ``now``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from src.indicators import smc
from src.strategies.ict.ict_2022._model import swing_levels


@dataclass(frozen=True, slots=True)
class IFVG:
    direction: int   # the NEW (flipped) direction it now supports: +1 support / -1 resistance
    top: float
    bottom: float
    pos: int         # bar position of the original FVG


def inverse_fvgs(bars: pd.DataFrame) -> list[IFVG]:
    """FVGs that price has traded *through* (a later close beyond the far side), flipping them into
    opposite support/resistance. A violated bullish FVG becomes bearish resistance, and vice-versa.
    """
    fvg = smc.fvg(bars)
    closes = bars["close"]
    out: list[IFVG] = []
    for ts in fvg.index[fvg["fvg"].notna()]:
        d = int(fvg.at[ts, "fvg"])
        top = float(max(fvg.at[ts, "fvg_top"], fvg.at[ts, "fvg_bottom"]))
        bottom = float(min(fvg.at[ts, "fvg_top"], fvg.at[ts, "fvg_bottom"]))
        pos = int(bars.index.get_loc(ts))
        after = closes.iloc[pos + 1:]
        if d == 1 and (after < bottom).any():      # bullish FVG violated down -> bearish IFVG
            out.append(IFVG(-1, top, bottom, pos))
        elif d == -1 and (after > top).any():       # bearish FVG violated up -> bullish IFVG
            out.append(IFVG(1, top, bottom, pos))
    return out


def breaker_level(bars: pd.DataFrame, length: int = 5) -> Optional[tuple[int, float]]:
    """Pragmatic breaker: when structure breaks, the broken swing level flips polarity and acts as
    support/resistance. Returns ``(direction, level)`` — (+1, broken high now support) /
    (-1, broken low now resistance) — or None. (A simplified level-only breaker; full zone-based
    breakers/mitigation blocks are a later refinement.)"""
    highs, lows = swing_levels(bars, length)
    close = float(bars["close"].iloc[-1])
    if len(highs) and close > float(highs.iloc[-1]):
        return 1, float(highs.iloc[-1])
    if len(lows) and close < float(lows.iloc[-1]):
        return -1, float(lows.iloc[-1])
    return None
