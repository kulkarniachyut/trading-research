"""Causal bridge for repainting indicators.

Some indicators (SMC swings/structure especially) are only correct *in hindsight* — recomputing
them on the full series rewrites past bars (they "repaint"). ``causal_apply`` makes any such
function safe to precompute as a feature column by doing exactly what the live engine does: at each
bar ``t`` it calls the function on the bars **up to and including ``t``** and keeps only the value
at ``t``. The result uses no future information, so it passes the causality guard.

This is the formal model of how the event-driven engine consumes SMC (read the current bar of a
past-only window). Use a bounded ``lookback`` so cost stays O(n * lookback) instead of O(n^2);
SMC features depend only on recent structure, so a few hundred bars is plenty.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd


def causal_apply(
    fn: Callable[[pd.DataFrame], pd.DataFrame],
    df: pd.DataFrame,
    *,
    lookback: int | None = None,
    min_bars: int = 3,
) -> pd.DataFrame:
    """Run ``fn`` causally over ``df`` and return its per-bar output aligned to ``df.index``.

    ``fn`` takes an OHLCV frame and returns a DataFrame row-aligned to it; only the **last** row of
    each call is kept. ``lookback`` bounds the window (None = expanding from the start). Bars with
    fewer than ``min_bars`` of history — or where ``fn`` raises on a short window — yield NaN.
    """
    n = len(df)
    last_rows: list[pd.Series | None] = []
    for t in range(n):
        lo = 0 if lookback is None else max(0, t - lookback + 1)
        window = df.iloc[lo : t + 1]
        if len(window) < min_bars:
            last_rows.append(None)
            continue
        try:
            res = fn(window)
            last_rows.append(res.iloc[-1])
        except Exception:
            last_rows.append(None)

    columns = next((r.index for r in last_rows if r is not None), None)
    if columns is None:
        return pd.DataFrame(index=df.index)
    return pd.DataFrame(
        [r if r is not None else pd.Series(index=columns, dtype="float64") for r in last_rows],
        index=df.index,
    )
