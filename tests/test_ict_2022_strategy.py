"""Checkpoint 2.6b-3 — ICT 2022 state machine v1."""

from __future__ import annotations

import pandas as pd

import src.strategies  # noqa: F401  (imports buckets -> registers strategies)
from src.core.types import Account, MarketContext, Position, TimeFrame
from src.strategies.base import get_strategy, list_strategies
from src.strategies.ict.ict_2022 import Ict2022

NY = "America/New_York"


class FakeCtx(MarketContext):
    def __init__(self, now, price, frames, position):
        self._now = now
        self._price = price
        self._frames = frames
        self._position = position

    @property
    def now(self):
        return self._now

    def bars(self, timeframe):
        return self._frames[timeframe]

    def last(self, timeframe):
        return self._frames[timeframe].iloc[-1]

    def window(self, timeframe, n):
        return self._frames[timeframe].tail(n)

    @property
    def price(self):
        return self._price

    @property
    def position(self):
        return self._position

    @property
    def account(self):
        return Account(100_000.0, 100_000.0, 100_000.0)


def _bars(rows, freq="5min", start="2024-03-12 09:30"):
    idx = pd.date_range(start, periods=len(rows), freq=freq, tz=NY)
    o, h, low, c = zip(*rows)
    return pd.DataFrame({"open": o, "high": h, "low": low, "close": c, "volume": 1000.0}, index=idx)


def _bullish_2022_sequence():
    return _bars([
        (100, 101, 99, 100),
        (100, 100, 98, 99),
        (99, 99, 96, 97),       # confirmed swing low / sellside liquidity
        (97, 100, 98, 99),
        (99, 101, 99, 100),
        (100, 105, 102, 104),   # confirmed swing high / MSS level
        (104, 103, 100, 101),
        (101, 102, 99, 100),
        (100, 101, 95, 97),     # sweep below 96, close back inside
        (97, 98, 96, 97),
        (98, 106, 97.5, 105),   # bullish impulse; FVG labels here
        (105, 107, 101, 106),   # close breaks 105 swing high
        (106, 102, 99.8, 100),  # retrace into FVG + OTE
    ])


def _ctx(frame, symbol="SPY"):
    return FakeCtx(
        now=frame.index[-1] + pd.Timedelta(minutes=5),
        price=float(frame["close"].iloc[-1]),
        frames={
            TimeFrame.M5: frame,
            TimeFrame.M15: frame,
            TimeFrame.H1: frame,
            TimeFrame.D1: frame,
        },
        position=Position(symbol, qty=0.0, avg_px=0.0),
    )


def _strategy():
    return Ict2022({
        "killzones": [("09:30", "16:00")],
        "require_daily_bias": False,
        "sweep_length": 2,
        "sweep_lookback": 3,
        "mss_length": 2,
        "displacement_atr_period": 3,
        "displacement_atr_mult": 1.0,
        "displacement_lookback": 4,
        "max_setup_bars": 8,
        "target_length": 2,
        "stop_buffer_atr": 0.0,
    })


def test_registered_in_ict_bucket():
    assert "ict_2022" in list_strategies()
    assert get_strategy("ict_2022") is Ict2022


def test_state_machine_emits_long_after_sweep_mss_displacement_and_retrace():
    bars = _bullish_2022_sequence()
    strat = _strategy()
    strat.on_start(_ctx(bars.iloc[:9]))

    assert strat.on_bar(_ctx(bars.iloc[:9])) is None
    assert strat._state == "swept"

    assert strat.on_bar(_ctx(bars.iloc[:12])) is None
    assert strat._state == "armed"

    sig = strat.on_bar(_ctx(bars.iloc[:13]))
    assert sig is not None
    assert sig.side == "long"
    assert sig.reason == "ict_2022_long"
    assert sig.stop == 95
    assert sig.target == 105
    assert sig.stop < 100 < sig.target
    assert sig.meta["sweep_side"] == "sellside"


def test_no_signal_outside_killzone():
    bars = _bullish_2022_sequence()
    strat = Ict2022({"killzones": [("15:00", "16:00")], "require_daily_bias": False})
    strat.on_start(_ctx(bars.iloc[:13]))
    assert strat.on_bar(_ctx(bars.iloc[:13])) is None
