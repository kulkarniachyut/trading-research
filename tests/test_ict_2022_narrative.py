"""Tests for the ICT 2022 narrative layers added in the redesign: the TIME layer (session anchor,
macro-time gate, premium/discount vs anchor) and the BIAS layer (Daily Rebalance Theory), plus the
strategy-level bias gate."""

from __future__ import annotations

import pandas as pd

from src.core.types import Account, MarketContext, Position, TimeFrame
from src.strategies.ict.ict_2022 import (
    Ict2022,
    anchor_allows,
    anchor_pd,
    at_macro_time,
    daily_rebalance,
    is_consolidation_day,
    session_anchor,
)

NY = "America/New_York"


# --------------------------------------------------------------------------- helpers
def _intraday(rows, freq="5min", start="2024-03-12 09:30"):
    idx = pd.date_range(start, periods=len(rows), freq=freq, tz=NY)
    o, h, low, c = zip(*rows)
    return pd.DataFrame({"open": o, "high": h, "low": low, "close": c, "volume": 1000.0}, index=idx)


def _daily(rows, start="2024-03-01"):
    idx = pd.date_range(start, periods=len(rows), freq="1D", tz=NY)
    o, h, low, c = zip(*rows)
    return pd.DataFrame({"open": o, "high": h, "low": low, "close": c, "volume": 1000.0}, index=idx)


# --------------------------------------------------------------------------- TIME layer
def test_session_anchor_rth_equity_is_session_open():
    """An RTH equity frame (first bar 09:30) anchors on the session open, not a midnight bar."""
    bars = _intraday([(100, 101, 99, 100), (100, 102, 99, 101)], start="2024-03-12 09:30")
    a = session_anchor(bars)
    assert a is not None
    assert a.kind == "session_open"
    assert a.price == 100


def test_session_anchor_crypto_is_midnight():
    """A 24/7 frame whose first bar is 00:00 NY anchors on the true Midnight-NY open."""
    bars = _intraday([(50, 51, 49, 50), (50, 52, 49, 51)], start="2024-03-12 00:00")
    a = session_anchor(bars)
    assert a is not None and a.kind == "midnight" and a.price == 50


def test_anchor_pd_and_allows():
    assert anchor_pd(105, 100) == "premium"
    assert anchor_pd(95, 100) == "discount"
    assert anchor_pd(100, 100) == "equilibrium"
    bars = _intraday([(100, 101, 99, 100)])
    a = session_anchor(bars)
    assert anchor_allows(95, a, 1)        # discount → long ok
    assert not anchor_allows(105, a, 1)   # premium → long blocked
    assert anchor_allows(105, a, -1)      # premium → short ok
    assert not anchor_allows(100, a, 1)   # equilibrium → blocked either way
    assert anchor_allows(105, None, 1)    # no anchor → permissive


def test_at_macro_time():
    ten_thirty = pd.Timestamp("2024-03-12 10:30", tz=NY)
    noon = pd.Timestamp("2024-03-12 12:00", tz=NY)
    windows = [("10:00", "11:00")]
    assert at_macro_time(ten_thirty, windows)
    assert not at_macro_time(noon, windows)
    assert at_macro_time(noon, None)      # no windows → always true


# --------------------------------------------------------------------------- BIAS layer
def test_daily_rebalance_neutral_without_history():
    d1 = _daily([(100, 110, 100, 105), (101, 111, 101, 106)])  # only 2 bars
    draw = daily_rebalance(d1, price=105)
    assert draw.direction == 0 and draw.basis == "none"


def test_daily_rebalance_purge_revert_up():
    """Last day sweeps the prior day's low (SSL purge) and nothing else → revert up to the 3-day high."""
    d1 = _daily([
        (105, 110, 100, 108),
        (106, 111, 101, 109),
        (107, 112, 102, 110),
        (108, 111.5, 101.5, 109),   # low 101.5 < prior low 102; high 111.5 < prior high 112
    ])
    draw = daily_rebalance(d1, price=106)
    assert draw.direction == 1
    assert draw.basis == "purge_revert"
    assert draw.draw == 112          # 3-day high over the last 3 bars


def test_daily_rebalance_purge_revert_down():
    d1 = _daily([
        (105, 110, 100, 108),
        (106, 111, 101, 109),
        (107, 112, 102, 110),
        (108, 113, 103, 112),        # high 113 > prior high 112; low 103 > prior low 102
    ])
    draw = daily_rebalance(d1, price=106)
    assert draw.direction == -1 and draw.basis == "purge_revert"
    assert draw.draw == 101          # 3-day low over the last 3 bars


def test_daily_rebalance_pdh_pdl_fallback_inside_day():
    """An inside day (no side swept, no FVG) → premium/discount of price vs the prior day's range."""
    d1 = _daily([
        (105, 110, 100, 108),
        (106, 111, 101, 109),
        (107, 112, 102, 110),
        (108, 111, 103, 109),        # inside day2 (high 111<112, low 103>102)
    ])
    draw = daily_rebalance(d1, price=104)   # below the (111+103)/2=107 midpoint → discount → up
    assert draw.direction == 1 and draw.basis == "pdh_pdl"
    assert draw.draw == 111                 # draw toward PDH


