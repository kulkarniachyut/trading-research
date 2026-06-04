"""Checkpoint 2.6b (sub-stage 1) — ICT 2022 model primitives.

Constructed bars verify sweep detection (buyside/sellside, close-back-inside), structure shift,
premium/discount classification, and the OTE retracement band.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.strategies.ict.ict_2022._model import (
    detect_sweep,
    ote_zone,
    premium_discount,
    structure_shift,
)

NY = "America/New_York"


def _bars(high, low, close) -> pd.DataFrame:
    idx = pd.date_range("2024-03-12 09:30", periods=len(high), freq="5min", tz=NY)
    open_ = [c for c in close]
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "volume": 1000.0}, index=idx)


def test_detect_buyside_sweep():
    # swing high 105 at idx3 (confirmed idx5); idx9 wicks to 106 but closes at 104 (back inside).
    high = [100, 101, 102, 105, 102, 101, 100, 101, 103, 106, 102, 101]
    low = [98, 99, 100, 103, 100, 99, 98, 99, 101, 103, 100, 99]
    close = [99, 100, 101, 104, 101, 100, 99, 100, 102, 104, 101, 100]
    sweep = detect_sweep(_bars(high, low, close), length=2, lookback=3)
    assert sweep is not None
    assert sweep.side == "buyside"
    assert sweep.level == 105 and sweep.extreme == 106 and sweep.pos == 9


def test_detect_sellside_sweep():
    # swing low 96 at idx3 (confirmed idx5); idx9 wicks to 95 but closes at 97 (back inside).
    low = [100, 99, 98, 96, 98, 99, 100, 99, 97, 95, 98, 99]
    high = [101, 100, 99, 99, 99, 100, 101, 100, 98, 98, 99, 100]
    close = [100, 99, 98, 97, 98, 99, 100, 99, 97, 97, 98, 99]
    sweep = detect_sweep(_bars(high, low, close), length=2, lookback=3)
    assert sweep is not None
    assert sweep.side == "sellside"
    assert sweep.level == 96 and sweep.extreme == 95 and sweep.pos == 9


def test_no_sweep_when_price_does_not_pierce():
    high = [100, 101, 102, 103, 102, 101, 100, 101, 102, 103, 102, 101]
    low = [98, 99, 100, 101, 100, 99, 98, 99, 100, 101, 100, 99]
    close = [99, 100, 101, 102, 101, 100, 99, 100, 101, 102, 101, 100]
    assert detect_sweep(_bars(high, low, close), length=2, lookback=3) is None


def test_structure_shift_up():
    high = [100, 101, 105, 101, 100, 99, 100, 106]   # last close breaks the 105 swing high
    low = [98, 99, 103, 99, 98, 97, 98, 104]
    close = [99, 100, 104, 100, 99, 98, 99, 106]
    assert structure_shift(_bars(high, low, close), direction=1, length=2) is True
    assert structure_shift(_bars(high, low, close), direction=-1, length=2) is False


def test_premium_discount():
    assert premium_discount(80, 100, 50)[0] == "premium"
    assert premium_discount(60, 100, 50)[0] == "discount"
    assert premium_discount(75, 100, 50) == ("equilibrium", 0.5)


def test_ote_zone_bullish_leg():
    lo, hi = ote_zone(100.0, 110.0)   # leg up 100 -> 110; 62-79% retrace
    assert lo == pytest.approx(102.1)
    assert hi == pytest.approx(103.8)
