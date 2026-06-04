"""India market cost presets. Statutory rates as of 2025 (overridable in settings).

India equity costs are heavy and differ by *product* (delivery vs intraday): STT, stamp duty,
exchange transaction charges, SEBI turnover fee, 18% GST on (brokerage+exchange+SEBI), plus a flat
DP charge on delivery sells. Brokerage defaults to the discount-broker model (delivery free,
intraday min(0.03%, ₹20)). Verify against your actual broker before live.
"""

from __future__ import annotations

from src.backtest.costs.components import (
    AtrSlippage,
    BpsSpread,
    FlatFee,
    GST,
    PercentCharge,
    PercentNotionalCommission,
)
from src.backtest.costs.core import CostModel, Product


def india_equity(
    product: Product = Product.DELIVERY,
    *,
    half_spread_bps: float = 3.0,
    slippage_atr_mult: float = 0.08,
    slippage_stress: float = 1.0,
    # statutory (turnover %, as fractions)
    stt_delivery: float = 0.001,        # 0.1% buy+sell
    stt_intraday_sell: float = 0.00025,  # 0.025% sell only
    stamp_delivery: float = 0.00015,    # 0.015% buy only
    stamp_intraday: float = 0.00003,    # 0.003% buy only
    exchange_txn_pct: float = 0.0000297,  # NSE ~0.00297%
    sebi_pct: float = 0.000001,         # ₹10 per crore
    gst_rate: float = 0.18,
    # brokerage (discount-broker defaults)
    brokerage_pct_intraday: float = 0.0003,  # 0.03%
    brokerage_cap_intraday: float = 20.0,    # ₹20 / order
    dp_charge: float = 15.0,            # flat ₹ on delivery sell
) -> CostModel:
    """India equities, ``delivery`` or ``intraday``. Builds the right component set per product."""
    micro = [BpsSpread(half_spread_bps), AtrSlippage(slippage_atr_mult, stress=slippage_stress)]

    if product is Product.DELIVERY:
        statutory = [
            PercentNotionalCommission(0.0, taxable=True, name="brokerage"),  # delivery free
            PercentCharge("stt", buy_pct=stt_delivery, sell_pct=stt_delivery),
            PercentCharge("stamp_duty", buy_pct=stamp_delivery),
            PercentCharge("exchange_txn", buy_pct=exchange_txn_pct, sell_pct=exchange_txn_pct, taxable=True),
            PercentCharge("sebi", buy_pct=sebi_pct, sell_pct=sebi_pct, taxable=True),
            FlatFee(dp_charge, side="sell", name="dp_charge"),
        ]
    elif product is Product.INTRADAY:
        statutory = [
            PercentNotionalCommission(
                brokerage_pct_intraday, cap=brokerage_cap_intraday, taxable=True, name="brokerage"
            ),
            PercentCharge("stt", sell_pct=stt_intraday_sell),
            PercentCharge("stamp_duty", buy_pct=stamp_intraday),
            PercentCharge("exchange_txn", buy_pct=exchange_txn_pct, sell_pct=exchange_txn_pct, taxable=True),
            PercentCharge("sebi", buy_pct=sebi_pct, sell_pct=sebi_pct, taxable=True),
        ]
    else:
        raise ValueError(f"india_equity supports DELIVERY or INTRADAY, got {product}")

    return CostModel([*micro, *statutory, GST(gst_rate)])  # GST last — taxes the taxable items


def india_fno(*args, **kwargs) -> CostModel:  # extension point
    raise NotImplementedError(
        "India F&O costs not built yet — reuse PercentCharge for STT (futures 0.02% sell, options "
        "0.1% sell premium), exchange/SEBI/stamp, GST, and set the contract multiplier/lot size."
    )
