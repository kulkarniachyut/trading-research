"""Black-Scholes pricing, greeks, and implied-vol solver — the concrete, tested core.

Self-contained (stdlib ``math`` only; normal CDF via ``erf``, no scipy/numpy dependency). All
functions are pure and deterministic. This is the one fully-implemented layer of the options
scaffold; everything above it (data, strategy, backtest) builds on these.

Conventions:
- ``r`` is the continuously-compounded risk-free rate; ``q`` the continuous dividend yield.
- ``t`` is time-to-expiry in YEARS (e.g. 30 calendar days ≈ 30/365).
- ``sigma`` is annualized implied volatility (0.20 = 20%).
- Greeks are returned per the standard conventions: theta per CALENDAR DAY (not per year),
  vega per 1 vol POINT (not per 1.0 of sigma), rho per 1% rate move — the units a trader uses.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

_SQRT2 = math.sqrt(2.0)
_INV_SQRT_2PI = 1.0 / math.sqrt(2.0 * math.pi)


def _norm_cdf(x: float) -> float:
    """Standard normal CDF via the error function (stdlib, no scipy)."""
    return 0.5 * (1.0 + math.erf(x / _SQRT2))


def _norm_pdf(x: float) -> float:
    return _INV_SQRT_2PI * math.exp(-0.5 * x * x)


def _d1_d2(s: float, k: float, t: float, r: float, sigma: float, q: float) -> tuple[float, float]:
    if t <= 0 or sigma <= 0 or s <= 0 or k <= 0:
        raise ValueError("d1/d2 require positive s, k, t, sigma")
    vol_t = sigma * math.sqrt(t)
    d1 = (math.log(s / k) + (r - q + 0.5 * sigma * sigma) * t) / vol_t
    return d1, d1 - vol_t


def bs_price(s: float, k: float, t: float, r: float, sigma: float,
             right: str, q: float = 0.0) -> float:
    """Black-Scholes(-Merton) price of a European option.

    ``right`` is "C"/"call" or "P"/"put". At/over expiry (``t<=0``) returns intrinsic value.
    """
    is_call = right.upper().startswith("C")
    if t <= 0 or sigma <= 0:
        intrinsic = (s - k) if is_call else (k - s)
        return max(intrinsic, 0.0)
    d1, d2 = _d1_d2(s, k, t, r, sigma, q)
    df_r, df_q = math.exp(-r * t), math.exp(-q * t)
    if is_call:
        return s * df_q * _norm_cdf(d1) - k * df_r * _norm_cdf(d2)
    return k * df_r * _norm_cdf(-d2) - s * df_q * _norm_cdf(-d1)


@dataclass(frozen=True, slots=True)
class Greeks:
    delta: float      # dPrice/dSpot
    gamma: float      # d²Price/dSpot²
    theta: float      # dPrice/dt, per CALENDAR DAY (typically negative)
    vega: float       # dPrice/dVol, per 1 vol POINT (1%)
    rho: float        # dPrice/dRate, per 1% rate move


def greeks(s: float, k: float, t: float, r: float, sigma: float,
           right: str, q: float = 0.0) -> Greeks:
    """First-order greeks in trader units (theta/day, vega/point, rho/1%)."""
    is_call = right.upper().startswith("C")
    if t <= 0 or sigma <= 0:
        # at expiry: delta is a step, the rest collapse to ~0
        itm = (s > k) if is_call else (s < k)
        return Greeks(delta=(1.0 if is_call else -1.0) if itm else 0.0,
                      gamma=0.0, theta=0.0, vega=0.0, rho=0.0)
    d1, d2 = _d1_d2(s, k, t, r, sigma, q)
    df_r, df_q = math.exp(-r * t), math.exp(-q * t)
    sqrt_t = math.sqrt(t)
    pdf_d1 = _norm_pdf(d1)

    delta = df_q * (_norm_cdf(d1) if is_call else _norm_cdf(d1) - 1.0)
    gamma = df_q * pdf_d1 / (s * sigma * sqrt_t)
    vega_year = s * df_q * pdf_d1 * sqrt_t                       # per 1.0 of sigma
    # theta per year, then convert to per calendar day
    term1 = -s * df_q * pdf_d1 * sigma / (2.0 * sqrt_t)
    if is_call:
        theta_year = term1 - r * k * df_r * _norm_cdf(d2) + q * s * df_q * _norm_cdf(d1)
        rho_full = k * t * df_r * _norm_cdf(d2)
    else:
        theta_year = term1 + r * k * df_r * _norm_cdf(-d2) - q * s * df_q * _norm_cdf(-d1)
        rho_full = -k * t * df_r * _norm_cdf(-d2)
    return Greeks(delta=delta, gamma=gamma, theta=theta_year / 365.0,
                  vega=vega_year / 100.0, rho=rho_full / 100.0)


def implied_vol(price: float, s: float, k: float, t: float, r: float,
                right: str, q: float = 0.0,
                lo: float = 1e-4, hi: float = 5.0, tol: float = 1e-6) -> float | None:
    """Recover annualized IV from a market price via bisection (robust; no derivative needed).

    Returns None if the price is below intrinsic / outside the no-arbitrage band, or if it does
    not bracket a root in ``[lo, hi]`` vol.
    """
    is_call = right.upper().startswith("C")
    if t <= 0:
        return None
    intrinsic = max((s - k) if is_call else (k - s), 0.0)
    if price < intrinsic - 1e-9:
        return None  # below intrinsic — not arbitrage-free
    f_lo = bs_price(s, k, t, r, lo, right, q) - price
    f_hi = bs_price(s, k, t, r, hi, right, q) - price
    if f_lo * f_hi > 0:
        return None  # price not bracketed by [lo, hi] vol
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        f_mid = bs_price(s, k, t, r, mid, right, q) - price
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return 0.5 * (lo + hi)
