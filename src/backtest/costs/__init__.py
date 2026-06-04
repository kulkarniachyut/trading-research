"""Composable, country-grouped cost model.

A ``CostModel`` is an ordered list of pluggable cost components applied to every fill. Build one
per market with the preset registry:

    from src.backtest.costs import cost_model, FillContext, InstrumentSpec, Market, AssetClass
    model = cost_model("US", "equity")                 # or cost_model_from_settings()
    res = model.apply(FillContext(side="buy", qty=100, price=755.0, atr=0.4, instrument=spec))
    res.fill_price, res.cost, res.breakdown
"""

from src.backtest.costs.core import (
    AssetClass,
    CostComponent,
    CostItem,
    CostKind,
    CostModel,
    FillContext,
    FillResult,
    InstrumentSpec,
    Market,
    Product,
)
from src.backtest.costs.presets import cost_model, cost_model_from_settings

__all__ = [
    "AssetClass",
    "Product",
    "Market",
    "InstrumentSpec",
    "FillContext",
    "FillResult",
    "CostItem",
    "CostKind",
    "CostComponent",
    "CostModel",
    "cost_model",
    "cost_model_from_settings",
]
