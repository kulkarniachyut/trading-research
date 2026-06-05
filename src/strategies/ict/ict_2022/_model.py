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

from src.indicators import classic, smc
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


@dataclass(frozen=True, slots=True)
class Displacement:
    direction: int          # +1 bullish / -1 bearish
    leg_low: float          # leg extreme low (OTE anchor for longs)
    leg_high: float         # leg extreme high (OTE anchor for shorts)
    fvg_top: float
    fvg_bottom: float
    pos: int                # bar position of the impulse candle that labels the FVG


@dataclass(frozen=True, slots=True)
class LiquidityLevel:
    side: str       # "buyside" / "sellside"
    level: float
    source: str     # swing, equal, previous_session_high/low, session_high/low


@dataclass(frozen=True, slots=True)
class DailyBiasContext:
    direction: int
    zone: str
    fraction: float
    range_high: float
    range_low: float
    draw: Optional[LiquidityLevel]


def detect_displacement(
    bars: pd.DataFrame,
    direction: int,
    atr_period: int = 14,
    atr_mult: float = 1.5,
    lookback: int = 3,
) -> Optional[Displacement]:
    """An energetic move that leaves an FVG: a recent ``direction`` FVG whose impulse (middle)
    candle's range is >= ``atr_mult`` * ATR. Returns the leg extremes + the FVG it left."""
    if len(bars) < atr_period + 3:
        return None
    atr_val = classic.atr(bars, atr_period).iloc[-1]
    if pd.isna(atr_val) or atr_val <= 0:
        return None
    fvg = smc.fvg(bars)
    recent = fvg.iloc[-(lookback + 1):]
    hits = recent[recent["fvg"] == direction]
    if hits.empty:
        return None
    ts = hits.index[-1]
    pos = int(bars.index.get_loc(ts))  # smc labels the FVG at the impulse (middle) candle
    impulse = bars.iloc[pos]
    if (impulse["high"] - impulse["low"]) < atr_mult * float(atr_val):
        return None
    top = float(max(hits.at[ts, "fvg_top"], hits.at[ts, "fvg_bottom"]))
    bottom = float(min(hits.at[ts, "fvg_top"], hits.at[ts, "fvg_bottom"]))
    seg = bars.iloc[max(pos - 1, 0): pos + 2]  # the 3-bar pattern around the impulse
    return Displacement(direction, float(seg["low"].min()), float(seg["high"].max()), top, bottom, pos)


def _current_session_levels(bars: pd.DataFrame) -> list[LiquidityLevel]:
    if not isinstance(bars.index, pd.DatetimeIndex) or bars.empty:
        return []
    sessions = bars.index.normalize()
    current = sessions[-1]
    frame = bars[sessions == current]
    return [
        LiquidityLevel("buyside", float(frame["high"].max()), "session_high"),
        LiquidityLevel("sellside", float(frame["low"].min()), "session_low"),
    ]


def _previous_session_levels(bars: pd.DataFrame) -> list[LiquidityLevel]:
    if not isinstance(bars.index, pd.DatetimeIndex) or bars.empty:
        return []
    sessions = bars.index.normalize()
    current = sessions[-1]
    previous = sessions[sessions < current]
    if previous.empty:
        return []
    prev_session = previous[-1]
    frame = bars[sessions == prev_session]
    return [
        LiquidityLevel("buyside", float(frame["high"].max()), "previous_session_high"),
        LiquidityLevel("sellside", float(frame["low"].min()), "previous_session_low"),
    ]


def liquidity_levels(
    bars: pd.DataFrame,
    length: int = 5,
    *,
    include_equal: bool = True,
    include_previous_session: bool = True,
    include_current_session: bool = True,
) -> list[LiquidityLevel]:
    """Known liquidity pools from confirmed swings, optional equal highs/lows, and optional
    prior/current session extremes. Bars are assumed to be past-only, so session highs/lows are
    causal highs/lows of the bars visible to the strategy."""
    highs, lows = swing_levels(bars, length)
    out = [LiquidityLevel("buyside", float(x), "swing") for x in highs.to_numpy(dtype=float)]
    out += [LiquidityLevel("sellside", float(x), "swing") for x in lows.to_numpy(dtype=float)]

    if include_equal:
        liq = smc.liquidity(bars, swing_length=length)
        out += [
            LiquidityLevel("buyside", float(x), "equal")
            for x in liq.loc[liq["liquidity"] == 1, "liq_level"].dropna().to_numpy(dtype=float)
        ]
        out += [
            LiquidityLevel("sellside", float(x), "equal")
            for x in liq.loc[liq["liquidity"] == -1, "liq_level"].dropna().to_numpy(dtype=float)
        ]
    if include_previous_session:
        out += _previous_session_levels(bars)
    if include_current_session:
        out += _current_session_levels(bars)

    seen: set[tuple[str, float, str]] = set()
    unique: list[LiquidityLevel] = []
    for level in out:
        key = (level.side, level.level, level.source)
        if key not in seen:
            unique.append(level)
            seen.add(key)
    return unique


