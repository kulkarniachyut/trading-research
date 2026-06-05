"""Multi-symbol portfolio runner — the spine for breadth (Phase B.5).

The single-symbol `BacktestEngine` answers "does this setup work on SPY?". The breadth thesis
(docs/ICT_RESEARCH_AND_PLAN.md §5a) needs "across a universe, how often do we trade and is the
*pooled* edge positive?". This runs the strategy independently per symbol (a fresh strategy
instance each — the state machines must not bleed across symbols) and aggregates into one
``PortfolioResult``: trades/week (frequency), pooled win-rate and expectancy, and a per-symbol table.

Independent-per-symbol-then-pool is deliberate for the baseline: it measures the *edge* and
*frequency* without coupling capital. Shared-capital portfolio heat (concurrent-risk limits) is a
risk-layer concern layered on later, once an edge is shown.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import pandas as pd

from src.backtest.costs import AssetClass, InstrumentSpec, Market, Product, cost_model
from src.backtest.simulator import BacktestEngine
from src.core.types import Result, TimeFrame, Trade
from src.strategies.base import BaseStrategy


@dataclass(frozen=True, slots=True)
class UniverseItem:
    symbol: str
    asset_class: AssetClass = AssetClass.EQUITY
    multiplier: float = 1.0
    tick_size: Optional[float] = None


def _engine_for(item: UniverseItem, initial_equity: float, risk_pct: float,
                max_leverage: float) -> BacktestEngine:
    if item.asset_class is AssetClass.CRYPTO:
        market = Market("US", AssetClass.CRYPTO, Product.INTRADAY)
        model = cost_model("US", "crypto")
    else:
        market = Market("US", AssetClass.EQUITY, Product.INTRADAY)
        model = cost_model("US", "equity")
    inst = InstrumentSpec(item.symbol, market, multiplier=item.multiplier, tick_size=item.tick_size)
    return BacktestEngine(model, inst, initial_equity=initial_equity, risk_pct=risk_pct,
                          max_leverage=max_leverage)


@dataclass
class PortfolioResult:
    """Aggregate of independent per-symbol backtests over one period."""

    results: dict[str, Result]
    start: pd.Timestamp
    end: pd.Timestamp
    initial_equity: float
    risk_pct: float
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def tagged_trades(self) -> list[tuple[str, Trade]]:
        out = [(sym, t) for sym, r in self.results.items() for t in r.trades]
        out.sort(key=lambda st: st[1].exit_ts)
        return out

    @property
    def trade_count(self) -> int:
        return sum(len(r.trades) for r in self.results.values())

    @property
    def weeks(self) -> float:
        return max((self.end - self.start).days / 7.0, 1e-9)

    @property
    def trades_per_week(self) -> float:
        return self.trade_count / self.weeks

    def _all(self) -> list[Trade]:
        return [t for r in self.results.values() for t in r.trades]

    @property
    def win_rate(self) -> float:
        ts = self._all()
        return sum(1 for t in ts if t.net_pnl > 0) / len(ts) * 100 if ts else 0.0

    @property
    def total_net(self) -> float:
        return sum(t.net_pnl for t in self._all())

    @property
    def expectancy_dollars(self) -> float:
        ts = self._all()
        return self.total_net / len(ts) if ts else 0.0

    @property
    def expectancy_r(self) -> float:
        """Avg net R/trade (scale-free edge). Risk/trade ≈ risk_pct × equity."""
        denom = self.risk_pct * self.initial_equity
        return self.expectancy_dollars / denom if denom else 0.0

    def per_symbol(self) -> list[tuple[str, int, float, float]]:
        """(symbol, n_trades, win%, net$) sorted by net descending."""
        rows = []
        for sym, r in self.results.items():
            n = len(r.trades)
            win = sum(1 for t in r.trades if t.net_pnl > 0) / n * 100 if n else 0.0
            rows.append((sym, n, win, sum(t.net_pnl for t in r.trades)))
        rows.sort(key=lambda x: x[3], reverse=True)
        return rows


def run_portfolio(
    make_strategy: Callable[[], BaseStrategy],
    universe: list[UniverseItem],
    start,
    end,
    *,
    provider,
    crypto_provider=None,
    base_tf: TimeFrame = TimeFrame.M5,
    initial_equity: float = 100_000.0,
    risk_pct: float = 0.005,
    max_leverage: float = 4.0,
) -> PortfolioResult:
    """Run ``make_strategy()`` on every symbol in ``universe`` over ``[start, end]`` and aggregate.

    ``make_strategy`` is a *factory* (not an instance) so each symbol gets a clean state machine.
    Crypto items are fetched via ``crypto_provider`` (24/7, no RTH filter) if given, else ``provider``.
    A per-symbol fetch/run failure is recorded in ``errors`` and skipped, never aborting the sweep.
    """
    start = pd.Timestamp(start)
    end = pd.Timestamp(end)
    results: dict[str, Result] = {}
    errors: dict[str, str] = {}
    for item in universe:
        try:
            src = crypto_provider if item.asset_class is AssetClass.CRYPTO and crypto_provider else provider
            bars = src.get_bars(item.symbol, base_tf, start, end)
            if bars is None or bars.empty:
                errors[item.symbol] = "no bars"
                continue
            eng = _engine_for(item, initial_equity, risk_pct, max_leverage)
            results[item.symbol] = eng.run(make_strategy(), bars, base_tf)
        except Exception as exc:  # noqa: BLE001 — one bad symbol must not kill the sweep
            errors[item.symbol] = f"{type(exc).__name__}: {exc}"
    return PortfolioResult(results=results, start=start, end=end, initial_equity=initial_equity,
                           risk_pct=risk_pct, errors=errors)
