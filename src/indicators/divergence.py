"""Generic regular/hidden divergence detection — reusable across any oscillator.

A divergence compares the slope of an **oscillator** against the slope of **price** between two
consecutive confirmed pivots:

- **Regular bullish** — price makes a lower low, oscillator makes a higher low (downtrend weakening).
- **Hidden bullish**  — price makes a higher low, oscillator makes a lower low (uptrend continuation).
- **Regular bearish** — price makes a higher high, oscillator makes a lower high.
- **Hidden bearish**  — price makes a lower high, oscillator makes a higher high.

Pivots come from ``pivots.py`` (confirmed ``right`` bars late), so every divergence flag is emitted
at the **confirmation bar** and is therefore causal. Works on WaveTrend, RSI, MACD — any oscillator.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.indicators.pivots import pivots


def find_divergences(
    oscillator: pd.Series,
    price: pd.Series,
    left: int = 3,
    right: int = 3,
) -> pd.DataFrame:
    """Detect divergences between ``oscillator`` and ``price``. Pivots are found on the oscillator;
    ``price`` is sampled at the same pivot bars. Returns a boolean DataFrame aligned to the index
    with columns ``regular_bullish, hidden_bullish, regular_bearish, hidden_bearish``.
    """
    idx = oscillator.index
    n = len(idx)
    osc = oscillator.to_numpy(dtype=float)
    px = price.to_numpy(dtype=float)

    cols = ["regular_bullish", "hidden_bullish", "regular_bearish", "hidden_bearish"]
    out = {c: np.zeros(n, dtype=bool) for c in cols}

    lows = pivots(oscillator, left, right, high=False)
    highs = pivots(oscillator, left, right, high=True)

    # --- bullish: compare consecutive pivot LOWS ---
    prev = None  # (osc_at_pivot, price_at_pivot)
    for j in range(n):
        i = lows["src_pos"].iloc[j]
        if np.isnan(i):
            continue
        i = int(i)
        osc_now, px_now = osc[i], px[i]
        if prev is not None:
            osc_prev, px_prev = prev
            if px_now < px_prev and osc_now > osc_prev:
                out["regular_bullish"][j] = True
            elif px_now > px_prev and osc_now < osc_prev:
                out["hidden_bullish"][j] = True
        prev = (osc_now, px_now)

    # --- bearish: compare consecutive pivot HIGHS ---
    prev = None
    for j in range(n):
        i = highs["src_pos"].iloc[j]
        if np.isnan(i):
            continue
        i = int(i)
        osc_now, px_now = osc[i], px[i]
        if prev is not None:
            osc_prev, px_prev = prev
            if px_now > px_prev and osc_now < osc_prev:
                out["regular_bearish"][j] = True
            elif px_now < px_prev and osc_now > osc_prev:
                out["hidden_bearish"][j] = True
        prev = (osc_now, px_now)

    return pd.DataFrame(out, index=idx)
