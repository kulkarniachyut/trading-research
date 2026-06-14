"""Options backtest harness — event-driven skeleton mirroring ``src/backtest/simulator.py``.

Steps over decision timestamps; at each step builds an as-of ``OptionContext`` (chain through
``now`` only), calls ``strategy.on_step``, fills the returned orders against the chain THROUGH THE
COST MODEL (never at mid), marks open positions, and books P&L. Expiry/assignment handled at the
contract's expiry. Produces a per-trade + equity-curve result that feeds the existing
``src/validation`` walk-forward + Monte-Carlo (the same gate every other strategy passes).

This is a SKELETON: the fill/mark/expiry mechanics are specified and partly implemented, but a
runnable backtest needs a real ``OptionsDataProvider`` with history (see ``options/data.py`` —
the data gap is the blocker, not this code). The structure is here so a concrete strategy + data
source plug in without redesigning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from options.contracts import OptionPosition, OptionQuote
from options.costs import OptionsCostModel
from options.data import OptionsDataProvider
from options.strategy import OptionContext, OptionOrder, OptionStrategy


@dataclass
class OptionTrade:
    """A closed options round-trip (entry → close/expiry), net of costs."""

    underlying: str
    description: str          # e.g. "SPY 2024-06-21 P 500 x-1"
    qty: int
    entry_ts: datetime
    exit_ts: datetime
    entry_px: float          # cost-adjusted premium per share
    exit_px: float
    multiplier: int
    gross_pnl: float
    costs: float
    net_pnl: float
    reason_out: str


@dataclass
class OptionBacktestResult:
    trades: list[OptionTrade] = field(default_factory=list)
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list)

    @property
    def total_net(self) -> float:
        return sum(t.net_pnl for t in self.trades)


class _Ctx(OptionContext):
    """Concrete as-of context the engine hands the strategy each step."""

    def __init__(self, engine: "OptionBacktest") -> None:
        self._e = engine

    @property
    def now(self) -> datetime:
        return self._e._now

    @property
    def underlying_price(self) -> float:
        return self._e._spot

    def chain(self, expiries=None) -> list[OptionQuote]:
        return self._e.provider.get_chain(self._e.underlying, self._e._now, expiries)

    @property
    def positions(self) -> list[OptionPosition]:
        return self._e._positions

    @property
    def equity(self) -> float:
        return self._e._equity


class OptionBacktest:
    """Event-driven options backtester (skeleton — see module docstring for what's left)."""

    def __init__(self, underlying: str, provider: OptionsDataProvider,
                 cost_model: OptionsCostModel | None = None,
                 initial_equity: float = 100_000.0) -> None:
        self.underlying = underlying
        self.provider = provider
        self.cost_model = cost_model or OptionsCostModel()
        self.initial_equity = initial_equity
        self._now: datetime | None = None
        self._spot: float = float("nan")
        self._equity = initial_equity
        self._positions: list[OptionPosition] = []

    def run(self, strategy: OptionStrategy, steps: list[datetime]) -> OptionBacktestResult:
        """Replay ``steps`` (decision timestamps). Each step: mark, decide, fill, then handle any
        expiries. Requires ``provider`` to serve real as-of chains — raises until one is wired."""
        result = OptionBacktestResult()
        ctx = _Ctx(self)
        strategy.on_start(ctx)
        for ts in steps:
            self._now = ts
            # 1. refresh spot + mark open positions (TODO: pull spot + quotes as-of ts)
            # 2. decide
            orders = strategy.on_step(ctx)
            # 3. fill each order through the cost model against the as-of chain (NEVER at mid)
            for _order in orders:
                self._fill(_order, result)  # TODO: implement fill + position bookkeeping
            # 4. process expirations/assignment for any contract expiring at/before ts
            self._settle_expiries(ts, result)
            self._equity = self._mark_equity()
            self.equity_curve_append(result, ts)
        return result

    # --- mechanics (specified; complete when a data provider is wired) -------
    def _fill(self, order: OptionOrder, result: OptionBacktestResult) -> None:
        """Fill ``order`` at the cost-adjusted bid/ask (``cost_model.fill_price``), update
        positions, and on a close emit an ``OptionTrade``. Skeleton."""
        raise NotImplementedError("OptionBacktest._fill — wire a data provider, then implement")

    def _settle_expiries(self, ts: datetime, result: OptionBacktestResult) -> None:
        """ITM expiries assign/exercise (cash or shares); OTM expire worthless. Skeleton."""

    def _mark_equity(self) -> float:
        return self._equity  # TODO: cash + marked open positions

    @staticmethod
    def equity_curve_append(result: OptionBacktestResult, ts: datetime) -> None:
        result.equity_curve.append((ts, 0.0))  # TODO: real marked equity
