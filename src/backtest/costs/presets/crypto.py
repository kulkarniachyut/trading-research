"""Crypto cost presets (country-agnostic) — proof that the model extends past equities."""

from __future__ import annotations

from src.backtest.costs.components import (
    AtrSlippage,
    BpsSpread,
    FundingRate,
    PercentNotionalCommission,
)
from src.backtest.costs.core import CostModel


def crypto_spot(
    taker_pct: float = 0.001,          # 0.10% taker fee
    half_spread_bps: float = 2.0,
    slippage_atr_mult: float = 0.10,   # thinner books -> more slippage
    slippage_stress: float = 1.0,
) -> CostModel:
    return CostModel(
        [
            BpsSpread(half_spread_bps),
            AtrSlippage(slippage_atr_mult, stress=slippage_stress),
            PercentNotionalCommission(taker_pct, name="commission"),
        ]
    )


def crypto_perp(funding_per_8h: float = 0.0001, **spot_kwargs) -> CostModel:
    model = crypto_spot(**spot_kwargs)
    model.components.append(FundingRate(funding_per_8h))
    return model
