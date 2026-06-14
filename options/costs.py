"""Options cost model — and a loud warning, because options costs are BRUTAL.

The single most common reason retail options backtests lie: they fill at the mid and ignore the
bid/ask spread. For options the spread is the dominant cost and it is *enormous* relative to
equities — a liquid SPY weekly might be 1-3% of mid, an illiquid single-name 10-30%. Charging
half-spread per side on a round trip routinely costs 5-40% of the premium, which silently
converts a "winning" strategy into a losing one. This module makes that cost explicit and
unavoidable, exactly as the equity engine does (CLAUDE.md: every backtest applies the cost model).

A fill is modelled as: cross half the quoted spread (PRICE impact) + per-contract commission +
exchange/regulatory fees (CASH). Assignment/exercise fees are separate. Defaults model a modern
retail broker; everything is overridable.
"""

from __future__ import annotations

from dataclasses import dataclass

from options.contracts import OptionQuote


@dataclass(frozen=True, slots=True)
class OptionsCostModel:
    """Per-fill options costs. ``spread_fraction`` is how much of the quoted half-spread you
    actually pay (1.0 = cross the full half-spread, the honest default; <1 models resting a
    limit and getting price improvement — justify it before lowering)."""

    commission_per_contract: float = 0.65    # typical US retail (e.g. $0.65/contract)
    exchange_fee_per_contract: float = 0.05  # OCC/ORF/exchange, approx
    spread_fraction: float = 1.0             # cross the full half-spread per side (conservative)
    min_ticket: float = 0.0

    def fill_price(self, quote: OptionQuote, side: str) -> float:
        """Per-share fill premium for ``side`` ("buy"/"sell"), crossing the half-spread from mid.
        Buys fill above mid, sells below — the spread always works against you."""
        half = 0.5 * quote.spread * self.spread_fraction
        return quote.mid + half if side == "buy" else quote.mid - half

    def cash_cost(self, qty: int, multiplier: int = 100) -> float:
        """Commission + fees for ``abs(qty)`` contracts (always a debit)."""
        n = abs(qty)
        c = n * (self.commission_per_contract + self.exchange_fee_per_contract)
        return max(c, self.min_ticket) if n else 0.0

    def round_trip_drag_pct(self, quote: OptionQuote, qty: int = 1) -> float:
        """Estimated round-trip cost as a fraction of entry PREMIUM — the number that decides
        whether an options edge can survive. Combines the full spread (both sides) + commissions.
        Use this as a first-pass filter: if the gross edge < this, the strategy is dead."""
        premium = quote.mid * quote.contract.multiplier * abs(qty)
        if premium <= 0:
            return float("inf")
        spread_cost = quote.spread * self.spread_fraction * quote.contract.multiplier * abs(qty)
        return (spread_cost + 2 * self.cash_cost(qty, quote.contract.multiplier)) / premium
