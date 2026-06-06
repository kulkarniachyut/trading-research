"""NARRATIVE / BIAS layer for ICT 2022 — the **Daily Rebalance Theory** draw engine (Ep25/Ep19/Ep37).

This is the piece the mechanical model was missing. Bias in ICT is *"where will price reach for"*
(the **draw on liquidity**), not a persistent break-of-structure. The cleanest, most testable
formulation in the decks is **Daily Rebalance Theory** (Ep25):

  When a major daily high/low is taken, study the **last 3 days**:
    • Is there a daily FVG?  → the draw is to **rebalance that gap** (price returns to fill it).
    • No FVG?                → use **PDH/PDL** and rebalance the previous day's move.
  Plus **purge & revert** (Ep19): after sweeping daily sell-side, revert to the high of the past
  3 days (the purge day counts as day 1); mirror for buy-side.

We also expose ``is_consolidation_day`` (Ep32): the day after an **outside day** is a 50/50
range/choppy day where the expansion model should stand aside (fade the EQ edges instead).

All functions are **causal** — they consume only the daily bars handed in (completed bars ≤ now).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from src.indicators import smc


@dataclass(frozen=True, slots=True)
class DailyDraw:
    """The HTF draw on liquidity. ``direction`` (+1 up / -1 down / 0 = stand aside) is the bias;
    ``draw`` is the price level price is reaching for (the rebalance target / pool); ``basis`` records
    which rule produced it (``daily_fvg`` | ``purge_revert`` | ``pdh_pdl`` | ``none``)."""

    direction: int
    draw: Optional[float]
    basis: str


def previous_day_levels(d1: pd.DataFrame) -> Optional[tuple[float, float]]:
    """(PDH, PDL) from the most recent completed daily bar, or None if there are no bars."""
    if d1.empty:
        return None
    last = d1.iloc[-1]
    return float(last["high"]), float(last["low"])


def n_day_range(d1: pd.DataFrame, lookback: int = 3) -> Optional[tuple[float, float]]:
    """(high, low) over the last ``lookback`` completed daily bars (the purge-&-revert range)."""
    if d1.empty:
        return None
    seg = d1.iloc[-lookback:]
    return float(seg["high"].max()), float(seg["low"].min())


def recent_unfilled_daily_fvg(
    d1: pd.DataFrame, price: float, lookback: int = 3
) -> Optional[tuple[int, float]]:
    """The nearest **unfilled** daily FVG formed within the last ``lookback`` daily bars, as
    ``(direction_to_gap, near_edge)`` — ``direction_to_gap`` is +1 when the gap sits **above**
    ``price`` (price is drawn up to rebalance it) and -1 when it sits below; ``near_edge`` is the
    gap edge price reaches first. Returns None if there's no qualifying gap.

    "Unfilled" = the smc FVG row has no mitigation index. We scan the most recent labelled gaps and
    pick the one whose near edge is closest to ``price``.
    """
    if len(d1) < 3:
        return None
    fvg = smc.fvg(d1)
    labelled = fvg[fvg["fvg"].notna()]
    if labelled.empty:
        return None
    # restrict to gaps whose impulse (middle) candle is within the last `lookback` daily bars
    cutoff = d1.index[-lookback] if len(d1) >= lookback else d1.index[0]
    recent = labelled[labelled.index >= cutoff]
    best: Optional[tuple[int, float]] = None
    best_dist = float("inf")
    for ts in recent.index:
        # smc's fvg_mitigated_index is the *positional* index of the candle that filled the gap, and
        # is 0 (not NaN) when unmitigated — so a gap is filled only when that index points to a bar
        # *after* the gap itself.
        mitigated = recent.at[ts, "fvg_mitigated_index"]
        gap_pos = int(d1.index.get_loc(ts))
        if pd.notna(mitigated) and int(mitigated) > gap_pos:
            continue  # already filled — no longer a draw
        top = float(max(recent.at[ts, "fvg_top"], recent.at[ts, "fvg_bottom"]))
        bottom = float(min(recent.at[ts, "fvg_top"], recent.at[ts, "fvg_bottom"]))
        if bottom > price:           # gap entirely above price -> draw up to its near (bottom) edge
            direction, near = 1, bottom
        elif top < price:            # gap entirely below price -> draw down to its near (top) edge
            direction, near = -1, top
        else:
            continue                 # price already inside the gap -> not a directional draw
        dist = abs(near - price)
        if dist < best_dist:
            best, best_dist = (direction, near), dist
    return best


def daily_rebalance(d1: pd.DataFrame, price: float, lookback: int = 3) -> DailyDraw:
    """Daily Rebalance Theory bias + draw (Ep25). Order of precedence:

    1. **Unfilled daily FVG** in the last ``lookback`` days → draw toward it (rebalance).
    2. **Purge & revert** (Ep19): if the last completed day swept the prior day's low (SSL purge),
       revert **up** to the 3-day high; if it swept the prior day's high (BSL purge), revert **down**
       to the 3-day low.
    3. **PDH/PDL** fallback: read premium/discount of ``price`` within the prior day's range — in
       discount → draw up to PDH; in premium → draw down to PDL.

    Returns a neutral ``DailyDraw(0, None, "none")`` when there isn't enough history to form an
    opinion (≥4 daily bars are required to apply the theory; "no confident bias ⇒ stand aside").
    """
    if len(d1) < 4:
        return DailyDraw(0, None, "none")

    gap = recent_unfilled_daily_fvg(d1, price, lookback)
    if gap is not None:
        return DailyDraw(gap[0], gap[1], "daily_fvg")

    prev = previous_day_levels(d1)
    rng = n_day_range(d1, lookback)
    if prev is None or rng is None:
        return DailyDraw(0, None, "none")
    pdh, pdl = prev
    hi3, lo3 = rng

    last, prior = d1.iloc[-1], d1.iloc[-2]
    swept_pdl = float(last["low"]) < float(prior["low"])
    swept_pdh = float(last["high"]) > float(prior["high"])

    # Purge & revert — only when exactly one side was taken (a clean directional purge).
    if swept_pdl and not swept_pdh:
        return DailyDraw(1, hi3, "purge_revert")
    if swept_pdh and not swept_pdl:
        return DailyDraw(-1, lo3, "purge_revert")

    # PDH/PDL fallback (inside day, or an ambiguous outside day): go with premium/discount location.
    mid = (pdh + pdl) / 2.0
    if price < mid:
        return DailyDraw(1, pdh, "pdh_pdl")
    if price > mid:
        return DailyDraw(-1, pdl, "pdh_pdl")
    return DailyDraw(0, None, "none")


def is_consolidation_day(d1: pd.DataFrame) -> bool:
    """Ep32: the day **after an outside day** tends to be a 50/50 range/choppy day where the
    expansion model should stand aside. An outside day = its range engulfs the prior day's
    (higher high **and** lower low). Reads the last two completed daily bars (the most recent
    completed day and the one before it). False if there isn't enough history."""
    if len(d1) < 3:
        return False
    prev_day, prev_prev = d1.iloc[-1], d1.iloc[-2]
    return (
        float(prev_day["high"]) > float(prev_prev["high"])
        and float(prev_day["low"]) < float(prev_prev["low"])
    )
