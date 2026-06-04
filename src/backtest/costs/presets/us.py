"""US market cost presets. Rates as of 2025 (overridable)."""

from __future__ import annotations

from src.backtest.costs.components import (
    AtrSlippage,
    BpsSpread,
    PerUnitCommission,
    UsRegFees,
)
from src.backtest.costs.core import CostModel


def us_equity(
    half_spread_bps: float = 1.0,
    slippage_atr_mult: float = 0.05,
    slippage_stress: float = 1.0,
    commission_per_share: float = 0.0,   # ~$0 at modern brokers (Alpaca)
    commission_min: float = 0.0,
    taf_per_share: float = 0.000166,     # FINRA TAF, sells only
    taf_cap: float = 8.30,
    sec_per_million: float = 0.0,        # SEC Sec.31: $0.00/MM from 2025-05-14
) -> CostModel:
    """US equities: tight spread, volatility slippage, ~zero commission, sell-side reg fees."""
    return CostModel(
        [
            BpsSpread(half_spread_bps),
            AtrSlippage(slippage_atr_mult, stress=slippage_stress),
            PerUnitCommission(commission_per_share, minimum=commission_min),
            UsRegFees(taf_per_share=taf_per_share, taf_cap=taf_cap, sec_per_million=sec_per_million),
        ]
    )


def us_equity_options(*args, **kwargs) -> CostModel:  # extension point
    raise NotImplementedError(
        "US options costs not built yet — add PerUnitCommission (per contract), OCC/ORF fees, "
        "and set InstrumentSpec.multiplier=100."
    )


def us_futures(*args, **kwargs) -> CostModel:  # extension point
    raise NotImplementedError(
        "US futures costs not built yet — use PerUnitCommission (per contract), TickSpread, "
        "exchange+NFA fees, and the contract point value as InstrumentSpec.multiplier."
    )
