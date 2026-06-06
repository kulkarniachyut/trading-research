"""Monte-Carlo resampling — "is the edge distinguishable from luck?".

A positive pooled expectancy can still be a fluke of trade ordering and a few outliers. We bootstrap
the per-trade R sequence (resample *with replacement*, same length, many times) to get a distribution
of total R, per-trade expectancy, and max-drawdown. The Phase-E gate reads the **5th-percentile**
outcome: if the unlucky-but-plausible tail is still >= breakeven, the edge is robust; if p5 total R
is negative, the central estimate is riding on order/outliers.

Deterministic given ``seed`` (``numpy.random.default_rng``) so a run is reproducible and testable.
Bootstrap (not permutation) is the default: resampling with replacement perturbs both ordering and
composition, which is the stricter "could this have been noise?" question for an i.i.d.-ish R series.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


def max_drawdown_r(returns_r: Sequence[float]) -> float:
    """Max peak-to-trough drawdown (in R) of the cumulative sum of a per-trade R sequence.

    Returns a non-negative magnitude (0.0 for an empty or monotonically rising curve).
    """
    arr = np.asarray(returns_r, dtype=float)
    if arr.size == 0:
        return 0.0
    curve = np.cumsum(arr)
    running_max = np.maximum.accumulate(curve)
    drawdown = running_max - curve  # >= 0 by construction
    return float(drawdown.max())


@dataclass(frozen=True, slots=True)
class MonteCarloResult:
    n_trades: int
    n_resamples: int
    seed: int
    observed_total_r: float
    observed_max_dd_r: float
    mean_total_r: float
    p5_total_r: float
    p95_total_r: float
    p5_expectancy_r: float       # p5_total_r / n_trades — the unlucky-tail per-trade edge
    median_max_dd_r: float
    p95_max_dd_r: float          # the bad-luck drawdown (95th pct of resampled DDs)
    prob_total_r_le_0: float     # share of resamples whose total R <= 0 (luck p-value-ish)

    @property
    def survives(self) -> bool:
        """Phase-E MC criterion: the 5th-percentile total-R outcome is still >= breakeven."""
        return self.p5_total_r >= 0.0


def monte_carlo(
    returns_r: Sequence[float],
    *,
    n_resamples: int = 2000,
    seed: int = 0,
) -> MonteCarloResult:
    """Bootstrap a per-trade R sequence into total-R / max-DD distributions.

    ``returns_r`` is the pooled OOS per-trade net R (e.g. ``WalkForwardResult.returns_r``). Each of
    ``n_resamples`` draws is ``len(returns_r)`` samples *with replacement*; we record each draw's
    total R and max drawdown, then report the central estimate, the 5th/95th percentiles, and the
    fraction of draws that lost money.
    """
    arr = np.asarray(returns_r, dtype=float)
    n = arr.size
    if n == 0:
        raise ValueError("monte_carlo needs a non-empty return sequence")

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_resamples, n))
    samples = arr[idx]                       # (n_resamples, n)
    totals = samples.sum(axis=1)

    # Max drawdown per resampled path (vectorised over resamples).
    curves = np.cumsum(samples, axis=1)
    running_max = np.maximum.accumulate(curves, axis=1)
    dds = (running_max - curves).max(axis=1)

    p5_total = float(np.percentile(totals, 5))
    return MonteCarloResult(
        n_trades=n,
        n_resamples=n_resamples,
        seed=seed,
        observed_total_r=float(arr.sum()),
        observed_max_dd_r=max_drawdown_r(arr),
        mean_total_r=float(totals.mean()),
        p5_total_r=p5_total,
        p95_total_r=float(np.percentile(totals, 95)),
        p5_expectancy_r=p5_total / n,
        median_max_dd_r=float(np.median(dds)),
        p95_max_dd_r=float(np.percentile(dds, 95)),
        prob_total_r_le_0=float((totals <= 0).mean()),
    )
