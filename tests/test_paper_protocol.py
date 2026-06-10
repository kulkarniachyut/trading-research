"""Step 6 bridge — the paper protocol's pure planning logic (no network, no broker).

Synthetic daily bars + journal lots must produce: an IBS limit-day entry plan with the frozen
rule's stop/size, an IBS exit on strength / on the 5th held session, no duplicate entries for
held or pending symbols, and TOM window entries (equal-notional) / exits keyed to the
(day #, days left) tuple of the next session.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.execution.protocol import Lot, plan_ibs, plan_tom, sessions_held

NY = "America/New_York"


def _bars(n: int = 220, last_ibs: float = 0.5, drift: float = 0.1) -> pd.DataFrame:
    """n daily bars in an uptrend; the LAST bar's close lands at ``last_ibs`` of its range."""
    idx = pd.bdate_range("2025-06-02", periods=n, tz=NY)
    base = 100 + drift * np.arange(n)
    o = base.copy()
    h = base + 1.0
    lo = base - 1.0
    c = base + 0.2
    c[-1] = lo[-1] + last_ibs * (h[-1] - lo[-1])
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c, "volume": 1e6}, index=idx)


def test_ibs_entry_plan_built_with_stop_and_size() -> None:
    bars = {"SPY": _bars(last_ibs=0.05)}
    plans = plan_ibs(bars, lots=[], pending_symbols=set(), risk_cash=500.0)
    assert len(plans) == 1
    p = plans[0]
    assert (p.system, p.action, p.symbol) == ("ibs", "limit_day", "SPY")
    assert p.limit_price == float(bars["SPY"]["close"].iloc[-1])
    assert p.stop_price < p.limit_price
    assert p.qty == int(500.0 / (p.limit_price - p.stop_price))


def test_no_entry_when_held_or_pending_or_weak_signal() -> None:
    bars = {"SPY": _bars(last_ibs=0.05)}
    held = [Lot("ibs", "SPY", 10, "2026-06-01")]
    assert plan_ibs(bars, held, set(), 500.0) == [] or \
        all(p.action != "limit_day" for p in plan_ibs(bars, held, set(), 500.0))
    assert plan_ibs(bars, [], {"SPY"}, 500.0) == []
    assert plan_ibs({"SPY": _bars(last_ibs=0.6)}, [], set(), 500.0) == []


def test_ibs_exit_on_strength_and_on_time() -> None:
    bars = {"SPY": _bars(last_ibs=0.95)}
    entry = str(bars["SPY"].index[-2].date())  # held 2 sessions
    plans = plan_ibs(bars, [Lot("ibs", "SPY", 10, entry)], set(), 500.0)
    assert any(p.action == "market_open_sell" and "ibs=0.9" in p.note for p in plans)

    bars2 = {"SPY": _bars(last_ibs=0.5)}  # no strength...
    entry2 = str(bars2["SPY"].index[-5].date())  # ...but 5 sessions held
    plans2 = plan_ibs(bars2, [Lot("ibs", "SPY", 10, entry2)], set(), 500.0)
    assert any(p.action == "market_open_sell" and "held=5" in p.note for p in plans2)
    assert sessions_held(bars2["SPY"], entry2) == 5


def test_tom_window_entry_and_exit() -> None:
    closes = {"SPY": 500.0, "QQQ": 400.0, "DIA": 380.0, "IWM": 200.0}
    plans = plan_tom((18, 4), [], closes, equity=100_000.0)  # next session = 4th-to-last
    assert {p.symbol for p in plans} == set(closes)
    assert all(p.action == "market_open_buy" for p in plans)
    spy = next(p for p in plans if p.symbol == "SPY")
    assert spy.qty == int(100_000.0 / 8.0 / 500.0)

    lots = [Lot("tom", "SPY", 25, "2026-05-27"), Lot("tom", "QQQ", 31, "2026-05-27")]
    exits = plan_tom((4, 17), lots, closes, equity=100_000.0)  # next session = day 4
    assert {p.symbol for p in exits} == {"SPY", "QQQ"}
    assert all(p.action == "market_open_sell" for p in exits)
    # mid-month: nothing
    assert plan_tom((10, 11), lots, closes, equity=100_000.0) == []
