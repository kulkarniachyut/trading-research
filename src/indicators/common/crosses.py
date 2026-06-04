"""Small reusable signal helpers shared across indicators.

These are deliberately generic (operate on any two aligned Series) so any indicator or strategy
can use them — not just Cipher B.
"""

from __future__ import annotations

import pandas as pd


def crossover(a: pd.Series, b: pd.Series) -> pd.Series:
    """True at bar t where ``a`` crosses **above** ``b`` (a<=b at t-1, a>b at t). Causal."""
    a_prev, b_prev = a.shift(1), b.shift(1)
    return ((a > b) & (a_prev <= b_prev)).fillna(False)


def crossunder(a: pd.Series, b: pd.Series) -> pd.Series:
    """True at bar t where ``a`` crosses **below** ``b`` (a>=b at t-1, a<b at t). Causal."""
    a_prev, b_prev = a.shift(1), b.shift(1)
    return ((a < b) & (a_prev >= b_prev)).fillna(False)