def liquidity_pools(bars: pd.DataFrame, length: int = 5) -> tuple[list[float], list[float]]:
    """Buyside and sellside liquidity prices. Includes confirmed swings, equal highs/lows,
    prior-session high/low, and current-session high/low."""
    levels = liquidity_levels(bars, length)
    buyside = sorted({x.level for x in levels if x.side == "buyside"})
    sellside = sorted({x.level for x in levels if x.side == "sellside"})
    return buyside, sellside


def draw_on_liquidity_level(
    bars: pd.DataFrame,
    direction: int,
    price: float,
    length: int = 5,
) -> Optional[LiquidityLevel]:
    """Nearest opposite liquidity pool: buyside above for longs, sellside below for shorts."""
    levels = liquidity_levels(bars, length)
    if direction == 1:
        above = [x for x in levels if x.side == "buyside" and x.level > price]
        return min(above, key=lambda x: x.level) if above else None
    below = [x for x in levels if x.side == "sellside" and x.level < price]
    return max(below, key=lambda x: x.level) if below else None


def draw_on_liquidity(bars: pd.DataFrame, direction: int, price: float, length: int = 5) -> Optional[float]:
    """The next opposite liquidity pool a trade should target: nearest buyside above (long) /
    sellside below (short)."""
    level = draw_on_liquidity_level(bars, direction, price, length)
    return level.level if level else None


def inducement_taken(bars: pd.DataFrame, direction: int, minor_length: int = 2, window: int = 3) -> bool:
    """Heuristic for inducement (IDM): a *minor* swing's liquidity was grabbed in the last
    ``window`` bars before the entry — price pierced the recent minor low (long) / high (short)
    and closed back beyond it."""
    highs, lows = swing_levels(bars, minor_length)
    last_close = float(bars["close"].iloc[-1])
    if direction == 1 and len(lows):
        lvl = float(lows.iloc[-1])
        return float(bars["low"].iloc[-window:].min()) < lvl <= last_close
    if direction == -1 and len(highs):
        lvl = float(highs.iloc[-1])
        return float(bars["high"].iloc[-window:].max()) > lvl >= last_close
    return False


def daily_bias(htf_bars: pd.DataFrame, length: int = 5) -> int:
    """HTF directional bias (+1/-1/0) as *persistent* market structure: carry the last
    break-of-structure forward. A close above the most-recent confirmed swing high flips bias
    bullish and a close below the most-recent confirmed swing low flips it bearish; the bias holds
    until the opposite side breaks. (An instantaneous "is *this* bar breaking" read is 0 almost
    always, so it can't function as a trend filter — this is the textbook SMC structure state.)

    Causal: confirmed swing levels are already lagged ``length`` bars, and each bar only consults
    swings confirmed at or before it.
    """
    highs, lows = swing_levels(htf_bars, length)
    if not len(highs) and not len(lows):
        return 0
    hvals = list(highs.items())  # (confirmation_ts, level), ascending
    lvals = list(lows.items())
    hi_i = lo_i = 0
    last_hi: Optional[float] = None
    last_lo: Optional[float] = None
    bias = 0
    for ts, close in htf_bars["close"].items():
        while hi_i < len(hvals) and hvals[hi_i][0] <= ts:
            last_hi = float(hvals[hi_i][1])
            hi_i += 1
        while lo_i < len(lvals) and lvals[lo_i][0] <= ts:
            last_lo = float(lvals[lo_i][1])
            lo_i += 1
        if last_hi is not None and close > last_hi:
            bias = 1
        elif last_lo is not None and close < last_lo:
            bias = -1
    return bias


def daily_bias_context(htf_bars: pd.DataFrame, length: int = 5, price: Optional[float] = None) -> DailyBiasContext:
    """Daily/HTF bias components for the state machine: structure direction, premium/discount
    location in the active dealing range, and the next structural liquidity draw."""
    if htf_bars.empty:
        raise ValueError("daily_bias_context requires at least one bar")
    px = float(htf_bars["close"].iloc[-1] if price is None else price)
    highs, lows = swing_levels(htf_bars, length)
    if len(highs) and len(lows):
        range_high = max(float(highs.iloc[-1]), float(lows.iloc[-1]))
        range_low = min(float(highs.iloc[-1]), float(lows.iloc[-1]))
    else:
        range_high = float(htf_bars["high"].max())
        range_low = float(htf_bars["low"].min())
    zone, fraction = premium_discount(px, range_high, range_low)
    direction = daily_bias(htf_bars, length)
    draw = draw_on_liquidity_level(htf_bars, direction, px, length) if direction else None
    return DailyBiasContext(direction, zone, fraction, range_high, range_low, draw)
