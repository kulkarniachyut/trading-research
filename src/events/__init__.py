"""Events & macro layer (Phase D) — the data-side context strategies consume as filters.

Two sub-layers, both exposed to ``on_bar`` via ``MarketContext`` and both **causal**:
- ``regime``  — macro risk-on/off gate (VIX), the yen-carry-style risk-off detector.
- ``calendar`` — high-impact scheduled-news days (FOMC/CPI/NFP); the schedule is public ahead of
  time so it is forward-safe to use as a filter.

Both are wired as *toggles* so we can measure the strategy with and without each layer.
"""

from src.events.calendar import HIGH_IMPACT_US, NewsCalendar, nfp_days
from src.events.regime import vix_regime

__all__ = ["vix_regime", "NewsCalendar", "HIGH_IMPACT_US", "nfp_days"]
