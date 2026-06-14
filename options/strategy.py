"""Options strategy base — the event-driven contract, mirroring ``src/strategies/base.py``.

A strategy reacts to one decision point (a day/timestamp) via ``on_step(ctx) -> list[OptionOrder]``,
seeing only completed, as-of data through ``ctx``. The SAME method runs in the backtest harness and
(eventually) the live loop — one code path, no drift, look-ahead impossible by construction.

This is the interface + a tiny registry; concrete strategies (covered call, cash-secured put,
short-strangle / vol-risk-premium, calendar, …) are separate files added later.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

from options.contracts import OptionContract, OptionPosition, OptionQuote

STRATEGY_REGISTRY: dict[str, type["OptionStrategy"]] = {}


def register_option_strategy(name: str) -> Callable[[type["OptionStrategy"]], type["OptionStrategy"]]:
    def _deco(cls: type["OptionStrategy"]) -> type["OptionStrategy"]:
        if name in STRATEGY_REGISTRY:
            raise ValueError(f"option strategy already registered: {name!r}")
        cls.name = name
        STRATEGY_REGISTRY[name] = cls
        return cls
    return _deco


@dataclass(frozen=True, slots=True)
class OptionOrder:
    """An intent to trade one contract. ``qty`` is signed (+open long / -open short / opposite to
    close). The harness fills it against the as-of chain through the cost model — never at mid."""

    contract: OptionContract
    qty: int
    intent: str = "open"          # "open" | "close"
    limit: Optional[float] = None  # per-share premium limit; None = take the (cost-adjusted) market
    reason: str = ""


class OptionContext(ABC):
    """What a strategy sees at a decision step — all as-of, no future data."""

    @property
    @abstractmethod
    def now(self) -> datetime: ...

    @property
    @abstractmethod
    def underlying_price(self) -> float: ...

    @abstractmethod
    def chain(self, expiries=None) -> list[OptionQuote]:
        """The current option chain for the traded underlying as of ``now``."""

    @property
    @abstractmethod
    def positions(self) -> list[OptionPosition]: ...

    @property
    @abstractmethod
    def equity(self) -> float: ...


class OptionStrategy(ABC):
    """Event-driven options strategy base. Declare params; implement ``on_step``."""

    name: str = "base_option"

    def __init__(self, params: Optional[dict[str, Any]] = None) -> None:
        self.params: dict[str, Any] = {**self.default_params(), **(params or {})}

    @classmethod
    def default_params(cls) -> dict[str, Any]:
        return {}

    @classmethod
    def param_space(cls) -> dict[str, list[Any]]:
        """Grid for walk-forward ablation (theory-led defaults preferred; this is for robustness
        checks, not curve-fitting — a real edge varies smoothly with a threshold)."""
        return {}

    def on_start(self, ctx: OptionContext) -> None:
        """Optional warm-up before the first step."""

    @abstractmethod
    def on_step(self, ctx: OptionContext) -> list[OptionOrder]:
        """The decision: given the as-of chain + current positions, return orders (possibly empty)."""


def get_option_strategy(name: str) -> type[OptionStrategy]:
    if name not in STRATEGY_REGISTRY:
        raise KeyError(f"unknown option strategy {name!r}; registered: {sorted(STRATEGY_REGISTRY)}")
    return STRATEGY_REGISTRY[name]
