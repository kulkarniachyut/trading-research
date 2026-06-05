"""SMT (Smart Money Technique) divergence — Phase C confluence.

Two correlated instruments (ES↔NQ, SPY↔QQQ, BTC↔ETH) should make matching highs/lows. When one
sweeps a liquidity extreme and its correlate **fails to confirm**, that non-confirmation is
institutional divergence — a higher-quality reversal signal than a sweep alone.

- Bullish SMT: the primary makes a *lower low* (sweeps sellside) while the reference makes a
  *higher low* (doesn't) → accumulation.
- Bearish SMT: the primary makes a *higher high* (sweeps buyside) while the reference makes a
  *lower high* (doesn't) → distribution.

Causal: compares only the bars handed in (the engine supplies completed bars ≤ now for both).
"""

from __future__ import annotations

import pandas as pd


def smt_divergence(
    primary: pd.DataFrame,
    reference: pd.DataFrame,
    direction: int,
    lookback: int = 12,
) -> bool:
    """True if a `direction`-aligned SMT divergence holds between `primary` and `reference`.

    Compares the recent window (last ``lookback`` aligned bars) against the prior window: the
    primary must have made the new extreme while the reference did not.
    """
    if primary is None or reference is None or primary.empty or reference.empty:
        return False
    common = primary.index.intersection(reference.index)
    if len(common) < 2 * lookback:
        return False
    p = primary.loc[common]
    r = reference.loc[common]
    recent_p, prior_p = p.iloc[-lookback:], p.iloc[-2 * lookback:-lookback]
    recent_r, prior_r = r.iloc[-lookback:], r.iloc[-2 * lookback:-lookback]

    if direction == 1:  # bullish: primary made a lower low, reference held higher
        primary_lower_low = recent_p["low"].min() < prior_p["low"].min()
        reference_held = recent_r["low"].min() >= prior_r["low"].min()
        return bool(primary_lower_low and reference_held)
    if direction == -1:  # bearish: primary made a higher high, reference held lower
        primary_higher_high = recent_p["high"].max() > prior_p["high"].max()
        reference_held = recent_r["high"].max() <= prior_r["high"].max()
        return bool(primary_higher_high and reference_held)
    return False
