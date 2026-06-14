"""Option contract & chain types — the shared vocabulary for the options module.

Mirrors ``src/core/types.py``'s dataclass style. An ``OptionContract`` is the immutable
identity of a listed option; an ``OptionQuote`` is a point-in-time market observation of one
(bid/ask/last + optional IV/greeks/OI). A chain is just ``list[OptionQuote]`` for one underlying
as of one timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class Right(str, Enum):
    CALL = "C"
    PUT = "P"


@dataclass(frozen=True, slots=True)
class OptionContract:
    """Immutable identity of a listed option. ``multiplier`` is shares per contract (100 US equity)."""

    underlying: str
    expiry: date
    strike: float
    right: Right
    multiplier: int = 100
    style: str = "american"  # US equity options are American; index options often European

    def dte(self, asof: datetime | date) -> int:
        """Calendar days to expiry from ``asof`` (>=0; 0 on expiry day)."""
        d = asof.date() if isinstance(asof, datetime) else asof
        return max((self.expiry - d).days, 0)

    def moneyness(self, spot: float) -> float:
        """Strike / spot. <1 = ITM call / OTM put; >1 = OTM call / ITM put."""
        return self.strike / spot if spot else float("nan")

    def is_itm(self, spot: float) -> bool:
        return (spot > self.strike) if self.right is Right.CALL else (spot < self.strike)


@dataclass(frozen=True, slots=True)
class OptionQuote:
    """Point-in-time market observation of one contract. ``mid`` is the fair print; trading
    happens at bid/ask (the spread is the dominant options cost — see ``options/costs.py``)."""

    contract: OptionContract
    asof: datetime
    bid: float
    ask: float
    last: Optional[float] = None
    iv: Optional[float] = None          # implied vol, if provided by the source
    delta: Optional[float] = None
    open_interest: Optional[int] = None
    volume: Optional[int] = None
    underlying_price: Optional[float] = None

    @property
    def mid(self) -> float:
        return 0.5 * (self.bid + self.ask)

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def spread_pct(self) -> float:
        """Bid/ask spread as a fraction of mid — the headline liquidity/cost number. A 20%-wide
        spread (common on illiquid options) means a round trip starts ~20% in the hole."""
        m = self.mid
        return (self.spread / m) if m > 0 else float("inf")


@dataclass(slots=True)
class OptionPosition:
    """An open options position (signed: + long / - short contracts)."""

    contract: OptionContract
    qty: int                     # +long / -short, in contracts
    entry_price: float           # per-share premium paid(+)/received(-) at entry, cost-adjusted
    entry_ts: datetime
    entry_underlying: float
    reason_in: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def is_short(self) -> bool:
        return self.qty < 0
