"""Smart Money Concepts (ICT) indicators — normalized wrappers over ``smartmoneyconcepts`` plus the
``causal_apply`` bridge that makes their (repainting) output look-ahead-safe.

Use the wrappers inside the event-driven engine on completed-bar windows, or wrap them with
``causal_apply`` to precompute a causal feature column. See ``indicators.py`` for the causality
contract.
"""

from src.indicators.smc.causal import causal_apply
from src.indicators.smc.indicators import (
    bos_choch,
    fvg,
    liquidity,
    order_blocks,
    previous_high_low,
    swings,
)

__all__ = [
    "swings",
    "fvg",
    "bos_choch",
    "order_blocks",
    "liquidity",
    "previous_high_low",
    "causal_apply",
]
