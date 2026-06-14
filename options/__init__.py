"""Options research module — self-contained, truth-machine-disciplined.

Everything options lives under this folder: pricing/greeks, contract & chain types, a brutal
options cost model, the data-provider contract, the strategy base, and the backtest harness.
It deliberately mirrors the main repo's discipline (no look-ahead; every backtest applies costs;
report OOS separately; validate with walk-forward + Monte Carlo) — see ``options/README.md``.

Nothing here is an edge yet — this is the scaffold. The pricing layer is fully implemented and
tested; data/strategy/backtest are interfaces + skeletons awaiting a concrete strategy + a real
historical-options data source (the genuine hard part — see README §Data reality).
"""

from options.contracts import OptionContract, OptionQuote, Right
from options.pricing import bs_price, greeks, implied_vol

__all__ = ["OptionContract", "OptionQuote", "Right", "bs_price", "greeks", "implied_vol"]
