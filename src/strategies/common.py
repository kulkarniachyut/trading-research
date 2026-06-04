"""Shared helpers for strategies — small, reusable pieces every bucket can lean on.

Kept deliberately generic so ICT, divergence, momentum, … strategies don't each reinvent killzone
filters, R-multiple targets, or swing-based stops.
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Optional

import pandas as pd

NY_TZ = "America/New_York"


def _parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def in_killzone(now: datetime, windows: Optional[list[tuple[str, str]]]) -> bool:
    """True if ``now`` (any tz) falls in one of the NY-local ``[start, end]`` windows
    (``("09:30", "11:30")``). ``None``/empty ⇒ always True (no time filter)."""
    if not windows:
        return True
    t = pd.Timestamp(now).tz_convert(NY_TZ).time()
    return any(_parse_hhmm(s) <= t <= _parse_hhmm(e) for s, e in windows)


def r_multiple_target(entry: float, stop: float, side: str, rr: float) -> float:
    """Take-profit at ``rr`` times the risk (entry→stop distance)."""
    risk = abs(entry - stop)
    return entry + rr * risk if side == "long" else entry - rr * risk
