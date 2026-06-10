"""Step 4, family 1 — the ORB strategy.

Constructed single-day 5m RTH sessions must produce: a long after an up first bar (entry at the
NEXT bar's open — the engine's no-look-ahead fill), a short after a down first bar, a stop exit at
the opposite OR extreme, an EOD flat (never holds past the cash close), one decision per day, and
``long_only`` standing down on down days. Runs through the real engine + futures cost model.
"""

from __future__ import annotations

import pandas as pd

import src.strategies  # noqa: F401  (imports buckets -> registers strategies)
from src.backtest.costs import AssetClass, InstrumentSpec, Market, Product, cost_model
from src.backtest.simulator import BacktestEngine
from src.core.types import TimeFrame
from src.strategies.base import get_strategy, list_strategies
from src.strategies.momentum.orb import Orb

NY = "America/New_York"


def _day(start: str, rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    """One RTH session of 5m bars; index = bar OPEN times from ``start``."""
    idx = pd.date_range(start, periods=len(rows), freq="5min", tz=NY)
    o, h, low, c = zip(*rows)
    return pd.DataFrame(
        {"open": o, "high": h, "low": low, "close": c, "volume": 1_000.0}, index=idx
    )


def _flat_up_day(start: str) -> pd.DataFrame:
    """First bar up (100 -> 100.5, low 99.9), then a drift that hits neither stop nor 10R."""
    rows = [(100.0, 100.6, 99.9, 100.5)]
    px = 100.5
    for _ in range(77):  # 78 bars: 09:30 .. 15:55 opens
        rows.append((px, px + 0.2, px - 0.2, px + 0.05))
        px += 0.05
    return _day(start, rows)


def _down_day(start: str) -> pd.DataFrame:
    """First bar down, then drift down — the short trends but hits neither stop nor far target."""
    rows = [(100.0, 100.1, 99.4, 99.5)]
    px = 99.5
    for _ in range(77):
        rows.append((px, px + 0.2, px - 0.2, px - 0.05))
        px -= 0.05
    return _day(start, rows)


def _stopped_day(start: str) -> pd.DataFrame:
    """First bar up, then a slide through the OR low -> the long must exit at the stop."""
    rows = [(100.0, 100.6, 99.9, 100.5)]
    px = 100.5
    for _ in range(77):
        rows.append((px, px + 0.1, px - 0.4, px - 0.3))
        px -= 0.3
    return _day(start, rows)


def _engine() -> BacktestEngine:
    inst = InstrumentSpec("ES.c.0", Market("US", AssetClass.FUTURE, Product.FUTURES),
                          multiplier=5.0, tick_size=0.25)
    return BacktestEngine(cost_model("US", "future"), inst,
                          initial_equity=100_000.0, risk_pct=0.005, max_leverage=4.0)


def _run(bars: pd.DataFrame, params: dict | None = None):
    return _engine().run(Orb(params or {}), bars, TimeFrame.M5)


def test_registered() -> None:
    assert "orb" in list_strategies()
    assert get_strategy("orb") is Orb


def test_long_after_up_first_bar_eod_flat() -> None:
    res = _run(_flat_up_day("2022-03-08 09:30"))
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.side == "long"
    # fill at the SECOND bar's open (09:35) — the engine's next-bar-open discipline
    assert t.entry_ts == pd.Timestamp("2022-03-08 09:40", tz=NY)  # close time of the fill bar
    assert t.reason_out == "signal"  # EOD flat, not stop/target
    assert pd.Timestamp(t.exit_ts).time() >= pd.Timestamp("2022-03-08 15:55").time()


def test_short_after_down_first_bar() -> None:
    res = _run(_down_day("2022-03-08 09:30"))
    assert len(res.trades) == 1
    assert res.trades[0].side == "short"
    assert res.trades[0].net_pnl > 0  # trended down all day


def test_long_only_stands_down_on_down_day() -> None:
    res = _run(_down_day("2022-03-08 09:30"), {"long_only": True})
    assert res.trades == []


def test_stop_exit_at_or_low() -> None:
    res = _run(_stopped_day("2022-03-08 09:30"))
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.side == "long"
    assert t.reason_out == "stop"
    assert t.net_pnl < 0


def test_one_decision_per_day_across_days() -> None:
    bars = pd.concat([_flat_up_day("2022-03-08 09:30"), _down_day("2022-03-09 09:30")])
    res = _run(bars)
    assert len(res.trades) == 2
    assert [t.side for t in res.trades] == ["long", "short"]
    # each trade exits the same day it entered (no overnight holds)
    for t in res.trades:
        assert pd.Timestamp(t.entry_ts).date() == pd.Timestamp(t.exit_ts).date()


def test_overnight_bars_ignored() -> None:
    """Globex bars (outside RTH) must produce no entries and no state confusion."""
    overnight = _day("2022-03-08 04:00", [(100.0, 100.5, 99.5, 100.4)] * 12)  # 04:00-05:00
    rth = _flat_up_day("2022-03-08 09:30")
    res = _run(pd.concat([overnight, rth]))
    assert len(res.trades) == 1
    assert res.trades[0].side == "long"
