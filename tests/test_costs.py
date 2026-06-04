"""Checkpoint 2.3 — the composable, country-grouped cost model.

Covers: US equity (spread/slippage/reg-fees, multiplier scaling), India equity delivery & intraday
(STT/stamp/exchange/SEBI/GST/brokerage/DP with worked numbers), crypto %-notional, the slippage
stress knob, and the preset registry + settings loader.
"""

from __future__ import annotations

import pytest

from src.backtest.costs import (
    AssetClass,
    CostModel,
    FillContext,
    InstrumentSpec,
    Market,
    Product,
    cost_model,
    cost_model_from_settings,
)
from src.backtest.costs.presets.india import india_equity
from src.backtest.costs.presets.us import us_equity


def spec(country, asset=AssetClass.EQUITY, product=Product.INTRADAY, multiplier=1.0, currency="USD"):
    return InstrumentSpec("X", Market(country, asset, product), multiplier=multiplier, currency=currency)


def fill(side, qty, price, instrument, atr=None):
    return FillContext(side=side, qty=qty, price=price, instrument=instrument, atr=atr)


# --- US equity -------------------------------------------------------------

def test_us_equity_buy_fills_high_sell_fills_low():
    m = us_equity()  # 1bp half-spread, 0.05*ATR slippage, $0 commission
    inst = spec("US")
    buy = m.apply(fill("buy", 100, 755.0, inst, atr=0.4))
    sell = m.apply(fill("sell", 100, 755.0, inst, atr=0.4))

    # spread 0.0755 + slippage 0.02 per share, adverse on both sides
    assert buy.fill_price == pytest.approx(755.0955)
    assert sell.fill_price == pytest.approx(754.9045)
    assert buy.breakdown["spread"] == pytest.approx(7.55)
    assert buy.breakdown["slippage"] == pytest.approx(2.0)
    # sell-side FINRA TAF only; round trip is never free
    assert sell.breakdown["reg_fees"] == pytest.approx(100 * 0.000166)
    assert buy.cost + sell.cost > 0


def test_multiplier_scales_price_costs():
    m = us_equity(commission_per_share=0.0)
    inst = spec("US", asset=AssetClass.OPTION, multiplier=100.0)
    res = m.apply(fill("buy", 1, 10.0, inst, atr=0.0))
    # spread 1bp * 10 = 0.001/unit, x1 contract x100 multiplier = 0.1
    assert res.breakdown["spread"] == pytest.approx(0.1)


# --- India equity (the heavy one) -----------------------------------------

def test_india_delivery_buy_breakdown():
    m = india_equity(Product.DELIVERY)
    inst = spec("IN", product=Product.DELIVERY, currency="INR")
    r = m.apply(fill("buy", 100, 100.0, inst, atr=1.0))  # notional 10,000

    assert r.breakdown["stt"] == pytest.approx(10.0)            # 0.1% both sides
    assert r.breakdown["stamp_duty"] == pytest.approx(1.5)      # 0.015% buy
    assert r.breakdown["exchange_txn"] == pytest.approx(0.297)
    assert r.breakdown["sebi"] == pytest.approx(0.01)
    assert r.breakdown["gst"] == pytest.approx(0.18 * (0.297 + 0.01))  # GST on taxable charges
    assert "dp_charge" not in r.breakdown                       # sell-only
    assert "brokerage" not in r.breakdown                       # delivery is free -> 0 -> dropped
    assert r.cost == pytest.approx(11.0 + 11.86226)             # price(3+8) + cash


def test_india_delivery_sell_has_stt_and_dp():
    m = india_equity(Product.DELIVERY)
    inst = spec("IN", product=Product.DELIVERY, currency="INR")
    r = m.apply(fill("sell", 100, 100.0, inst, atr=1.0))
    assert r.breakdown["stt"] == pytest.approx(10.0)
    assert r.breakdown["dp_charge"] == pytest.approx(15.0)


def test_india_intraday_stt_sell_only_and_brokerage_cap():
    m = india_equity(Product.INTRADAY)
    inst = spec("IN", product=Product.INTRADAY, currency="INR")

    buy = m.apply(fill("buy", 100, 100.0, inst, atr=1.0))       # notional 10,000
    assert "stt" not in buy.breakdown                           # intraday STT is sell-only
    assert buy.breakdown["brokerage"] == pytest.approx(3.0)     # 0.03% of 10,000

    big = m.apply(fill("buy", 100_000, 100.0, inst, atr=1.0))   # notional 10,000,000
    assert big.breakdown["brokerage"] == pytest.approx(20.0)    # capped at ₹20


# --- crypto + stress -------------------------------------------------------

def test_crypto_percent_notional_commission():
    m = cost_model("US", "crypto")  # crypto is country-agnostic
    inst = spec("US", asset=AssetClass.CRYPTO)
    r = m.apply(fill("buy", 2, 50_000.0, inst, atr=500.0))      # notional 100,000
    assert r.breakdown["commission"] == pytest.approx(100.0)    # 0.10%


def test_slippage_stress_doubles_slippage():
    inst = spec("US")
    base = us_equity().apply(fill("buy", 100, 755.0, inst, atr=0.4)).breakdown["slippage"]
    stressed = us_equity().with_slippage_stress(2.0).apply(fill("buy", 100, 755.0, inst, atr=0.4)).breakdown["slippage"]
    assert stressed == pytest.approx(2 * base)


# --- registry + settings ---------------------------------------------------

def test_registry_dispatch_and_unknown_raises():
    assert isinstance(cost_model("US", "equity"), CostModel)
    assert isinstance(cost_model("IN", "equity", "delivery"), CostModel)
    with pytest.raises(NotImplementedError):
        cost_model("JP", "equity")


def test_from_settings_default_is_us_equity():
    m = cost_model_from_settings()  # default_market in settings.yaml = US/equity/intraday
    inst = spec("US")
    res = m.apply(fill("buy", 10, 100.0, inst, atr=0.5))
    assert res.cost > 0 and "spread" in res.breakdown


def test_from_settings_flattens_india_product_block():
    settings = {
        "costs": {
            "default_market": {"country": "India", "asset_class": "equity", "product": "delivery"},
            "India": {"equity": {
                "half_spread_bps": 3.0, "slippage_atr_mult": 0.08,
                "exchange_txn_pct": 0.0000297, "sebi_pct": 0.000001, "gst_rate": 0.18,
                "delivery": {"stt_delivery": 0.001, "stamp_delivery": 0.00015, "dp_charge": 15.0},
                "intraday": {"stt_intraday_sell": 0.00025, "stamp_intraday": 0.00003,
                             "brokerage_pct_intraday": 0.0003, "brokerage_cap_intraday": 20.0},
            }},
        }
    }
    m = cost_model_from_settings(settings)
    inst = spec("IN", product=Product.DELIVERY, currency="INR")
    r = m.apply(fill("sell", 100, 100.0, inst, atr=1.0))
    assert r.breakdown["stt"] == pytest.approx(10.0)
    assert r.breakdown["dp_charge"] == pytest.approx(15.0)
