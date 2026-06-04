"""Causal pivot (fractal) detection — a reusable primitive.

A *pivot high* at bar ``i`` is a local maximum: higher than the ``left`` bars before it and the
``right`` bars after it. The catch for backtesting: a pivot can only be **confirmed** once the
``right`` bars after it have printed. So we emit each pivot at its **confirmation bar**
(``i + right``), never at bar ``i`` itself — that is what makes this causal (no repainting).

This is the shared engine behind divergence detection (``divergence.py``) and is equally usable
for swing-based structure, support/resistance, etc.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def pivots(series: pd.Series, left: int = 3, right: int = 3, *, high: bool = True) -> pd.DataFrame:
    """Detect pivots on ``series``. Returns a DataFrame aligned to ``series.index`` with:

    - ``value``   — the pivot's price/level, placed at the **confirmation bar** (``i+right``).
    - ``src_pos`` — the integer position ``i`` of the pivot itself (for slope/divergence math).

    Both are NaN on non-confirmation bars. Causal: a pivot only appears once it is confirmable.
    """
    arr = series.to_numpy(dtype=float)
    n = len(arr)
    value = np.full(n, np.nan)
    src_pos = np.full(n, np.nan)

    for i in range(left, n - right):
        window = arr[i - left : i + right + 1]
        if np.isnan(window).any():
            continue
        center = arr[i]
        # Require the extreme to sit exactly at the center (argmax==left) — this both confirms
        # the pivot and breaks ties deterministically (an earlier equal bar wins, no duplicates).
        is_pivot = (center == window.max() and window.argmax() == left) if high else (
            center == window.min() and window.argmin() == left
        )
        if is_pivot:
            j = i + right  # confirmation bar
            value[j] = center
            src_pos[j] = i

    return pd.DataFrame({"value": value, "src_pos": src_pos}, index=series.index)
