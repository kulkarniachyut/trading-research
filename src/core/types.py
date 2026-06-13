"""Shared data contracts — the backbone every component speaks.

Defined here so that `data`, `indicators`, `strategies`, `backtest`, `risk`, `validation`,
`reporting`, and `execution` all depend on these contracts rather than each other's internals.

OHLCV convention (not a class): a pandas DataFrame with a tz-aware DatetimeIndex in
America/New_York and columns ``open, high, low, close, volume`` — monotonic, de-duped,
RTH-filtered. Functions that produce/consume bars document this expectation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

Side = Literal["long", "short", "flat"]
OrderType = Literal["market", "limit"]
OrderStatus = Literal["new", "submitted", "filled", "cancelled", "rejected"]


class TimeFrame(Enum):
    """Supported bar timeframes, ordered low → high.

    ``minutes`` is the bar's span in *trading* minutes and doubles as the ordering key (D1 = one
    6.5h RTH session = 390; W1 = 5 sessions = 1950). ``pandas_freq`` is the resample alias.
    """

    M1 = "1m"
    M2 = "2m"
    M3 = "3m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H2 = "2h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"

    @property
    def minutes(self) -> int:
        return {
            "1m": 1, "2m": 2, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
            "1h": 60, "2h": 120, "4h": 240, "1d": 390, "1w": 1950,
        }[self.value]

    @property
    def pandas_freq(self) -> str:
        """Resampling alias for pandas (e.g. ``5min``, ``4h``, ``1D``, ``1W``)."""
        return {
            "1m": "1min", "2m": "2min", "3m": "3min", "5m": "5min", "15m": "15min",
            "30m": "30min", "1h": "1h", "2h": "2h", "4h": "4h", "1d": "1D", "1w": "1W",
        }[self.value]

    def __lt__(self, other: "TimeFrame") -> bool:
        return self.minutes < other.minutes


@dataclass(slots=True)
class Signal:
    """What a strategy emits from ``on_bar``. At most one per bar."""

    timestamp: datetime
    symbol: str
    side: Side
    size_hint: Optional[float] = None
    stop: Optional[float] = None
    target: Optional[float] = None
    reason: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    #: Passive entry: rest a limit at this price instead of taking the next bar's open.
    #: Fill rules (engine, conservative): gap-through fills at the open, strict trade-through
    #: fills at the limit, a mere *touch* does NOT fill, unfilled after ``ttl_bars`` cancels.
    limit: Optional[float] = None
    #: How many base bars the resting limit lives before it is cancelled.
    ttl_bars: int = 1


@dataclass(slots=True)
class Trade:
    """A completed round-trip, produced by the backtest engine."""

    symbol: str
    side: Side
    entry_ts: datetime
    exit_ts: datetime
    entry_px: float
    exit_px: float
    qty: float
    gross_pnl: float
    costs: float
    net_pnl: float
    return_pct: float
    bars_held: int
    reason_in: str = ""
    reason_out: str = ""


@dataclass(slots=True)
class Order:
    """An intended order, handed to a Broker (execution side)."""

    symbol: str
    side: Side
    qty: float
    type: OrderType = "market"
    limit_price: Optional[float] = None
    stop: Optional[float] = None
    target: Optional[float] = None
    status: OrderStatus = "new"
    id: Optional[str] = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Position:
    symbol: str
    qty: float
    avg_px: float
    market_value: float = 0.0
    unrealized_pnl: float = 0.0

    @property
    def side(self) -> Side:
        if self.qty > 0:
            return "long"
        if self.qty < 0:
            return "short"
        return "flat"


@dataclass(slots=True)
class Account:
    cash: float
    equity: float
    buying_power: float


@dataclass(slots=True)
class Result:
    """The unit everything downstream (validation, reporting) consumes."""

    strategy: str
    symbol: str
    params: dict[str, Any]
    trades: list[Trade]
    equity_curve: Any  # pandas Series; kept as Any to avoid a hard import here
    metrics: dict[str, float] = field(default_factory=dict)
    is_oos: bool = False
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


class MarketContext(ABC):
    """The per-bar view handed to a strategy's ``on_bar``.

    Exposes ONLY completed bars as of ``now`` — the forming bar and any future bar are
    physically absent, so look-ahead is impossible by construction (not by discipline).
    Concrete implementations live in the backtest engine and the live paper loop, but a
    strategy only ever depends on this interface.
    """

    @property
    @abstractmethod
    def now(self) -> datetime:
        """Timestamp of the just-closed low-timeframe bar."""

    @abstractmethod
    def bars(self, timeframe: TimeFrame):
        """All completed bars (OHLCV DataFrame) at or before ``now`` for ``timeframe``."""

    @abstractmethod
    def last(self, timeframe: TimeFrame):
        """The most recent completed bar (pandas Series) for ``timeframe``."""

    @abstractmethod
    def window(self, timeframe: TimeFrame, n: int):
        """The last ``n`` completed bars for ``timeframe``."""

    @property
    @abstractmethod
    def price(self) -> float:
        """Latest known price (close of the just-closed low-timeframe bar)."""

    @property
    @abstractmethod
    def position(self) -> Position:
        """Current position in the traded symbol (qty 0 ⇒ flat)."""

    @property
    @abstractmethod
    def account(self) -> Account:
        """Current account snapshot (cash/equity/buying power)."""

    def ref(self, timeframe: TimeFrame):
        """Completed bars (as of ``now``) of the single *correlated reference* instrument, for SMT
        divergence (Phase C). Returns an empty DataFrame when no reference is wired — so strategies
        treat "no reference" as "no SMT confluence available". Causal: reference exposes only bars
        closed at or before ``now``, same as ``bars()``. Default no-op keeps it optional for
        contexts (live, tests) that don't supply a reference."""
        import pandas as pd

        return pd.DataFrame()

    # --- Phase D: events/regime side-channel (optional; default no-op) -----

    def regime(self) -> Optional[str]:
        """Macro risk regime as of ``now`` (e.g. "risk_on"/"risk_off"), or None if not wired.
        Causal: built from data available before ``now`` (see ``src/events/regime.py``)."""
        return None

    def is_news_day(self) -> bool:
        """Whether ``now`` falls on a high-impact scheduled-news day (FOMC/CPI/NFP…). False if no
        calendar is wired. The *schedule* is public ahead of time, so this is forward-safe."""
        return False
