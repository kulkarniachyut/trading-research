"""Checkpoint 2.4 — multi-timeframe rollup (resample) + MultiTFClock (no look-ahead).

Shows how each base bar rolls up into the higher timeframes (OHLCV aggregation), and proves the
clock only ever serves *completed* higher-TF bars as of ``now`` — never the forming one.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.backtest.clock import MultiTFClock
from src.core.types import TimeFrame
from src.data.resample import resample_ohlcv

NY = "America/New_York"


def session_5m(date: str, base_price: float = 100.0) -> pd.DataFrame:
    """One RTH session of deterministic 5m bars (09:30–15:55)."""
    idx = pd.date_range(f"{date} 09:30", f"{date} 15:55", freq="5min", tz=NY)
    close = base_price + pd.Series(range(len(idx)), index=idx) * 0.1
    return pd.DataFrame(
        {
            "open": close - 0.05,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 100.0,
        },
        index=idx,
    )


# --- rollup / resample -----------------------------------------------------

def test_h1_rollup_aggregates_constituent_5m_bars():
    base = session_5m("2024-03-12")
    h1 = resample_ohlcv(base, TimeFrame.H1)

    # 09:30–15:55 -> hourly buckets at :00 -> 7 bars (09:00 holds only 09:30–09:55).
    assert len(h1) == 7
    label = pd.Timestamp("2024-03-12 10:00", tz=NY)
    constituents = base[base.index.floor("1h") == label]   # the 10:00–10:55 5m bars
    bar = h1.loc[label]
    assert bar["open"] == constituents.iloc[0]["open"]      # first
    assert bar["high"] == constituents["high"].max()        # max
    assert bar["low"] == constituents["low"].min()          # min
    assert bar["close"] == constituents.iloc[-1]["close"]   # last
    assert bar["volume"] == constituents["volume"].sum()    # sum


def test_daily_rollup_one_bar_per_session():
    base = pd.concat([session_5m(d) for d in ("2024-03-11", "2024-03-12", "2024-03-13")])
    d1 = resample_ohlcv(base, TimeFrame.D1)
    assert len(d1) == 3
    day = pd.Timestamp("2024-03-12", tz=NY)
    sess = base[base.index.normalize() == day]
    assert d1.loc[day]["high"] == sess["high"].max()
    assert d1.loc[day]["volume"] == sess["volume"].sum()


def test_weekly_rollup_groups_the_week():
    # Mon–Fri of one week -> a single weekly bar labeled Monday.
    base = pd.concat([session_5m(d) for d in ("2024-03-11", "2024-03-12", "2024-03-13", "2024-03-14", "2024-03-15")])
    w1 = resample_ohlcv(base, TimeFrame.W1)
    assert len(w1) == 1
    assert w1.index[0] == pd.Timestamp("2024-03-11", tz=NY)   # Monday
    assert w1.iloc[0]["volume"] == base["volume"].sum()
    assert w1.iloc[0]["high"] == base["high"].max()


# --- the clock: completed bars only ---------------------------------------

def test_clock_serves_only_completed_higher_tf_bars():
    base = session_5m("2024-03-12")
    clock = MultiTFClock(base, TimeFrame.M5, [TimeFrame.M5, TimeFrame.M15, TimeFrame.H1])

    now = pd.Timestamp("2024-03-12 10:25", tz=NY)  # the 10:20 bar just closed

    # base: last completed 5m bar opened 10:20 (closes exactly at now)
    assert clock.last(TimeFrame.M5, now).name == pd.Timestamp("2024-03-12 10:20", tz=NY)
    # M15: 10:15 bar (closes 10:30) is still forming -> last completed is the 10:00 bar
    assert clock.last(TimeFrame.M15, now).name == pd.Timestamp("2024-03-12 10:00", tz=NY)
    # H1: the 10:00 bar (closes 11:00) is forming -> only the 09:00 bar is complete
    completed_h1 = clock.completed(TimeFrame.H1, now)
    assert list(completed_h1.index) == [pd.Timestamp("2024-03-12 09:00", tz=NY)]


def test_clock_no_higher_bar_before_its_window_closes():
    base = session_5m("2024-03-12")
    clock = MultiTFClock(base, TimeFrame.M5, [TimeFrame.H1])
    # at 09:55 close, the first H1 bar (09:00–10:00) has NOT closed yet
    assert clock.last(TimeFrame.H1, pd.Timestamp("2024-03-12 09:55", tz=NY)) is None
    # at 10:00 close it is available
    assert clock.last(TimeFrame.H1, pd.Timestamp("2024-03-12 10:00", tz=NY)) is not None


def test_clock_rejects_timeframe_below_base():
    base = session_5m("2024-03-12")
    with pytest.raises(ValueError, match="below the base"):
        MultiTFClock(base, TimeFrame.M15, [TimeFrame.M5])
