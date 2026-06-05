"""US market cost presets. Rates as of 2025 (overridable)."""

from __future__ import annotations

from src.backtest.costs.components import (
    AtrSlippage,
    BpsSpread,
    PerUnitCommission,
    TickSpread,
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


def us_futures(
    half_spread_ticks: float = 0.5,      # micros quote ~1 tick wide; half-spread per side
    slippage_atr_mult: float = 0.05,
    slippage_stress: float = 1.0,
    broker_commission: float = 0.0,      # Robinhood futures: $0 broker commission
    exchange_fee: float = 0.37,          # CME micro exchange + clearing + NFA, per contract per side
) -> CostModel:
    """US index-futures micros (MES/MNQ…). P&L scales by the contract point value, carried on
    ``InstrumentSpec.multiplier`` (MES $5/pt, MNQ $2/pt) — see ``src/backtest/instruments.py``.
    Costs: tick-wide spread + volatility slippage (PRICE), $0 broker commission, and the
    per-contract CME+NFA fee (CASH). Defaults model Robinhood micros; everything is overridable."""
    return CostModel(
        [
            TickSpread(half_spread_ticks),
            AtrSlippage(slippage_atr_mult, stress=slippage_stress),
            PerUnitCommission(broker_commission, name="commission"),
            PerUnitCommission(exchange_fee, name="exchange_fee"),
        ]
    )
