"""Strategy framework: the event-driven ``BaseStrategy`` ABC + a plug-in registry.

Every strategy bucket (ICT/SMC, momentum, mean-reversion, event) subclasses ``BaseStrategy``
and reacts to bar closes via ``on_bar(ctx) -> Signal | None``. The SAME method runs in the
backtest engine and the live paper loop — there is no second code path to drift out of sync.

Look-ahead is impossible because ``ctx`` (a ``MarketContext``) only ever exposes completed
bars; the strategy cannot reach a future or forming bar.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from src.core.types import MarketContext, Signal, TimeFrame, Trade

# Registry: name -> strategy class. Populated by the @register_strategy decorator so the
# runner can discover strategies with zero manual wiring.
STRATEGY_REGISTRY: dict[str, type["BaseStrategy"]] = {}


def register_strategy(name: str) -> Callable[[type["BaseStrategy"]], type["BaseStrategy"]]:
    """Class decorator that registers a strategy under ``name``."""

    def _decorator(cls: type["BaseStrategy"]) -> type["BaseStrategy"]:
        if name in STRATEGY_REGISTRY:
            raise ValueError(f"strategy name already registered: {name!r}")
        cls.name = name
        STRATEGY_REGISTRY[name] = cls
        return cls

    return _decorator


def get_strategy(name: str) -> type["BaseStrategy"]:
    if name not in STRATEGY_REGISTRY:
        raise KeyError(f"unknown strategy: {name!r}. registered: {sorted(STRATEGY_REGISTRY)}")
    return STRATEGY_REGISTRY[name]


def list_strategies() -> list[str]:
    return sorted(STRATEGY_REGISTRY)


class BaseStrategy(ABC):
    """Event-driven strategy base.

    Subclasses declare the timeframes they need and implement ``on_bar``. They may hold
    internal state (e.g. a setup state machine) between bars — this is encouraged and mirrors
    how the strategy would run live.
    """

    #: Set by @register_strategy.
    name: str = "base"

    #: Timeframes this strategy reads, low → high (e.g. [M5, M15, H1] for ICT).
    required_timeframes: list[TimeFrame] = []

    def __init__(self, params: Optional[dict[str, Any]] = None) -> None:
        self.params: dict[str, Any] = {**self.default_params(), **(params or {})}

    # --- overridable hooks -------------------------------------------------

    @classmethod
    def default_params(cls) -> dict[str, Any]:
        """Default parameter values; merged with any overrides at construction."""
        return {}

    @classmethod
    def param_space(cls) -> dict[str, list[Any]]:
        """Grid of parameter values walk-forward optimization searches over.

        Returns {param_name: [candidate values]}. Empty ⇒ no optimization.
        """
        return {}

    def on_start(self, ctx: MarketContext) -> None:
        """Optional warm-up / state initialization before the first ``on_bar``."""

    def on_fill(self, trade: Trade) -> None:
        """Optional hook called when an order originating from this strategy fills."""

    # --- the contract ------------------------------------------------------

    @abstractmethod
    def on_bar(self, ctx: MarketContext) -> Optional[Signal]:
        """Called once per low-timeframe bar close. Return at most one Signal, or None."""