def test_daily_rebalance_targets_unfilled_daily_fvg():
    """A clean unfilled bullish daily FVG above price → the draw is to rebalance that gap (up)."""
    d1 = _daily([
        (100, 101, 100, 100),        # c1 (gap reference high = 101)
        (101, 106, 101, 105),        # impulse up — FVG labels here
        (104, 107, 103, 106),        # c3 low 103 > c1 high 101 → bullish gap [101, 103]
        (105, 108, 104, 107),        # later day stays above the gap → unfilled
    ])
    draw = daily_rebalance(d1, price=99)    # price below the gap → drawn up to it
    assert draw.direction == 1
    assert draw.basis == "daily_fvg"


def test_is_consolidation_day_after_outside_day():
    d1 = _daily([
        (100, 108, 100, 104),
        (104, 106, 102, 105),
        (105, 110, 99, 106),         # outside day: high 110 > 106 and low 99 < 102
    ])
    assert is_consolidation_day(d1)
    trending = _daily([(100, 105, 99, 104), (104, 108, 103, 107), (107, 111, 106, 110)])
    assert not is_consolidation_day(trending)


# --------------------------------------------------------------------------- strategy bias gate
class _FakeCtx(MarketContext):
    def __init__(self, now, price, frames, symbol="SPY"):
        self._now, self._price, self._frames = now, price, frames
        self._position = Position(symbol, qty=0.0, avg_px=0.0)

    @property
    def now(self):
        return self._now

    def bars(self, tf):
        return self._frames[tf]

    def last(self, tf):
        return self._frames[tf].iloc[-1]

    def window(self, tf, n):
        return self._frames[tf].tail(n)

    @property
    def price(self):
        return self._price

    @property
    def position(self):
        return self._position

    @property
    def account(self):
        return Account(100_000.0, 100_000.0, 100_000.0)


def _bullish_m5():
    return _intraday([
        (100, 101, 99, 100), (100, 100, 98, 99), (99, 99, 96, 97),
        (97, 100, 98, 99), (99, 101, 99, 100), (100, 105, 102, 104),
        (104, 103, 100, 101), (101, 102, 99, 100), (100, 101, 95, 97),
        (97, 98, 96, 97), (98, 106, 97.5, 105), (105, 107, 101, 106),
        (106, 102, 99.8, 100),
    ])


def _ctx(m5, daily):
    return _FakeCtx(
        now=m5.index[-1] + pd.Timedelta(minutes=5),
        price=float(m5["close"].iloc[-1]),
        frames={TimeFrame.M5: m5, TimeFrame.M15: m5, TimeFrame.H1: m5, TimeFrame.D1: daily},
    )


def _bias_only_strategy():
    # isolate the Daily-Rebalance bias gate from the other narrative layers
    return Ict2022({
        "killzones": [("09:30", "16:00")],
        "macro_time_gate": False,
        "require_anchor_pd": False,
        "skip_consolidation_day": False,
        "no_trade_lunch": False,
        "require_fvg_in_disp_half": False,
        "target_rebalance_draw": False,
        "max_trades_per_day": 0,
        "require_rebalance_bias": True,     # the gate under test
        "sweep_length": 2, "sweep_lookback": 3, "mss_length": 2,
        "displacement_atr_period": 3, "displacement_atr_mult": 1.0,
        "min_disp_strength": 0.0, "displacement_lookback": 4,
        "max_setup_bars": 8, "target_length": 2, "stop_buffer_atr": 0.0,
    })


_BULLISH_DAILY = _daily([   # purge-&-revert up → bias +1 (agrees with the bullish setup)
    (105, 110, 100, 108), (106, 111, 101, 109),
    (107, 112, 102, 110), (108, 111.5, 101.5, 109),
])
_BEARISH_DAILY = _daily([   # purge-&-revert down → bias -1 (opposes the bullish setup)
    (105, 110, 100, 108), (106, 111, 101, 109),
    (107, 112, 102, 110), (108, 113, 103, 112),
])


def test_bias_gate_allows_setup_aligned_with_daily_draw():
    m5 = _bullish_m5()
    strat = _bias_only_strategy()
    strat.on_start(_ctx(m5.iloc[:9], _BULLISH_DAILY))
    strat.on_bar(_ctx(m5.iloc[:9], _BULLISH_DAILY))
    assert strat._state == "swept"
    strat.on_bar(_ctx(m5.iloc[:12], _BULLISH_DAILY))
    assert strat._state == "armed"
    sig = strat.on_bar(_ctx(m5.iloc[:13], _BULLISH_DAILY))
    assert sig is not None and sig.side == "long"
    assert sig.meta["draw_basis"] == "purge_revert"


def test_bias_gate_blocks_setup_against_daily_draw():
    m5 = _bullish_m5()
    strat = _bias_only_strategy()
    strat.on_start(_ctx(m5.iloc[:9], _BEARISH_DAILY))
    # the bullish sweep is counter to a bearish daily draw → never leaves idle.
    assert strat.on_bar(_ctx(m5.iloc[:9], _BEARISH_DAILY)) is None
    assert strat._state == "idle"
