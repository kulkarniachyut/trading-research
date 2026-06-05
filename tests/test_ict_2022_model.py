"""Checkpoint 2.6b (sub-stage 1) — ICT 2022 model primitives.

Constructed bars verify sweep detection (buyside/sellside, close-back-inside), structure shift,
premium/discount classification, and the OTE retracement band.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.strategies.ict.ict_2022._model import (
    daily_bias,
    daily_bias_context,
    detect_displacement,
    detect_sweep,
    draw_on_liquidity,
    draw_on_liquidity_level,
    inducement_taken,
    liquidity_levels,
    ote_zone,
    premium_discount,
    structure_shift,
)
from src.strategies.ict.ict_2022._pd_arrays import breaker_level, inverse_fvgs

NY = "America/New_York"


def _bars(high, low, close, open_=None, start: str = "2024-03-12 09:30") -> pd.DataFrame:
    idx = pd.date_range(start, periods=len(high), freq="5min", tz=NY)
    open_ = close if open_ is None else open_
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


def test_detect_displacement_leaves_fvg():
    # 17 flat bars, then a big bullish impulse (idx18) leaving an FVG.
    high = [100.2] * 17 + [100.3, 106.0, 107.0]
    low = [99.8] * 17 + [99.7, 100.5, 103.0]
    close = [100.0] * 17 + [100.0, 105.5, 106.0]
    open_ = [100.0] * 17 + [100.0, 101.0, 106.0]
    disp = detect_displacement(_bars(high, low, close, open_), direction=1, atr_mult=1.5)
    assert disp is not None
    assert disp.direction == 1
    assert disp.fvg_top > disp.fvg_bottom
    assert disp.leg_high >= disp.fvg_top


def test_draw_on_liquidity_nearest_pool():
    high = [100, 101, 105, 101, 100, 101, 108, 101, 100, 101, 102, 101]
    low = [97, 98, 102, 98, 97, 98, 105, 98, 97, 98, 99, 98]
    close = [99, 100, 104, 100, 99, 100, 107, 100, 99, 100, 101, 100]
    bars = _bars(high, low, close)
    assert draw_on_liquidity(bars, direction=1, price=104.0, length=2) == 105  # nearest BSL above
    assert draw_on_liquidity(bars, direction=1, price=200.0, length=2) is None  # nothing above


def test_liquidity_levels_include_prior_and_current_session_extremes():
    yesterday = _bars(
        high=[100, 101, 103],
        low=[97, 96, 98],
        close=[99, 100, 101],
        start="2024-03-11 15:45",
    )
    today = _bars(
        high=[99, 102, 104],
        low=[98, 99, 100],
        close=[98.5, 101, 103],
        start="2024-03-12 09:30",
    )
    bars = pd.concat([yesterday, today])
    levels = liquidity_levels(bars, length=2)
    assert ("buyside", 103.0, "previous_session_high") in {
        (x.side, x.level, x.source) for x in levels
    }
    assert ("sellside", 96.0, "previous_session_low") in {
        (x.side, x.level, x.source) for x in levels
    }
    assert draw_on_liquidity_level(bars, direction=1, price=102.5, length=2).level == 103


def test_inducement_taken():
    high = [104, 103, 102, 103, 104, 101, 103]
    low = [102, 101, 100, 101, 102, 99, 101]   # minor swing low 100 (idx2); idx5 dips to 99
    close = [103, 102, 101, 102, 103, 100, 101]  # last close 101 > 100
    assert inducement_taken(_bars(high, low, close), direction=1, minor_length=2, window=3) is True


def test_daily_bias_from_structure():
    high = [100, 101, 105, 101, 100, 99, 100, 106]
    low = [98, 99, 103, 99, 98, 97, 98, 104]
    close = [99, 100, 104, 100, 99, 98, 99, 106]
    assert daily_bias(_bars(high, low, close), length=2) == 1
    ctx = daily_bias_context(_bars(high, low, close), length=2)
    assert ctx.direction == 1
    assert ctx.zone == "premium"
    assert ctx.range_high == 105
    assert ctx.range_low == 97


def test_inverse_fvg_flips_when_violated():
    # bullish FVG [100, 101] at idx1; later closes drop below 100 -> bearish IFVG.
    high = [100.0, 103.0, 104.0, 101.0, 100.0, 99.0, 98.0]
    low = [99.0, 99.5, 101.0, 100.0, 99.0, 98.0, 97.0]
    close = [100.0, 102.8, 103.0, 100.5, 99.5, 98.5, 97.5]
    open_ = [100.0, 100.0, 103.0, 100.5, 99.5, 98.5, 97.5]
    ifvgs = inverse_fvgs(_bars(high, low, close, open_))
    assert any(i.direction == -1 for i in ifvgs)


def test_breaker_level_on_structure_break():
    high = [100, 101, 105, 101, 100, 99, 100, 106]
    low = [98, 99, 103, 99, 98, 97, 98, 104]
    close = [99, 100, 104, 100, 99, 98, 99, 106]
    assert breaker_level(_bars(high, low, close), length=2) == (1, 105)
