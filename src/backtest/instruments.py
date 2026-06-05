"""CME micro index-futures contract specs — the instruments ICT is built for, and the ones
tradeable on Robinhood (see ``docs/ICT_RESEARCH_AND_PLAN.md``).

Each entry is the reference data the engine + cost model need: the **point value**
(``InstrumentSpec.multiplier``) and the **tick size**. P&L = price_move_in_points × multiplier ×
contracts; one tick is worth ``multiplier × tick_size``.

Futures price is quoted in *index points* (MES≈SPX, MNQ≈NDX), not the ETF price — so to run a
strategy on the SPY/QQQ RTH proxy we rescale the proxy into index-point space (Phase A.2);
``PROXY`` records the ETF→index point factor for that.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.backtest.costs.core import AssetClass, InstrumentSpec, Market, Product

_US_FUT = Market("US", AssetClass.FUTURE, Product.FUTURES)


@dataclass(frozen=True, slots=True)
class MicroFuture:
    symbol: str
    name: str
    multiplier: float        # $ per 1.0 point move (point value)
    tick_size: float         # minimum price increment, in points
    proxy_etf: str | None = None     # RTH equity proxy
    proxy_factor: float = 1.0        # index_points ≈ etf_price × proxy_factor

    @property
    def tick_value(self) -> float:
        return self.multiplier * self.tick_size

    def instrument(self) -> InstrumentSpec:
        return InstrumentSpec(self.symbol, _US_FUT, multiplier=self.multiplier, tick_size=self.tick_size)


# Point values / ticks per CME contract specs. proxy_factor is the rough ETF→index scale used only
# for the RTH proxy backtest (index ≈ ETF × factor); it is recalibrated empirically in Phase A.2.
CME_MICROS: dict[str, MicroFuture] = {
    "MES": MicroFuture("MES", "Micro E-mini S&P 500", 5.0, 0.25, proxy_etf="SPY", proxy_factor=10.0),
    "MNQ": MicroFuture("MNQ", "Micro E-mini Nasdaq-100", 2.0, 0.25, proxy_etf="QQQ", proxy_factor=41.0),
    "M2K": MicroFuture("M2K", "Micro E-mini Russell 2000", 5.0, 0.10, proxy_etf="IWM", proxy_factor=10.0),
    "MYM": MicroFuture("MYM", "Micro E-mini Dow", 0.50, 1.0, proxy_etf="DIA", proxy_factor=100.0),
    "MGC": MicroFuture("MGC", "Micro Gold", 10.0, 0.10, proxy_etf="GLD", proxy_factor=10.0),
}


def micro_future(symbol: str) -> MicroFuture:
    """Look up a CME micro by its contract root (e.g. ``"MNQ"``)."""
    try:
        return CME_MICROS[symbol.upper()]
    except KeyError as exc:
        raise KeyError(f"unknown CME micro {symbol!r}; known: {sorted(CME_MICROS)}") from exc


def futures_instrument(symbol: str) -> InstrumentSpec:
    """``InstrumentSpec`` for a CME micro, ready to hand to ``BacktestEngine``."""
    return micro_future(symbol).instrument()
