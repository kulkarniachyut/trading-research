"""Checkpoint 2.5 — the event-driven engine.

Hand-built bar scenarios with known outcomes verify: next-bar-open fills, intrabar stop/target,
stop-first on a straddle, costs subtracted from gross, a flat-signal exit, and the equity curve.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.backtest.costs import AssetClass, InstrumentSpec, Market, Product, cost_model
from src.backtest.simulator import BacktestEngine
from src.core.types import MarketContext, Signal, TimeFrame
from src.strategies.base import BaseStrategy

NY = "America/New_York"


def bars(rows: list[tuple[float, float, float, float]], date: str = "2024-03-12") -> pd.DataFrame:
    idx = pd.date_range(f"{date} 09:30", periods=len(rows), freq="5min", tz=NY)
    o, h, low, c = zip(*rows)
    return pd.DataFrame({"open": o, "high": h, "low": low, "close": c, "volume": 1000.0}, index=idx)


def engine() -> BacktestEngine:
    inst = InstrumentSpec("TEST", Market("US", AssetClass.EQUITY, Product.INTRADAY))
    return BacktestEngine(cost_model("US", "equity"), inst, initial_equity=100_000.0, risk_pct=0.005)


class BuyOnce(BaseStrategy):
    """Long on the first bar with the given stop/target offsets; then hold."""

    required_timeframes = [TimeFrame.M5]

    def __init__(self, stop_off=1.0, tgt_off=2.0):
        super().__init__()
        self._fired = False
        self._stop_off, self._tgt_off = stop_off, tgt_off

    def on_bar(self, ctx: MarketContext):
        if not self._fired and ctx.position.side == "flat":
            self._fired = True
            p = ctx.price
            return Signal(ctx.now, "TEST", "long", stop=p - self._stop_off, target=p + self._tgt_off)
        return None


def test_long_trade_hits_target_net_of_costs():
    # signal at bar0 (c=100) -> entry at bar1 open (100.2); target 102 hit at bar3.
    data = bars([
        (100.0, 100.5, 99.5, 100.0),
        (100.2, 100.8, 100.0, 100.5),
        (101.0, 101.5, 100.5, 101.0),
        (101.5, 102.5, 101.0, 102.0),
        (102.0, 102.5, 101.5, 102.0),
        (102.0, 102.2, 101.8, 102.0),
    ])
    res = engine().run(BuyOnce(stop_off=1.0, tgt_off=2.0), data, TimeFrame.M5)

    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.side == "long" and t.reason_out == "target"
    assert t.qty == 416                      # floor(0.005*100000 / 1.2 stop distance)
    assert t.gross_pnl == pytest.approx((102.0 - 100.2) * 416)   # frictionless
    assert t.costs > 0 and 0 < t.net_pnl < t.gross_pnl           # friction eats into it
    assert t.bars_held == 2
    assert len(res.equity_curve) == 6
    assert res.equity_curve.iloc[-1] == pytest.approx(100_000.0 + t.net_pnl)


def test_stop_first_when_bar_straddles_both():
    # bar that hits BOTH stop (98.5<=99) and target (102.5>=102) -> stop taken (pessimistic).
    data = bars([
        (100.0, 100.5, 99.5, 100.0),     # signal: stop 99, target 102
        (100.0, 100.5, 99.8, 100.0),     # entry at 100.0
        (100.0, 102.5, 98.5, 100.0),     # straddle
        (100.0, 100.5, 99.8, 100.0),
    ])
    res = engine().run(BuyOnce(stop_off=1.0, tgt_off=2.0), data, TimeFrame.M5)
    assert len(res.trades) == 1
    assert res.trades[0].reason_out == "stop"
    assert res.trades[0].net_pnl < 0


class BuyThenFlat(BaseStrategy):
    required_timeframes = [TimeFrame.M5]

    def __init__(self):
        super().__init__()
        self._n = 0

    def on_bar(self, ctx: MarketContext):
        self._n += 1
        if self._n == 1 and ctx.position.side == "flat":
            p = ctx.price
            return Signal(ctx.now, "TEST", "long", stop=p - 100, target=p + 100)  # wide; never hit
        if self._n == 3 and ctx.position.side == "long":
            return Signal(ctx.now, "TEST", "flat")
        return None


def test_flat_signal_exits_at_next_open():
    data = bars([
        (100.0, 100.2, 99.8, 100.0),
        (100.0, 100.2, 99.8, 100.0),   # entry ~100
        (100.0, 100.2, 99.8, 100.0),   # n==3 -> flat signal
        (101.0, 101.2, 100.8, 101.0),  # exit at this open (101)
        (101.0, 101.2, 100.8, 101.0),
    ])
    res = engine().run(BuyThenFlat(), data, TimeFrame.M5)
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.reason_out == "signal"
    assert t.exit_px == pytest.approx(101.0, abs=0.05)   # next bar open, minus a hair of spread


def test_no_trade_without_a_stop():
    class NoStop(BaseStrategy):
        required_timeframes = [TimeFrame.M5]

        def on_bar(self, ctx: MarketContext):
            return Signal(ctx.now, "TEST", "long")  # no stop -> sizing returns 0

    data = bars([(100.0, 100.5, 99.5, 100.0)] * 4)
    res = engine().run(NoStop(), data, TimeFrame.M5)
    assert res.trades == []


def test_sizing_is_capped_by_max_leverage():
    # A one-cent stop would risk-size to 50k shares, but 1x notional caps it near 1k shares.
    data = bars([
        (100.0, 100.2, 99.8, 100.0),
        (100.0, 100.2, 99.8, 100.0),
        (100.0, 101.5, 99.8, 101.0),
        (101.0, 101.2, 100.8, 101.0),
    ])
    eng = BacktestEngine(
        cost_model("US", "equity"),
        InstrumentSpec("TEST", Market("US", AssetClass.EQUITY, Product.INTRADAY)),
        initial_equity=100_000.0,
        risk_pct=0.005,
        max_leverage=1.0,
    )
    res = eng.run(BuyOnce(stop_off=0.01, tgt_off=1.0), data, TimeFrame.M5)
    assert len(res.trades) == 1
    assert res.trades[0].qty == 1000
