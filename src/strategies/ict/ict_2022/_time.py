"""TIME layer for ICT 2022 — session anchors, macro-time windows, and premium/discount read
relative to the daily anchor.

ICT's thesis is **TIME × PRICE**: a price array (FVG/OB/old level) only matters when reached at a
key *macro time*, and price *location* is judged versus the daily **anchor** (Ep17/19/38/39). The
old model had the price half and none of the time half — these helpers supply the time half.

Data reality (important): our equity feed is **RTH-only** (09:30–16:00 NY), so the true 00:00
Midnight-NY-Open (MNO) and the 08:30 release bar are physically absent. The decks say the **09:30
cash open behaves like the 08:30/MNO anchor** for index/stock RTH, so we anchor on the **session
open** (first bar of the NY day). For 24/7 instruments (crypto, and futures once wired) the true
midnight-NY bar is present and used as the MNO. ``session_anchor`` reports which kind it found.

All functions are **causal**: they read only the bars handed in (the engine supplies completed bars
≤ ``now``), so no look-ahead is possible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from src.strategies.common import in_killzone

# The ICT macro times (Ep35/Ep39): the windows where the algo acts and where SMT/entries are valid.
# Open-ended a touch so a setup that completes a few minutes into the window still qualifies.
# RTH-equity note: 08:30 is pre-market (absent) but kept so the same config serves crypto/futures.
DEFAULT_MACRO_WINDOWS: list[tuple[str, str]] = [
    ("08:30", "09:00"),   # NY data release / AM manipulation (futures/crypto)
    ("09:30", "10:00"),   # equities cash open (the RTH manipulation anchor)
    ("10:00", "11:00"),   # Silver Bullet — highest-probability entry hour
    ("13:30", "14:30"),   # PM session anchor
]


@dataclass(frozen=True, slots=True)
class SessionAnchor:
    """The day's reference open. ``kind`` is ``"midnight"`` when a true 00:00-NY bar exists in the
    data (crypto/futures) or ``"session_open"`` when the first available bar is the RTH 09:30 open."""

    price: float
    ts: pd.Timestamp
    kind: str  # "midnight" | "session_open"


def _ny_index(bars: pd.DataFrame) -> Optional[pd.DatetimeIndex]:
    if not isinstance(bars.index, pd.DatetimeIndex) or bars.empty:
        return None
    return bars.index


def session_anchor(bars: pd.DataFrame) -> Optional[SessionAnchor]:
    """The current session's anchor open: the **open of the first bar of the latest NY date**.

    For RTH equities that first bar is 09:30 (``kind="session_open"``); for 24/7 instruments it is
    the 00:00 bar (``kind="midnight"`` = the true MNO). Returns ``None`` if there are no dated bars.
    """
    idx = _ny_index(bars)
    if idx is None:
        return None
    dates = idx.normalize()
    current = dates[-1]
    frame = bars[dates == current]
    if frame.empty:
        return None
    ts = frame.index[0]
    kind = "midnight" if ts.hour == 0 else "session_open"
    return SessionAnchor(float(frame["open"].iloc[0]), ts, kind)


def anchor_pd(price: float, anchor: float) -> str:
    """Premium/discount of ``price`` relative to the daily ``anchor`` open (Ep38): above the anchor
    = ``"premium"`` (sell location), below = ``"discount"`` (buy location), equal = ``"equilibrium"``."""
    if price > anchor:
        return "premium"
    if price < anchor:
        return "discount"
    return "equilibrium"


def anchor_allows(price: float, anchor: Optional[SessionAnchor], direction: int) -> bool:
    """Whether ``price`` is in the correct location vs the anchor for a ``direction`` trade:
    longs only in **discount** (below the anchor), shorts only in **premium** (above). A missing
    anchor (no dated bars) is permissive — the gate can't form an opinion, so it doesn't veto."""
    if anchor is None:
        return True
    zone = anchor_pd(price, anchor.price)
    if zone == "equilibrium":
        return False
    return (direction == 1 and zone == "discount") or (direction == -1 and zone == "premium")


def at_macro_time(now, windows: Optional[list[tuple[str, str]]]) -> bool:
    """True if ``now`` falls inside one of the NY-local macro ``windows``. ``None``/empty ⇒ always
    True (no time gate). Thin wrapper over the shared killzone check so the semantics match."""
    return in_killzone(now, windows)
