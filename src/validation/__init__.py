"""Validation layer — walk-forward OOS folds + Monte-Carlo robustness (Phase E).

Depends only on the backtest/portfolio contract and ``src.core.types``; it *measures* strategies,
it does not fit them. See ``scripts/run_phase_e.py`` for the driver.
"""

from __future__ import annotations

from src.validation.monte_carlo import MonteCarloResult, max_drawdown_r, monte_carlo
from src.validation.walk_forward import (
    Fold,
    FoldResult,
    WalkForwardResult,
    make_folds,
    walk_forward,
    year_span,
)

__all__ = [
    "Fold",
    "FoldResult",
    "WalkForwardResult",
    "make_folds",
    "walk_forward",
    "year_span",
    "MonteCarloResult",
    "max_drawdown_r",
    "monte_carlo",
]
