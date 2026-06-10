"""Step 4, family 5 — the turn-of-month strategy.

Real NYSE calendar (public, forward-safe), synthetic daily bars: the strategy must enter at the
open of the 4th-to-last session of a month (signal on the 5th-to-last close), exit at the open
of the 4th session of the next month (signal on the 3rd close), hold nothing mid-month, and
repeat monthly. Also checks ``month_position`` bookkeeping directly.
"""

from __future__ import annotations

import pandas as pd
import pandas_market_calendars as mcal

import src.strategies  # noqa: F401  (imports buckets -> registers strategies)
from src.backtest.costs import AssetClass, InstrumentSpec, Market, Product, cost_model
from src.backtest.simulator import BacktestEngine
from src.core.types import TimeFrame
from src.strategies.base import get_strategy, list_strategies
from src.strategies.meanrev.turn_of_month import TurnOfMonth, month_position

NY = "America/New_York"


def _nyse_daily_bars(start: str, end: str, px: float = 100.0) -> pd.DataFrame:
    sched = mcal.get_calendar("NYSE").schedule(start_date=start, end_date=end)
    idx = pd.DatetimeIndex(sched.index).tz_localize(NY)
    n = len(idx)
    closes = [px + 0.05 * i for i in range(n)]  # gentle drift, never near a 3-ATR stop
    return pd.DataFrame({
        "open": closes, "high": [c + 0.5 for c in closes],
        "low": [c - 0.5 for c in closes], "close": closes, "volume": 1e6,
    }, index=idx)


def _run(bars: pd.DataFrame):
    inst = InstrumentSpec("SPY", Market("US", AssetClass.EQUITY, Product.INTRADAY))
    eng = BacktestEngine(cost_model("US", "equity"), inst, initial_equity=100_000.0,
                         max_leverage=2.0)
    return eng.run(TurnOfMonth({"atr_period": 5}), bars, TimeFrame.D1)


def test_registered() -> None:
    assert "turn_of_month" in list_strategies()
    assert get_strategy("turn_of_month") is TurnOfMonth


def test_month_position_bookkeeping() -> None:
    sched = mcal.get_calendar("NYSE").schedule(start_date="2022-03-01", end_date="2022-03-31")
    pos = month_position(pd.DatetimeIndex(sched.index))
    days = sorted(pos)
    assert pos[days[0]] == (1, len(days))          # first session: day 1, all remaining
    assert pos[days[-1]] == (len(days), 1)         # last session: day N, 1 remaining
    assert pos[days[-5]][1] == 5                   # 5th-to-last has 5 left (incl. itself)


def test_monthly_cycle_entry_and_exit_days() -> None:
    bars = _nyse_daily_bars("2022-02-01", "2022-07-29")
    res = _run(bars)
    assert len(res.trades) >= 4  # ~one round trip per month boundary
    sched = mcal.get_calendar("NYSE").schedule(start_date="2022-01-01", end_date="2022-08-31")
    pos = month_position(pd.DatetimeIndex(sched.index))
    one_day = pd.Timedelta(days=1)  # ts are bar CLOSE times = label + 1 day (D1 convention)
    for t in res.trades[:-1]:  # last may be end_of_data
        entry_day = (pd.Timestamp(t.entry_ts) - one_day).tz_localize(None).normalize()
        exit_day = (pd.Timestamp(t.exit_ts) - one_day).tz_localize(None).normalize()
        # fills happen at the open AFTER the signal close: 4th-to-last in, 4th session out
        assert pos[entry_day][1] == 4, f"entered with {pos[entry_day][1]} sessions left"
        assert pos[exit_day][0] == 4, f"exited on month-day {pos[exit_day][0]}"
        assert t.reason_out == "signal"
        # held through the boundary: entry near month-end, exit early next month
        assert exit_day.month != entry_day.month


def test_flat_mid_month() -> None:
    bars = _nyse_daily_bars("2022-02-01", "2022-07-29")
    res = _run(bars)
    for t in res.trades:
        assert t.bars_held <= 9  # ~4 + ~4 sessions, never weeks
