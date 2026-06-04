"""Preset registry — dispatch ``(country, asset_class, product)`` to the right cost model, and
build one from ``settings.yaml``."""

from __future__ import annotations

from typing import Any

from src.backtest.costs.core import AssetClass, CostModel, Product
from src.backtest.costs.presets import crypto, india, us

_US = {"US", "USA"}
_IN = {"IN", "INDIA"}


def cost_model(
    country: str,
    asset_class: str | AssetClass,
    product: str | Product = Product.INTRADAY,
    **overrides: Any,
) -> CostModel:
    """Return the cost model for a market. ``**overrides`` are passed to the preset."""
    ac = AssetClass(asset_class)
    prod = Product(product)
    c = country.upper()

    if ac is AssetClass.CRYPTO:
        return crypto.crypto_spot(**overrides)
    if c in _US:
        if ac is AssetClass.EQUITY:
            return us.us_equity(**overrides)
        if ac is AssetClass.OPTION:
            return us.us_equity_options(**overrides)
        if ac is AssetClass.FUTURE:
            return us.us_futures(**overrides)
    if c in _IN:
        if ac is AssetClass.EQUITY:
            return india.india_equity(product=prod, **overrides)
        if ac in (AssetClass.OPTION, AssetClass.FUTURE):
            return india.india_fno(product=prod, **overrides)
    raise NotImplementedError(f"no cost preset for country={country!r} asset={ac.value} product={prod.value}")


def cost_model_from_settings(settings: dict | None = None) -> CostModel:
    """Build the cost model from the ``costs:`` block of ``settings.yaml``.

    Expects ``costs.default_market: {country, asset_class, product}`` and a matching parameter block
    at ``costs.<COUNTRY>.<asset_class>`` (optionally nested by product for India equity).
    """
    if settings is None:
        from src.core.config import load_settings

        settings = load_settings()
    costs = settings.get("costs", {})
    market = costs.get("default_market", {"country": "US", "asset_class": "equity", "product": "intraday"})
    country, asset_class, product = market["country"], market["asset_class"], market.get("product", "intraday")

    params = dict(costs.get(country.upper(), {}).get(asset_class, {}))
    # India equity nests params by product; flatten the selected product up.
    if product in params and isinstance(params[product], dict):
        nested = params.pop(product)
        params = {k: v for k, v in params.items() if not isinstance(v, dict)}
        params.update(nested)
    return cost_model(country, asset_class, product, **params)
