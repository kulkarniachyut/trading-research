"""Phase E — Monte-Carlo: deterministic under a seed, correct drawdown maths, and the p5 "survives"
gate has the right sign on degenerate all-positive / all-negative sequences.
"""

from __future__ import annotations

import pytest

from src.validation.monte_carlo import max_drawdown_r, monte_carlo


def test_max_drawdown_basic():
    # cumsum [1, -1, 0]; running-max [1, 1, 1]; dd [0, 2, 1] → max 2.
    assert max_drawdown_r([1.0, -2.0, 1.0]) == pytest.approx(2.0)
    assert max_drawdown_r([]) == 0.0
    assert max_drawdown_r([1.0, 1.0, 1.0]) == 0.0          # monotone up → no drawdown


def test_seed_is_deterministic_and_seed_matters():
    seq = [0.5, -1.0, 2.0, -0.5, 1.5, -2.0, 0.3, 0.8] * 6
    a = monte_carlo(seq, n_resamples=500, seed=0)
    b = monte_carlo(seq, n_resamples=500, seed=0)
    c = monte_carlo(seq, n_resamples=500, seed=1)
    assert a == b                                          # same seed → identical result
    assert a.p5_total_r != c.p5_total_r                    # different seed → different draw
    # observed stats don't depend on the seed at all.
    assert a.observed_total_r == c.observed_total_r


def test_empty_sequence_rejected():
    with pytest.raises(ValueError, match="non-empty"):
        monte_carlo([])


def test_all_positive_survives_all_negative_does_not():
    pos = monte_carlo([1.0] * 50, n_resamples=300, seed=0)
    assert pos.survives and pos.p5_total_r > 0
    assert pos.prob_total_r_le_0 == 0.0
    assert pos.observed_max_dd_r == 0.0                    # never draws down

    neg = monte_carlo([-1.0] * 50, n_resamples=300, seed=0)
    assert not neg.survives and neg.p5_total_r < 0
    assert neg.prob_total_r_le_0 == 1.0


def test_p5_expectancy_is_total_over_n():
    seq = [0.4, -0.2, 0.9, -0.1, 0.6] * 10
    mc = monte_carlo(seq, n_resamples=400, seed=7)
    assert mc.p5_expectancy_r == pytest.approx(mc.p5_total_r / mc.n_trades)
