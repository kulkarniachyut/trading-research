"""Tests for the options pricing core — the one fully-implemented layer.

Validates against properties that MUST hold for any correct Black-Scholes implementation:
put-call parity, intrinsic-value bounds, greek signs/magnitudes, and IV round-trip. If these
pass, the pricing is trustworthy; everything else in the module builds on it.
"""

from __future__ import annotations

import math

import pytest

from options.pricing import bs_price, greeks, implied_vol

# A representative ATM-ish contract: S=100, K=100, 30d, 4% rate, 20% vol.
S, K, T, R, SIG = 100.0, 100.0, 30 / 365, 0.04, 0.20


def test_put_call_parity() -> None:
    # C - P == S*e^{-qT} - K*e^{-rT}   (q=0 here)
    c = bs_price(S, K, T, R, SIG, "C")
    p = bs_price(S, K, T, R, SIG, "P")
    assert c - p == pytest.approx(S - K * math.exp(-R * T), abs=1e-9)


def test_price_within_no_arbitrage_bounds() -> None:
    c = bs_price(S, K, T, R, SIG, "C")
    p = bs_price(S, K, T, R, SIG, "P")
    assert 0 < c < S                       # call worth less than the stock
    assert 0 < p < K                       # put worth less than the strike
    # deep ITM call ≈ intrinsic (+ small time value); deep OTM ≈ ~0
    assert bs_price(150, 100, T, R, SIG, "C") > 49
    assert bs_price(50, 100, T, R, SIG, "C") < 0.5


def test_expiry_returns_intrinsic() -> None:
    assert bs_price(110, 100, 0, R, SIG, "C") == pytest.approx(10.0)
    assert bs_price(90, 100, 0, R, SIG, "C") == 0.0
    assert bs_price(90, 100, 0, R, SIG, "P") == pytest.approx(10.0)


def test_greek_signs_and_bounds() -> None:
    gc = greeks(S, K, T, R, SIG, "C")
    gp = greeks(S, K, T, R, SIG, "P")
    assert 0 < gc.delta < 1 and -1 < gp.delta < 0       # call +, put -
    assert gc.delta - gp.delta == pytest.approx(math.exp(0) , abs=0.02)  # call_delta - put_delta ≈ 1
    assert gc.gamma > 0 and gp.gamma == pytest.approx(gc.gamma)          # gamma same for C/P
    assert gc.vega > 0 and gp.vega == pytest.approx(gc.vega)             # vega same, positive
    assert gc.theta < 0                                                  # long call decays
    # ATM call delta is near 0.5
    assert gc.delta == pytest.approx(0.5, abs=0.1)


def test_vega_units_per_point() -> None:
    # bumping vol by 1 point (0.20 -> 0.21) should change price by ~vega
    base = bs_price(S, K, T, R, SIG, "C")
    bumped = bs_price(S, K, T, R, SIG + 0.01, "C")
    assert bumped - base == pytest.approx(greeks(S, K, T, R, SIG, "C").vega, abs=0.02)


def test_implied_vol_round_trip() -> None:
    for right in ("C", "P"):
        for k in (90.0, 100.0, 110.0):
            price = bs_price(S, k, T, R, 0.27, right)
            iv = implied_vol(price, S, k, T, R, right)
            assert iv == pytest.approx(0.27, abs=1e-4)


def test_implied_vol_below_intrinsic_returns_none() -> None:
    # a price under intrinsic is not arbitrage-free -> no IV
    assert implied_vol(1.0, 120, 100, T, R, "C") is None
