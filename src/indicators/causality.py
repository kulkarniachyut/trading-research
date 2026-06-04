"""Causality guard for indicators — the look-ahead truth test.

An indicator is **causal** if its value at bar ``t`` is unaffected by bars *after* ``t``. We prove
that empirically: compute the indicator on the full series, then recompute it on the prefix
``df[:t+1]`` (everything up to and including ``t``, nothing after). If the value at ``t`` is the
same both ways, the indicator did not peek into the future. If removing future bars changes a past
value, the indicator look-aheads (a.k.a. "repaints") and ``assert_causal`` raises.

Every indicator strategies rely on must pass this — see ``tests/test_indicators.py``.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd


def assert_causal(
    fn: Callable[[pd.DataFrame], pd.Series | pd.DataFrame],
    df: pd.DataFrame,
    *,
    sample: int = 12,
    tol: float = 1e-9,
) -> None:
    """Assert ``fn`` is causal on ``df`` by spot-checking ``sample`` bars across the series.

    Raises ``AssertionError`` at the first bar where the prefix value disagrees with the
    full-series value (i.e. where the future leaked backward).
    """
    full = fn(df)
    n = len(df)
    # Spread test points across the back ~70% of the series (past the warm-up region).
    points = sorted({int(x) for x in np.linspace(int(n * 0.3), n - 1, sample) if x >= 1})
    for t in points:
        prefix_val = fn(df.iloc[: t + 1])
        _compare_at(full, prefix_val, t, tol)


def _compare_at(full, prefix, t: int, tol: float) -> None:
    """Compare the full-series value at position ``t`` with the prefix's last value."""
    if isinstance(full, pd.DataFrame):
        full_row, prefix_row = full.iloc[t], prefix.iloc[-1]
        for col in full.columns:
            _check(full_row[col], prefix_row[col], t, str(col), tol)
    else:
        _check(full.iloc[t], prefix.iloc[-1], t, str(full.name), tol)


def _check(x, y, t: int, name: str, tol: float) -> None:
    if pd.isna(x) and pd.isna(y):
        return
    if pd.isna(x) != pd.isna(y):
        raise AssertionError(
            f"causality violated: {name!r} at t={t} is {'NaN' if pd.isna(x) else x} on the full "
            f"series but {'NaN' if pd.isna(y) else y} on the prefix — future bars changed it."
        )
    if not np.isclose(x, y, atol=tol, rtol=tol):
        raise AssertionError(
            f"causality violated: {name!r} at t={t} = {x} on the full series but {y} when future "
            f"bars are removed — the indicator peeks ahead (repaints)."
        )
