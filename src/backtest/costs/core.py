"""Cost-model core: the contracts every cost component and preset speaks.

A ``CostModel`` is just an ordered list of pluggable ``CostComponent`` objects. Each component
turns a fill into one ``CostItem`` (or None if it doesn't apply). This makes costs **composable**:
add/modify/delete a line item by editing the list, and assemble different models per
country x asset-class x product (see ``presets/``). The engine only ever calls ``apply()``.

Two kinds of cost:
- PRICE — moves the *fill price* against you (spread, slippage), per unit.
- CASH  — a flat charge in account currency (commission, taxes, fees).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Literal, Optional, Protocol, runtime_checkable

FillSide = Literal["buy", "sell"]


class AssetClass(str, Enum):
    EQUITY = "equity"
    FUTURE = "future"
    OPTION = "option"
    CRYPTO = "crypto"


class Product(str, Enum):
    DELIVERY = "delivery"     # equities held (cash/positional)
    INTRADAY = "intraday"     # equities squared off same day
    FUTURES = "futures"
    OPTIONS = "options"


class CostKind(str, Enum):
    PRICE = "price"
    CASH = "cash"


@dataclass(frozen=True, slots=True)
class Market:
    """Where/what is traded — the axis along which cost schedules differ."""

    country: str                       # "US", "IN"
    asset_class: AssetClass
    product: Product = Product.INTRADAY


@dataclass(frozen=True, slots=True)
class InstrumentSpec:
    symbol: str
    market: Market
    multiplier: float = 1.0            # 1 equity share; 100 option; point value for futures
    tick_size: Optional[float] = None
    currency: str = "USD"


@dataclass(frozen=True, slots=True)
class FillContext:
    """Everything a cost component might need about a single fill."""

    side: FillSide
    qty: float
    price: float
    instrument: InstrumentSpec
    atr: Optional[float] = None        # for volatility-scaled slippage
    volume: Optional[float] = None     # for participation/impact
    holding_hours: Optional[float] = None  # for funding / borrow

    @property
    def notional(self) -> float:
        return abs(self.qty) * self.price * self.instrument.multiplier


@dataclass(frozen=True, slots=True)
class CostItem:
    name: str
    kind: CostKind
    amount: float                      # PRICE: per-unit price delta; CASH: currency amount
    taxable: bool = False              # subject to GST (India) — read by the GST component


@runtime_checkable
class CostComponent(Protocol):
    name: str

    def compute(self, ctx: FillContext, prior: list[CostItem]) -> Optional[CostItem]:
        """Return this component's charge for ``ctx`` (or None if N/A). ``prior`` holds the items
        already computed this fill, so meta-charges (e.g. GST on other fees) can read them."""
        ...


@dataclass(frozen=True, slots=True)
class FillResult:
    fill_price: float                  # price after PRICE adjustments (moved against you)
    cost: float                        # total cost in account currency (price_cost + cash_cost)
    breakdown: dict[str, float]        # component name -> currency cost
    items: tuple[CostItem, ...]
    price_cost: float = 0.0            # spread+slippage already reflected in fill_price
    cash_cost: float = 0.0             # commissions/taxes/fees charged separately


@dataclass
class CostModel:
    """An ordered set of cost components. Order matters (e.g. GST runs last)."""

    components: list[CostComponent]

    def apply(self, ctx: FillContext) -> FillResult:
        items: list[CostItem] = []
        for comp in self.components:
            item = comp.compute(ctx, items)
            if item is not None and item.amount != 0.0:
                items.append(item)

        direction = 1.0 if ctx.side == "buy" else -1.0
        mult = ctx.instrument.multiplier
        per_unit_price = sum(it.amount for it in items if it.kind is CostKind.PRICE)
        fill_price = ctx.price + direction * per_unit_price

        breakdown: dict[str, float] = {}
        price_cost = 0.0
        cash_cost = 0.0
        for it in items:
            if it.kind is CostKind.PRICE:
                dollars = it.amount * abs(ctx.qty) * mult
                price_cost += dollars
            else:
                dollars = it.amount
                cash_cost += dollars
            breakdown[it.name] = breakdown.get(it.name, 0.0) + dollars
        return FillResult(
            fill_price=fill_price,
            cost=price_cost + cash_cost,
            breakdown=breakdown,
            items=tuple(items),
            price_cost=price_cost,
            cash_cost=cash_cost,
        )

    def with_slippage_stress(self, factor: float) -> "CostModel":
        """Return a copy with slippage scaled by ``factor`` (the Step-3 cost-fragility stress)."""
        from src.backtest.costs.components import AtrSlippage

        scaled = [
            replace(c, stress=c.stress * factor) if isinstance(c, AtrSlippage) else c
            for c in self.components
        ]
        return CostModel(scaled)
