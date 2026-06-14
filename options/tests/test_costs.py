"""Tests for the options cost model — the part that keeps backtests honest.

Confirms the spread always works against the trader, commissions are charged per contract, and
the round-trip drag % (the go/no-go filter) is computed correctly.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from options.contracts import OptionContract, OptionQuote, Right
from options.costs import OptionsCostModel


def _quote(bid: float, ask: float) -> OptionQuote:
    c = OptionContract("SPY", date(2024, 6, 21), 500.0, Right.PUT)
    return OptionQuote(contract=c, asof=datetime(2024, 5, 1), bid=bid, ask=ask)


def test_buy_fills_above_mid_sell_below() -> None:
    m = OptionsCostModel()
    q = _quote(1.00, 1.20)            # mid 1.10, half-spread 0.10
    assert m.fill_price(q, "buy") == pytest.approx(1.20)   # mid + half = ask
    assert m.fill_price(q, "sell") == pytest.approx(1.00)  # mid - half = bid


def test_partial_spread_fraction() -> None:
    m = OptionsCostModel(spread_fraction=0.5)
    q = _quote(1.00, 1.20)
    assert m.fill_price(q, "buy") == pytest.approx(1.15)   # mid + 0.5*half
    assert m.fill_price(q, "sell") == pytest.approx(1.05)


def test_cash_cost_per_contract() -> None:
    m = OptionsCostModel(commission_per_contract=0.65, exchange_fee_per_contract=0.05)
    assert m.cash_cost(3) == pytest.approx(3 * 0.70)
    assert m.cash_cost(0) == 0.0


def test_round_trip_drag_pct_flags_thin_premium() -> None:
    m = OptionsCostModel()
    # wide spread relative to premium -> big drag. mid 1.10, spread 0.20, mult 100.
    q = _quote(1.00, 1.20)
    drag = m.round_trip_drag_pct(q, qty=1)
    # spread cost = 0.20*100 = $20 on $110 premium -> ~18%+ before commissions
    assert drag > 0.18
    # a tight, rich option should have far lower drag
    q2 = _quote(5.00, 5.05)          # mid 5.025, spread 0.05, premium $502
    assert m.round_trip_drag_pct(q2, qty=1) < 0.02
