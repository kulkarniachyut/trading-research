"""Wolfpack ID oscillator (Darrell Fischer) — a reusable momentum oscillator.

Per the indicator's own author and the open-source clones, "Wolfpack ID" is simply a MACD line
with Fibonacci 3/8 settings: ``EMA(close, 3) - EMA(close, 8)``. It is colored GREEN above the zero
line (bullish momentum) and RED below (bearish). A "green crossing" — the buy trigger used in the
VMC multi-timeframe playbook — is the oscillator crossing UP through zero.

Both EMAs are trailing, so the oscillator is **causal** by construction (proven in tests).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import talib


def wolfpack(df: pd.DataFrame, fast: int = 3, slow: int = 8) -> pd.Series:
    """Wolfpack ID = EMA(close, fast) - EMA(close, slow). > 0 is green (bullish), < 0 is red."""
    close = df["close"].to_numpy(dtype=float)
    osc = talib.EMA(close, timeperiod=fast) - talib.EMA(close, timeperiod=slow)
    return pd.Series(osc, index=df.index, name="wolfpack")


def wolfpack_green(df: pd.DataFrame, fast: int = 3, slow: int = 8) -> pd.Series:
    """Boolean: Wolfpack in the green zone (oscillator > 0). NaN warm-up treated as False."""
    osc = wolfpack(df, fast=fast, slow=slow)
    return (osc > 0) & np.isfinite(osc)
