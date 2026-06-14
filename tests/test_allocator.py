"""Step 6 risk layer — the sleeve allocator.

The allocator must: size each sleeve to its risk-share of the gross-leverage budget (preserving
the sleeve's internal proportions), net overlapping symbols across sleeves, cap total gross
leverage, and force the book flat at the drawdown circuit breaker.
"""

from __future__ import annotations

import pytest

from src.execution.allocator import SleeveTarget, allocate


def test_weights_size_each_sleeve_to_its_budget() -> None:
    mr = SleeveTarget("mr", {"SPY": 1000.0, "IWM": 1000.0})   # gross 2000
    vix = SleeveTarget("vix", {"VIXY": -500.0})               # gross 500 (short)
    res = allocate([mr, vix], {"mr": 0.5, "vix": 0.3}, equity=100_000,
                   max_gross_leverage=1.0)
    # mr budget = 0.5 * 100k = 50k gross; vix = 0.3 * 100k = 30k gross
    assert res.sleeve_gross["mr"] == pytest.approx(50_000)
    assert res.sleeve_gross["vix"] == pytest.approx(30_000)
    # internal proportions preserved: SPY == IWM within mr
    assert res.targets["SPY"] == pytest.approx(25_000)
    assert res.targets["IWM"] == pytest.approx(25_000)
    assert res.targets["VIXY"] == pytest.approx(-30_000)   # short preserved
    assert res.gross_leverage == pytest.approx(0.8)        # 0.5+0.3 of 1x


def test_overlapping_symbols_net_across_sleeves() -> None:
    a = SleeveTarget("a", {"SPY": 100.0})   # long SPY
    b = SleeveTarget("b", {"SPY": -100.0})  # short SPY, equal internal size
    res = allocate([a, b], {"a": 0.5, "b": 0.5}, equity=100_000, max_gross_leverage=1.0)
    # both sized to 50k gross on SPY but opposite signs -> net flat
    assert res.targets.get("SPY", 0.0) == pytest.approx(0.0, abs=1e-6)


def test_gross_leverage_cap_scales_down() -> None:
    # weights sum > 1 would breach the cap -> pro-rata scale to the budget
    s = SleeveTarget("s", {"SPY": 1.0})
    res = allocate([s], {"s": 2.0}, equity=100_000, max_gross_leverage=1.0)
    assert res.gross_leverage == pytest.approx(1.0)
    assert res.scaled < 1.0
    assert res.targets["SPY"] == pytest.approx(100_000)


def test_leverage_above_one_allowed_up_to_cap() -> None:
    mr = SleeveTarget("mr", {"SPY": 1.0})
    res = allocate([mr], {"mr": 1.0}, equity=100_000, max_gross_leverage=3.0)
    assert res.targets["SPY"] == pytest.approx(300_000)
    assert res.gross_leverage == pytest.approx(3.0)


def test_drawdown_circuit_breaker_forces_flat() -> None:
    mr = SleeveTarget("mr", {"SPY": 1000.0})
    res = allocate([mr], {"mr": 1.0}, equity=100_000,
                   current_drawdown=0.55, drawdown_halt=0.5)
    assert res.halted is True
    assert res.targets == {}
    assert res.gross_leverage == 0.0


def test_zero_weight_sleeve_ignored() -> None:
    mr = SleeveTarget("mr", {"SPY": 1000.0})
    trend = SleeveTarget("trend", {"TLT": 1000.0})
    res = allocate([mr, trend], {"mr": 1.0, "trend": 0.0}, equity=100_000,
                   max_gross_leverage=1.0)
    assert "TLT" not in res.targets
    assert res.sleeve_gross["trend"] == 0.0


def test_empty_and_invalid() -> None:
    assert allocate([], {}, equity=100_000).targets == {}
    with pytest.raises(ValueError):
        allocate([], {}, equity=0)
