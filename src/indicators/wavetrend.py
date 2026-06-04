"""WaveTrend oscillator (LazyBear / VuManChu) — a reusable momentum oscillator.

Standalone on purpose: WaveTrend is useful well beyond Cipher B (momentum entries, exit timing,
divergence source). Every step is an EMA/SMA over trailing bars, so it is **causal** by
construction (proven in tests via the causality guard).

    ap   = (high + low + close) / 3
    esa  = EMA(ap, channel_len)
    d    = EMA(|ap - esa|, channel_len)
    ci   = (ap - esa) / (0.015 * d)
    wt1  = EMA(ci, average_len)
    wt2  = SMA(wt1, ma_len)

Defaults are VuManChu's Cipher B values (9 / 12 / 3).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import talib


def wavetrend(
    df: pd.DataFrame,
    channel_len: int = 9,
    average_len: int = 12,
    ma_len: int = 3,
) -> pd.DataFrame:
    """Return WaveTrend lines as a DataFrame with columns ``wt1`` and ``wt2`` (aligned to df)."""
    ap = ((df["high"] + df["low"] + df["close"]) / 3.0).to_numpy(dtype=float)
    esa = talib.EMA(ap, timeperiod=channel_len)
    d = talib.EMA(np.abs(ap - esa), timeperiod=channel_len)
    # Guard the divide: where d==0 the channel is flat → treat CI as 0 rather than inf.
    denom = 0.015 * d
    ci = np.where(denom != 0, (ap - esa) / denom, 0.0)
    wt1 = talib.EMA(ci, timeperiod=average_len)
    wt2 = talib.SMA(wt1, timeperiod=ma_len)
    return pd.DataFrame({"wt1": wt1, "wt2": wt2}, index=df.index)
